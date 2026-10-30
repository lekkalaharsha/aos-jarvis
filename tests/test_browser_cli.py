from __future__ import annotations

import json

from typer.testing import CliRunner

from aos.interfaces.cli import browser_commands
from aos.interfaces.cli.main import app
from aos.browser.domains import ApprovedDomainRegistry
from aos.browser.quarantine import QuarantineStore
from aos.safety.approved_projects import ApprovedProjectRegistry, HumanOwnerEnrollmentAuthority
from aos.tools.browser import BrowserTool

runner = CliRunner()


def _patch_data_dir(monkeypatch, tmp_path):
    """Mirrors the existing Phase 9 CLI test convention (see
    tests/test_workspace_cli.py): DATA_DIR is resolved once at import time,
    so tests must monkeypatch the CLI module's imported names directly
    rather than the AOS_DATA_DIR environment variable, which has no effect
    after import."""
    registry = ApprovedDomainRegistry(tmp_path / "domains.json")
    project_registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    quarantine = QuarantineStore(tmp_path / "quarantine")
    monkeypatch.setattr(browser_commands, "ApprovedDomainRegistry", lambda: registry)
    monkeypatch.setattr(browser_commands, "ApprovedProjectRegistry", lambda: project_registry)
    monkeypatch.setattr(browser_commands, "QuarantineStore", lambda: quarantine)
    monkeypatch.setattr(browser_commands, "BrowserTool", lambda: BrowserTool(registry=registry, audit_path=tmp_path / "audit.db", quarantine=quarantine))
    return registry, quarantine, project_registry


def test_browser_help_exits_zero():
    result = runner.invoke(app, ["browser", "--help"])
    assert result.exit_code == 0
    assert "task" in result.output


def test_browser_task_help_has_no_yes_flag():
    # Remediation Critical #3: --yes was removed entirely -- there is no
    # non-interactive bulk-approval bypass left in the CLI.
    result = runner.invoke(app, ["browser", "task", "--help"])
    assert result.exit_code == 0
    assert "--yes" not in result.output


def test_browser_domain_help_exits_zero():
    result = runner.invoke(app, ["browser", "domain", "--help"])
    assert result.exit_code == 0


def test_browser_domain_add_requires_approve_flag(tmp_path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    result = runner.invoke(app, ["browser", "domain", "add", "example.com"])
    assert result.exit_code == 1


def test_browser_domain_add_list_revoke(tmp_path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    add_result = runner.invoke(app, ["browser", "domain", "add", "example.com", "--approve"])
    assert add_result.exit_code == 0
    domain_id = add_result.output.strip()

    list_result = runner.invoke(app, ["browser", "domain", "list"])
    assert domain_id in list_result.output

    revoke_result = runner.invoke(app, ["browser", "domain", "revoke", domain_id])
    assert revoke_result.exit_code == 0


def test_browser_task_dry_run(tmp_path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    add_result = runner.invoke(app, ["browser", "domain", "add", "example.com", "--approve"])
    domain_id = add_result.output.strip()

    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps({"domain_id": domain_id, "operations": [{"operation": "read"}]}))

    result = runner.invoke(app, ["browser", "task", str(spec_file), "--dry-run"])
    assert result.exit_code == 0
    assert "task_id=" in result.output


def test_browser_task_unknown_domain_denied(tmp_path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps({"domain_id": "nonexistent", "operations": [{"operation": "read"}]}))
    result = runner.invoke(app, ["browser", "task", str(spec_file), "--dry-run"])
    assert result.exit_code == 1


def test_browser_task_prompts_per_operation_and_denies_on_no(tmp_path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    add_result = runner.invoke(app, ["browser", "domain", "add", "example.com", "--approve"])
    domain_id = add_result.output.strip()
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps({"domain_id": domain_id, "operations": [{"operation": "navigate", "url": "https://example.com/"}]}))
    # Declining the single interactive per-operation prompt must deny the
    # whole task -- there is no way to skip this prompt from the CLI.
    result = runner.invoke(app, ["browser", "task", str(spec_file)], input="n\n")
    assert result.exit_code == 1


def test_browser_quarantine_list_and_cleanup_empty(tmp_path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    list_result = runner.invoke(app, ["browser", "quarantine", "list"])
    assert list_result.exit_code == 0
    cleanup_result = runner.invoke(app, ["browser", "quarantine", "cleanup"])
    assert cleanup_result.exit_code == 0
    assert "removed 0" in cleanup_result.output


def test_browser_quarantine_promote_requires_enrolled_project(tmp_path, monkeypatch):
    registry, quarantine, project_registry = _patch_data_dir(monkeypatch, tmp_path)
    file_id_result = quarantine.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    result = runner.invoke(app, ["browser", "quarantine", "promote", file_id_result.file_id, "not-a-real-project", "--approve"])
    assert result.exit_code == 1


def test_browser_quarantine_promote_success_uses_exact_destination_binding(tmp_path, monkeypatch):
    registry, quarantine, project_registry = _patch_data_dir(monkeypatch, tmp_path)
    project_root = tmp_path / "project"
    project_root.mkdir()
    approval = HumanOwnerEnrollmentAuthority().approve_one(project_root, human_owner_confirmed=True, origin="terminal")
    project = project_registry.enroll(project_root, approval=approval)
    file_id_result = quarantine.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    result = runner.invoke(app, ["browser", "quarantine", "promote", file_id_result.file_id, project.project_id, "--approve"])
    assert result.exit_code == 0
    assert (project_root / "notes.txt").read_bytes() == b"hello"
