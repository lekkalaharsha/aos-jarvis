from __future__ import annotations

from pathlib import Path

from aos.memory.recall import recall
from aos.project.git_tools import git_branch, git_diff, git_log, git_status
from aos.project.types import ProjectChangeSummary
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event


def _audit(action: str, *, cwd: str, success: bool, **payload: object) -> None:
    append_event(
        DEFAULT_AUDIT_PATH,
        actor="project",
        event_type=action,
        action=action,
        resource=cwd,
        risk_tier="T0",
        status="ALLOW" if success else "DENY",
        payload={"action": action, "cwd": cwd, "success": success, **payload},
    )


def summarize_project_changes(cwd: str | Path = ".") -> ProjectChangeSummary:
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    branch = git_branch(resolved_cwd).name
    status = git_status(resolved_cwd)
    diff = git_diff(resolved_cwd, stat=True)
    commits = git_log(resolved_cwd, limit=5)
    changed_files = [item.path for item in status.changed_files]
    if status.clean:
        summary = f"Branch {branch} is clean. Recent commits: {', '.join(commit.title for commit in commits[:3]) or 'none'}."
    else:
        summary = (
            f"Branch {branch} has {len(changed_files)} changed files. "
            f"Diff stat: {diff.files_changed} files, {diff.insertions} insertions, {diff.deletions} deletions. "
            f"Recent commits: {', '.join(commit.title for commit in commits[:3]) or 'none'}."
        )
    _audit("project.summary", cwd=resolved_cwd, success=True, branch=branch, changed_file_count=len(changed_files), result_summary=summary)
    return ProjectChangeSummary(
        branch=branch,
        clean=status.clean,
        changed_files=changed_files,
        diff_summary=diff,
        recent_commits=commits,
        summary=summary,
    )


def summarize_recent_project_activity(cwd: str | Path = ".") -> str:
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    change_summary = summarize_project_changes(resolved_cwd)
    memory_summary = recall("what did I work on recently")
    return f"{change_summary.summary}\nRecent memory:\n{memory_summary.summary}"


def summarize_failures(cwd: str | Path = ".") -> str:
    return recall("what failed recently").summary

