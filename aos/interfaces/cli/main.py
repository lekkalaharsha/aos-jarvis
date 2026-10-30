"""AOS-Jarvis CLI with audit, config, eval, safe tools, agent loop, memory, git, model support, read-only dashboard, and voice interface."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aos import __version__
from aos.config.loader import CONFIG_PATH, DATA_DIR, load_config
from aos.evals.runner import run_fixtures
from aos.interfaces.cli import ask_commands, browser_commands, dashboard_commands, fs_commands, git_commands, memory_commands, model_commands, run_commands, snapshot_commands, voice_commands, workspace_commands
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event, init_audit_db, list_events, verify_chain

app = typer.Typer(help="AOS-Jarvis CLI: audit, doctor, config, eval, safe tools, agent loop, memory, git, model support, dashboard, and voice interface.")
audit_app = typer.Typer(help="Inspect and verify the audit log.")
app.add_typer(audit_app, name="audit")
eval_app = typer.Typer(help="Run Phase 0 evaluation fixtures.")
app.add_typer(eval_app, name="eval")
config_app = typer.Typer(help="Inspect Phase 0 configuration.")
app.add_typer(config_app, name="config")
app.add_typer(fs_commands.app, name="fs")
app.add_typer(snapshot_commands.app, name="snapshot")
app.add_typer(memory_commands.app, name="memory")
app.add_typer(git_commands.app, name="git")
app.add_typer(model_commands.app, name="model")
app.add_typer(dashboard_commands.app, name="dashboard")
app.add_typer(voice_commands.app, name="voice")
app.add_typer(workspace_commands.app, name="workspace")
app.add_typer(browser_commands.app, name="browser")
app.command("run")(run_commands.run_cli)
app.command("ask")(ask_commands.ask_cli)
app.command("recall")(memory_commands.recall_cli)

console = Console()
CONFIG_DIR = DATA_DIR


@app.command()
def version() -> None:
    """Print package version."""
    typer.echo(__version__)


@app.command()
def doctor() -> None:
    """Check config directory, audit DB, and audit chain health."""
    ok = True

    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        console.print(f"[green][ok][/green] config directory: {CONFIG_DIR}")
    except OSError as exc:
        ok = False
        console.print(f"[red][fail][/red] config directory: {exc}")

    try:
        load_config(CONFIG_PATH)
        console.print(f"[green][ok][/green] config file: {CONFIG_PATH}")
    except OSError as exc:
        ok = False
        console.print(f"[red][fail][/red] config file: {exc}")

    try:
        init_audit_db(DEFAULT_AUDIT_PATH)
        console.print(f"[green][ok][/green] audit db: {DEFAULT_AUDIT_PATH}")
    except OSError as exc:
        ok = False
        console.print(f"[red][fail][/red] audit db: {exc}")

    result = verify_chain(DEFAULT_AUDIT_PATH)
    if result.valid:
        console.print(f"[green][ok][/green] audit chain valid ({result.checked_count} events)")
    else:
        ok = False
        console.print(f"[red][fail][/red] audit chain invalid: {result.reason}")

    if not ok:
        raise typer.Exit(code=1)


@config_app.command("show")
def config_show() -> None:
    """Print the current Phase 0 configuration."""
    config = load_config(CONFIG_PATH)
    console.print(config)


@audit_app.command("list")
def audit_list() -> None:
    """Print audit events."""
    table = Table(show_header=True, header_style="bold")
    for column in ("id", "timestamp", "actor", "event_type", "action", "resource", "risk_tier", "status"):
        table.add_column(column)

    for event in list_events(DEFAULT_AUDIT_PATH):
        table.add_row(
            str(event.id),
            event.timestamp,
            event.actor,
            event.event_type,
            event.action,
            event.resource,
            event.risk_tier,
            event.status,
        )
    console.print(table)


@audit_app.command("verify")
def audit_verify() -> None:
    """Verify hash-chain and print valid/invalid result."""
    result = verify_chain(DEFAULT_AUDIT_PATH)
    if result.valid:
        console.print(f"valid ({result.checked_count} events)")
    else:
        console.print(f"invalid: {result.reason} (event id {result.first_broken_id})")
        raise typer.Exit(code=1)


@eval_app.command("run")
def eval_run() -> None:
    """Run Phase 0 fixture checks."""
    outcomes = run_fixtures()
    failures = 0
    for outcome in outcomes:
        status = "pass" if outcome.passed else "fail"
        color = "green" if outcome.passed else "red"
        console.print(f"[{color}][{status}][/{color}] {outcome.eval_id}: {outcome.detail}")
        if not outcome.passed:
            failures += 1

    append_event(
        DEFAULT_AUDIT_PATH,
        actor="cli",
        event_type="eval_run",
        action="eval run",
        resource="phase0_basic",
        risk_tier="T0",
        status="ALLOW",
        payload={"total": len(outcomes), "failures": failures},
    )

    if failures:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
