import subprocess
from pathlib import Path
import os

import pytest

import aos.project.git_tools as git_tools
import aos.safety.commands as safety_commands
import aos.tools.shell_runner as shell_runner
from aos.project.git_tools import draft_commit_message, git_branch, git_diff, git_log, git_status
from aos.safety.command_policy import evaluate_command
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
def git_env(tmp_path, monkeypatch):
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
    return audit_path


def test_git_policy_allows_safe_reads_and_denies_writes(tmp_path, git_env):
    repo = _make_repo(tmp_path)
    allowed = [
        "git status",
        "git status --short",
        "git diff",
        "git diff --stat",
        "git log --oneline -n 5",
        "git branch --show-current",
    ]
    denied = [
        "git push",
        "git pull",
        "git fetch",
        "git clone https://example.com/repo.git",
        "git commit -m test",
        "git reset --hard",
        "git clean -fd",
        "git checkout main",
        "git switch main",
        "git rebase main",
        "git merge main",
    ]
    for command in allowed:
        assert evaluate_command(command, cwd=repo, approved_roots=[repo]).allowed
    for command in denied:
        assert not evaluate_command(command, cwd=repo, approved_roots=[repo]).allowed


def test_git_tools_use_safe_shell_runner(tmp_path, git_env, monkeypatch):
    repo = _make_repo(tmp_path)
    calls: list[str] = []

    class _Result:
        def __init__(self, command: str, stdout: str):
            self.command_original = command
            self.return_code = 0
            self.stdout = stdout
            self.stderr = ""
            self.timed_out = False
            self.error = None

    def _fake_run(command: str, **kwargs):
        calls.append(command)
        outputs = {
            "git branch --show-current": "main\n",
            "git status --short": "M  README.md\n",
            "git diff --stat": " README.md | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)\n",
            "git diff": "diff --git a/README.md b/README.md\n",
            "git log --oneline -n 2": "abc1234 feat: initial commit\n",
        }
        return _Result(command, outputs[command])

    monkeypatch.setattr(git_tools, "run_command", _fake_run)
    assert git_branch(repo).name == "main"
    assert git_status(repo).branch == "main"
    assert git_diff(repo, stat=True).files_changed == 1
    assert git_log(repo, limit=2)[0].title == "feat: initial commit"
    assert calls


def test_non_git_repo_returns_friendly_error(tmp_path, git_env, monkeypatch):
    class _Result:
        command_original = "git status --short"
        return_code = 128
        stdout = ""
        stderr = "fatal: not a git repository (or any of the parent directories): .git"
        timed_out = False
        error = None

    with pytest.raises(ProjectToolError, match="not a git repository"):
        monkeypatch.setattr(git_tools, "run_command", lambda *args, **kwargs: _Result())
        git_status(tmp_path)


def test_draft_commit_message_returns_draft_only(tmp_path, git_env, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "README.md").write_text("# Test\nchanged\n", encoding="utf-8")
    draft = draft_commit_message(repo)
    assert "chore(" in draft.title or "chore:" in draft.title


def test_no_direct_subprocess_usage_in_project_modules():
    project_root = Path(__file__).resolve().parents[1] / "aos" / "project"
    for path in project_root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "subprocess" not in text
