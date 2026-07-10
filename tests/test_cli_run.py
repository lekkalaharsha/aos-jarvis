from typer.testing import CliRunner

from aos.interfaces.cli import main as cli_main
from aos.safety.commands import CommandPreview, CommandResult, EnvironmentSummary
from aos.safety.sandbox import SandboxMode

runner = CliRunner()


def _preview(*, allowed=True, requires_approval=False, risk_tier="T0", reason="ok"):
    return CommandPreview(
        command_original="python --version",
        argv=["python", "--version"],
        cwd="D:/repo",
        policy_category="ALLOW_READONLY" if allowed else "DENY",
        risk_tier=risk_tier,
        allowed=allowed,
        requires_approval=requires_approval,
        timeout_seconds=30,
        sandbox_mode=SandboxMode.BASIC,
        environment_summary=EnvironmentSummary(preserved_keys=["PATH"], removed_keys=["OPENAI_API_KEY"]),
        reason=reason,
    )


def _result():
    return CommandResult(
        command_original="python --version",
        argv=["python", "--version"],
        cwd="D:/repo",
        policy_category="ALLOW_READONLY",
        risk_tier="T0",
        allowed=True,
        approved=False,
        return_code=0,
        stdout="Python 3.12.7\n",
        stderr="",
        duration_ms=10,
        timed_out=False,
        output_truncated=False,
        audit_event_id=1,
        error=None,
    )


def test_cli_run_preview_works(monkeypatch):
    monkeypatch.setattr("aos.interfaces.cli.run_commands.preview_command", lambda *args, **kwargs: _preview())

    result = runner.invoke(cli_main.app, ["run", "--preview", "git status"])

    assert result.exit_code == 0
    assert "policy:" in result.output


def test_cli_run_python_version_works(monkeypatch):
    monkeypatch.setattr("aos.interfaces.cli.run_commands.preview_command", lambda *args, **kwargs: _preview())
    monkeypatch.setattr("aos.interfaces.cli.run_commands.run_command", lambda *args, **kwargs: _result())

    result = runner.invoke(cli_main.app, ["run", "python --version"])

    assert result.exit_code == 0
    assert "Python 3.12.7" in result.output


def test_cli_run_blocked_command_exits(monkeypatch):
    monkeypatch.setattr(
        "aos.interfaces.cli.run_commands.preview_command",
        lambda *args, **kwargs: _preview(allowed=False, reason="blocked command"),
    )

    result = runner.invoke(cli_main.app, ["run", "sudo ls"])

    assert result.exit_code == 1
    assert "blocked:" in result.output


def test_cli_run_pytest_yes_works(monkeypatch):
    monkeypatch.setattr(
        "aos.interfaces.cli.run_commands.preview_command",
        lambda *args, **kwargs: _preview(requires_approval=True, risk_tier="T1"),
    )
    monkeypatch.setattr("aos.interfaces.cli.run_commands.run_command", lambda *args, **kwargs: _result())

    result = runner.invoke(cli_main.app, ["run", "pytest", "--yes"])

    assert result.exit_code == 0
    assert "return code: 0" in result.output
