"""Phase 2 safe shell command runner."""

from __future__ import annotations

import subprocess
import sys
import time
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from shlex import join as shlex_join
from pathlib import Path

from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.safety.command_policy import evaluate_command
from aos.safety.commands import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    CommandPreview,
    CommandResult,
    redact_audited_argv,
    sanitize_environment,
    summarize_truncation,
)
from aos.safety.errors import ApprovalRequired, CommandPolicyBlocked
from aos.safety.sandbox import default_sandbox_mode


WORKSPACE_LAUNCHERS = {
    "folder": {"win32": ("explorer.exe",), "linux": ("xdg-open",)},
    "editor": {"win32": ("code.cmd", "code.exe"), "linux": ("code",)},
    "terminal": {"win32": ("wt.exe",), "linux": ("x-terminal-emulator",)},
}


class LaunchKind(str, Enum):
    FOLDER = "folder"
    EDITOR = "editor"
    TERMINAL = "terminal"
    DEV_SERVER = "dev_server"


class EditorId(str, Enum):
    VSCODE = "vscode"


class TerminalId(str, Enum):
    DEFAULT = "default"


class DevServerProfile(str, Enum):
    LOOPBACK_PYTHON_HTTP = "python-http-loopback"


class LaunchState(str, Enum):
    REQUESTED = "requested"
    VALIDATED = "validated"
    STARTING = "starting"
    RUNNING = "running"
    STOP_REQUESTED = "stop_requested"
    STOPPED = "stopped"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class EditorLaunchRequest:
    project_id: str
    cwd: Path
    editor: EditorId = EditorId.VSCODE


@dataclass(frozen=True)
class TerminalLaunchRequest:
    project_id: str
    cwd: Path
    terminal: TerminalId = TerminalId.DEFAULT


@dataclass(frozen=True)
class FolderLaunchRequest:
    project_id: str
    cwd: Path


@dataclass(frozen=True)
class DevServerLaunchRequest:
    project_id: str
    cwd: Path
    profile: DevServerProfile
    port: int


@dataclass(frozen=True)
class SafeProcessHandle:
    """Public lifecycle reference; deliberately contains no PID or process."""

    handle_id: str
    launch_kind: LaunchKind
    project_id: str
    state: LaunchState
    started_at: str
    stop_method: str = "typed-stop"


@dataclass(frozen=True)
class LaunchOutcome:
    state: LaunchState
    handle: SafeProcessHandle | None
    error_code: str | None = None


class WorkspaceLaunchAdapter:
    """Closed typed Phase 9 process boundary; no generic subprocess API."""

    def __init__(self, *, platform: str | None = None, process_factory: object = subprocess.Popen, stop_timeout_seconds: float = 3.0) -> None:
        self._platform = platform or ("win32" if sys.platform == "win32" else "linux" if sys.platform.startswith("linux") else "unknown")
        self._process_factory = process_factory
        self._stop_timeout_seconds = stop_timeout_seconds
        self._processes: dict[str, tuple[object, SafeProcessHandle]] = {}
        self._stopped: dict[str, SafeProcessHandle] = {}

    def launch(self, request: FolderLaunchRequest | EditorLaunchRequest | TerminalLaunchRequest | DevServerLaunchRequest) -> LaunchOutcome:
        try:
            cwd = request.cwd.resolve(strict=True)
            argv, kind = self._argv(request, cwd)
        except (OSError, ValueError):
            return LaunchOutcome(LaunchState.FAILED, None, "validation_denied")
        env, _ = sanitize_environment()
        try:
            process = self._process_factory(argv, cwd=str(cwd), env=env, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return LaunchOutcome(LaunchState.FAILED, None, "launcher_unavailable")
        if process.poll() is not None:
            return LaunchOutcome(LaunchState.FAILED, None, "process_exited")
        handle = SafeProcessHandle(secrets.token_urlsafe(24), kind, request.project_id, LaunchState.RUNNING, datetime.now(timezone.utc).isoformat())
        self._processes[handle.handle_id] = (process, handle)
        return LaunchOutcome(LaunchState.RUNNING, handle)

    def wait(self, handle_id: str, *, project_id: str) -> LaunchOutcome:
        """Block until the launched process exits or the terminal interrupts."""
        item = self._processes.get(handle_id)
        if item is None:
            stopped = self._stopped.get(handle_id)
            if stopped is not None and stopped.project_id == project_id:
                return LaunchOutcome(LaunchState.STOPPED, stopped)
            return LaunchOutcome(LaunchState.FAILED, None, "unknown_handle")
        process, handle = item
        if handle.project_id != project_id:
            return LaunchOutcome(LaunchState.FAILED, None, "project_mismatch")
        try:
            while True:
                if process.poll() is not None:
                    self._processes.pop(handle_id, None)
                    stopped = SafeProcessHandle(handle.handle_id, handle.launch_kind, handle.project_id, LaunchState.STOPPED, handle.started_at)
                    self._stopped[handle_id] = stopped
                    return LaunchOutcome(LaunchState.STOPPED, stopped)
                time.sleep(0.05)
        except KeyboardInterrupt:
            stop_outcome = self.stop(handle_id, project_id=project_id)
            if stop_outcome.state is LaunchState.STOPPED:
                return LaunchOutcome(LaunchState.CANCELLED, stop_outcome.handle, "ctrl_c_foreground_terminal")
            if stop_outcome.state is LaunchState.TIMED_OUT:
                return LaunchOutcome(LaunchState.CANCELLED, stop_outcome.handle, stop_outcome.error_code or "cleanup_timeout")
            return LaunchOutcome(LaunchState.CANCELLED, stop_outcome.handle, stop_outcome.error_code or "stop_failed")

    def status(self, handle_id: str, *, project_id: str) -> LaunchOutcome:
        """Check the status of a running or stopped handle.

        Returns the current state without side effects.
        """
        item = self._processes.get(handle_id)
        if item is not None:
            process, handle = item
            if handle.project_id != project_id:
                return LaunchOutcome(LaunchState.FAILED, None, "project_mismatch")
            is_running = process.poll() is None
            if is_running:
                return LaunchOutcome(LaunchState.RUNNING, handle)
            # Process exited without explicit stop — clean up and record as stopped.
            self._processes.pop(handle_id, None)
            stopped = SafeProcessHandle(
                handle.handle_id, handle.launch_kind, handle.project_id,
                LaunchState.STOPPED, handle.started_at,
            )
            self._stopped[handle_id] = stopped
            return LaunchOutcome(LaunchState.STOPPED, stopped)
        stopped = self._stopped.get(handle_id)
        if stopped is not None:
            if stopped.project_id != project_id:
                return LaunchOutcome(LaunchState.FAILED, None, "project_mismatch")
            return LaunchOutcome(LaunchState.STOPPED, stopped)
        return LaunchOutcome(LaunchState.FAILED, None, "unknown_handle")

    def stop(self, handle_id: str, *, project_id: str) -> LaunchOutcome:
        item = self._processes.get(handle_id)
        if item is None:
            stopped = self._stopped.get(handle_id)
            if stopped is not None and stopped.project_id == project_id:
                return LaunchOutcome(LaunchState.STOPPED, stopped)
            return LaunchOutcome(LaunchState.FAILED, None, "unknown_handle")
        process, handle = item
        if handle.project_id != project_id:
            return LaunchOutcome(LaunchState.FAILED, None, "project_mismatch")
        if process.poll() is not None:
            self._processes.pop(handle_id, None)
            stopped = SafeProcessHandle(handle.handle_id, handle.launch_kind, handle.project_id, LaunchState.STOPPED, handle.started_at)
            self._stopped[handle_id] = stopped
            return LaunchOutcome(LaunchState.STOPPED, stopped)
        try:
            process.terminate()
            process.wait(timeout=self._stop_timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=self._stop_timeout_seconds)
            except (OSError, subprocess.TimeoutExpired):
                # Cleanup failed — process may still be running.
                self._processes.pop(handle_id, None)
                failed = SafeProcessHandle(handle.handle_id, handle.launch_kind, handle.project_id, LaunchState.TIMED_OUT, handle.started_at)
                self._stopped[handle_id] = failed
                return LaunchOutcome(LaunchState.TIMED_OUT, None, "cleanup_timeout")
        except OSError:
            self._processes.pop(handle_id, None)
            failed = SafeProcessHandle(handle.handle_id, handle.launch_kind, handle.project_id, LaunchState.FAILED, handle.started_at)
            self._stopped[handle_id] = failed
            return LaunchOutcome(LaunchState.FAILED, None, "stop_failed")
        self._processes.pop(handle_id, None)
        stopped = SafeProcessHandle(handle.handle_id, handle.launch_kind, handle.project_id, LaunchState.STOPPED, handle.started_at)
        self._stopped[handle_id] = stopped
        return LaunchOutcome(LaunchState.STOPPED, stopped)

    def _argv(
        self,
        request: FolderLaunchRequest | EditorLaunchRequest | TerminalLaunchRequest | DevServerLaunchRequest,
        cwd: Path,
    ) -> tuple[list[str], LaunchKind]:
        if self._platform not in {"linux", "win32"}:
            raise ValueError("unsupported platform")
        if isinstance(request, FolderLaunchRequest):
            executable = "explorer.exe" if self._platform == "win32" else "xdg-open"
            return [executable, str(cwd)], LaunchKind.FOLDER
        if isinstance(request, EditorLaunchRequest):
            if request.editor is not EditorId.VSCODE:
                raise ValueError("unsupported editor")
            executable = "code.cmd" if self._platform == "win32" else "code"
            return [executable, str(cwd)], LaunchKind.EDITOR
        if isinstance(request, TerminalLaunchRequest):
            if request.terminal is not TerminalId.DEFAULT:
                raise ValueError("unsupported terminal")
            executable = "wt.exe" if self._platform == "win32" else "x-terminal-emulator"
            return [executable], LaunchKind.TERMINAL
        if request.profile is not DevServerProfile.LOOPBACK_PYTHON_HTTP:
            raise ValueError("unsupported development server profile")
        if not 1024 <= request.port <= 65535:
            raise ValueError("invalid port")
        return [sys.executable, "-m", "http.server", str(request.port), "--bind", "127.0.0.1"], LaunchKind.DEV_SERVER


def _audit(action: str, preview: CommandPreview, allowed: bool, **payload: object) -> int:
    redacted_argv = redact_audited_argv(preview.argv)
    event = append_event(
        DEFAULT_AUDIT_PATH,
        actor="run",
        event_type=action,
        action=action,
        resource=preview.cwd,
        risk_tier=preview.risk_tier,
        status="ALLOW" if allowed else "DENY",
        payload={
            "action": action,
            "command_original": shlex_join(redacted_argv) if redacted_argv else preview.command_original,
            "argv": redacted_argv,
            "cwd": preview.cwd,
            "risk_tier": preview.risk_tier,
            "policy_category": preview.policy_category,
            "allowed": allowed,
            "requires_approval": preview.requires_approval,
            **payload,
        },
    )
    return event.id


def preview_command(
    command: str,
    cwd: str = ".",
    *,
    approved_roots: list[str | Path] | None = None,
    timeout_seconds: int | None = None,
) -> CommandPreview:
    timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
    policy = evaluate_command(command, cwd=cwd, approved_roots=approved_roots)
    _, env_summary = sanitize_environment()
    preview = CommandPreview(
        command_original=command,
        argv=policy.argv,
        cwd=policy.cwd,
        policy_category=policy.policy_category,
        risk_tier=policy.risk_tier.value,
        allowed=policy.allowed,
        requires_approval=policy.requires_approval,
        timeout_seconds=timeout,
        sandbox_mode=default_sandbox_mode(),
        environment_summary=env_summary,
        reason=policy.reason,
    )
    _audit(
        "run.preview",
        preview,
        allowed=preview.allowed,
        approved=False,
        timed_out=False,
        output_truncated=False,
        reason=preview.reason,
    )
    return preview


def run_command(
    command: str,
    cwd: str = ".",
    *,
    yes: bool = False,
    timeout_seconds: int | None = None,
    approved_roots: list[str | Path] | None = None,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> CommandResult:
    preview = preview_command(
        command,
        cwd=cwd,
        approved_roots=approved_roots,
        timeout_seconds=timeout_seconds,
    )
    if not preview.allowed:
        audit_id = _audit(
            "run.blocked",
            preview,
            allowed=False,
            approved=False,
            timed_out=False,
            output_truncated=False,
            reason=preview.reason,
            error=preview.reason,
        )
        raise CommandPolicyBlocked(preview.reason + f" [audit_event_id={audit_id}]")
    if preview.requires_approval and not yes:
        _audit(
            "run.blocked",
            preview,
            allowed=False,
            approved=False,
            timed_out=False,
            output_truncated=False,
            reason="approval required",
            error="approval required",
        )
        raise ApprovalRequired("command requires explicit approval")

    env, _ = sanitize_environment()
    start = time.perf_counter()
    audit_event_id: int | None = None
    try:
        process = subprocess.Popen(
            preview.argv,
            cwd=preview.cwd,
            env=env,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = process.communicate(timeout=preview.timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_bytes, stderr_bytes = process.communicate()
            timed_out = True
    except FileNotFoundError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        result = CommandResult(
            command_original=preview.command_original,
            argv=preview.argv,
            cwd=preview.cwd,
            policy_category=preview.policy_category,
            risk_tier=preview.risk_tier,
            allowed=True,
            approved=yes,
            return_code=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            timed_out=False,
            output_truncated=False,
            audit_event_id=None,
            error=f"command not found: {preview.argv[0]}",
        )
        audit_event_id = _audit(
            "run.blocked",
            preview,
            allowed=False,
            approved=yes,
            timed_out=False,
            output_truncated=False,
            reason="command could not be started",
            error=str(exc),
        )
        return CommandResult(**{**result.__dict__, "audit_event_id": audit_event_id})

    duration_ms = int((time.perf_counter() - start) * 1000)
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    stdout, stdout_truncated = summarize_truncation(stdout, max_output_bytes)
    stderr, stderr_truncated = summarize_truncation(stderr, max_output_bytes)
    output_truncated = stdout_truncated or stderr_truncated

    if timed_out:
        audit_event_id = _audit(
            "run.timeout",
            preview,
            allowed=True,
            approved=yes,
            timed_out=True,
            output_truncated=output_truncated,
            return_code=process.returncode,
            duration_ms=duration_ms,
            reason="command timed out",
        )
    else:
        audit_event_id = _audit(
            "run.apply",
            preview,
            allowed=True,
            approved=yes,
            timed_out=False,
            output_truncated=output_truncated,
            return_code=process.returncode,
            duration_ms=duration_ms,
            reason="command executed",
        )
    if output_truncated:
        _audit(
            "run.output_truncated",
            preview,
            allowed=True,
            approved=yes,
            timed_out=timed_out,
            output_truncated=True,
            return_code=process.returncode,
            duration_ms=duration_ms,
            reason="command output truncated",
        )

    return CommandResult(
        command_original=preview.command_original,
        argv=preview.argv,
        cwd=preview.cwd,
        policy_category=preview.policy_category,
        risk_tier=preview.risk_tier,
        allowed=True,
        approved=yes,
        return_code=process.returncode,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
        output_truncated=output_truncated,
        audit_event_id=audit_event_id,
        error="command timed out" if timed_out else None,
    )
