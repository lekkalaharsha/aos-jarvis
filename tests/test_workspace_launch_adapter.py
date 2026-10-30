from __future__ import annotations

from aos.tools.shell_runner import (
    FolderLaunchRequest,
    DevServerLaunchRequest,
    DevServerProfile,
    EditorLaunchRequest,
    EditorId,
    LaunchState,
    TerminalId,
    TerminalLaunchRequest,
    WorkspaceLaunchAdapter,
)


class FakeProcess:
    def __init__(self, exited: bool = False) -> None:
        self.exited = exited
        self.terminated = 0
        self.killed = 0

    def poll(self):
        return 0 if self.exited else None

    def terminate(self) -> None:
        self.terminated += 1
        self.exited = True

    def kill(self) -> None:
        self.killed += 1
        self.exited = True

    def wait(self, timeout: float) -> int:
        if not self.exited:
            raise AssertionError("wait before termination")
        return 0


def test_editor_launch_uses_fixed_argv_and_opaque_handle(tmp_path):
    calls = []
    adapter = WorkspaceLaunchAdapter(platform="linux", process_factory=lambda *args, **kwargs: calls.append((args, kwargs)) or FakeProcess())
    outcome = adapter.launch(EditorLaunchRequest("a" * 32, tmp_path, EditorId.VSCODE))
    assert outcome.state is LaunchState.RUNNING
    assert outcome.handle is not None and outcome.handle.project_id == "a" * 32
    assert "pid" not in outcome.handle.__dict__ if hasattr(outcome.handle, "__dict__") else True
    assert calls[0][0][0] == ["code", str(tmp_path.resolve())]
    assert calls[0][1]["shell"] is False


def test_folder_launch_uses_fixed_argv_and_cwd(tmp_path):
    calls = []
    adapter = WorkspaceLaunchAdapter(platform="linux", process_factory=lambda *args, **kwargs: calls.append((args, kwargs)) or FakeProcess())
    outcome = adapter.launch(FolderLaunchRequest("a" * 32, tmp_path))
    assert outcome.state is LaunchState.RUNNING
    assert outcome.handle is not None and outcome.handle.project_id == "a" * 32
    assert calls[0][0][0] == ["xdg-open", str(tmp_path.resolve())]
    assert calls[0][1]["cwd"] == str(tmp_path.resolve())
    assert calls[0][1]["shell"] is False


def test_terminal_rejects_injected_identifier_and_unsupported_platform(tmp_path):
    adapter = WorkspaceLaunchAdapter(platform="linux", process_factory=lambda *args, **kwargs: FakeProcess())
    injected = TerminalLaunchRequest("a" * 32, tmp_path, "default --evil")  # type: ignore[arg-type]
    assert adapter.launch(injected).state is LaunchState.FAILED
    assert WorkspaceLaunchAdapter(platform="other", process_factory=lambda *args, **kwargs: FakeProcess()).launch(TerminalLaunchRequest("a" * 32, tmp_path, TerminalId.DEFAULT)).state is LaunchState.FAILED


def test_server_is_loopback_only_and_stop_is_project_bound_idempotent(tmp_path):
    calls = []
    adapter = WorkspaceLaunchAdapter(platform="linux", process_factory=lambda *args, **kwargs: calls.append(args[0]) or FakeProcess())
    started = adapter.launch(DevServerLaunchRequest("a" * 32, tmp_path, DevServerProfile.LOOPBACK_PYTHON_HTTP, 8765))
    assert started.handle is not None
    assert calls[0][-2:] == ["--bind", "127.0.0.1"]
    assert adapter.stop(started.handle.handle_id, project_id="b" * 32).error_code == "project_mismatch"
    assert adapter.stop(started.handle.handle_id, project_id="a" * 32).state is LaunchState.STOPPED
    assert adapter.stop(started.handle.handle_id, project_id="a" * 32).state is LaunchState.STOPPED


def test_bad_port_and_unknown_handle_fail_closed(tmp_path):
    adapter = WorkspaceLaunchAdapter(platform="linux", process_factory=lambda *args, **kwargs: FakeProcess())
    assert adapter.launch(DevServerLaunchRequest("a" * 32, tmp_path, DevServerProfile.LOOPBACK_PYTHON_HTTP, 1)).error_code == "validation_denied"
    assert adapter.stop("forged", project_id="a" * 32).error_code == "unknown_handle"
