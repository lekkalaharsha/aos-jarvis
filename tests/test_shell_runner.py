import subprocess
import json
from pathlib import Path

import pytest

import aos.tools.shell_runner as shell_runner
from aos.safety.audit import list_events, verify_chain
from aos.safety.commands import sanitize_environment
from aos.safety.errors import ApprovalRequired, CommandPolicyBlocked
from aos.tools.shell_runner import preview_command, run_command


class _FakeProcess:
    def __init__(self, *, stdout=b"", stderr=b"", returncode=0, timeout=False):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._timeout = timeout
        self.kill_called = False
        self._communicated = False

    def communicate(self, timeout=None):
        if self._timeout and not self._communicated:
            self._communicated = True
            raise subprocess.TimeoutExpired(cmd=["python"], timeout=timeout)
        return self._stdout, self._stderr

    def kill(self):
        self.kill_called = True
        self.returncode = -9


@pytest.fixture()
def run_root(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)
    return root, audit_path


def test_preview_does_not_execute(run_root, monkeypatch):
    root, _ = run_root

    def _boom(*args, **kwargs):
        raise AssertionError("subprocess should not be called")

    monkeypatch.setattr(shell_runner.subprocess, "Popen", _boom)
    preview = preview_command("git status", cwd=root, approved_roots=[root])

    assert preview.allowed
    assert preview.argv == ["git", "status"]


def test_allowed_command_executes(run_root, monkeypatch):
    root, _ = run_root
    fake = _FakeProcess(stdout=b"Python 3.12.0\n", returncode=0)
    monkeypatch.setattr(shell_runner.subprocess, "Popen", lambda *args, **kwargs: fake)

    result = run_command("python --version", cwd=root, approved_roots=[root])

    assert result.return_code == 0
    assert "Python 3.12.0" in result.stdout


def test_denied_command_does_not_execute(run_root, monkeypatch):
    root, _ = run_root

    def _boom(*args, **kwargs):
        raise AssertionError("subprocess should not be called")

    monkeypatch.setattr(shell_runner.subprocess, "Popen", _boom)
    with pytest.raises(CommandPolicyBlocked):
        run_command("sudo ls", cwd=root, approved_roots=[root], yes=True)


def test_timeout_kills_long_running_command(run_root, monkeypatch):
    root, audit_path = run_root
    fake = _FakeProcess(stdout=b"partial", stderr=b"", returncode=0, timeout=True)
    monkeypatch.setattr(shell_runner.subprocess, "Popen", lambda *args, **kwargs: fake)

    result = run_command("pytest", cwd=root, approved_roots=[root], yes=True, timeout_seconds=1)

    assert result.timed_out
    assert fake.kill_called
    assert any(event.event_type == "run.timeout" for event in list_events(audit_path))


def test_output_is_captured(run_root, monkeypatch):
    root, _ = run_root
    fake = _FakeProcess(stdout=b"out\n", stderr=b"err\n", returncode=0)
    monkeypatch.setattr(shell_runner.subprocess, "Popen", lambda *args, **kwargs: fake)

    result = run_command("pytest", cwd=root, approved_roots=[root], yes=True)

    assert result.stdout == "out\n"
    assert result.stderr == "err\n"


def test_large_output_is_truncated(run_root, monkeypatch):
    root, audit_path = run_root
    fake = _FakeProcess(stdout=b"x" * 4096, stderr=b"", returncode=0)
    monkeypatch.setattr(shell_runner.subprocess, "Popen", lambda *args, **kwargs: fake)

    result = run_command("pytest", cwd=root, approved_roots=[root], yes=True, max_output_bytes=64)

    assert result.output_truncated
    assert "[truncated]" in result.stdout
    assert any(event.event_type == "run.output_truncated" for event in list_events(audit_path))


def test_return_code_is_captured(run_root, monkeypatch):
    root, _ = run_root
    fake = _FakeProcess(stdout=b"", stderr=b"", returncode=5)
    monkeypatch.setattr(shell_runner.subprocess, "Popen", lambda *args, **kwargs: fake)

    result = run_command("pytest", cwd=root, approved_roots=[root], yes=True)
    assert result.return_code == 5


def test_file_not_found_is_handled(run_root, monkeypatch):
    root, audit_path = run_root

    def _missing(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(shell_runner.subprocess, "Popen", _missing)
    result = run_command("python --version", cwd=root, approved_roots=[root])

    assert result.return_code is None
    assert result.error is not None
    assert any(event.event_type == "run.blocked" for event in list_events(audit_path))


def test_approval_required_command_does_not_run_without_yes(run_root, monkeypatch):
    root, _ = run_root

    def _boom(*args, **kwargs):
        raise AssertionError("subprocess should not be called")

    monkeypatch.setattr(shell_runner.subprocess, "Popen", _boom)
    script = root / "script.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    with pytest.raises(ApprovalRequired):
        run_command("python script.py", cwd=root, approved_roots=[root], yes=False)


def test_yes_allows_approval_required_command(run_root, monkeypatch):
    root, _ = run_root
    script = root / "script.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    fake = _FakeProcess(stdout=b"ok\n", returncode=0)
    monkeypatch.setattr(shell_runner.subprocess, "Popen", lambda *args, **kwargs: fake)

    result = run_command("python script.py", cwd=root, approved_roots=[root], yes=True)

    assert result.return_code == 0
    assert result.approved


def test_denied_command_still_denied_with_yes(run_root, monkeypatch):
    root, _ = run_root
    with pytest.raises(CommandPolicyBlocked):
        run_command("sudo ls", cwd=root, approved_roots=[root], yes=True)


def test_environment_secrets_are_removed(run_root, monkeypatch):
    env = {
        "PATH": "safe",
        "OPENAI_API_KEY": "secret",
        "TOKEN": "token",
        "PASSWORD_STORE": "pw",
        "PYTHONPATH": "pkg",
    }
    clean, summary = sanitize_environment(env)

    assert "PATH" in clean
    assert "PYTHONPATH" in clean
    assert "OPENAI_API_KEY" not in clean
    assert "TOKEN" not in clean
    assert "PASSWORD_STORE" not in clean
    assert "OPENAI_API_KEY" in summary.removed_keys


def test_audit_redacts_secret_like_command_arguments(run_root, monkeypatch):
    root, audit_path = run_root
    script = root / "script.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    fake = _FakeProcess(stdout=b"ok\n", returncode=0)
    monkeypatch.setattr(shell_runner.subprocess, "Popen", lambda *args, **kwargs: fake)

    result = run_command(
        "python script.py --token=abc123 --password hunter2 --name visible",
        cwd=root,
        approved_roots=[root],
        yes=True,
    )

    assert result.return_code == 0
    apply_event = next(event for event in list_events(audit_path) if event.event_type == "run.apply")
    payload = json.loads(apply_event.payload_json)
    assert payload["argv"] == [
        "python",
        "script.py",
        "--token=[REDACTED]",
        "--password",
        "[REDACTED]",
        "--name",
        "visible",
    ]
    assert "abc123" not in payload["command_original"]
    assert "hunter2" not in payload["command_original"]


def test_audit_preview_apply_and_verify(run_root, monkeypatch):
    root, audit_path = run_root
    fake = _FakeProcess(stdout=b"ok\n", returncode=0)
    monkeypatch.setattr(shell_runner.subprocess, "Popen", lambda *args, **kwargs: fake)

    run_command("python --version", cwd=root, approved_roots=[root])

    events = list_events(audit_path)
    assert any(event.event_type == "run.preview" for event in events)
    assert any(event.event_type == "run.apply" for event in events)
    assert verify_chain(audit_path).valid
