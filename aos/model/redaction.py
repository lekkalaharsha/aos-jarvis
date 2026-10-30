from __future__ import annotations

import re
from typing import Any

from aos.model.types import RedactionResult

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
    ("ssh_key", re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----.*?-----END OPENSSH PRIVATE KEY-----", re.DOTALL), "[REDACTED_SSH_KEY]"),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED_SECRET]"),
    ("openai_token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_SECRET]"),
    ("provider_token", re.compile(r"\b(?:anthropic|gemini|groq|openrouter)[_-]?[A-Za-z0-9_-]{16,}\b", re.IGNORECASE), "[REDACTED_SECRET]"),
    ("aws_access_key", re.compile(r"\bA(?:KIA|SIA)[A-Z0-9]{16}\b"), "[REDACTED_SECRET]"),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[REDACTED_JWT]"),
    ("database_url", re.compile(r"\b(postgres(?:ql)?|mysql|mongodb|redis)://([^:\s/@]+):([^@\s]+)@([^\s]+)", re.IGNORECASE), r"\1://[REDACTED_CREDENTIALS]@\4"),
    ("authorization_header", re.compile(r"(?im)^(Authorization\s*:\s*)(Bearer|Basic)\s+[^\r\n]+"), r"\1[REDACTED_SECRET]"),
    ("cookie", re.compile(r"(?im)^(Cookie\s*:\s*)[^\r\n]+"), r"\1[REDACTED_COOKIE]"),
    ("env_secret", re.compile(r"(?im)^([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|ACCESS_KEY|PRIVATE_KEY)[A-Z0-9_]*\s*=\s*)([^\r\n]+)"), r"\1[REDACTED_SECRET]"),
    ("credential_pair", re.compile(r"(?i)\b(password|api[_-]?key|secret|token)\b(\s*[:=]\s*)([^\s,;]+)"), r"\1\2[REDACTED_SECRET]"),
]

_SENSITIVE_METADATA_KEYS = re.compile(
    r"(?:api[_-]?key|authorization|cookie|credential|password|private[_-]?key|secret|token)",
    re.IGNORECASE,
)


def redact_text(text: str) -> RedactionResult:
    redacted_text = text
    counts: dict[str, int] = {}
    for category, pattern, replacement in _PATTERNS:
        redacted_text, count = pattern.subn(replacement, redacted_text)
        if count:
            counts[category] = counts.get(category, 0) + count
    return RedactionResult(text=redacted_text, redacted=bool(counts), counts_by_category=counts)


def redact_messages(messages: list[str]) -> RedactionResult:
    joined = "\n".join(messages)
    return redact_text(joined)


def redact_metadata(value: Any) -> Any:
    """Return JSON-safe audit metadata with secret-shaped content removed.

    Audit metadata is caller-supplied context, not a trusted schema.  Keep
    only JSON primitives/containers and redact both sensitive-looking keys and
    secret-shaped string values before persistence.
    """
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            result[key] = "[REDACTED]" if _SENSITIVE_METADATA_KEYS.search(key) else redact_metadata(raw_value)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_metadata(item) for item in value]
    if isinstance(value, str):
        return redact_text(value).text
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "[REDACTED_UNSUPPORTED_METADATA]"
