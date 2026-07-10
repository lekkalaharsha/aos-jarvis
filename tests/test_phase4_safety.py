import aos.agent.loop as agent_loop
import aos.interfaces.cli.memory_commands as memory_commands
import aos.tools.fs_tools as fs_tools
import aos.tools.shell_runner as shell_runner

from aos.agent.loop import ask
from aos.memory.indexer import rebuild_memory_from_audit
from aos.safety.audit import append_event, verify_chain


def test_memory_rebuild_is_idempotent_and_audit_stays_valid(tmp_path):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    append_event(audit_path, "fs", "fs.write.apply", "fs.write.apply", "D:/project/a.txt", "T1", "ALLOW", {"path": "D:/project/a.txt"})

    first = rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)
    second = rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)

    assert first.indexed_event_count == second.indexed_event_count
    assert verify_chain(audit_path).valid


def test_agent_memory_recall_uses_memory_only(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    root = tmp_path / "project"
    root.mkdir()
    append_event(audit_path, "fs", "fs.write.apply", "fs.write.apply", str(root / "a.txt"), "T1", "ALLOW", {"path": str(root / "a.txt")})
    rebuild_memory_from_audit(audit_path=audit_path, memory_db_path=memory_db_path)
    monkeypatch.setattr(agent_loop, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(fs_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr("aos.agent.tool_registry.DEFAULT_AUDIT_PATH", audit_path, raising=False)
    monkeypatch.setattr("aos.agent.tool_registry.read_file", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fs.read should not run")))
    monkeypatch.setattr("aos.agent.tool_registry.run_command", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("run_command should not run")))
    monkeypatch.setattr("aos.agent.tool_registry.DEFAULT_MEMORY_DB_PATH", memory_db_path, raising=False)

    result = ask("what did I work on recently", cwd=root)
    assert result.success


def test_unknown_memory_query_executes_no_unsafe_action(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(agent_loop, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr("aos.agent.tool_registry.read_file", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fs.read should not run")))
    monkeypatch.setattr("aos.agent.tool_registry.run_command", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("run_command should not run")))
    result = ask("what do bananas mean in memory", cwd=root)

    assert result.intent.value == "UNKNOWN"
