from typer.testing import CliRunner

from aos.interfaces.cli import main as cli_main
from aos.interfaces.cli import model_commands
from aos.model.config import ModelConfig

runner = CliRunner()


def test_aos_model_list_works(monkeypatch):
    monkeypatch.setattr(model_commands, "_load", lambda: ModelConfig())
    result = runner.invoke(cli_main.app, ["model", "list"])
    assert result.exit_code == 0
    assert "local" in result.output
    assert "cloud" in result.output


def test_aos_model_show_works(monkeypatch):
    monkeypatch.setattr(model_commands, "_load", lambda: ModelConfig())
    result = runner.invoke(cli_main.app, ["model", "show"])
    assert result.exit_code == 0
    assert "allow_cloud: False" in result.output


def test_aos_model_doctor_warns_cloud_disabled(monkeypatch):
    monkeypatch.setattr(model_commands, "_load", lambda: ModelConfig())
    result = runner.invoke(cli_main.app, ["model", "doctor"])
    assert result.exit_code == 0
    assert "cloud disabled" in result.output


def test_aos_model_test_dry_run_works(monkeypatch):
    monkeypatch.setattr(model_commands, "_load", lambda: ModelConfig())
    result = runner.invoke(cli_main.app, ["model", "test", "--model", "local"])
    assert result.exit_code == 0
    assert "dry-run ok" in result.output


def test_set_default_cloud_blocked_when_cloud_disabled(monkeypatch):
    monkeypatch.setattr(model_commands, "_load", lambda: ModelConfig())
    result = runner.invoke(cli_main.app, ["model", "set-default", "cloud"])
    assert result.exit_code == 1
    assert "blocked" in result.output


def test_aos_ask_model_option_passed(monkeypatch):
    captured = {}

    def fake_ask(*args, **kwargs):
        captured.update(kwargs)
        from aos.agent.types import AgentResult, Intent, Plan

        return AgentResult("x", Intent.UNKNOWN, Plan(Intent.UNKNOWN, "x", []), [], [], "ok", True, False, None, 1)

    from aos.interfaces.cli import ask_commands

    monkeypatch.setattr(ask_commands, "ask", fake_ask)
    result = runner.invoke(cli_main.app, ["ask", "--model", "local", "hello"])
    assert result.exit_code == 0
    assert captured["model"] == "local"
