from __future__ import annotations

import re

from aos.agent.types import Intent

_READ_FILE_PATTERN = re.compile(r"\b(?:read|show|open)\s+([^\s].+)$", re.IGNORECASE)
_CREATE_NOTES_PATTERN = re.compile(r"\b(?:create|write)\s+([^\s]+(?:\.md|\.txt)?)", re.IGNORECASE)


def classify_intent(user_message: str) -> Intent:
    message = user_message.strip().lower()
    if "workspace" in message and "serve" in message:
        return Intent.WORKSPACE_SERVE
    if "workspace" in message and "editor" in message:
        return Intent.WORKSPACE_EDITOR
    if "workspace" in message and "terminal" in message:
        return Intent.WORKSPACE_TERMINAL
    if "open workspace" in message:
        return Intent.WORKSPACE_OPEN
    if any(
        phrase in message
        for phrase in (
            "git push",
            "run git push",
            "draft commit and push",
            "git pull",
            "git fetch",
            "git clone",
            "git commit",
            "git reset",
            "git clean",
            "git checkout",
            "git switch",
            "git rebase",
            "git merge",
        )
    ):
        return Intent.UNKNOWN
    if any(
        phrase in message
        for phrase in (
            "what did i work on recently",
            "what did i edit today",
            "what files changed",
            "what commands did i run",
            "what failed recently",
            "show blocked actions",
            "show project timeline",
            "show recent activity",
        )
    ):
        return Intent.RECALL_MEMORY
    if any(phrase in message for phrase in ("summarize this project", "what is this repo about", "explain this project")):
        return Intent.PROJECT_SUMMARY
    if any(phrase in message for phrase in ("what changed in this repo", "summarize project changes", "summarize git diff")):
        return Intent.PROJECT_CHANGES
    if any(phrase in message for phrase in ("draft a commit message", "write commit message", "suggest commit message")):
        return Intent.DRAFT_COMMIT
    if any(phrase in message for phrase in ("what branch am i on", "current git branch")):
        return Intent.CURRENT_BRANCH
    if any(phrase in message for phrase in ("show recent commits", "summarize git log")):
        return Intent.RECENT_COMMITS
    if "todo" in message or "fixme" in message or "hack" in message:
        return Intent.FIND_TODOS
    if any(phrase in message for phrase in ("show git status", "repo status", "what changed")):
        return Intent.GIT_STATUS
    if any(phrase in message for phrase in ("run tests", "run pytest", "test this project")):
        return Intent.RUN_TESTS
    if _CREATE_NOTES_PATTERN.search(user_message) and "note" in message:
        return Intent.CREATE_NOTES
    if _READ_FILE_PATTERN.search(user_message):
        return Intent.READ_FILE
    return Intent.UNKNOWN


def extract_project_id(user_message: str) -> str | None:
    """Only accept a registry-shaped opaque ID, never a path from agent text."""
    match = re.search(r"\b[a-fA-F0-9]{32}\b", user_message)
    return match.group(0).lower() if match else None


def extract_requested_file(user_message: str) -> str | None:
    match = _READ_FILE_PATTERN.search(user_message.strip())
    if not match:
        return None
    candidate = match.group(1).strip().strip("\"'")
    lowered = candidate.lower()
    if lowered.startswith("git status"):
        return None
    return candidate


def extract_notes_filename(user_message: str) -> str:
    match = _CREATE_NOTES_PATTERN.search(user_message.strip())
    if not match:
        return "notes.md"
    candidate = match.group(1).strip().strip("\"'")
    lowered = candidate.lower()
    if lowered in {"a", "notes", "note", "file", "notes file", "a notes file", "project notes file"}:
        return "notes.md"
    if "." not in candidate:
        return "notes.md"
    return candidate
