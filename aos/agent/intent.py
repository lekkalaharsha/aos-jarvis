from __future__ import annotations

import re

from aos.agent.types import Intent

_READ_FILE_PATTERN = re.compile(r"\b(?:read|show|open)\s+([^\s].+)$", re.IGNORECASE)
_CREATE_NOTES_PATTERN = re.compile(r"\b(?:create|write)\s+([^\s]+(?:\.md|\.txt)?)", re.IGNORECASE)


def classify_intent(user_message: str) -> Intent:
    message = user_message.strip().lower()
    if any(phrase in message for phrase in ("summarize this project", "what is this repo about", "explain this project")):
        return Intent.PROJECT_SUMMARY
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

