from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GitChangedFile:
    path: str
    index_status: str
    worktree_status: str
    staged: bool
    unstaged: bool
    untracked: bool


@dataclass(frozen=True)
class GitStatus:
    branch: str
    clean: bool
    changed_files: list[GitChangedFile] = field(default_factory=list)
    staged_count: int = 0
    unstaged_count: int = 0
    untracked_count: int = 0


@dataclass(frozen=True)
class GitDiffSummary:
    files_changed: int
    insertions: int
    deletions: int
    changed_files: list[str] = field(default_factory=list)
    raw_text: str = ""


@dataclass(frozen=True)
class GitCommitSummary:
    commit_hash: str
    title: str


@dataclass(frozen=True)
class GitBranchInfo:
    name: str


@dataclass(frozen=True)
class CommitMessageDraft:
    title: str
    body: str = ""

    @property
    def text(self) -> str:
        return self.title if not self.body else f"{self.title}\n\n{self.body}"


@dataclass(frozen=True)
class ProjectChangeSummary:
    branch: str
    clean: bool
    changed_files: list[str]
    diff_summary: GitDiffSummary
    recent_commits: list[GitCommitSummary]
    summary: str

