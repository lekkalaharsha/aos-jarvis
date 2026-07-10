from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aos.memory.entities import redact_text
from aos.memory.indexer import rebuild_memory_from_audit
from aos.memory.recall import recall
from aos.memory.store import DEFAULT_MEMORY_DB_PATH, get_memory_status, init_memory_store
from aos.memory.timeline import (
    get_blocked_events,
    get_command_history,
    get_failed_commands,
    get_recent_activity,
    get_recent_files,
)
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event

app = typer.Typer(help="Audit-derived local memory system.")
console = Console()


def _audit_query(action: str, *, query: str | None = None, result_count: int = 0, success: bool = True, error: str | None = None) -> None:
    append_event(
        DEFAULT_AUDIT_PATH,
        actor="memory",
        event_type="memory.query",
        action=action,
        resource=str(DEFAULT_MEMORY_DB_PATH),
        risk_tier="T0",
        status="ALLOW" if success else "DENY",
        payload={
            "action": action,
            "query": redact_text(query),
            "result_count": result_count,
            "success": success,
            "error": redact_text(error),
        },
    )


@app.command("status")
def memory_status() -> None:
    init_memory_store(DEFAULT_MEMORY_DB_PATH)
    status = get_memory_status(db_path=DEFAULT_MEMORY_DB_PATH)
    console.print(f"indexed events: {status.indexed_event_count}")
    console.print(f"entities: {status.entity_count}")
    console.print(f"timeline entries: {status.timeline_count}")
    console.print(f"last indexed audit event: {status.last_indexed_audit_event}")
    console.print(f"schema version: {status.schema_version}")


@app.command("rebuild")
def memory_rebuild() -> None:
    status = rebuild_memory_from_audit(audit_path=DEFAULT_AUDIT_PATH, memory_db_path=DEFAULT_MEMORY_DB_PATH)
    console.print(f"indexed events: {status.indexed_event_count}")
    console.print(f"entities: {status.entity_count}")
    console.print(f"timeline entries: {status.timeline_count}")
    console.print(f"last indexed audit event: {status.last_indexed_audit_event}")


@app.command("recent")
def memory_recent(limit: int = typer.Option(20, "--limit")) -> None:
    entries = get_recent_activity(limit=limit, db_path=DEFAULT_MEMORY_DB_PATH)
    table = Table(show_header=True, header_style="bold")
    table.add_column("timestamp")
    table.add_column("title")
    table.add_column("description")
    for entry in entries:
        table.add_row(entry.timestamp, entry.title, entry.description)
    console.print(table)
    _audit_query("memory.recent", result_count=len(entries))


@app.command("timeline")
def memory_timeline(limit: int = typer.Option(20, "--limit")) -> None:
    entries = get_recent_activity(limit=limit, db_path=DEFAULT_MEMORY_DB_PATH)
    table = Table(show_header=True, header_style="bold")
    table.add_column("timestamp")
    table.add_column("category")
    table.add_column("description")
    for entry in entries:
        table.add_row(entry.timestamp, entry.category, entry.description)
    console.print(table)
    _audit_query("memory.timeline", result_count=len(entries))


@app.command("files")
def memory_files(limit: int = typer.Option(20, "--limit")) -> None:
    entities = get_recent_files(limit=limit, db_path=DEFAULT_MEMORY_DB_PATH)
    table = Table(show_header=True, header_style="bold")
    table.add_column("file")
    table.add_column("last_seen")
    table.add_column("count")
    for entity in entities:
        table.add_row(entity.name, entity.last_seen, str(entity.counters.get("seen", 0)))
    console.print(table)
    _audit_query("memory.files", result_count=len(entities))


@app.command("commands")
def memory_commands(limit: int = typer.Option(20, "--limit")) -> None:
    events = get_command_history(limit=limit, db_path=DEFAULT_MEMORY_DB_PATH)
    table = Table(show_header=True, header_style="bold")
    table.add_column("timestamp")
    table.add_column("command")
    table.add_column("status")
    for event in events:
        table.add_row(event.timestamp, event.command or "", "blocked" if event.blocked else "ok")
    console.print(table)
    _audit_query("memory.commands", result_count=len(events))


@app.command("blocked")
def memory_blocked(limit: int = typer.Option(20, "--limit")) -> None:
    events = get_blocked_events(limit=limit, db_path=DEFAULT_MEMORY_DB_PATH)
    table = Table(show_header=True, header_style="bold")
    table.add_column("timestamp")
    table.add_column("summary")
    for event in events:
        table.add_row(event.timestamp, event.summary)
    console.print(table)
    _audit_query("memory.blocked", result_count=len(events))


@app.command("failures")
def memory_failures(limit: int = typer.Option(20, "--limit")) -> None:
    events = get_failed_commands(limit=limit, db_path=DEFAULT_MEMORY_DB_PATH)
    table = Table(show_header=True, header_style="bold")
    table.add_column("timestamp")
    table.add_column("summary")
    for event in events:
        table.add_row(event.timestamp, event.summary)
    console.print(table)
    _audit_query("memory.failures", result_count=len(events))


def recall_cli(
    query: str = typer.Argument(..., help="Memory recall query."),
    limit: int = typer.Option(10, "--limit"),
) -> None:
    result = recall(query, limit=limit, db_path=DEFAULT_MEMORY_DB_PATH, audit_path=DEFAULT_AUDIT_PATH)
    console.print(result.summary)
