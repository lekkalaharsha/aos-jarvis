"""Phase 9 allowlisted workspace control.

No user-controlled executable, argv, shell string, or environment crosses this
module. GUI launches are delegated to the bounded Phase 2 runner adapter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from aos.config.loader import DATA_DIR
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.safety.dev_server import DevServerApproval, canonical_project_digest, consume_dev_server_approval
from aos.safety.errors import PermissionBlocked
from aos.safety.permissions import PermissionEngine
from aos.safety.approved_projects import ApprovedProjectRegistry
from aos.safety.risk import RiskTier
from aos.tools.base import BaseTool, ToolDecision, ToolResult, ToolSchema
from aos.tools.shell_runner import (
    FolderLaunchRequest,
    DevServerLaunchRequest,
    DevServerProfile,
    EditorLaunchRequest,
    LaunchState,
    TerminalLaunchRequest,
    WorkspaceLaunchAdapter,
)

STATE_SCHEMA_VERSION = 1
WORKSPACE_STATE_PATH = DATA_DIR / "workspace.json"
SUPPORTED_EDITORS = {"vscode"}
SUPPORTED_TERMINALS = {"default"}
SUPPORTED_SERVERS = {"python-http"}
ALLOWED_HANDLE_FIELDS = {"handle_id", "launch_kind", "project_id", "state", "started_at", "stop_method"}
CTRL_C_STOP_METHOD = "ctrl_c_foreground_terminal"
CTRL_C_STOP_GUIDANCE = "Press Ctrl+C in the terminal that started this server."


class WorkspaceOperation(str, Enum):
    STATUS = "status"
    OPEN = "open"
    EDITOR = "editor"
    TERMINAL = "terminal"
    SAVE = "save"
    RESTORE = "restore"
    SERVE = "serve"


@dataclass(frozen=True)
class WorkspaceRequest:
    operation: WorkspaceOperation
    project_id: str | None = None
    editor: str = "vscode"
    terminal: str = "default"
    server: str = "python-http"
    port: int = 8000
    approval: DevServerApproval | None = None


def _safe_error(exc: Exception) -> str:
    return "workspace request denied" if isinstance(exc, PermissionBlocked) else "workspace operation failed"


def _safe_handle_summary(handle: object) -> dict[str, Any]:
    """Return only safe, non-secret handle metadata for audit payloads."""
    if not hasattr(handle, "__dict__"):
        return {}
    return {k: v for k, v in handle.__dict__.items() if k in ALLOWED_HANDLE_FIELDS}


class WorkspaceTool(BaseTool):
    def __init__(self, *, registry: ApprovedProjectRegistry | None = None, state_path: Path | None = None, audit_path: Path | None = None, launch_adapter: WorkspaceLaunchAdapter | None = None, consumed_path: Path | None = None) -> None:
        self.registry = registry or ApprovedProjectRegistry()
        self.state_path = state_path or WORKSPACE_STATE_PATH
        self.audit_path = audit_path or DEFAULT_AUDIT_PATH
        self.launch_adapter = launch_adapter or WorkspaceLaunchAdapter()
        self.consumed_path = consumed_path

    def describe(self) -> ToolSchema:
        return ToolSchema(name="workspace", description="Allowlisted approved-root workspace actions")

    def required_capabilities(self, args: dict[str, Any]) -> list[str]:
        operation = str(args.get("operation", ""))
        return [f"workspace.{operation}"] if operation in {item.value for item in WorkspaceOperation} else []

    def risk_tier(self) -> RiskTier:
        return RiskTier.T1

    def _risk_for_operation(self, operation: str) -> RiskTier:
        return RiskTier.T2 if operation == WorkspaceOperation.SERVE.value else RiskTier.T1

    def _audit(self, event_type: str, *, operation: str, project_id: str | None, ok: bool, detail: str, editor: str = "vscode", terminal: str = "default", server: str = "python-http", port: int | None = None, handle_summary: dict[str, Any] | None = None, stop_method: str | None = None) -> None:
        payload: dict[str, Any] = {
            "operation": operation,
            "project_id": project_id,
            "editor": editor if editor in SUPPORTED_EDITORS else None,
            "terminal": terminal if terminal in SUPPORTED_TERMINALS else None,
            "server": server if server in SUPPORTED_SERVERS else None,
            "port": port,
            "detail": detail,
        }
        if handle_summary is not None:
            payload["handle"] = handle_summary
        if stop_method is not None:
            payload["stop_method"] = stop_method
        append_event(
            self.audit_path, actor="workspace", event_type=event_type,
            action=operation,
            resource=project_id or "workspace",
            risk_tier=self._risk_for_operation(operation).value,
            status="ALLOW" if ok else "DENY",
            payload=payload,
        )

    def _project(self, request: WorkspaceRequest, capability: str, risk: RiskTier) -> Path:
        if not request.project_id or not request.project_id.strip():
            raise PermissionBlocked("approved project id is required")
        path = self.registry.resolve(request.project_id)
        # Membership resolution and PermissionEngine authorization are separate.
        path = PermissionEngine([path]).require_path(path, capability, risk)
        if not path.exists() or not path.is_dir():
            raise PermissionBlocked("approved project directory is required")
        return path

    def _request(self, args: dict[str, Any]) -> WorkspaceRequest:
        try:
            operation = WorkspaceOperation(str(args["operation"]))
        except (KeyError, ValueError) as exc:
            raise PermissionBlocked("unknown workspace operation") from exc
        allowed = {"operation", "project_id", "editor", "terminal", "server", "port", "approval"}
        if set(args) - allowed:
            raise PermissionBlocked("unexpected workspace arguments")
        port = args.get("port", 8000)
        if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
            raise PermissionBlocked("invalid server port")
        approval = args.get("approval")
        if approval is not None and not isinstance(approval, DevServerApproval):
            raise PermissionBlocked("invalid dev-server approval")
        return WorkspaceRequest(
            operation,
            args.get("project_id"),
            str(args.get("editor", "vscode")),
            str(args.get("terminal", "default")),
            str(args.get("server", "python-http")),
            port,
            approval,
        )

    def _audit_denied_from_args(self, args: dict[str, Any], detail: str) -> None:
        operation = str(args.get("operation", "unknown"))
        project_id = args.get("project_id")
        editor = str(args.get("editor", "vscode"))
        terminal = str(args.get("terminal", "default"))
        server = str(args.get("server", "python-http"))
        port = args.get("port") if isinstance(args.get("port"), int) and not isinstance(args.get("port"), bool) else None
        self._audit(
            "workspace.denied",
            operation=operation,
            project_id=project_id if isinstance(project_id, str) else None,
            ok=False,
            detail=detail,
            editor=editor,
            terminal=terminal,
            server=server,
            port=port,
        )

    def _audit_denied_from_request(self, request: WorkspaceRequest, detail: str) -> None:
        self._audit(
            "workspace.denied",
            operation=request.operation.value,
            project_id=request.project_id,
            ok=False,
            detail=detail,
            editor=request.editor,
            terminal=request.terminal,
            server=request.server,
            port=request.port if request.operation is WorkspaceOperation.SERVE else None,
        )

    def dry_run(self, args: dict[str, Any]) -> ToolResult:
        try:
            request = self._request(args)
            if request.operation not in {WorkspaceOperation.STATUS, WorkspaceOperation.RESTORE}:
                self._project(request, f"workspace.{request.operation.value}", self._risk_for_operation(request.operation.value))
            self._audit(
                "workspace.requested",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=True,
                detail="dry_run",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
                port=request.port if request.operation is WorkspaceOperation.SERVE else None,
            )
            decision = ToolDecision.REQUIRE_STRONG_APPROVAL if request.operation == WorkspaceOperation.SERVE else ToolDecision.REQUIRE_APPROVAL
            return ToolResult(ok=True, output="workspace request validated", decision=decision)
        except Exception as exc:
            return ToolResult(ok=False, output=_safe_error(exc), decision=ToolDecision.DENY)

    def execute(self, args: dict[str, Any]) -> ToolResult:
        request: WorkspaceRequest | None = None
        try:
            request = self._request(args)
            if request.operation == WorkspaceOperation.STATUS:
                output = "workspace state available" if self.state_path.exists() else "no saved workspace"
                self._audit(
                    "workspace.status",
                    operation=request.operation.value,
                    project_id=request.project_id,
                    ok=True,
                    detail="state_checked",
                    editor=request.editor,
                    terminal=request.terminal,
                    server=request.server,
                )
                return ToolResult(ok=True, output=output, decision=ToolDecision.ALLOW)
            if request.operation == WorkspaceOperation.RESTORE:
                return self._restore(request)
            risk = self._risk_for_operation(request.operation.value)
            project = self._project(request, f"workspace.{request.operation.value}", risk)
            if request.operation == WorkspaceOperation.SAVE:
                return self._save(request, project)
            if request.operation == WorkspaceOperation.SERVE:
                return self._serve(request, project)
            return self._launch(request, project)
        except Exception as exc:
            if request is not None:
                self._audit_denied_from_request(request, _safe_error(exc))
            else:
                self._audit_denied_from_args(args, _safe_error(exc))
            return ToolResult(ok=False, output=_safe_error(exc), decision=ToolDecision.DENY)

    def _launch(self, request: WorkspaceRequest, project: Path) -> ToolResult:
        if request.operation == WorkspaceOperation.EDITOR and request.editor not in SUPPORTED_EDITORS:
            raise PermissionBlocked("unsupported editor")
        if request.operation == WorkspaceOperation.TERMINAL and request.terminal not in SUPPORTED_TERMINALS:
            raise PermissionBlocked("unsupported terminal")
        if request.operation == WorkspaceOperation.OPEN:
            launch_request: FolderLaunchRequest | EditorLaunchRequest | TerminalLaunchRequest = FolderLaunchRequest(request.project_id or "", project)
        elif request.operation == WorkspaceOperation.EDITOR:
            launch_request = EditorLaunchRequest(request.project_id or "", project)
        elif request.operation == WorkspaceOperation.TERMINAL:
            launch_request = TerminalLaunchRequest(request.project_id or "", project)
        else:
            raise PermissionBlocked("unsupported workspace application")
        self._audit(
            f"workspace.{request.operation.value}.requested",
            operation=request.operation.value,
            project_id=request.project_id,
            ok=True,
            detail="launch_requested",
            editor=request.editor,
            terminal=request.terminal,
            server=request.server,
        )
        outcome = self.launch_adapter.launch(launch_request)
        handle_id = outcome.handle.handle_id if outcome.handle else None
        if outcome.state is LaunchState.RUNNING:
            self._audit(
                f"workspace.{request.operation.value}.running",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=True,
                detail="launch_running",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
                handle_summary=_safe_handle_summary(outcome.handle),
            )
            output = "workspace folder opened" if request.operation == WorkspaceOperation.OPEN else "workspace application launched"
            if handle_id:
                output += f"; handle {handle_id}"
            return ToolResult(ok=True, output=output, decision=ToolDecision.REQUIRE_APPROVAL)
        self._audit(
            f"workspace.{request.operation.value}.failed",
            operation=request.operation.value,
            project_id=request.project_id,
            ok=False,
            detail=outcome.error_code or "launch_failed",
            editor=request.editor,
            terminal=request.terminal,
            server=request.server,
        )
        return ToolResult(ok=False, output="workspace launcher unavailable", decision=ToolDecision.REQUIRE_APPROVAL)

    def _save(self, request: WorkspaceRequest, project: Path) -> ToolResult:
        if request.editor not in SUPPORTED_EDITORS or request.terminal not in SUPPORTED_TERMINALS:
            raise PermissionBlocked("unsupported workspace application")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({"schema_version": STATE_SCHEMA_VERSION, "project_id": request.project_id, "editor": request.editor, "terminal": request.terminal}, sort_keys=True), encoding="utf-8")
        self._audit(
            "workspace.state.saved",
            operation=request.operation.value,
            project_id=request.project_id,
            ok=True,
            detail="metadata_saved",
            editor=request.editor,
            terminal=request.terminal,
            server=request.server,
        )
        return ToolResult(ok=True, output="workspace state saved", decision=ToolDecision.REQUIRE_APPROVAL)

    def _restore(self, request: WorkspaceRequest) -> ToolResult:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if set(data) != {"schema_version", "project_id", "editor", "terminal"} or data["schema_version"] != STATE_SCHEMA_VERSION:
                raise PermissionBlocked("invalid workspace state")
            restored = WorkspaceRequest(WorkspaceOperation.EDITOR, data["project_id"], data["editor"], data["terminal"])
            project = self._project(restored, "workspace.restore", RiskTier.T1)
            self._audit(
                "workspace.restore.started",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=True,
                detail="state_revalidated",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
            )
            result = self._launch(restored, project)
            self._audit(
                "workspace.restore.completed" if result.ok else "workspace.restore.failed",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=result.ok,
                detail="editor_only",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
            )
            return result
        except (OSError, ValueError, TypeError, KeyError, PermissionBlocked):
            self._audit(
                "workspace.restore.failed",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=False,
                detail="invalid_or_unavailable_state",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
            )
            return ToolResult(ok=False, output="workspace restore unavailable", decision=ToolDecision.DENY)

    def _serve(self, request: WorkspaceRequest, project: Path) -> ToolResult:
        if request.server not in SUPPORTED_SERVERS:
            raise PermissionBlocked("unsupported development server")
        if request.approval is None:
            self._audit(
                "workspace.server.denied",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=False,
                detail="fresh_approval_required",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
                port=request.port,
                stop_method=CTRL_C_STOP_METHOD,
            )
            return ToolResult(ok=False, output="development server requires explicit approval", decision=ToolDecision.REQUIRE_STRONG_APPROVAL)
        # Validate and consume the opaque approval before any process launch.
        try:
            consume_dev_server_approval(
                request.approval,
                project_id=request.project_id or "",
                profile=request.server,
                port=request.port,
                canonical_project_id=canonical_project_digest(project),
                consumed_path=self.consumed_path,
            )
        except PermissionBlocked:
            self._audit(
                "workspace.server.denied",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=False,
                detail="approval_invalid",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
                port=request.port,
                stop_method=CTRL_C_STOP_METHOD,
            )
            return ToolResult(ok=False, output="development server requires explicit approval", decision=ToolDecision.REQUIRE_STRONG_APPROVAL)
        self._audit(
            "workspace.server.approval_consumed",
            operation=request.operation.value,
            project_id=request.project_id,
            ok=True,
            detail="approval_consumed",
            editor=request.editor,
            terminal=request.terminal,
            server=request.server,
            port=request.port,
            stop_method=CTRL_C_STOP_METHOD,
        )
        self._audit(
            "workspace.server.starting",
            operation=request.operation.value,
            project_id=request.project_id,
            ok=True,
            detail="server_starting",
            editor=request.editor,
            terminal=request.terminal,
            server=request.server,
            port=request.port,
            stop_method=CTRL_C_STOP_METHOD,
        )
        outcome = self.launch_adapter.launch(DevServerLaunchRequest(request.project_id or "", project, DevServerProfile.LOOPBACK_PYTHON_HTTP, request.port))
        if outcome.state is not LaunchState.RUNNING or outcome.handle is None:
            self._audit(
                "workspace.server.failed",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=False,
                detail=outcome.error_code or "server_not_started",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
                port=request.port,
                stop_method=CTRL_C_STOP_METHOD,
            )
            return ToolResult(ok=False, output="development server did not start", decision=ToolDecision.REQUIRE_STRONG_APPROVAL)
        self._audit(
            "workspace.server.running",
            operation=request.operation.value,
            project_id=request.project_id,
            ok=True,
            detail="server_running",
            editor=request.editor,
            terminal=request.terminal,
            server=request.server,
            port=request.port,
            handle_summary=_safe_handle_summary(outcome.handle),
            stop_method=CTRL_C_STOP_METHOD,
        )
        terminal_outcome = self.launch_adapter.wait(outcome.handle.handle_id, project_id=request.project_id or "")
        if terminal_outcome.state is LaunchState.CANCELLED:
            self._audit(
                "workspace.server.cancelled",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=True,
                detail=terminal_outcome.error_code or CTRL_C_STOP_METHOD,
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
                port=request.port,
                handle_summary=_safe_handle_summary(terminal_outcome.handle) if terminal_outcome.handle else None,
                stop_method=CTRL_C_STOP_METHOD,
            )
            return ToolResult(ok=True, output=f"development server cancelled; stop method {CTRL_C_STOP_METHOD}", decision=ToolDecision.REQUIRE_STRONG_APPROVAL)
        if terminal_outcome.state is LaunchState.STOPPED:
            self._audit(
                "workspace.server.stopped",
                operation=request.operation.value,
                project_id=request.project_id,
                ok=True,
                detail=terminal_outcome.error_code or "foreground_exit",
                editor=request.editor,
                terminal=request.terminal,
                server=request.server,
                port=request.port,
                handle_summary=_safe_handle_summary(terminal_outcome.handle) if terminal_outcome.handle else None,
                stop_method=CTRL_C_STOP_METHOD,
            )
            return ToolResult(ok=True, output=f"development server stopped; stop method {CTRL_C_STOP_METHOD}", decision=ToolDecision.REQUIRE_STRONG_APPROVAL)
        self._audit(
            "workspace.server.failed",
            operation=request.operation.value,
            project_id=request.project_id,
            ok=False,
            detail=terminal_outcome.error_code or "server_wait_failed",
            editor=request.editor,
            terminal=request.terminal,
            server=request.server,
            port=request.port,
            stop_method=CTRL_C_STOP_METHOD,
        )
        return ToolResult(ok=False, output="development server failed", decision=ToolDecision.REQUIRE_STRONG_APPROVAL)
