import aos.tools.shell_runner as shell_runner
from aos.safety.audit import list_events, verify_chain
from aos.tools.shell_runner import preview_command, run_command
import pytest


def test_run_preview_blocked_command_is_audited(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)

    preview = preview_command("sudo ls", cwd=root, approved_roots=[root])

    assert not preview.allowed
    events = list_events(audit_path)
    assert any(event.event_type == "run.preview" for event in events)
    assert verify_chain(audit_path).valid


def test_run_blocked_command_emits_blocked_event(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)

    with pytest.raises(Exception):
        run_command("sudo ls", cwd=root, approved_roots=[root], yes=True)

    events = list_events(audit_path)
    assert any(event.event_type == "run.blocked" for event in events)
    assert verify_chain(audit_path).valid


def test_run_preview_outside_approved_root_is_blocked(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)

    preview = preview_command("git status", cwd=tmp_path.parent, approved_roots=[root])

    assert not preview.allowed
    assert preview.policy_category == "DENY"
