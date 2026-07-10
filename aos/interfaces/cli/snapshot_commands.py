"""Phase 1 snapshot CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aos.safety.snapshots import list_snapshots, restore_snapshot

app = typer.Typer(help="List and restore Phase 1 file snapshots.")
console = Console()


def _approved_roots() -> list[Path]:
    return [Path.cwd()]


@app.command("list")
def snapshot_list() -> None:
    """List stored snapshots."""
    table = Table(show_header=True, header_style="bold")
    for column in ("snapshot_id", "timestamp", "original_path", "size_bytes", "action"):
        table.add_column(column)
    for snapshot in list_snapshots():
        table.add_row(
            snapshot.snapshot_id,
            snapshot.timestamp,
            snapshot.original_path,
            str(snapshot.size_bytes),
            snapshot.created_by_action,
        )
    console.print(table)


@app.command("restore")
def snapshot_restore(
    snapshot_id: str,
    yes: bool = typer.Option(False, "--yes", help="Internal/test approval flag. Skips both T2 prompts."),
) -> None:
    """Restore a snapshot to its original approved path (T2, strong approval required)."""
    try:
        snapshot = next(item for item in list_snapshots() if item.snapshot_id == snapshot_id)
        console.print("[red]warning:[/red] this is a T2 high-risk action: it overwrites the original path")
        console.print(f"original path: {snapshot.original_path}")
        if not yes:
            if not typer.confirm("This is a T2 high-risk action. Continue?", default=False):
                raise typer.Abort()
            typed = typer.prompt("Type RESTORE to confirm")
            if typed != "RESTORE":
                console.print("[red]aborted:[/red] confirmation text did not match")
                raise typer.Abort()
        restored = restore_snapshot(snapshot_id, approved_roots=_approved_roots())
        console.print(f"[green]restored:[/green] {restored.original_path}")
    except StopIteration as exc:
        console.print(f"[red]failed:[/red] snapshot not found: {snapshot_id}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
