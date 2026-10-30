"""Voice-layer safety: TTS output filtering, confidence handling, injection guards.

All functions here are pure or near-pure — no I/O, no optional deps.
"""

from __future__ import annotations

import re

# Maximum characters spoken aloud.  Long responses are truncated with a
# visible indicator so the user knows to check the terminal for the full output.
MAX_TTS_CHARS: int = 500

# Patterns that indicate secret-shaped content that must not be spoken.
# Same spirit as the dashboard sanitizer; TTS surface-area is narrower so we
# keep this focused.
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{4,}"),                  # OpenAI-style key
    re.compile(r"(?i)\bghp_[A-Za-z0-9_-]{4,}"),                 # GitHub PAT
    # Safety-biased: any bearer/basic value after an auth prefix is secret-shaped.
    re.compile(r"(?i)\bBearer\s+\S+"),
    re.compile(r"(?i)Authorization:\s*Basic\s+\S+"),
    re.compile(r"(?i)AWS_SECRET_ACCESS_KEY\s*[=:]\s*\S+"),
    # Redact a complete key block, or everything following a malformed BEGIN line.
    re.compile(
        r"-----BEGIN\s+(?:[A-Z]+\s+)*PRIVATE\s+KEY-----.*?(?:-----END\s+(?:[A-Z]+\s+)*PRIVATE\s+KEY-----|\Z)",
        re.DOTALL,
    ),
    re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|token|credential)\s*[=:]\s*\S{4,}"),
]

# Phrases that, if transcribed verbatim, could be prompt-injection attempts.
# We don't block them (they're treated as UNKNOWN intent by the agent), but
# we flag them in audit metadata so reviewers can spot injection patterns.
_INJECTION_INDICATORS: list[re.Pattern[str]] = [
    re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions"),
    re.compile(r"(?i)system\s*:\s*you\s+are"),
    re.compile(r'(?i)\{["\']tool["\']\s*:'),          # JSON tool-call attempt
    re.compile(r"(?i)\bsudo\b.*\brm\b"),
    re.compile(r"(?i)\bapprove\b.*\blast\s+action"),
]


def redact_tts_output(text: str) -> str:
    """Redact secret-shaped strings from *text* before TTS synthesis.

    Returns the cleaned text, bounded to MAX_TTS_CHARS.  A suffix is appended
    when truncation occurs so the user knows to check the terminal.
    """
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)

    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS].rstrip() + " [output truncated, see terminal]"

    return text


def contains_secret_pattern(text: str) -> bool:
    """Return True if *text* contains any secret-shaped string."""
    return any(p.search(text) for p in _SECRET_PATTERNS)


def looks_like_injection_attempt(text: str) -> bool:
    """Return True if *text* matches a known prompt-injection indicator.

    This does NOT block execution — the agent's intent classifier handles
    unknown inputs safely.  The flag is used for audit metadata only.
    """
    return any(p.search(text) for p in _INJECTION_INDICATORS)


def confidence_allows_destructive(confidence: float | None) -> bool:
    """Return True only if confidence is high enough to permit a destructive action.

    Destructive/irreversible actions (T2+) require ≥0.85 confidence.
    Actions where the provider did not report confidence (None) return False —
    unknown confidence is treated conservatively.
    """
    if confidence is None:
        return False
    return confidence >= 0.85


def voice_approval_always_denied() -> bool:
    """Voice input must never serve as approval for risky actions.

    This exists as a named function (rather than a constant) so tests can
    assert the invariant explicitly and any future change requires a deliberate
    edit with a clear paper trail.
    """
    return True
