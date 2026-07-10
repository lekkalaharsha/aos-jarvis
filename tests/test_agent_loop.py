import aos.agent.loop as agent_loop
import aos.tools.fs_tools as fs_tools
import aos.tools.shell_runner as shell_runner
import pytest

from aos.agent.loop import ask
from aos.safety.audit import list_events


@pytest.fixture()
def agent_env(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(agent_loop, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(fs_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)
    return root, audit_path


def test_dry_run_executes_nothing(agent_env, monkeypatch):
    root, _ = agent_env

    def _boom(*args, **kwargs):
        raise AssertionError("safe runner preview/apply should not be called during dry run")

    monkeypatch.setattr("aos.agent.tool_registry.run_command", _boom)
    monkeypatch.setattr("aos.agent.tool_registry.preview_command", _boom)
    monkeypatch.setattr("aos.agent.tool_registry.preview_write", _boom)
    result = ask("run tests", cwd=root, dry_run=True)

    assert result.success
    assert "Dry run only" in result.final_answer


def test_unknown_intent_executes_nothing(agent_env, monkeypatch):
    root, _ = agent_env

    def _boom(*args, **kwargs):
        raise AssertionError("tool execution should not happen")

    monkeypatch.setattr("aos.agent.tool_registry.read_file", _boom)
    result = ask("deploy this project", cwd=root)

    assert result.success
    assert result.intent.value == "UNKNOWN"


def test_summarize_project_reads_safe_files_only(agent_env):
    root, _ = agent_env
    (root / "README.md").write_text("# AOS-Jarvis\nLocal-first system control.\n", encoding="utf-8")
    result = ask("summarize this project", cwd=root)

    assert result.success
    assert "AOS-Jarvis" in result.final_answer


def test_find_todos_searches_safe_files_only(agent_env):
    root, _ = agent_env
    (root / "todo.txt").write_text("TODO: test this\n", encoding="utf-8")
    result = ask("find TODOs", cwd=root)

    assert result.success
    assert "todo.txt:1" in result.final_answer


def test_run_tests_requires_approval(agent_env):
    root, _ = agent_env
    result = ask("run tests", cwd=root, yes=False)

    assert result.blocked
    assert "Approval required" in result.final_answer


def test_run_tests_with_yes_executes_via_safe_shell_runner(agent_env, monkeypatch):
    root, _ = agent_env

    class _Result:
        command_original = "pytest"
        return_code = 0
        stdout = "2 passed"
        stderr = ""
        timed_out = False
        error = None

    monkeypatch.setattr("aos.agent.tool_registry.run_command", lambda *args, **kwargs: _Result())
    monkeypatch.setattr(
        "aos.agent.tool_registry.preview_command",
        lambda *args, **kwargs: type(
            "Preview",
            (),
            {
                "allowed": True,
                "requires_approval": True,
                "command_original": "pytest",
                "reason": "command allowed by policy",
            },
        )(),
    )
    result = ask("run tests", cwd=root, yes=True)

    assert result.success
    assert "2 passed" in result.final_answer


def test_git_status_executes_via_safe_shell_runner(agent_env, monkeypatch):
    root, _ = agent_env

    class _Result:
        command_original = "git status"
        return_code = 0
        stdout = "On branch main"
        stderr = ""
        timed_out = False
        error = None

    monkeypatch.setattr("aos.agent.tool_registry.run_command", lambda *args, **kwargs: _Result())
    monkeypatch.setattr(
        "aos.agent.tool_registry.preview_command",
        lambda *args, **kwargs: type(
            "Preview",
            (),
            {
                "allowed": True,
                "requires_approval": False,
                "command_original": "git status",
                "reason": "command allowed by policy",
            },
        )(),
    )
    result = ask("show git status", cwd=root)

    assert result.success
    assert "On branch main" in result.final_answer


def test_read_secret_file_is_blocked(agent_env):
    root, _ = agent_env
    (root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    result = ask("read .env", cwd=root)

    assert result.blocked


def test_read_traversal_to_ssh_key_is_blocked(agent_env):
    root, _ = agent_env
    result = ask("read ../../.ssh/id_rsa", cwd=root)

    assert result.blocked


def test_create_notes_requires_approval(agent_env):
    root, _ = agent_env
    result = ask("create notes.md", cwd=root)

    assert result.blocked
    assert not (root / "notes.md").exists()


def test_create_notes_with_yes_writes_via_safe_fs_tool(agent_env):
    root, _ = agent_env
    result = ask("create notes.md", cwd=root, yes=True)

    assert result.success
    assert (root / "notes.md").exists()


def test_denied_command_cannot_run_even_with_yes(agent_env):
    root, _ = agent_env
    result = ask("show git status", cwd="/etc", yes=True)

    assert result.blocked


def test_agent_audit_events_are_written(agent_env):
    root, audit_path = agent_env
    (root / "README.md").write_text("# AOS\n", encoding="utf-8")
    ask("summarize this project", cwd=root)

    event_types = [event.event_type for event in list_events(audit_path)]
    assert "agent.ask" in event_types
    assert "agent.plan" in event_types
    assert "agent.result" in event_types
