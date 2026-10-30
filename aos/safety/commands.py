"""Shared helpers and data models for Phase 2 command execution."""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from aos.safety.errors import CommandPolicyBlocked
from aos.safety.sandbox import SandboxMode

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_OUTPUT_BYTES = 200 * 1024

SAFE_ENV_KEYS = {
    "PATH",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "TEMP",
    "TMP",
    "VIRTUAL_ENV",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "LANG",
    "LC_ALL",
    "TERM",
}

SECRET_ENV_EXACT = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN",
    "HF_TOKEN",
    "TOKEN",
    "API_KEY",
    "PASSWORD",
    "SECRET",
}

SECRET_ENV_PARTS = ("TOKEN", "API_KEY", "PASSWORD", "SECRET")
SHELL_CONTROL_PATTERNS = ("&&", "||", ";", "|", ">", "<", "`", "$(")

_SECRET_OPTION_NAME_SPLIT = re.compile(r"[^A-Z0-9]+")


@dataclass(frozen=True)
class EnvironmentSummary:
    preserved_keys: list[str]
    removed_keys: list[str]


@dataclass(frozen=True)
class CommandPreview:
    command_original: str
    argv: list[str]
    cwd: str
    policy_category: str
    risk_tier: str
    allowed: bool
    requires_approval: bool
    timeout_seconds: int
    sandbox_mode: SandboxMode
    environment_summary: EnvironmentSummary
    reason: str


@dataclass(frozen=True)
class CommandResult:
    command_original: str
    argv: list[str]
    cwd: str
    policy_category: str
    risk_tier: str
    allowed: bool
    approved: bool
    return_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    output_truncated: bool
    audit_event_id: int | None
    error: str | None


def reject_shell_control(command: str) -> None:
    for pattern in SHELL_CONTROL_PATTERNS:
        if pattern in command:
            raise CommandPolicyBlocked(f"blocked shell control syntax: {pattern}")


def _strip_matching_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        return token[1:-1]
    return token


def parse_command(command: str) -> list[str]:
    stripped = command.strip()
    if not stripped:
        raise CommandPolicyBlocked("empty command is not allowed")
    reject_shell_control(stripped)
    try:
        # posix=False on Windows avoids shlex treating backslashes in paths (C:\Users\...)
        # as escape characters; that leaves surrounding quote chars in each token, so strip them.
        argv = shlex.split(stripped, posix=os.name != "nt")
    except ValueError as exc:
        raise CommandPolicyBlocked(f"command could not be parsed safely: {exc}") from exc
    if not argv:
        raise CommandPolicyBlocked("empty command is not allowed")
    return [_strip_matching_quotes(arg) for arg in argv]


def sanitize_environment(env: dict[str, str] | None = None) -> tuple[dict[str, str], EnvironmentSummary]:
    source = dict(env or os.environ)
    safe_env: dict[str, str] = {}
    removed_keys: list[str] = []
    preserved_keys: list[str] = []

    for key, value in source.items():
        key_upper = key.upper()
        is_python_var = key_upper.startswith("PYTHON")
        is_safe = key_upper in SAFE_ENV_KEYS or is_python_var
        if key_upper in SECRET_ENV_EXACT or any(part in key_upper for part in SECRET_ENV_PARTS):
            removed_keys.append(key)
            continue
        if is_safe:
            safe_env[key] = value
            preserved_keys.append(key)
        else:
            removed_keys.append(key)

    return safe_env, EnvironmentSummary(
        preserved_keys=sorted(preserved_keys),
        removed_keys=sorted(removed_keys),
    )


def looks_like_path_argument(arg: str) -> bool:
    if not arg or arg.startswith("-"):
        return False
    lowered = arg.lower()
    if lowered in {"status", "diff", "log", "test", "build"}:
        return False
    if any(sep in arg for sep in ("/", "\\")):
        return True
    if arg.startswith((".", "~")):
        return True
    if len(arg) > 2 and arg[1] == ":":
        return True
    return lowered.endswith((".py", ".js", ".sh", ".env", ".pem", ".key"))


def summarize_truncation(text: str, max_bytes: int) -> tuple[str, bool]:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return text, False
    clipped = data[:max_bytes].decode("utf-8", errors="replace")
    return clipped + "\n[truncated]", True


def _looks_secret_like_option(name: str) -> bool:
    normalized = "_".join(part for part in _SECRET_OPTION_NAME_SPLIT.split(name.upper()) if part)
    return any(part in normalized for part in SECRET_ENV_PARTS)


def redact_audited_argv(argv: list[str]) -> list[str]:
    redacted: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg.startswith("-"):
            option, separator, value = arg.partition("=")
            if separator and _looks_secret_like_option(option.lstrip("-")):
                redacted.append(f"{option}=[REDACTED]")
                index += 1
                continue
            if not separator and _looks_secret_like_option(arg.lstrip("-")) and index + 1 < len(argv):
                redacted.append(arg)
                redacted.append("[REDACTED]")
                index += 2
                continue
        redacted.append(arg)
        index += 1
    return redacted
