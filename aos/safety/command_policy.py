"""Command policy classification for the Phase 2 safe shell runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aos.safety.commands import looks_like_path_argument, parse_command
from aos.safety.errors import CommandPolicyBlocked, PermissionBlocked
from aos.safety.paths import check_dangerous_path, check_secret_path
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import RiskTier, classify_command_risk


@dataclass(frozen=True)
class CommandPolicyDecision:
    command_original: str
    argv: list[str]
    cwd: str
    policy_category: str
    risk_tier: RiskTier
    allowed: bool
    requires_approval: bool
    reason: str


DENY_COMMANDS = {
    "cmd",
    "cmd.exe",
    "bash",
    "sh",
    "sudo",
    "su",
    "doas",
    "rm",
    "del",
    "format",
    "mkfs",
    "dd",
    "chmod",
    "chown",
    "curl",
    "wget",
    "powershell",
    "pwsh",
    "iwr",
    "invoke-webrequest",
    "invoke-expression",
    "iex",
    "ssh",
    "scp",
    "nc",
    "netcat",
    "telnet",
    "ftp",
    "sftp",
}

READONLY_COMMANDS = {
    ("pwd",),
    ("ls",),
    ("dir",),
    ("git", "status"),
    ("git", "diff"),
    ("git", "log"),
    ("python", "--version"),
    ("python3", "--version"),
    ("node", "--version"),
    ("npm", "--version"),
    ("pytest", "--version"),
}

PROJECT_TEST_COMMANDS = {
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("npm", "test"),
    ("npm", "run", "test"),
    ("cargo", "test"),
    ("go", "test"),
}

APPROVAL_COMMANDS = {
    ("python",),
    ("python3",),
    ("node",),
    ("npm", "run", "build"),
    ("make", "test"),
    ("make", "build"),
}


def _matches_prefix(argv: list[str], patterns: set[tuple[str, ...]]) -> bool:
    return any(tuple(argv[: len(pattern)]) == pattern for pattern in patterns)


INLINE_EVAL_FLAGS = {"-c", "-e", "--eval"}
INLINE_EVAL_COMMANDS = {"python", "python3", "node"}


def _deny_reason(argv: list[str]) -> str | None:
    first = argv[0].lower()
    if first in DENY_COMMANDS:
        return f"blocked command: {argv[0]}"
    if first in INLINE_EVAL_COMMANDS and any(arg in INLINE_EVAL_FLAGS for arg in argv[1:]):
        return f"blocked inline code execution flag for {argv[0]}"
    joined = " ".join(item.lower() for item in argv)
    if "rm -rf" in joined or "del /s /q" in joined:
        return "blocked destructive command"
    if "curl" in joined and "sh" in joined:
        return "blocked remote shell pattern"
    if "wget" in joined and "sh" in joined:
        return "blocked remote shell pattern"
    return None


def _classify_category(argv: list[str]) -> str:
    if _matches_prefix(argv, READONLY_COMMANDS):
        return "ALLOW_READONLY"
    if _matches_prefix(argv, PROJECT_TEST_COMMANDS):
        return "ALLOW_PROJECT_TEST"
    if _matches_prefix(argv, APPROVAL_COMMANDS):
        return "ALLOW_WITH_APPROVAL"
    return "UNKNOWN"


def _validate_argument_paths(argv: list[str], cwd: Path, approved_roots: list[str | Path] | None) -> None:
    engine = PermissionEngine(approved_roots=approved_roots)
    risk = RiskTier.T2
    for arg in argv[1:]:
        if not looks_like_path_argument(arg):
            continue
        expanded = Path(arg).expanduser()
        if expanded.is_absolute() or arg.startswith(("~", ".", "..")) or any(sep in arg for sep in ("/", "\\")):
            check_dangerous_path(arg)
            check_secret_path(arg)
            engine.require_path(cwd / expanded if not expanded.is_absolute() else expanded, "run.command", risk)
        else:
            check_secret_path(arg)


def evaluate_command(
    command: str,
    *,
    cwd: str | Path = ".",
    approved_roots: list[str | Path] | None = None,
) -> CommandPolicyDecision:
    try:
        argv = parse_command(command)
    except CommandPolicyBlocked as exc:
        return CommandPolicyDecision(
            command_original=command,
            argv=[],
            cwd=str(cwd),
            policy_category="DENY",
            risk_tier=RiskTier.T3,
            allowed=False,
            requires_approval=False,
            reason=str(exc),
        )
    deny_reason = _deny_reason(argv)
    if deny_reason:
        return CommandPolicyDecision(
            command_original=command,
            argv=argv,
            cwd=str(cwd),
            policy_category="DENY",
            risk_tier=RiskTier.T3,
            allowed=False,
            requires_approval=False,
            reason=deny_reason,
        )

    engine = PermissionEngine(approved_roots=approved_roots)
    try:
        resolved_cwd = engine.require_path(cwd, "run.command", RiskTier.T0)
        _validate_argument_paths(argv, resolved_cwd, approved_roots)
    except (PermissionBlocked, CommandPolicyBlocked) as exc:
        return CommandPolicyDecision(
            command_original=command,
            argv=argv,
            cwd=str(cwd),
            policy_category="DENY",
            risk_tier=RiskTier.T3,
            allowed=False,
            requires_approval=False,
            reason=str(exc),
        )

    category = _classify_category(argv)
    risk_tier = classify_command_risk(argv, category)
    if category == "UNKNOWN":
        return CommandPolicyDecision(
            command_original=command,
            argv=argv,
            cwd=str(resolved_cwd),
            policy_category=category,
            risk_tier=risk_tier,
            allowed=False,
            requires_approval=False,
            reason="unknown command is blocked by default",
        )

    requires_approval = risk_tier != RiskTier.T0
    return CommandPolicyDecision(
        command_original=command,
        argv=argv,
        cwd=str(resolved_cwd),
        policy_category=category,
        risk_tier=risk_tier,
        allowed=True,
        requires_approval=requires_approval,
        reason="command allowed by policy",
    )
