import subprocess
from pathlib import Path
import os

import aos.project.git_tools as git_tools
import aos.project.project_summary as project_summary
import aos.safety.commands as safety_commands
import aos.tools.shell_runner as shell_runner
from typer.testing import CliRunner

from aos.interfaces.cli import main as cli_main

runner = CliRunner()


def _git_env(base_dir: Path | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    if base_dir is not None:
        env["GIT_CEILING_DIRECTORIES"] = str(base_dir.resolve())
    return env


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_git_env(cwd.parent))


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "."], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    _run(["git", "add", "README.md"], repo)
    _run(["git", "commit", "-m", "feat: initial commit"], repo)
    return repo


def test_cli_git_commands_work(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(git_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(project_summary, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)
    sanitized_env = _git_env(tmp_path)
    summary = safety_commands.EnvironmentSummary(
        preserved_keys=["GIT_CEILING_DIRECTORIES", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"],
        removed_keys=[],
    )
    monkeypatch.setattr(safety_commands, "sanitize_environment", lambda env=None: (dict(sanitized_env), summary))
    monkeypatch.setattr(shell_runner, "sanitize_environment", lambda env=None: (dict(sanitized_env), summary))
    monkeypatch.chdir(repo)
    assert runner.invoke(cli_main.app, ["git", "status"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["git", "diff", "--stat"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["git", "log", "--limit", "5"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["git", "branch"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["git", "summarize"]).exit_code == 0
    assert runner.invoke(cli_main.app, ["git", "draft-commit"]).exit_code == 0


def test_cli_git_cwd_cannot_escape_current_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli_main.app, ["git", "status", "--cwd", str(tmp_path.parent)])
    assert result.exit_code == 1
    assert "blocked" in result.stdout.lower()
