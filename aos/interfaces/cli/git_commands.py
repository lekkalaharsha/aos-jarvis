from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aos.project.git_tools import draft_commit_message, git_branch, git_diff, git_log, git_status
from aos.project.project_summary import summarize_project_changes
from aos.safety.errors import ProjectToolError, SafetyError
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import RiskTier

app = typer.Typer(help="Safe Phase 5 git and project assistant commands.")
console = Console()


def _safe_cwd(cwd: str) -> str:
    return str(PermissionEngine(approved_roots=[Path.cwd()]).require_path(cwd, "run.command", RiskTier.T0))


@app.command("status")
def git_status_cli(cwd: str = typer.Option(".", "--cwd")) -> None:
    try:
        status = git_status(_safe_cwd(cwd))
        console.print(f"branch: {status.branch}")
        console.print(f"clean: {'yes' if status.clean else 'no'}")
        if status.changed_files:
            table = Table(show_header=True, header_style="bold")
            table.add_column("path")
            table.add_column("staged")
            table.add_column("unstaged")
            table.add_column("untracked")
            for item in status.changed_files:
                table.add_row(item.path, "yes" if item.staged else "no", "yes" if item.unstaged else "no", "yes" if item.untracked else "no")
            console.print(table)
    except (ProjectToolError, SafetyError) as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("diff")
def git_diff_cli(
    cwd: str = typer.Option(".", "--cwd"),
    stat: bool = typer.Option(False, "--stat", help="Show diff stat only."),
) -> None:
    try:
        diff = git_diff(_safe_cwd(cwd), stat=stat)
        if stat:
            console.print(f"files changed: {diff.files_changed}")
            console.print(f"insertions: {diff.insertions}")
            console.print(f"deletions: {diff.deletions}")
            if diff.changed_files:
                for path in diff.changed_files:
                    console.print(path)
        else:
            console.print(diff.raw_text or "No diff output.")
    except (ProjectToolError, SafetyError) as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("log")
def git_log_cli(
    cwd: str = typer.Option(".", "--cwd"),
    limit: int = typer.Option(10, "--limit"),
) -> None:
    try:
        commits = git_log(_safe_cwd(cwd), limit=limit)
        for commit in commits:
            console.print(f"{commit.commit_hash} {commit.title}")
    except (ProjectToolError, SafetyError) as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("branch")
def git_branch_cli(cwd: str = typer.Option(".", "--cwd")) -> None:
    try:
        console.print(git_branch(_safe_cwd(cwd)).name)
    except (ProjectToolError, SafetyError) as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("summarize")
def git_summarize_cli(cwd: str = typer.Option(".", "--cwd")) -> None:
    try:
        summary = summarize_project_changes(_safe_cwd(cwd))
        console.print(summary.summary)
    except (ProjectToolError, SafetyError) as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("draft-commit")
def git_draft_commit_cli(cwd: str = typer.Option(".", "--cwd")) -> None:
    try:
        draft = draft_commit_message(_safe_cwd(cwd))
        console.print(draft.text)
    except (ProjectToolError, SafetyError) as exc:
        console.print(f"[red]blocked:[/red] {exc}")
        raise typer.Exit(code=1) from exc
