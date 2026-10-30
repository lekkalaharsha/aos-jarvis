"""Deterministic transcript normalization.

Pure functions with no I/O and no optional-dependency imports.  Tested
standalone without the [voice] extra installed.
"""

from __future__ import annotations

import re
import unicodedata

# Filler tokens produced by STT models that carry no command intent.
_FILLERS: frozenset[str] = frozenset(
    {
        "uh", "um", "er", "ah", "like", "you know", "i mean",
        "sort of", "kind of", "basically", "actually", "literally",
    }
)

# Homophone / spoken-command aliases → canonical written form.
# Only safe, unambiguous rewrites are included.
_ALIASES: dict[str, str] = {
    "run tests": "run tests",
    "run the tests": "run tests",
    "show git status": "show git status",
    "what's the git status": "show git status",
    "git status": "show git status",
    "summarize project": "summarize this project",
    "summarize this project": "summarize this project",
    "find to-dos": "find TODOs",
    "find todos": "find TODOs",
    "show recent commits": "show recent commits",
    "show commits": "show recent commits",
    "what branch am i on": "what branch am I on",
    "current branch": "what branch am I on",
    "what changed": "what changed in this repo",
    "show changes": "what changed in this repo",
    "draft commit": "draft a commit message",
    "draft a commit": "draft a commit message",
    "what did i work on": "what did I work on recently",
    "recall memory": "what did I work on recently",
}

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[.!?,;:]+$")


def _remove_fillers(text: str) -> str:
    for filler in _FILLERS:
        # Replace whole-word occurrences only.
        pattern = r"(?<!\w)" + re.escape(filler) + r"(?!\w),?\s*"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text


def _normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize_transcript(text: str) -> str:
    """Return a cleaned, lowercased, filler-stripped version of *text*.

    The alias table maps common spoken homophones to the canonical form
    that the intent classifier expects.  The function is deterministic and
    idempotent — calling it twice produces the same result.
    """
    if not text or not text.strip():
        return ""

    text = _normalize_unicode(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = _remove_fillers(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = _TRAILING_PUNCT_RE.sub("", text).strip()
    lower = text.lower()

    # Try longest-match alias first.
    for alias in sorted(_ALIASES, key=len, reverse=True):
        if lower == alias or lower.startswith(alias + " "):
            replacement = _ALIASES[alias]
            suffix = text[len(alias):].strip()
            return (replacement + (" " + suffix if suffix else "")).strip()

    return text


def is_empty_transcript(text: str) -> bool:
    """Return True if *text* is blank after normalization (nothing useful was said)."""
    return not normalize_transcript(text).strip()
