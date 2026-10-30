from __future__ import annotations

from typer.testing import CliRunner

from aos.interfaces.cli.main import app
from aos.interfaces.cli import workspace_commands
from aos.safety.approved_projects import ApprovedProjectRegistry, HumanOwnerEnrollmentAuthority
from aos.safety.audit import list_events
from aos.tools.shell_runner import WorkspaceLaunchAdapter
from aos.tools.workspace import WorkspaceTool


class _ForegroundProcess:
    def __init__(self, *, exit_after_polls: int = 2) -> None:
        self.exit_after_polls = exit_after_polls
        self.poll_calls = 0

    def poll(self):
        self.poll_calls += 1
        return None if self.poll_calls < self.exit_after_polls else 0

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass

    def wait(self, timeout: float) -> int:
        return 0


def _registry(tmp_path):
    return ApprovedProjectRegistry(tmp_path / "projects.json")


def _enroll(registry, project):
    approval = HumanOwnerEnrollmentAuthority().approve_one(project, human_owner_confirmed=True, origin="terminal")
    return registry.enroll(project, approval=approval)


def _tool(tmp_path):
    adapter = WorkspaceLaunchAdapter(platform="linux", process_factory=lambda *args, **kwargs: _ForegroundProcess())
    return WorkspaceTool(
        registry=_registry(tmp_path),
        state_path=tmp_path / "state.json",
        audit_path=tmp_path / "audit.db",
        launch_adapter=adapter,
        consumed_path=tmp_path / "consumed.json",
    )


def test_workspace_serve_rejected_confirmation_does_not_launch(tmp_path, monkeypatch):
    registry = _registry(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    enrolled = _enroll(registry, project)
    tool = _tool(tmp_path)
    calls: list[object] = []

    monkeypatch.setattr(workspace_commands, "ApprovedProjectRegistry", lambda: registry)
    monkeypatch.setattr(workspace_commands, "_tool", lambda: tool)
    monkeypatch.setattr(workspace_commands.typer, "confirm", lambda *args, **kwargs: False)
    monkeypatch.setattr(tool.launch_adapter, "launch", lambda *args, **kwargs: calls.append("launch"))

    result = CliRunner().invoke(app, ["workspace", "serve", enrolled.project_id, "--port", "8000"])

    assert result.exit_code == 1
    assert calls == []
    assert "Press Ctrl+C in the terminal that started this server." in result.output
    assert "stop method: ctrl_c_foreground_terminal" in result.output
    assert enrolled.project_id in result.output


def test_workspace_serve_accepts_confirmation_and_runs_foreground(tmp_path, monkeypatch):
    registry = _registry(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    enrolled = _enroll(registry, project)
    tool = _tool(tmp_path)
    monkeypatch.setattr(workspace_commands, "ApprovedProjectRegistry", lambda: registry)
    monkeypatch.setattr(workspace_commands, "_tool", lambda: tool)

    result = CliRunner().invoke(app, ["workspace", "serve", enrolled.project_id, "--port", "8000", "--approve"])

    assert result.exit_code == 0
    assert "Press Ctrl+C in the terminal that started this server." in result.output
    assert "stop method: ctrl_c_foreground_terminal" in result.output
    assert "development server stopped" in result.output or "development server cancelled" in result.output
    assert not tool.launch_adapter._processes
    events = list_events(tmp_path / "audit.db")
    assert any(event.event_type == "workspace.server.running" for event in events)
    assert any(event.event_type in {"workspace.server.stopped", "workspace.server.cancelled"} for event in events)
    assert all("token" not in event.payload_json.lower() for event in events)
