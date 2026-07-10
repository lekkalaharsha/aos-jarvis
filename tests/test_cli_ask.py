from typer.testing import CliRunner

from aos.interfaces.cli import ask_commands
from aos.interfaces.cli import main as cli_main
from aos.agent.types import AgentResult, Intent, Observation, Plan, ToolCall

runner = CliRunner()


def _result(**overrides):
    base = AgentResult(
        user_message="x",
        intent=Intent.PROJECT_SUMMARY,
        plan=Plan(Intent.PROJECT_SUMMARY, "summary", [ToolCall("fs.read", {"path": "README.md"}, "T0", False)]),
        tool_calls=[ToolCall("fs.read", {"path": "README.md"}, "T0", False)],
        observations=[],
        final_answer="done",
        success=True,
        blocked=False,
        error=None,
        audit_event_id=1,
    )
    return AgentResult(**{**base.__dict__, **overrides})


def test_cli_ask_dry_run_works(monkeypatch):
    monkeypatch.setattr(ask_commands, "ask", lambda *args, **kwargs: _result(final_answer="Dry run only. No tools were executed."))
    result = runner.invoke(cli_main.app, ["ask", "run tests", "--dry-run"])

    assert result.exit_code == 0
    assert "intent: PROJECT_SUMMARY" in result.output


def test_cli_ask_summarize_project_works(monkeypatch):
    monkeypatch.setattr(ask_commands, "ask", lambda *args, **kwargs: _result(final_answer="summary"))
    result = runner.invoke(cli_main.app, ["ask", "summarize this project"])

    assert result.exit_code == 0
    assert "summary" in result.output


def test_cli_ask_run_tests_without_yes_does_not_run(monkeypatch):
    monkeypatch.setattr(
        ask_commands,
        "ask",
        lambda *args, **kwargs: _result(
            intent=Intent.RUN_TESTS,
            plan=Plan(Intent.RUN_TESTS, "run tests", [ToolCall("run.apply", {"command": "pytest", "cwd": "."}, "T1", True)]),
            tool_calls=[ToolCall("run.apply", {"command": "pytest", "cwd": "."}, "T1", True)],
            final_answer="Approval required. Re-run with --yes to execute run.apply.",
            success=False,
            blocked=True,
            audit_event_id=2,
        ),
    )
    result = runner.invoke(cli_main.app, ["ask", "run tests"])

    assert result.exit_code == 1
    assert "Approval required" in result.output


def test_cli_ask_read_secret_file_is_blocked(monkeypatch):
    monkeypatch.setattr(
        ask_commands,
        "ask",
        lambda *args, **kwargs: _result(
            intent=Intent.READ_FILE,
            final_answer="blocked: blocked secret file pattern: .env",
            success=False,
            blocked=True,
            audit_event_id=3,
        ),
    )
    result = runner.invoke(cli_main.app, ["ask", "read .env"])

    assert result.exit_code == 1
    assert "blocked" in result.output


def test_cli_ask_unsupported_request_returns_supported_actions(monkeypatch):
    monkeypatch.setattr(
        ask_commands,
        "ask",
        lambda *args, **kwargs: _result(intent=Intent.UNKNOWN, plan=Plan(Intent.UNKNOWN, "unsupported", []), tool_calls=[], final_answer="Supported requests: summarize this project, find TODOs"),
    )
    result = runner.invoke(cli_main.app, ["ask", "deploy this project"])

    assert result.exit_code == 0
    assert "Supported requests" in result.output

