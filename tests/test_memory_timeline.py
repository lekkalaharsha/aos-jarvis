from aos.memory.indexer import rebuild_memory_from_audit
from aos.memory.timeline import (
    get_blocked_events,
    get_command_history,
    get_failed_commands,
    get_file_activity,
    get_recent_activity,
)
from aos.safety.audit import append_event


def _seed(audit_path):
    append_event(audit_path, "fs", "fs.write.apply", "fs.write.apply", "D:/project/a.txt", "T1", "ALLOW", {"path": "D:/project/a.txt"})
    append_event(audit_path, "run", "run.apply", "run.apply", "D:/project", "T1", "ALLOW", {"command_original": "pytest", "return_code": 0, "cwd": "D:/project"})
    append_event(audit_path, "run", "run.blocked", "run.blocked", "D:/project", "T3", "DENY", {"command_original": "sudo ls", "cwd": "D:/project"})
    append_event(audit_path, "run", "run.timeout", "run.timeout", "D:/project", "T1", "ALLOW", {"command_original": "pytest", "timed_out": True, "cwd": "D:/project"})


def test_recent_activity_returns_newest_entries(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed(audit_path)
    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)

    entries = get_recent_activity(db_path=memory_db_path)
    assert entries
    assert entries[0].source_event_id > entries[-1].source_event_id


def test_file_activity_returns_matching_path(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed(audit_path)
    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)

    events = get_file_activity("D:/project/a.txt", db_path=memory_db_path)
    assert len(events) == 1


def test_command_history_blocked_and_failed_queries_work(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed(audit_path)
    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)

    assert get_command_history(db_path=memory_db_path)
    assert get_blocked_events(db_path=memory_db_path)
    assert get_failed_commands(db_path=memory_db_path)

