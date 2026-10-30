from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from aos.agent.types import Observation, ToolCall
from aos.memory.recall import recall
from aos.memory.store import DEFAULT_MEMORY_DB_PATH, get_memory_status
from aos.memory.timeline import get_recent_activity
from aos.project.git_tools import draft_commit_message, git_branch, git_log, git_status, summarize_git_diff
from aos.project.project_summary import summarize_project_changes
from aos.safety.audit import DEFAULT_AUDIT_PATH
from aos.safety.command_policy import evaluate_command
from aos.safety.errors import PermissionBlocked
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import RiskTier, classify_file_action
from aos.safety.snapshots import get_snapshot, list_snapshots, restore_snapshot
from aos.tools.fs_tools import (
    edit_file,
    list_dir,
    preview_edit,
    preview_write,
    read_file,
    search_files,
    write_file,
)
from aos.browser.domains import ApprovedDomainRegistry
from aos.tools.shell_runner import preview_command, run_command
from aos.tools.workspace import WorkspaceTool


def _resolve_arg_path(base_cwd: Path, value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    return str((base_cwd / candidate).resolve(strict=False))


def _resolve_project_cwd(base_cwd: Path, value: str) -> str:
    """Resolve a project cwd without allowing an agent tool-call escape."""
    candidate = _resolve_arg_path(base_cwd, value)
    return str(PermissionEngine(approved_roots=[base_cwd]).require_path(candidate, "run.command", RiskTier.T0))


@dataclass(frozen=True)
class ToolSpec:
    name: str
    required_args: frozenset[str]
    optional_args: frozenset[str]
    risk_tier_resolver: Callable[[dict[str, Any], Path], str]
    requires_approval_resolver: Callable[[dict[str, Any], Path], bool]
    previewer: Callable[[dict[str, Any], Path], Observation]
    executor: Callable[[dict[str, Any], Path, bool], Observation]


class ToolRegistry:
    def __init__(self) -> None:
        self._specs = {
            "fs.list": ToolSpec(
                "fs.list",
                frozenset({"path"}),
                frozenset(),
                lambda args, cwd: classify_file_action("list").value,
                lambda args, cwd: False,
                self._preview_fs_list,
                self._execute_fs_list,
            ),
            "fs.read": ToolSpec(
                "fs.read",
                frozenset({"path"}),
                frozenset(),
                lambda args, cwd: classify_file_action("read").value,
                lambda args, cwd: False,
                self._preview_fs_read,
                self._execute_fs_read,
            ),
            "fs.search": ToolSpec(
                "fs.search",
                frozenset({"query"}),
                frozenset({"root"}),
                lambda args, cwd: classify_file_action("search").value,
                lambda args, cwd: False,
                self._preview_fs_search,
                self._execute_fs_search,
            ),
            "fs.write": ToolSpec(
                "fs.write",
                frozenset({"path", "content"}),
                frozenset(),
                lambda args, cwd: classify_file_action("write").value,
                lambda args, cwd: True,
                self._preview_fs_write,
                self._execute_fs_write,
            ),
            "fs.edit": ToolSpec(
                "fs.edit",
                frozenset({"path", "old_text", "new_text"}),
                frozenset(),
                lambda args, cwd: classify_file_action("edit").value,
                lambda args, cwd: True,
                self._preview_fs_edit,
                self._execute_fs_edit,
            ),
            "snapshot.list": ToolSpec(
                "snapshot.list",
                frozenset(),
                frozenset(),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_snapshot_list,
                self._execute_snapshot_list,
            ),
            "snapshot.restore": ToolSpec(
                "snapshot.restore",
                frozenset({"snapshot_id"}),
                frozenset(),
                lambda args, cwd: classify_file_action("restore").value,
                lambda args, cwd: True,
                self._preview_snapshot_restore,
                self._execute_snapshot_restore,
            ),
            "run.preview": ToolSpec(
                "run.preview",
                frozenset({"command", "cwd"}),
                frozenset(),
                self._resolve_command_risk,
                lambda args, cwd: False,
                self._preview_run_preview,
                self._execute_run_preview,
            ),
            "run.apply": ToolSpec(
                "run.apply",
                frozenset({"command", "cwd"}),
                frozenset(),
                self._resolve_command_risk,
                self._resolve_command_approval,
                self._preview_run_apply,
                self._execute_run_apply,
            ),
            "memory.status": ToolSpec(
                "memory.status",
                frozenset(),
                frozenset(),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_memory_status,
                self._execute_memory_status,
            ),
            "memory.recent": ToolSpec(
                "memory.recent",
                frozenset(),
                frozenset({"limit"}),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_memory_recent,
                self._execute_memory_recent,
            ),
            "memory.timeline": ToolSpec(
                "memory.timeline",
                frozenset(),
                frozenset({"limit"}),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_memory_timeline,
                self._execute_memory_timeline,
            ),
            "memory.recall": ToolSpec(
                "memory.recall",
                frozenset({"query"}),
                frozenset({"limit"}),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_memory_recall,
                self._execute_memory_recall,
            ),
            "git.status": ToolSpec(
                "git.status",
                frozenset({"cwd"}),
                frozenset(),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_git_status,
                self._execute_git_status,
            ),
            "git.diff_stat": ToolSpec(
                "git.diff_stat",
                frozenset({"cwd"}),
                frozenset(),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_git_diff_stat,
                self._execute_git_diff_stat,
            ),
            "git.log": ToolSpec(
                "git.log",
                frozenset({"cwd"}),
                frozenset({"limit"}),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_git_log,
                self._execute_git_log,
            ),
            "git.branch": ToolSpec(
                "git.branch",
                frozenset({"cwd"}),
                frozenset(),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_git_branch,
                self._execute_git_branch,
            ),
            "project.summarize_changes": ToolSpec(
                "project.summarize_changes",
                frozenset({"cwd"}),
                frozenset(),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_project_summarize_changes,
                self._execute_project_summarize_changes,
            ),
            "project.draft_commit": ToolSpec(
                "project.draft_commit",
                frozenset({"cwd"}),
                frozenset(),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_project_draft_commit,
                self._execute_project_draft_commit,
            ),
            "workspace.open": self._workspace_spec("workspace.open", "T1"),
            "workspace.editor": self._workspace_spec("workspace.editor", "T1"),
            "workspace.terminal": self._workspace_spec("workspace.terminal", "T1"),
            "workspace.serve": self._workspace_spec("workspace.serve", "T2"),
            # Phase 10: only a T0, read-only domain listing is agent-reachable.
            # No T2 browser operation is registered here -- ToolCall.args is
            # JSON-serializable and a BrowserApproval cannot be forwarded
            # through it (contract Sec10/Sec11); every T2 browser action
            # requires the terminal-only `aos browser task` entrypoint.
            "browser.domain_list": ToolSpec(
                "browser.domain_list",
                frozenset(),
                frozenset(),
                lambda args, cwd: "T0",
                lambda args, cwd: False,
                self._preview_browser_domain_list,
                self._execute_browser_domain_list,
            ),
        }

    def _workspace_spec(self, name: str, risk: str) -> ToolSpec:
        return ToolSpec(name, frozenset({"project_id"}), frozenset(), lambda args, cwd: risk, lambda args, cwd: True, lambda args, cwd: self._preview_workspace(name, args, cwd), lambda args, cwd, yes: self._execute_workspace(name, args, cwd, yes))

    def _preview_workspace(self, tool: str, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation(tool, True, "Validated enrolled workspace request.", {"project_id": args["project_id"]})

    def _execute_workspace(self, tool: str, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        operation = tool.removeprefix("workspace.")
        result = WorkspaceTool().execute({"operation": operation, "project_id": args["project_id"]})
        return Observation(tool, result.ok, result.output, {"project_id": args["project_id"]})

    def list_tools(self) -> list[str]:
        return sorted(self._specs)

    def validate(self, tool_call: ToolCall, *, cwd: str | Path = ".") -> None:
        spec = self._specs.get(tool_call.tool)
        if spec is None:
            raise PermissionBlocked(f"unknown tool: {tool_call.tool}")
        args = tool_call.args
        keys = set(args)
        if not spec.required_args.issubset(keys):
            missing = sorted(spec.required_args - keys)
            raise PermissionBlocked(f"missing args for {tool_call.tool}: {', '.join(missing)}")
        allowed_keys = spec.required_args | spec.optional_args
        if not keys.issubset(allowed_keys):
            extra = sorted(keys - allowed_keys)
            raise PermissionBlocked(f"unexpected args for {tool_call.tool}: {', '.join(extra)}")
        if tool_call.tool.startswith("workspace.") and not re.fullmatch(r"[a-f0-9]{32}", str(args.get("project_id", ""))):
            raise PermissionBlocked("workspace project_id must be an opaque registry ID")
        base_cwd = Path(cwd).expanduser().resolve(strict=False)
        expected_risk = spec.risk_tier_resolver(args, base_cwd)
        expected_approval = spec.requires_approval_resolver(args, base_cwd)
        if tool_call.risk_tier != expected_risk:
            raise PermissionBlocked(
                f"tool risk tier mismatch for {tool_call.tool}: expected {expected_risk}, got {tool_call.risk_tier}"
            )
        if tool_call.requires_approval != expected_approval:
            raise PermissionBlocked(
                f"tool approval mismatch for {tool_call.tool}: expected {expected_approval}, got {tool_call.requires_approval}"
            )

    def preview(self, tool_call: ToolCall, *, cwd: str | Path = ".") -> Observation:
        self.validate(tool_call, cwd=cwd)
        spec = self._specs[tool_call.tool]
        return spec.previewer(tool_call.args, Path(cwd).expanduser().resolve(strict=False))

    def execute(self, tool_call: ToolCall, *, cwd: str | Path = ".", yes: bool = False) -> Observation:
        self.validate(tool_call, cwd=cwd)
        spec = self._specs[tool_call.tool]
        return spec.executor(tool_call.args, Path(cwd).expanduser().resolve(strict=False), yes)

    def _approved_roots(self, cwd: Path) -> list[Path]:
        return [cwd]

    def _resolve_command_risk(self, args: dict[str, Any], cwd: Path) -> str:
        command_cwd = _resolve_arg_path(cwd, str(args["cwd"]))
        decision = evaluate_command(str(args["command"]), cwd=command_cwd, approved_roots=self._approved_roots(cwd))
        return decision.risk_tier.value

    def _resolve_command_approval(self, args: dict[str, Any], cwd: Path) -> bool:
        command_cwd = _resolve_arg_path(cwd, str(args["cwd"]))
        decision = evaluate_command(str(args["command"]), cwd=command_cwd, approved_roots=self._approved_roots(cwd))
        return decision.requires_approval

    def _preview_fs_list(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("fs.list", True, f"List directory {_resolve_arg_path(cwd, str(args['path']))}.")

    def _execute_fs_list(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        path = _resolve_arg_path(cwd, str(args["path"]))
        entries = list_dir(path, approved_roots=self._approved_roots(cwd))
        return Observation("fs.list", True, f"Listed {len(entries)} entries.", {"entries": entries, "path": path})

    def _preview_fs_read(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("fs.read", True, f"Read file {_resolve_arg_path(cwd, str(args['path']))}.")

    def _execute_fs_read(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        path = _resolve_arg_path(cwd, str(args["path"]))
        text = read_file(path, approved_roots=self._approved_roots(cwd))
        return Observation("fs.read", True, f"Read {path}.", {"path": path, "text": text})

    def _preview_fs_search(self, args: dict[str, Any], cwd: Path) -> Observation:
        root = _resolve_arg_path(cwd, str(args.get("root", ".")))
        return Observation("fs.search", True, f"Search {root} for {args['query']}.")

    def _execute_fs_search(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        root = _resolve_arg_path(cwd, str(args.get("root", ".")))
        results = search_files(str(args["query"]), root=root, approved_roots=self._approved_roots(cwd))
        return Observation("fs.search", True, f"Found {len(results)} matches for {args['query']}.", {"results": results})

    def _preview_fs_write(self, args: dict[str, Any], cwd: Path) -> Observation:
        path = _resolve_arg_path(cwd, str(args["path"]))
        preview = preview_write(path, str(args["content"]), approved_roots=self._approved_roots(cwd))
        return Observation(
            "fs.write",
            True,
            f"Write preview for {path}.",
            {"path": path, "diff": preview.diff, "exists": preview.existed},
        )

    def _execute_fs_write(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        path = _resolve_arg_path(cwd, str(args["path"]))
        result = write_file(path, str(args["content"]), approved=yes, approved_roots=self._approved_roots(cwd))
        return Observation("fs.write", True, f"Wrote {path}.", {"path": path, "sha256_after": result.sha256_after})

    def _preview_fs_edit(self, args: dict[str, Any], cwd: Path) -> Observation:
        path = _resolve_arg_path(cwd, str(args["path"]))
        preview = preview_edit(
            path,
            str(args["old_text"]),
            str(args["new_text"]),
            approved_roots=self._approved_roots(cwd),
        )
        return Observation("fs.edit", True, f"Edit preview for {path}.", {"path": path, "diff": preview.diff})

    def _execute_fs_edit(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        path = _resolve_arg_path(cwd, str(args["path"]))
        result = edit_file(
            path,
            str(args["old_text"]),
            str(args["new_text"]),
            approved=yes,
            approved_roots=self._approved_roots(cwd),
        )
        return Observation("fs.edit", True, f"Edited {path}.", {"path": path, "sha256_after": result.sha256_after})

    def _preview_snapshot_list(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("snapshot.list", True, "List snapshots.")

    def _execute_snapshot_list(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        snapshots = [snapshot.snapshot_id for snapshot in list_snapshots()]
        return Observation("snapshot.list", True, f"Found {len(snapshots)} snapshots.", {"snapshot_ids": snapshots})

    def _preview_snapshot_restore(self, args: dict[str, Any], cwd: Path) -> Observation:
        snapshot = get_snapshot(str(args["snapshot_id"]))
        return Observation(
            "snapshot.restore",
            True,
            f"Restore snapshot {snapshot.snapshot_id} to {snapshot.original_path}.",
            {"snapshot_id": snapshot.snapshot_id, "path": snapshot.original_path},
        )

    def _execute_snapshot_restore(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        snapshot = restore_snapshot(str(args["snapshot_id"]), approved_roots=self._approved_roots(cwd))
        return Observation(
            "snapshot.restore",
            True,
            f"Restored snapshot {snapshot.snapshot_id}.",
            {"snapshot_id": snapshot.snapshot_id, "path": snapshot.original_path},
        )

    def _preview_run_preview(self, args: dict[str, Any], cwd: Path) -> Observation:
        command_cwd = _resolve_arg_path(cwd, str(args["cwd"]))
        preview = preview_command(
            str(args["command"]),
            cwd=command_cwd,
            approved_roots=self._approved_roots(cwd),
        )
        return Observation(
            "run.preview",
            preview.allowed,
            f"Previewed command {preview.command_original}.",
            {"command": preview.command_original, "allowed": preview.allowed, "reason": preview.reason},
        )

    def _execute_run_preview(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        return self._preview_run_preview(args, cwd)

    def _preview_run_apply(self, args: dict[str, Any], cwd: Path) -> Observation:
        command_cwd = _resolve_arg_path(cwd, str(args["cwd"]))
        preview = preview_command(
            str(args["command"]),
            cwd=command_cwd,
            approved_roots=self._approved_roots(cwd),
        )
        return Observation(
            "run.apply",
            preview.allowed,
            f"Run preview for {preview.command_original}.",
            {
                "command": preview.command_original,
                "allowed": preview.allowed,
                "requires_approval": preview.requires_approval,
                "reason": preview.reason,
            },
        )

    def _execute_run_apply(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        command_cwd = _resolve_arg_path(cwd, str(args["cwd"]))
        result = run_command(
            str(args["command"]),
            cwd=command_cwd,
            yes=yes,
            approved_roots=self._approved_roots(cwd),
        )
        return Observation(
            "run.apply",
            result.error is None and not result.timed_out,
            f"Ran {result.command_original} with return code {result.return_code}.",
            {
                "command": result.command_original,
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
            },
        )

    def _preview_memory_status(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("memory.status", True, "Inspect memory store status.")

    def _execute_memory_status(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        status = get_memory_status(db_path=DEFAULT_MEMORY_DB_PATH)
        return Observation("memory.status", True, "Loaded memory status.", {"status": status})

    def _preview_memory_recent(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("memory.recent", True, "Read recent memory activity.")

    def _execute_memory_recent(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        entries = get_recent_activity(limit=int(args.get("limit", 10)), db_path=DEFAULT_MEMORY_DB_PATH)
        return Observation("memory.recent", True, f"Loaded {len(entries)} recent memory entries.", {"entries": entries})

    def _preview_memory_timeline(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("memory.timeline", True, "Read memory timeline.")

    def _execute_memory_timeline(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        entries = get_recent_activity(limit=int(args.get("limit", 20)), db_path=DEFAULT_MEMORY_DB_PATH)
        return Observation("memory.timeline", True, f"Loaded {len(entries)} timeline entries.", {"entries": entries})

    def _preview_memory_recall(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("memory.recall", True, f"Recall memory for query: {args['query']}")

    def _execute_memory_recall(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        result = recall(
            str(args["query"]),
            limit=int(args.get("limit", 10)),
            db_path=DEFAULT_MEMORY_DB_PATH,
            audit_path=DEFAULT_AUDIT_PATH,
        )
        return Observation("memory.recall", True, "Memory recall completed.", {"summary": result.summary, "result": result})

    def _preview_git_status(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("git.status", True, f"Read git status for {_resolve_project_cwd(cwd, str(args['cwd']))}.")

    def _execute_git_status(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        repo_cwd = _resolve_project_cwd(cwd, str(args["cwd"]))
        status = git_status(repo_cwd)
        return Observation("git.status", True, f"Loaded git status for {repo_cwd}.", {"status": status})

    def _preview_git_diff_stat(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("git.diff_stat", True, f"Read git diff --stat for {_resolve_project_cwd(cwd, str(args['cwd']))}.")

    def _execute_git_diff_stat(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        repo_cwd = _resolve_project_cwd(cwd, str(args["cwd"]))
        summary = summarize_git_diff(repo_cwd)
        return Observation("git.diff_stat", True, f"Loaded git diff summary for {repo_cwd}.", {"summary": summary})

    def _preview_git_log(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("git.log", True, f"Read git log for {_resolve_project_cwd(cwd, str(args['cwd']))}.")

    def _execute_git_log(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        repo_cwd = _resolve_project_cwd(cwd, str(args["cwd"]))
        commits = git_log(repo_cwd, limit=int(args.get("limit", 10)))
        return Observation("git.log", True, f"Loaded {len(commits)} commits for {repo_cwd}.", {"commits": commits})

    def _preview_git_branch(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("git.branch", True, f"Read current branch for {_resolve_project_cwd(cwd, str(args['cwd']))}.")

    def _execute_git_branch(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        repo_cwd = _resolve_project_cwd(cwd, str(args["cwd"]))
        branch = git_branch(repo_cwd)
        return Observation("git.branch", True, f"Loaded branch for {repo_cwd}.", {"branch": branch})

    def _preview_project_summarize_changes(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("project.summarize_changes", True, f"Summarize project changes for {_resolve_project_cwd(cwd, str(args['cwd']))}.")

    def _execute_project_summarize_changes(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        repo_cwd = _resolve_project_cwd(cwd, str(args["cwd"]))
        summary = summarize_project_changes(repo_cwd)
        return Observation("project.summarize_changes", True, f"Summarized project changes for {repo_cwd}.", {"summary": summary})

    def _preview_project_draft_commit(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("project.draft_commit", True, f"Draft commit message for {_resolve_project_cwd(cwd, str(args['cwd']))}.")

    def _execute_project_draft_commit(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        repo_cwd = _resolve_project_cwd(cwd, str(args["cwd"]))
        draft = draft_commit_message(repo_cwd)
        return Observation("project.draft_commit", True, f"Drafted commit message for {repo_cwd}.", {"draft": draft})


    def _preview_browser_domain_list(self, args: dict[str, Any], cwd: Path) -> Observation:
        return Observation("browser.domain_list", True, "List enrolled browser domains.")

    def _execute_browser_domain_list(self, args: dict[str, Any], cwd: Path, yes: bool) -> Observation:
        domains = [{"domain_id": d.domain_id, "host": d.host, "revoked": d.revoked} for d in ApprovedDomainRegistry().list()]
        return Observation("browser.domain_list", True, f"Found {len(domains)} enrolled domains.", {"domains": domains})


def default_registry() -> ToolRegistry:
    return ToolRegistry()
