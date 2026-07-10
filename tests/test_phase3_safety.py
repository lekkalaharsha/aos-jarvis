import json

import aos.agent.loop as agent_loop
import aos.tools.fs_tools as fs_tools
import aos.tools.shell_runner as shell_runner

from aos.agent.loop import ask
from aos.safety.audit import list_events, verify_chain


def test_agent_unknown_request_executes_nothing_and_audit_stays_valid(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(agent_loop, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(fs_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)

    result = ask("deploy this project", cwd=root)

    assert result.success
    assert not result.tool_calls
    assert verify_chain(audit_path).valid


def test_agent_blocked_secret_read_is_audited(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(agent_loop, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(fs_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)

    result = ask("read .env", cwd=root)

    assert result.blocked
    assert verify_chain(audit_path).valid


def test_agent_audit_redacts_secret_like_user_message(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(agent_loop, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(fs_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)

    ask("create notes.md token abc123", cwd=root)

    ask_event = next(event for event in list_events(audit_path) if event.event_type == "agent.ask")
    payload = json.loads(ask_event.payload_json)
    assert payload["user_message"] == "create notes.md token [REDACTED]"
