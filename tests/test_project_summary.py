import subprocess
from pathlib import Path
import os

import pytest

import aos.project.git_tools as git_tools
import aos.project.project_summary as project_summary
import aos.safety.commands as safety_commands
import aos.tools.shell_runner as shell_runner

from aos.project.project_summary import summarize_project_changes
from aos.project.git_tools import draft_commit_message
from aos.safety.errors import ProjectToolError


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


@pytest.fixture()
def project_env(tmp_path, monkeypatch):
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
    return audit_path


def test_summarize_project_changes_handles_dirty_and_clean_repo(tmp_path, project_env):
    repo = _make_repo(tmp_path)
    clean = summarize_project_changes(repo)
    assert clean.clean
    (repo / "README.md").write_text("# Test\nchange\n", encoding="utf-8")
    dirty = summarize_project_changes(repo)
    assert not dirty.clean
    assert "README.md" in dirty.changed_files


def test_summarize_project_changes_handles_non_git_repo(tmp_path, project_env, monkeypatch):
    monkeypatch.setattr(project_summary, "git_branch", lambda *args, **kwargs: (_ for _ in ()).throw(ProjectToolError("current directory is not a git repository")))
    with pytest.raises(ProjectToolError):
        summarize_project_changes(tmp_path)


def test_draft_commit_message_does_not_modify_files(tmp_path, project_env):
    repo = _make_repo(tmp_path)
    (repo / "README.md").write_text("# Test\nchange\n", encoding="utf-8")
    before = (repo / "README.md").read_text(encoding="utf-8")
    draft = draft_commit_message(repo)
    after = (repo / "README.md").read_text(encoding="utf-8")
    assert draft.title
    assert before == after
