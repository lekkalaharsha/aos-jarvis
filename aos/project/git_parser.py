from __future__ import annotations

import re

from aos.project.types import GitBranchInfo, GitChangedFile, GitCommitSummary, GitDiffSummary, GitStatus

_STATUS_LINE_RE = re.compile(r"^(?P<index>.)(?P<worktree>.) (?P<path>.+)$")
_DIFF_STAT_RE = re.compile(r"^(?P<path>.+?)\s+\|\s+\d+")
_DIFF_TOTAL_RE = re.compile(
    r"(?P<files>\d+)\s+files?\s+changed(?:,\s+(?P<insertions>\d+)\s+insertions?\(\+\))?(?:,\s+(?P<deletions>\d+)\s+deletions?\(-\))?"
)
_LOG_LINE_RE = re.compile(r"^(?P<commit>[0-9a-fA-F]+)\s+(?P<title>.+)$")


def parse_branch(output: str) -> GitBranchInfo:
    name = output.strip()
    return GitBranchInfo(name=name or "(unknown)")


def parse_status(output: str, branch: str) -> GitStatus:
    changed_files: list[GitChangedFile] = []
    staged_count = 0
    unstaged_count = 0
    untracked_count = 0
    for line in output.splitlines():
        if not line.strip():
            continue
        match = _STATUS_LINE_RE.match(line)
        if not match:
            continue
        index_status = match.group("index")
        worktree_status = match.group("worktree")
        path = match.group("path")
        untracked = index_status == "?" and worktree_status == "?"
        staged = index_status not in {" ", "?"}
        unstaged = worktree_status not in {" ", "?"}
        changed_files.append(
            GitChangedFile(
                path=path,
                index_status=index_status,
                worktree_status=worktree_status,
                staged=staged,
                unstaged=unstaged,
                untracked=untracked,
            )
        )
        staged_count += int(staged)
        unstaged_count += int(unstaged)
        untracked_count += int(untracked)
    return GitStatus(
        branch=branch,
        clean=not changed_files,
        changed_files=changed_files,
        staged_count=staged_count,
        unstaged_count=unstaged_count,
        untracked_count=untracked_count,
    )


def parse_diff_stat(output: str) -> GitDiffSummary:
    changed_files: list[str] = []
    files_changed = 0
    insertions = 0
    deletions = 0
    for line in output.splitlines():
        stat_match = _DIFF_STAT_RE.match(line.rstrip())
        if stat_match:
            changed_files.append(stat_match.group("path").strip())
            continue
        total_match = _DIFF_TOTAL_RE.search(line)
        if total_match:
            files_changed = int(total_match.group("files"))
            insertions = int(total_match.group("insertions") or 0)
            deletions = int(total_match.group("deletions") or 0)
    if files_changed == 0 and changed_files:
        files_changed = len(changed_files)
    return GitDiffSummary(
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
        changed_files=changed_files,
        raw_text=output.strip(),
    )


def parse_log_oneline(output: str) -> list[GitCommitSummary]:
    commits: list[GitCommitSummary] = []
    for line in output.splitlines():
        match = _LOG_LINE_RE.match(line.strip())
        if not match:
            continue
        commits.append(GitCommitSummary(commit_hash=match.group("commit"), title=match.group("title")))
    return commits

