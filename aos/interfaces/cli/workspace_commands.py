"""Phase 9 workspace CLI. Project paths are accepted only at enrollment."""
from __future__ import annotations

import typer

from aos.safety.approved_projects import (
    ApprovedProjectRegistry,
    HumanOwnerEnrollmentAuthority,
)
from aos.safety.dev_server import canonical_project_digest, mint_dev_server_approval
from aos.safety.errors import PermissionBlocked
from aos.tools.workspace import CTRL_C_STOP_GUIDANCE, CTRL_C_STOP_METHOD
from aos.tools.workspace import WorkspaceTool

app = typer.Typer(help="Safely control explicitly enrolled local workspaces.")


def _tool() -> WorkspaceTool:
    return WorkspaceTool(registry=ApprovedProjectRegistry())


def _run(operation: str, project_id: str | None = None, **args: object) -> None:
    result = _tool().execute({"operation": operation, "project_id": project_id, **args})
    typer.echo(result.output)
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("enroll")
def enroll(project: str = typer.Argument(..., help="Exact existing project directory."), approve: bool = typer.Option(False, "--approve", help="Direct Human Owner confirmation for this exact path.")) -> None:
    """Enroll one exact project; this never trusts cwd or a parent directory."""
    try:
        authority = HumanOwnerEnrollmentAuthority()
        approval = authority.approve_one(project, human_owner_confirmed=approve, origin="terminal")
        enrolled = ApprovedProjectRegistry().enroll(project, approval=approval)
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(enrolled.project_id)


@app.command("list")
def list_projects() -> None:
    """List registry membership only; this grants no new approval."""
    try:
        for project in ApprovedProjectRegistry().list():
            typer.echo(f"{project.project_id}\t{'revoked' if project.revoked else 'active'}\t{project.path}")
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command("status")
def status() -> None:
    _run("status")


@app.command("open")
def open_project(project_id: str = typer.Argument(..., help="Active enrolled project ID.")) -> None:
    _run("open", project_id)


@app.command("editor")
def editor(project_id: str = typer.Argument(...), editor: str = typer.Option("vscode", "--editor")) -> None:
    _run("editor", project_id, editor=editor)


@app.command("terminal")
def terminal(project_id: str = typer.Argument(...), terminal: str = typer.Option("default", "--terminal")) -> None:
    _run("terminal", project_id, terminal=terminal)


@app.command("save")
def save(project_id: str = typer.Argument(...), editor: str = typer.Option("vscode", "--editor"), terminal: str = typer.Option("default", "--terminal")) -> None:
    _run("save", project_id, editor=editor, terminal=terminal)


@app.command("restore")
def restore() -> None:
    _run("restore")


@app.command("serve")
def serve(
    project_id: str = typer.Argument(...),
    port: int = typer.Option(8000, "--port"),
    approve: bool = typer.Option(False, "--approve", help="Explicit Human Owner confirmation for this previewed request."),
) -> None:
    """Start a foreground loopback dev server after explicit confirmation."""
    registry = ApprovedProjectRegistry()
    try:
        resolved_project = registry.resolve(project_id)
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"workspace serve preview: project={project_id} profile=python-http port={port}")
    typer.echo(CTRL_C_STOP_GUIDANCE)
    typer.echo(f"stop method: {CTRL_C_STOP_METHOD}")
    if not approve and not typer.confirm("Start this foreground dev server?", default=False):
        raise typer.Exit(code=1)
    approval = mint_dev_server_approval(
        project_id=project_id,
        canonical_project_id=canonical_project_digest(resolved_project),
        profile="python-http",
        port=port,
        human_owner_confirmed=True,
        origin="terminal",
    )
    _run("serve", project_id, approval=approval, port=port)
