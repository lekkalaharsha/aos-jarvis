import subprocess
from pathlib import Path
import os

import aos.project.git_tools as git_tools
import aos.safety.commands as safety_commands
import aos.tools.shell_runner as shell_runner

from aos.project.git_tools import git_status
from aos.safety.audit import list_events, verify_chain


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


def test_git_status_audits_without_full_diff(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(git_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)
    sanitized_env = _git_env(tmp_path)
    summary = safety_commands.EnvironmentSummary(
        preserved_keys=["GIT_CEILING_DIRECTORIES", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"],
        removed_keys=[],
    )
    monkeypatch.setattr(safety_commands, "sanitize_environment", lambda env=None: (dict(sanitized_env), summary))
    monkeypatch.setattr(shell_runner, "sanitize_environment", lambda env=None: (dict(sanitized_env), summary))
    git_status(repo)

    events = list_events(audit_path)
    assert any(event.event_type == "git.status" for event in events)
    assert verify_chain(audit_path).valid
