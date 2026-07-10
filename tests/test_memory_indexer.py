import json

from aos.memory.indexer import index_new_audit_events, rebuild_memory_from_audit
from aos.memory.store import list_entities, list_memory_events
from aos.safety.audit import append_event


def _seed_audit(audit_path):
    append_event(
        audit_path,
        actor="fs",
        event_type="fs.write.apply",
        action="fs.write.apply",
        resource="D:/project/notes.md",
        risk_tier="T1",
        status="ALLOW",
        payload={"path": "D:/project/notes.md", "sha256_after": "abc"},
    )
    append_event(
        audit_path,
        actor="fs",
        event_type="fs.edit.apply",
        action="fs.edit.apply",
        resource="D:/project/README.md",
        risk_tier="T1",
        status="ALLOW",
        payload={"path": "D:/project/README.md", "sha256_after": "def"},
    )
    append_event(
        audit_path,
        actor="run",
        event_type="run.apply",
        action="run.apply",
        resource="D:/project",
        risk_tier="T1",
        status="ALLOW",
        payload={"command_original": "pytest", "return_code": 1, "cwd": "D:/project"},
    )
    append_event(
        audit_path,
        actor="run",
        event_type="run.timeout",
        action="run.timeout",
        resource="D:/project",
        risk_tier="T1",
        status="ALLOW",
        payload={"command_original": "pytest", "timed_out": True, "cwd": "D:/project"},
    )
    append_event(
        audit_path,
        actor="run",
        event_type="run.blocked",
        action="run.blocked",
        resource="D:/project",
        risk_tier="T3",
        status="DENY",
        payload={"command_original": "sudo ls", "error": "blocked command: sudo", "cwd": "D:/project"},
    )
    append_event(
        audit_path,
        actor="agent",
        event_type="agent.ask",
        action="agent.ask",
        resource="D:/project",
        risk_tier="T0",
        status="ALLOW",
        payload={"user_message": "create notes.md token [REDACTED]", "reason": "request received"},
    )
    append_event(
        audit_path,
        actor="fs",
        event_type="fs.blocked",
        action="fs.blocked",
        resource="D:/project/.env",
        risk_tier="T3",
        status="DENY",
        payload={"path": ".env", "error": "blocked secret file pattern: .env"},
    )


def test_rebuild_from_audit_creates_memory_events(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed_audit(audit_path)

    status = rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)

    assert status.indexed_event_count >= 7
    assert list_memory_events(db_path=memory_db_path)


def test_index_new_audit_events_is_idempotent(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed_audit(audit_path)

    first = index_new_audit_events(audit_path=audit_path, memory_db_path=memory_db_path)
    second = index_new_audit_events(audit_path=audit_path, memory_db_path=memory_db_path)

    assert first.indexed_event_count == second.indexed_event_count


def test_fs_apply_events_create_file_activity(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed_audit(audit_path)

    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)
    file_entities = list_entities(db_path=memory_db_path, entity_type="File")

    names = {entity.name for entity in file_entities}
    assert "notes.md" in names
    assert "README.md" in names


def test_run_events_create_command_activity_and_blocked_events(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed_audit(audit_path)

    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)
    command_events = [event for event in list_memory_events(db_path=memory_db_path) if event.category == "command"]

    assert any(event.command == "pytest" for event in command_events)
    assert any(event.blocked for event in command_events)


def test_secrets_are_redacted_in_memory(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed_audit(audit_path)

    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)
    events = list_memory_events(db_path=memory_db_path)

    assert any(event.path == "[REDACTED_PATH]" for event in events if event.action == "fs.blocked")
    assert any("[REDACTED]" in (event.summary or "") for event in events if event.action == "agent.ask")

