from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

from aos.safety.commands import SECRET_ENV_PARTS

SECRET_FILE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "token.json",
    "secrets.*",
)

_SECRET_TEXT_PATTERN = re.compile(
    r"(?i)\b(?P<name>token|api[_-]?key|password|secret)\b(?P<sep>\s+|=|:\s*)(?P<value>\S+)"
)


def redact_text(value: str | None) -> str | None:
    if value is None:
        return None

    def _replace(match: re.Match[str]) -> str:
        normalized = match.group("name").replace("-", "_").upper()
        if any(part in normalized for part in SECRET_ENV_PARTS):
            return f"{match.group('name')}{match.group('sep')}[REDACTED]"
        return match.group(0)

    return _SECRET_TEXT_PATTERN.sub(_replace, value)


def redact_path(path: str | None) -> str | None:
    if path is None:
        return None
    candidate = path.replace("\\", "/")
    name = Path(candidate).name.lower()
    if any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_FILE_PATTERNS):
        return "[REDACTED_PATH]"
    lowered = candidate.lower()
    if ".ssh" in lowered or ".aws" in lowered or ".gnupg" in lowered or "credentials" in lowered:
        return "[REDACTED_PATH]"
    return path


def redact_command(command: str | None) -> str | None:
    return redact_text(command)


def entity_id_for(entity_type: str, name: str, path: str | None = None) -> str:
    identity = path or name
    return f"{entity_type}:{identity}"


def json_dumps(data: dict) -> str:
    return json.dumps(data, sort_keys=True)

