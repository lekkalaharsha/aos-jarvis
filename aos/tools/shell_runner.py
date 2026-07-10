"""Phase 2 safe shell command runner."""

from __future__ import annotations

import subprocess
import time
from shlex import join as shlex_join
from pathlib import Path

from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.safety.command_policy import evaluate_command
from aos.safety.commands import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    CommandPreview,
    CommandResult,
    redact_audited_argv,
    sanitize_environment,
    summarize_truncation,
)
from aos.safety.errors import ApprovalRequired, CommandExecutionFailed, CommandPolicyBlocked
from aos.safety.sandbox import default_sandbox_mode


def _audit(action: str, preview: CommandPreview, allowed: bool, **payload: object) -> int:
    redacted_argv = redact_audited_argv(preview.argv)
    event = append_event(
        DEFAULT_AUDIT_PATH,
        actor="run",
        event_type=action,
        action=action,
        resource=preview.cwd,
        risk_tier=preview.risk_tier,
        status="ALLOW" if allowed else "DENY",
        payload={
            "action": action,
            "command_original": shlex_join(redacted_argv) if redacted_argv else preview.command_original,
            "argv": redacted_argv,
            "cwd": preview.cwd,
            "risk_tier": preview.risk_tier,
            "policy_category": preview.policy_category,
            "allowed": allowed,
            "requires_approval": preview.requires_approval,
            **payload,
        },
    )
    return event.id


def preview_command(
    command: str,
    cwd: str = ".",
    *,
    approved_roots: list[str | Path] | None = None,
    timeout_seconds: int | None = None,
) -> CommandPreview:
    timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
    policy = evaluate_command(command, cwd=cwd, approved_roots=approved_roots)
    _, env_summary = sanitize_environment()
    preview = CommandPreview(
        command_original=command,
        argv=policy.argv,
        cwd=policy.cwd,
        policy_category=policy.policy_category,
        risk_tier=policy.risk_tier.value,
        allowed=policy.allowed,
        requires_approval=policy.requires_approval,
        timeout_seconds=timeout,
        sandbox_mode=default_sandbox_mode(),
        environment_summary=env_summary,
        reason=policy.reason,
    )
    _audit(
        "run.preview",
        preview,
        allowed=preview.allowed,
        approved=False,
        timed_out=False,
        output_truncated=False,
        reason=preview.reason,
    )
    return preview


def run_command(
    command: str,
    cwd: str = ".",
    *,
    yes: bool = False,
    timeout_seconds: int | None = None,
    approved_roots: list[str | Path] | None = None,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> CommandResult:
    preview = preview_command(
        command,
        cwd=cwd,
        approved_roots=approved_roots,
        timeout_seconds=timeout_seconds,
    )
    if not preview.allowed:
        audit_id = _audit(
            "run.blocked",
            preview,
            allowed=False,
            approved=False,
            timed_out=False,
            output_truncated=False,
            reason=preview.reason,
            error=preview.reason,
        )
        raise CommandPolicyBlocked(preview.reason + f" [audit_event_id={audit_id}]")
    if preview.requires_approval and not yes:
        _audit(
            "run.blocked",
            preview,
            allowed=False,
            approved=False,
            timed_out=False,
            output_truncated=False,
            reason="approval required",
            error="approval required",
        )
        raise ApprovalRequired("command requires explicit approval")

    env, _ = sanitize_environment()
    start = time.perf_counter()
    audit_event_id: int | None = None
    try:
        process = subprocess.Popen(
            preview.argv,
            cwd=preview.cwd,
            env=env,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = process.communicate(timeout=preview.timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_bytes, stderr_bytes = process.communicate()
            timed_out = True
    except FileNotFoundError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        result = CommandResult(
            command_original=preview.command_original,
            argv=preview.argv,
            cwd=preview.cwd,
            policy_category=preview.policy_category,
            risk_tier=preview.risk_tier,
            allowed=True,
            approved=yes,
            return_code=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            timed_out=False,
            output_truncated=False,
            audit_event_id=None,
            error=f"command not found: {preview.argv[0]}",
        )
        audit_event_id = _audit(
            "run.blocked",
            preview,
            allowed=False,
            approved=yes,
            timed_out=False,
            output_truncated=False,
            reason="command could not be started",
            error=str(exc),
        )
        return CommandResult(**{**result.__dict__, "audit_event_id": audit_event_id})

    duration_ms = int((time.perf_counter() - start) * 1000)
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    stdout, stdout_truncated = summarize_truncation(stdout, max_output_bytes)
    stderr, stderr_truncated = summarize_truncation(stderr, max_output_bytes)
    output_truncated = stdout_truncated or stderr_truncated

    if timed_out:
        audit_event_id = _audit(
            "run.timeout",
            preview,
            allowed=True,
            approved=yes,
            timed_out=True,
            output_truncated=output_truncated,
            return_code=process.returncode,
            duration_ms=duration_ms,
            reason="command timed out",
        )
    else:
        audit_event_id = _audit(
            "run.apply",
            preview,
            allowed=True,
            approved=yes,
            timed_out=False,
            output_truncated=output_truncated,
            return_code=process.returncode,
            duration_ms=duration_ms,
            reason="command executed",
        )
    if output_truncated:
        _audit(
            "run.output_truncated",
            preview,
            allowed=True,
            approved=yes,
            timed_out=timed_out,
            output_truncated=True,
            return_code=process.returncode,
            duration_ms=duration_ms,
            reason="command output truncated",
        )

    return CommandResult(
        command_original=preview.command_original,
        argv=preview.argv,
        cwd=preview.cwd,
        policy_category=preview.policy_category,
        risk_tier=preview.risk_tier,
        allowed=True,
        approved=yes,
        return_code=process.returncode,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
        output_truncated=output_truncated,
        audit_event_id=audit_event_id,
        error="command timed out" if timed_out else None,
    )
