from __future__ import annotations

from pathlib import Path

from aos.project.git_parser import parse_branch, parse_diff_stat, parse_log_oneline, parse_status
from aos.project.types import CommitMessageDraft, GitBranchInfo, GitCommitSummary, GitDiffSummary, GitStatus
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.safety.errors import ProjectToolError
from aos.tools.shell_runner import run_command


def _approved_roots(cwd: str | Path) -> list[Path]:
    return [Path(cwd).expanduser().resolve(strict=False)]


def _friendly_git_error(result) -> str:
    text = "\n".join(part for part in [result.stderr, result.stdout, result.error or ""] if part).lower()
    if "not a git repository" in text:
        return "current directory is not a git repository"
    if "command not found" in text:
        return "git is not available in PATH"
    return result.error or result.stderr.strip() or result.stdout.strip() or "git command failed"


def _run_git(command: str, *, cwd: str | Path = "."):
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    result = run_command(command, cwd=resolved_cwd, approved_roots=_approved_roots(resolved_cwd))
    if result.error or (result.return_code not in (0, None)):
        raise ProjectToolError(_friendly_git_error(result))
    return result


def _require_git_repo(cwd: str | Path) -> None:
    _run_git("git status --short", cwd=cwd)


def _audit(action: str, *, cwd: str, success: bool, blocked: bool = False, **payload: object) -> None:
    append_event(
        DEFAULT_AUDIT_PATH,
        actor="project",
        event_type=action,
        action=action,
        resource=cwd,
        risk_tier="T0",
        status="ALLOW" if success and not blocked else "DENY" if blocked else "ALLOW",
        payload={"action": action, "cwd": cwd, "success": success, "blocked": blocked, **payload},
    )


def git_branch(cwd: str | Path = ".") -> GitBranchInfo:
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    _require_git_repo(resolved_cwd)
    branch = parse_branch(_run_git("git branch --show-current", cwd=resolved_cwd).stdout)
    _audit("git.branch", cwd=resolved_cwd, success=True, branch=branch.name)
    return branch


def git_status(cwd: str | Path = ".") -> GitStatus:
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    status_output = _run_git("git status --short", cwd=resolved_cwd).stdout
    branch = parse_branch(_run_git("git branch --show-current", cwd=resolved_cwd).stdout).name
    status = parse_status(status_output, branch)
    _audit(
        "git.status",
        cwd=resolved_cwd,
        success=True,
        branch=status.branch,
        changed_file_count=len(status.changed_files),
        result_summary=f"clean={status.clean}",
    )
    return status


def git_diff(cwd: str | Path = ".", *, stat: bool = False) -> GitDiffSummary:
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    command = "git diff --stat" if stat else "git diff"
    result = _run_git(command, cwd=resolved_cwd)
    summary = parse_diff_stat(result.stdout if stat else _run_git("git diff --stat", cwd=resolved_cwd).stdout)
    _audit(
        "git.diff",
        cwd=resolved_cwd,
        success=True,
        changed_file_count=summary.files_changed,
        result_summary=f"files={summary.files_changed}, insertions={summary.insertions}, deletions={summary.deletions}",
    )
    return GitDiffSummary(
        files_changed=summary.files_changed,
        insertions=summary.insertions,
        deletions=summary.deletions,
        changed_files=summary.changed_files,
        raw_text=result.stdout.strip(),
    )


def git_log(cwd: str | Path = ".", *, limit: int = 10) -> list[GitCommitSummary]:
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    limit = max(1, min(int(limit), 50))
    result = _run_git(f"git log --oneline -n {limit}", cwd=resolved_cwd)
    commits = parse_log_oneline(result.stdout)
    _audit("git.log", cwd=resolved_cwd, success=True, result_summary=f"commit_count={len(commits)}")
    return commits


def git_changed_files(cwd: str | Path = ".") -> list[str]:
    return [item.path for item in git_status(cwd).changed_files]


def summarize_git_status(cwd: str | Path = ".") -> str:
    status = git_status(cwd)
    if status.clean:
        return f"Branch {status.branch} is clean."
    files = ", ".join(item.path for item in status.changed_files[:10])
    return f"Branch {status.branch} has {len(status.changed_files)} changed files: {files}"


def summarize_git_diff(cwd: str | Path = ".") -> str:
    diff = git_diff(cwd, stat=True)
    if diff.files_changed == 0:
        return "No unstaged diff is present."
    return (
        f"{diff.files_changed} files changed, {diff.insertions} insertions, "
        f"{diff.deletions} deletions."
    )


def draft_commit_message(cwd: str | Path = ".") -> CommitMessageDraft:
    status = git_status(cwd)
    diff = git_diff(cwd, stat=True)
    if status.clean:
        draft = CommitMessageDraft(title="chore: no repository changes detected")
    else:
        paths = [Path(path).stem for path in git_changed_files(cwd)[:3]]
        scope = paths[0].replace("_", "-") if paths else "repo"
        title = f"chore({scope}): update {', '.join(paths[:2])}" if paths else "chore: update repository changes"
        body = (
            f"- branch: {status.branch}\n"
            f"- files changed: {diff.files_changed}\n"
            f"- insertions/deletions: {diff.insertions}/{diff.deletions}"
        )
        draft = CommitMessageDraft(title=title, body=body)
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    _audit("project.commit_draft", cwd=resolved_cwd, success=True, branch=status.branch, result_summary=draft.title)
    return draft
