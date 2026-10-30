"""Phase 10 browser CLI. Hosts are accepted only at enrollment; a task-spec
is the only execution entrypoint -- there is no independent open/read/fill/
submit/close subcommand (contract Sec2a/Sec10).

Remediation (docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md Critical #3): the
earlier ``--yes`` flag, which bulk-minted every approval before launch and
could skip every individual confirmation, has been REMOVED. Every T2
operation -- including each cross-domain redirect hop encountered mid-task
-- is confirmed interactively, one at a time, immediately before it takes
effect, via the ``approval_callback`` this CLI passes into
``BrowserTool.execute``. There is no non-interactive bypass.
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from aos.browser.approval import mint_browser_approval
from aos.browser.domains import ApprovedDomainRegistry, DomainEnrollmentAuthority
from aos.browser.quarantine import QuarantineStore
from aos.browser.types import ApprovalRequest
from aos.safety.approved_projects import ApprovedProjectRegistry
from aos.safety.errors import PermissionBlocked
from aos.tools.browser import BrowserTool

app = typer.Typer(help="Bounded, per-task, permission-governed browser automation.")
domain_app = typer.Typer(help="Manage the enrolled-domain allowlist.")
app.add_typer(domain_app, name="domain")
quarantine_app = typer.Typer(help="Inspect and promote quarantined downloads.")
app.add_typer(quarantine_app, name="quarantine")


@domain_app.command("add")
def domain_add(
    host: str = typer.Argument(..., help="Exact host to enroll."),
    approve: bool = typer.Option(False, "--approve", help="Direct Human Owner confirmation for this exact host."),
    allow_http: bool = typer.Option(False, "--allow-http"),
    allow_ip_literal: bool = typer.Option(False, "--allow-ip-literal"),
) -> None:
    try:
        authority = DomainEnrollmentAuthority()
        approval = authority.approve_one(host, human_owner_confirmed=approve, origin="terminal", allow_http=allow_http, allow_ip_literal=allow_ip_literal)
        enrolled = ApprovedDomainRegistry().enroll(host, approval=approval)
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(enrolled.domain_id)


@domain_app.command("list")
def domain_list() -> None:
    try:
        for domain in ApprovedDomainRegistry().list():
            typer.echo(f"{domain.domain_id}\t{'revoked' if domain.revoked else 'active'}\t{domain.host}")
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@domain_app.command("revoke")
def domain_revoke(domain_id: str = typer.Argument(...)) -> None:
    try:
        ApprovedDomainRegistry().revoke(domain_id)
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"revoked {domain_id}")


def _describe_request(request: ApprovalRequest) -> str:
    line = f"  {request.operation}"
    if request.host:
        line += f" host={request.host}"
    if request.path_present:
        line += " (url has a path)"
    if request.role and request.accessible_name:
        line += f" field={request.role}:{request.accessible_name!r}"
    if request.field_classification:
        line += f" classification={request.field_classification}"
    if request.redirect_to_host:
        line += f" redirect {request.redirect_from_host} -> {request.redirect_to_host}"
    if request.file_identity_hash:
        line += f" file_hash={request.file_identity_hash[:12]}"
    return line


@app.command("task")
def task(
    spec_file: Path = typer.Argument(..., help="Path to a JSON task-spec file (see docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md Sec10)."),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Run one bounded browser task: validate -> launch -> run (each T2
    action individually confirmed as it happens) -> teardown, all within
    this single invocation. No session/task ID this command prints is
    usable by any later invocation. There is no bulk/non-interactive
    approval bypass (contract Sec3/Sec7a)."""
    try:
        raw = json.loads(spec_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        typer.echo("browser task spec could not be read", err=True)
        raise typer.Exit(code=1) from exc

    tool = BrowserTool()
    preview_args = {**raw, "origin": "terminal"}
    try:
        preview_spec = tool._build_spec(preview_args)  # noqa: SLF001 -- CLI needs the same task_id used through the run
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    dry_result = tool.runner.dry_run(preview_spec)
    typer.echo(f"task preview: task_id={dry_result.task_id} domain_id={dry_result.domain_id} operations={len(preview_spec.operations)}")
    if dry_run:
        typer.echo(f"browser task {dry_result.state.value}")
        if dry_result.state.value != "validated":
            raise typer.Exit(code=1)
        return

    def approval_callback(request: ApprovalRequest) -> bool:
        typer.echo(_describe_request(request))
        return typer.confirm(f"  Approve this exact {request.operation} action?", default=False)

    args = {**raw, "origin": "terminal", "task_id": dry_result.task_id}
    result = tool.execute(args, approval_callback=approval_callback)
    typer.echo(result.output)
    if not result.ok:
        raise typer.Exit(code=1)


@quarantine_app.command("list")
def quarantine_list() -> None:
    store = QuarantineStore()
    manifest = store._read_manifest()  # noqa: SLF001 -- CLI-only, read-only listing
    for file_id, item in manifest["files"].items():
        typer.echo(f"{file_id}\t{item['filename']}\t{item['size_bytes']}B\t{item['sha256'][:12]}")


@quarantine_app.command("cleanup")
def quarantine_cleanup() -> None:
    expired = QuarantineStore().sweep_expired()
    typer.echo(f"removed {len(expired)} expired quarantine entr{'y' if len(expired) == 1 else 'ies'}")


@quarantine_app.command("promote")
def quarantine_promote(
    file_id: str = typer.Argument(...),
    project_id: str = typer.Argument(..., help="Enrolled project ID (see `aos project list` / approved_projects registry) to promote into."),
    relative_subpath: str = typer.Option(".", "--subpath", help="Relative subpath inside the enrolled project root -- must not escape it."),
    approve: bool = typer.Option(False, "--approve", help="Explicit Human Owner confirmation for this exact promotion."),
) -> None:
    """Contract Sec8: promotion is a separate exact-file T2 operation from
    the download itself, and now requires its own fresh, exact-bound
    :class:`BrowserApproval` at the store boundary -- the destination is an
    ENROLLED project ID, never an arbitrary caller-supplied path
    (remediation Critical #4)."""
    store = QuarantineStore()
    try:
        record = store.get(file_id)
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"promotion preview: file={record.filename} sha256={record.sha256} size={record.size_bytes}B -> project={project_id} subpath={relative_subpath}")
    if not approve and not typer.confirm("Promote this exact file into the enrolled project?", default=False):
        raise typer.Exit(code=1)
    try:
        project_registry = ApprovedProjectRegistry()
        project_root = project_registry.resolve(project_id)
        relative = Path(relative_subpath)
        if any(part in {"..", ""} for part in relative.parts) or relative.is_absolute():
            raise PermissionBlocked("promotion subpath must be a relative path with no traversal")
        dest = (project_root / relative_subpath / record.filename).resolve(strict=False)
        file_identity = store.promotion_file_identity(
            record,
            project_id=project_id,
            project_root=project_root,
            relative_subpath=relative_subpath,
            destination_path=dest,
        )
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    approval = mint_browser_approval(
        operation="promote", task_id=f"promotion-{file_id}", domain_id="",
        file_identity=file_identity, human_owner_confirmed=True, origin="terminal",
    )
    try:
        dest = store.promote(
            file_id,
            project_id=project_id,
            relative_subpath=relative_subpath,
            approval=approval,
            project_registry=project_registry,
            approvals_consumed_path=store.root / ".promotion_approvals_consumed.json",
        )
    except PermissionBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(str(dest))
