"""Phase 1 safe filesystem CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aos.safety.errors import ApprovalRequired, SafetyError
from aos.tools.fs_tools import (
    edit_file,
    list_dir,
    preview_edit,
    preview_write,
    read_file,
    search_files,
    write_file,
)

app = typer.Typer(help="Safe Phase 1 file tools.")
console = Console()


def _approved_roots() -> list[Path]:
    return [Path.cwd()]


def _confirm(prompt: str, yes: bool) -> None:
    if yes:
        return
    if not typer.confirm(prompt, default=False):
        raise typer.Abort()


@app.command("list")
def fs_list(path: str) -> None:
    """List an approved directory."""
    try:
        for item in list_dir(path, approved_roots=_approved_roots()):
            typer.echo(item)
    except Exception as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("read")
def fs_read(path: str) -> None:
    """Read an approved non-secret text file."""
    try:
        typer.echo(read_file(path, approved_roots=_approved_roots()))
    except Exception as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("search")
def fs_search(query: str, root: str = typer.Option(".", "--root")) -> None:
    """Search approved project text files."""
    try:
        table = Table(show_header=True, header_style="bold")
        table.add_column("path")
        table.add_column("line")
        table.add_column("text")
        for path, line_number, line in search_files(query, root=root, approved_roots=_approved_roots()):
            table.add_row(path, str(line_number), line)
        console.print(table)
    except Exception as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("write")
def fs_write(
    path: str,
    content: str = typer.Option(..., "--content"),
    yes: bool = typer.Option(False, "--yes", help="Internal/test approval flag."),
) -> None:
    """Write an approved file after explicit approval."""
    try:
        preview = preview_write(path, content, approved_roots=_approved_roots())
        console.print(f"risk: {preview.risk_tier.value}")
        console.print(f"target: {preview.path}")
        console.print(f"snapshot required: {'yes' if preview.existed else 'no'}")
        if preview.diff:
            console.print(preview.diff)
        _confirm("Apply write?", yes)
        result = write_file(path, content, approved=True, approved_roots=_approved_roots())
        if result.snapshot:
            console.print(f"snapshot: {result.snapshot.snapshot_id}")
        console.print(f"[green]wrote:[/green] {result.path}")
    except ApprovalRequired as exc:
        console.print(f"[red]approval required:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except SafetyError as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("edit")
def fs_edit(
    path: str,
    old: str = typer.Option(..., "--old"),
    new: str = typer.Option(..., "--new"),
    yes: bool = typer.Option(False, "--yes", help="Internal/test approval flag."),
) -> None:
    """Edit an approved text file after explicit approval."""
    try:
        preview = preview_edit(path, old, new, approved_roots=_approved_roots())
        console.print(f"risk: {preview.risk_tier.value}")
        console.print(f"target: {preview.path}")
        console.print("snapshot required: yes")
        console.print(preview.diff)
        _confirm("Apply edit?", yes)
        result = edit_file(path, old, new, approved=True, approved_roots=_approved_roots())
        console.print(f"snapshot: {result.snapshot.snapshot_id if result.snapshot else ''}")
        console.print(f"[green]edited:[/green] {result.path}")
    except ApprovalRequired as exc:
        console.print(f"[red]approval required:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except SafetyError as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
