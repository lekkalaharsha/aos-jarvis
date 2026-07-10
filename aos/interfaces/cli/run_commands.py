"""Phase 2 CLI command runner."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from aos.safety.errors import ApprovalRequired, SafetyError
from aos.safety.risk import RiskTier
from aos.tools.shell_runner import preview_command, run_command

console = Console()


def _approved_roots() -> list[Path]:
    return [Path.cwd()]


def _print_preview(preview) -> None:
    console.print(f"command: {preview.command_original}")
    console.print(f"argv: {preview.argv}")
    console.print(f"cwd: {preview.cwd}")
    console.print(f"risk: {preview.risk_tier}")
    console.print(f"policy: {preview.policy_category}")
    console.print(f"approval required: {'yes' if preview.requires_approval else 'no'}")
    console.print(f"allowed: {'yes' if preview.allowed else 'no'}")
    console.print(f"sandbox: {preview.sandbox_mode.value}")
    console.print(f"timeout seconds: {preview.timeout_seconds}")
    console.print(f"env removed: {len(preview.environment_summary.removed_keys)}")
    console.print(f"reason: {preview.reason}")


def _confirm(preview, yes: bool) -> None:
    if yes:
        return
    if preview.risk_tier == RiskTier.T2.value:
        if not typer.confirm("This is a T2 high-risk command. Continue?", default=False):
            raise typer.Abort()
        typed = typer.prompt("Type RUN to execute")
        if typed != "RUN":
            raise typer.Abort()
        return
    if preview.requires_approval and not typer.confirm("Run command?", default=False):
        raise typer.Abort()


def run_cli(
    command: str = typer.Argument(..., help="Quoted command string to classify and run."),
    cwd: str = typer.Option(".", "--cwd"),
    yes: bool = typer.Option(False, "--yes", help="Skip approval prompts."),
    timeout: int = typer.Option(30, "--timeout"),
    preview: bool = typer.Option(False, "--preview", help="Show preview and do not execute."),
) -> None:
    """Preview or execute a safe shell command."""
    try:
        cmd_preview = preview_command(
            command,
            cwd=cwd,
            approved_roots=_approved_roots(),
            timeout_seconds=timeout,
        )
        _print_preview(cmd_preview)
        if preview:
            return
        if not cmd_preview.allowed:
            console.print(f"[red]blocked:[/red] {cmd_preview.reason}")
            raise typer.Exit(code=1)
        _confirm(cmd_preview, yes)
        result = run_command(
            command,
            cwd=cwd,
            yes=True if cmd_preview.requires_approval else yes,
            timeout_seconds=timeout,
            approved_roots=_approved_roots(),
        )
        console.print(f"return code: {result.return_code}")
        if result.stdout:
            console.print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            console.print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
        console.print(f"timed out: {'yes' if result.timed_out else 'no'}")
        console.print(f"output truncated: {'yes' if result.output_truncated else 'no'}")
        if result.audit_event_id is not None:
            console.print(f"audit event: {result.audit_event_id}")
        if result.error:
            raise typer.Exit(code=1)
        if result.return_code:
            raise typer.Exit(code=result.return_code)
    except (typer.Exit, typer.Abort):
        raise
    except ApprovalRequired as exc:
        console.print(f"[red]approval required:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except SafetyError as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
