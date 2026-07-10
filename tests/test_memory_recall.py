from aos.memory.indexer import rebuild_memory_from_audit
from aos.memory.recall import recall
from aos.safety.audit import append_event


def _seed(audit_path):
    append_event(audit_path, "fs", "fs.edit.apply", "fs.edit.apply", "D:/project/README.md", "T1", "ALLOW", {"path": "D:/project/README.md"})
    append_event(audit_path, "fs", "fs.read", "fs.read", "D:/project/README.md", "T0", "ALLOW", {"path": "D:/project/README.md"})
    append_event(audit_path, "run", "run.apply", "run.apply", "D:/project", "T1", "ALLOW", {"command_original": "pytest", "return_code": 1, "cwd": "D:/project"})
    append_event(audit_path, "run", "run.blocked", "run.blocked", "D:/project", "T3", "DENY", {"command_original": "sudo ls", "cwd": "D:/project"})


def test_recent_work_query_works(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed(audit_path)
    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)

    result = recall("what did I work on recently", db_path=memory_db_path, audit_path=audit_path)
    assert "fs.edit.apply" in result.summary or "run.apply" in result.summary


def test_edited_today_commands_failures_and_blocked_queries_work(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed(audit_path)
    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)

    edited_today = recall("what did I edit today", db_path=memory_db_path, audit_path=audit_path).summary
    assert "fs.edit.apply" in edited_today
    assert "fs.read" not in edited_today
    changed_files = recall("what files changed", db_path=memory_db_path, audit_path=audit_path).summary
    assert "README.md" in changed_files
    assert "pytest" in recall("what commands did I run", db_path=memory_db_path, audit_path=audit_path).summary
    assert "failed" in recall("what failed recently", db_path=memory_db_path, audit_path=audit_path).summary.lower() or "run.apply" in recall("what failed recently", db_path=memory_db_path, audit_path=audit_path).summary
    assert "sudo" in recall("show blocked actions", db_path=memory_db_path, audit_path=audit_path).summary


def test_unknown_query_returns_supported_options_and_no_data_is_honest(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)

    unknown = recall("banana history", db_path=memory_db_path, audit_path=audit_path)
    empty = recall("what did I work on recently", db_path=memory_db_path, audit_path=audit_path)

    assert "Supported recall queries" in unknown.summary
    assert "No matching" in empty.summary or "No recent" in empty.summary or "No matching memory entries" in empty.summary
