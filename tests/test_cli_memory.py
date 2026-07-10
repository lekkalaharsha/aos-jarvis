from typer.testing import CliRunner

import aos.interfaces.cli.memory_commands as memory_commands
from aos.interfaces.cli import main as cli_main
from aos.safety.audit import append_event

runner = CliRunner()


def _seed(audit_path):
    append_event(audit_path, "fs", "fs.write.apply", "fs.write.apply", "D:/project/a.txt", "T1", "ALLOW", {"path": "D:/project/a.txt"})
    append_event(audit_path, "run", "run.apply", "run.apply", "D:/project", "T1", "ALLOW", {"command_original": "pytest", "return_code": 1, "cwd": "D:/project"})


def test_cli_memory_status_rebuild_recent_commands_failures_and_recall(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.db"
    memory_db_path = tmp_path / "memory.db"
    _seed(audit_path)
    monkeypatch.setattr(memory_commands, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(memory_commands, "DEFAULT_MEMORY_DB_PATH", memory_db_path)

    assert runner.invoke(cli_main.app, ["memory", "status"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["memory", "rebuild"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["memory", "recent"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["memory", "commands"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["memory", "failures"]).exit_code == 0
    recall_result = runner.invoke(cli_main.app, ["recall", "what did I work on recently"])
    assert recall_result.exit_code == 0
    assert recall_result.output.strip()

