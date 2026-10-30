from __future__ import annotations

import json

from typer.testing import CliRunner

from aos.interfaces.cli.main import app
from aos.safety.approved_projects import ApprovedProjectRegistry, HumanOwnerEnrollmentAuthority
from aos.safety.audit import verify_chain
from aos.tools.shell_runner import WorkspaceLaunchAdapter
from aos.tools.workspace import WorkspaceTool


class _ForegroundProcess:
    def __init__(self, *, exit_after_polls: int = 2) -> None:
        self.exit_after_polls = exit_after_polls
        self.poll_calls = 0
        self.terminated = 0
        self.killed = 0

    def poll(self):
        self.poll_calls += 1
        return None if self.poll_calls < self.exit_after_polls else 0

    def terminate(self) -> None:
        self.terminated += 1

    def kill(self) -> None:
        self.killed += 1

    def wait(self, timeout: float) -> int:
        return 0


def _tool(tmp_path, *, process_factory=None, launch_adapter=None):
    adapter = launch_adapter or WorkspaceLaunchAdapter(
        platform="linux",
        process_factory=process_factory or (lambda *args, **kwargs: _ForegroundProcess()),
    )
    return WorkspaceTool(
        registry=ApprovedProjectRegistry(tmp_path / "projects.json"),
        state_path=tmp_path / "state.json",
        audit_path=tmp_path / "audit.db",
        launch_adapter=adapter,
        consumed_path=tmp_path / "consumed.json",
    )


def _enroll(tool, project):
    approval = HumanOwnerEnrollmentAuthority().approve_one(project, human_owner_confirmed=True, origin="terminal")
    return tool.registry.enroll(project, approval=approval)


def test_workspace_tool_implements_base_contract(tmp_path):
    tool = _tool(tmp_path)
    assert tool.describe().name == "workspace"
    assert tool.required_capabilities({"operation": "open"}) == ["workspace.open"]


def test_open_launch_is_audited_end_to_end(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool = _tool(tmp_path)
    registered = _enroll(tool, project)

    result = tool.execute({"operation": "open", "project_id": registered.project_id})

    assert result.ok
    assert verify_chain(tmp_path / "audit.db").valid


def test_editor_launch_is_audited(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool = _tool(tmp_path)
    registered = _enroll(tool, project)

    result = tool.execute({"operation": "editor", "project_id": registered.project_id})

    assert result.ok
    assert verify_chain(tmp_path / "audit.db").valid


def test_outside_and_unknown_applications_are_denied(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool = _tool(tmp_path)
    registered = _enroll(tool, project)

    assert not tool.execute({"operation": "editor", "project_id": "unknown"}).ok
    assert not tool.execute({"operation": "editor", "project_id": registered.project_id, "editor": "evil"}).ok
    assert not tool.execute({"operation": "terminal", "project_id": registered.project_id, "terminal": "--run=bad"}).ok


def test_save_restore_revalidates_state_and_never_serves(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool = _tool(tmp_path)
    registered = _enroll(tool, project)

    assert tool.execute({"operation": "save", "project_id": registered.project_id}).ok
    assert tool.execute({"operation": "restore"}).ok

    tool.state_path.write_text(
        json.dumps({"schema_version": 99, "project_id": registered.project_id, "editor": "vscode", "terminal": "default"}),
        encoding="utf-8",
    )
    assert not tool.execute({"operation": "restore"}).ok


def test_server_requires_fresh_approval_and_valid_port(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool = _tool(tmp_path)
    registered = _enroll(tool, project)

    assert not tool.execute({"operation": "serve", "project_id": registered.project_id}).ok
    assert not tool.execute({"operation": "serve", "project_id": registered.project_id, "port": 1, "approval": "bad"}).ok


def test_workspace_help_has_no_legacy_server_commands() -> None:
    result = CliRunner().invoke(app, ["workspace", "--help"])
    assert result.exit_code == 0
    assert "server-status" not in result.output.lower()
    assert "server-stop" not in result.output.lower()


def test_workspace_serve_help_shows_confirmation_option() -> None:
    result = CliRunner().invoke(app, ["workspace", "serve", "--help"])
    assert result.exit_code == 0
    assert "--approve" in result.output
