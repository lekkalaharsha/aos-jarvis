"""Comprehensive Phase 9 regression tests for workspace and app control."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aos.safety.approved_projects import ApprovedProject, ApprovedProjectRegistry, HumanOwnerEnrollmentAuthority
from aos.safety.audit import list_events, verify_chain
from aos.safety.dev_server import canonical_project_digest, consume_dev_server_approval, mint_dev_server_approval
from aos.safety.errors import PermissionBlocked
from aos.tools.shell_runner import (
    LaunchOutcome,
    LaunchState,
    WorkspaceLaunchAdapter,
)
from aos.tools.workspace import CTRL_C_STOP_METHOD, WorkspaceTool


class _ForegroundProcess:
    def __init__(self, *, exit_after_polls: int = 2) -> None:
        self.exit_after_polls = exit_after_polls
        self.poll_calls = 0
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self):
        self.poll_calls += 1
        return None if self.poll_calls < self.exit_after_polls else 0

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1

    def wait(self, timeout: float) -> int:
        return 0


class _CtrlCProcess(_ForegroundProcess):
    def __init__(self) -> None:
        super().__init__()
        self.interrupted = False

    def poll(self):
        self.poll_calls += 1
        if self.poll_calls == 1:
            return None
        if not self.interrupted:
            self.interrupted = True
            raise KeyboardInterrupt
        return None


def _enroll(tool: WorkspaceTool, project: Path) -> ApprovedProject:
    approval = HumanOwnerEnrollmentAuthority().approve_one(project, human_owner_confirmed=True, origin="terminal")
    return tool.registry.enroll(project, approval=approval)


def _approval(project_id: str, *, profile: str = "python-http", port: int = 8000, origin: str = "terminal", human_owner_confirmed: bool = True, canonical_path: Path | None = None):
    return mint_dev_server_approval(
        project_id=project_id,
        canonical_project_id=canonical_project_digest(canonical_path) if canonical_path is not None else project_id,
        profile=profile,
        port=port,
        human_owner_confirmed=human_owner_confirmed,
        origin=origin,
    )


def _tool(tmp_path: Path, *, process_factory=None, stop_timeout: float = 3.0) -> WorkspaceTool:
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    adapter = WorkspaceLaunchAdapter(
        platform="linux",
        process_factory=process_factory or (lambda *args, **kwargs: _ForegroundProcess()),
        stop_timeout_seconds=stop_timeout,
    )
    return WorkspaceTool(
        registry=registry,
        state_path=tmp_path / "state.json",
        audit_path=tmp_path / "audit.db",
        launch_adapter=adapter,
        consumed_path=tmp_path / "consumed.json",
    )


def _tool_events(tmp_path: Path):
    return list_events(tmp_path / "audit.db")


class TestApproval:
    def test_exact_valid_approval(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id)

        result = consume_dev_server_approval(
            approval,
            project_id=registered.project_id,
            profile="python-http",
            port=8000,
            consumed_path=tmp_path / "consumed.json",
        )

        assert result is approval

    def test_missing_approval_raises(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)

        result = tool.execute({"operation": "serve", "project_id": registered.project_id, "port": 8000})

        assert not result.ok

    def test_malformed_approval_rejected(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)

        result = tool.execute({"operation": "serve", "project_id": registered.project_id, "approval": "not-an-approval", "port": 8000})

        assert not result.ok

    def test_wrong_operation_rejected(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id)
        object.__setattr__(approval, "_operation", "wrong.operation")

        with pytest.raises(PermissionBlocked):
            consume_dev_server_approval(
                approval,
                project_id=registered.project_id,
                profile="python-http",
                port=8000,
                consumed_path=tmp_path / "consumed.json",
            )

    def test_wrong_project_rejected(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id)

        with pytest.raises(PermissionBlocked):
            consume_dev_server_approval(
                approval,
                project_id="b" * 32,
                profile="python-http",
                port=8000,
                consumed_path=tmp_path / "consumed.json",
            )

    def test_wrong_profile_rejected(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id)

        with pytest.raises(PermissionBlocked):
            consume_dev_server_approval(
                approval,
                project_id=registered.project_id,
                profile="wrong-profile",
                port=8000,
                consumed_path=tmp_path / "consumed.json",
            )

    def test_wrong_port_rejected(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id)

        with pytest.raises(PermissionBlocked):
            consume_dev_server_approval(
                approval,
                project_id=registered.project_id,
                profile="python-http",
                port=9000,
                consumed_path=tmp_path / "consumed.json",
            )

    def test_expired_approval_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("aos.safety.dev_server.APPROVAL_TTL_SECONDS", 0)
        approval = _approval("a" * 32)
        with pytest.raises(PermissionBlocked, match="expired"):
            consume_dev_server_approval(
                approval,
                project_id="a" * 32,
                profile="python-http",
                port=8000,
                consumed_path=tmp_path / "consumed.json",
            )

    def test_replay_rejected(self, tmp_path):
        consumed_path = tmp_path / "consumed.json"
        approval = _approval("a" * 32)
        consume_dev_server_approval(
            approval,
            project_id="a" * 32,
            profile="python-http",
            port=8000,
            consumed_path=consumed_path,
        )
        with pytest.raises(PermissionBlocked, match="already consumed"):
            consume_dev_server_approval(
                approval,
                project_id="a" * 32,
                profile="python-http",
                port=8000,
                consumed_path=consumed_path,
            )

    def test_voice_and_model_origin_denied(self, tmp_path):
        with pytest.raises(PermissionBlocked, match="terminal"):
            _approval("a" * 32, origin="voice")
        with pytest.raises(PermissionBlocked, match="terminal"):
            _approval("a" * 32, origin="model")

    def test_human_owner_confirmation_is_required(self, tmp_path):
        with pytest.raises(PermissionBlocked, match="terminal"):
            _approval("a" * 32, human_owner_confirmed=False)

    def test_canonical_project_binding_is_enforced(self, tmp_path):
        approval = _approval("a" * 32)
        object.__setattr__(approval, "_canonical_project_id", "b" * 32)
        with pytest.raises(PermissionBlocked, match="canonical"):
            consume_dev_server_approval(
                approval,
                project_id="a" * 32,
                profile="python-http",
                port=8000,
                consumed_path=tmp_path / "consumed.json",
            )

    def test_canonical_project_binding_catches_path_change_with_same_project_id(self, tmp_path):
        """The canonical binding is independent of project_id: a path change
        between mint and consume must be rejected even if project_id matches."""
        project = tmp_path / "project"
        project.mkdir()
        moved = tmp_path / "moved"
        moved.mkdir()
        approval = _approval("a" * 32, canonical_path=project)

        with pytest.raises(PermissionBlocked, match="canonical"):
            consume_dev_server_approval(
                approval,
                project_id="a" * 32,
                profile="python-http",
                port=8000,
                canonical_project_id=canonical_project_digest(moved),
                consumed_path=tmp_path / "consumed.json",
            )

    def test_canonical_project_binding_accepts_matching_resolved_path(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        approval = _approval("a" * 32, canonical_path=project)

        result = consume_dev_server_approval(
            approval,
            project_id="a" * 32,
            profile="python-http",
            port=8000,
            canonical_project_id=canonical_project_digest(project),
            consumed_path=tmp_path / "consumed.json",
        )

        assert result is approval

    def test_token_immutable(self, tmp_path):
        approval = _approval("a" * 32)
        with pytest.raises(PermissionBlocked, match="immutable"):
            approval.project_id = "b" * 32


class TestWorkspaceLaunch:
    def test_open_end_to_end_uses_registry_project_id(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)

        result = tool.execute({"operation": "open", "project_id": registered.project_id})

        assert result.ok
        events = _tool_events(tmp_path)
        assert any(event.event_type == "workspace.open.requested" for event in events)
        assert any(event.event_type == "workspace.open.running" for event in events)

    def test_open_denied_unknown_project_preserves_operation(self, tmp_path):
        tool = _tool(tmp_path)

        result = tool.execute({"operation": "open", "project_id": "a" * 32})

        assert not result.ok
        events = _tool_events(tmp_path)
        denied = next(event for event in events if event.event_type == "workspace.denied")
        assert json.loads(denied.payload_json)["operation"] == "open"
        assert json.loads(denied.payload_json)["project_id"] == "a" * 32

    def test_open_denied_revoked_project(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)
        tool.registry.revoke(registered.project_id)

        result = tool.execute({"operation": "open", "project_id": registered.project_id})

        assert not result.ok

    def test_open_denied_path_replacement(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)
        project.rmdir()
        try:
            os.symlink(outside, project, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")

        result = tool.execute({"operation": "open", "project_id": registered.project_id})

        assert not result.ok

    def test_open_denied_unavailable_launcher(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path, process_factory=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no launcher")))
        registered = _enroll(tool, project)

        result = tool.execute({"operation": "open", "project_id": registered.project_id})

        assert not result.ok

    def test_open_denied_unsupported_platform(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = WorkspaceTool(
            registry=ApprovedProjectRegistry(tmp_path / "projects.json"),
            state_path=tmp_path / "state.json",
            audit_path=tmp_path / "audit.db",
            launch_adapter=WorkspaceLaunchAdapter(platform="other", process_factory=lambda *args, **kwargs: _ForegroundProcess()),
            consumed_path=tmp_path / "consumed.json",
        )
        registered = _enroll(tool, project)

        result = tool.execute({"operation": "open", "project_id": registered.project_id})

        assert not result.ok

    def test_editor_and_terminal_launches_use_one_terminal_event(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        tool = _tool(tmp_path)
        registered = _enroll(tool, project)

        assert tool.execute({"operation": "editor", "project_id": registered.project_id}).ok
        assert tool.execute({"operation": "terminal", "project_id": registered.project_id}).ok
        events = _tool_events(tmp_path)
        terminal_events = [event for event in events if event.event_type in {"workspace.editor.running", "workspace.terminal.running"}]
        assert len(terminal_events) == 2


class TestServeLifecycle:
    def _serve(self, tmp_path, *, process_factory=None, stop_timeout: float = 3.0):
        tool = _tool(tmp_path, process_factory=process_factory, stop_timeout=stop_timeout)
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id, canonical_path=Path(registered.path))
        result = tool.execute({"operation": "serve", "project_id": registered.project_id, "approval": approval, "port": 8000})
        return tool, registered, approval, result

    def test_successful_foreground_launch_stops_cleanly(self, tmp_path):
        tool, registered, approval, result = self._serve(tmp_path)

        assert result.ok
        assert "stop method ctrl_c_foreground_terminal" in result.output
        assert not tool.launch_adapter._processes
        events = _tool_events(tmp_path)
        assert any(event.event_type == "workspace.server.running" for event in events)
        assert any(event.event_type == "workspace.server.stopped" for event in events)

    def test_ctrl_c_cancellation_returns_safe_terminal_outcome(self, tmp_path):
        tool = _tool(
            tmp_path,
            process_factory=lambda *args, **kwargs: _CtrlCProcess(),
        )
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id, canonical_path=Path(registered.path))

        result = tool.execute({"operation": "serve", "project_id": registered.project_id, "approval": approval, "port": 8000})

        assert result.ok
        assert "cancelled" in result.output
        assert CTRL_C_STOP_METHOD in result.output

    def test_cleanup_failure_is_audited(self, tmp_path, monkeypatch):
        tool = _tool(
            tmp_path,
            process_factory=lambda *args, **kwargs: _CtrlCProcess(),
        )
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id, canonical_path=Path(registered.path))

        def _timed_out(*args, **kwargs):
            return LaunchOutcome(LaunchState.TIMED_OUT, None, "cleanup_timeout")

        monkeypatch.setattr(tool.launch_adapter, "stop", _timed_out)
        result = tool.execute({"operation": "serve", "project_id": registered.project_id, "approval": approval, "port": 8000})

        assert result.ok
        assert "cancelled" in result.output
        events = _tool_events(tmp_path)
        assert any(event.event_type == "workspace.server.cancelled" for event in events)

    def test_immediate_exit_fails_closed(self, tmp_path):
        tool = _tool(tmp_path, process_factory=lambda *args, **kwargs: _ForegroundProcess(exit_after_polls=1))
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id, canonical_path=Path(registered.path))

        result = tool.execute({"operation": "serve", "project_id": registered.project_id, "approval": approval, "port": 8000})

        assert not result.ok
        assert "did not start" in result.output

    def test_approval_consumed_before_launch(self, tmp_path):
        tool, registered, approval, result = self._serve(tmp_path)

        assert result.ok
        consumed_path = tmp_path / "consumed.json"
        assert consumed_path.exists()
        consumed = json.loads(consumed_path.read_text(encoding="utf-8"))
        assert len(consumed) == 1

    def test_token_never_in_audit(self, tmp_path):
        tool = _tool(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id, canonical_path=Path(registered.path))
        token = approval._token

        tool.execute({"operation": "serve", "project_id": registered.project_id, "approval": approval, "port": 8000})

        events = _tool_events(tmp_path)
        for event in events:
            assert token not in event.payload_json
            assert approval._digest not in event.payload_json

    def test_foreground_stop_guidance_is_audited(self, tmp_path):
        tool, _, _, result = self._serve(tmp_path)

        assert result.ok
        events = _tool_events(tmp_path)
        server_events = [event for event in events if event.event_type.startswith("workspace.server.")]
        assert all(json.loads(event.payload_json).get("stop_method") == CTRL_C_STOP_METHOD for event in server_events if event.event_type not in {"workspace.server.denied"})

    def test_no_orphan_after_return(self, tmp_path):
        tool, _, _, result = self._serve(tmp_path)

        assert result.ok
        assert not tool.launch_adapter._processes


class TestUnsupportedOperations:
    def test_removed_status_and_stop_operations_fail_closed(self, tmp_path):
        tool = _tool(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)

        status = tool.execute({"operation": "server_status", "project_id": registered.project_id, "handle_id": "opaque"})
        stop = tool.execute({"operation": "server_stop", "project_id": registered.project_id, "handle_id": "opaque"})

        assert not status.ok
        assert not stop.ok
        events = _tool_events(tmp_path)
        denied_ops = [json.loads(event.payload_json)["operation"] for event in events if event.event_type == "workspace.denied"]
        assert "server_status" in denied_ops
        assert "server_stop" in denied_ops


class TestServeDenialAuditIsSingular:
    def test_missing_approval_produces_exactly_one_denial_event(self, tmp_path):
        tool = _tool(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)

        result = tool.execute({"operation": "serve", "project_id": registered.project_id, "port": 8000})

        assert not result.ok
        events = _tool_events(tmp_path)
        denied = [event for event in events if event.status == "DENY"]
        assert len(denied) == 1
        assert denied[0].event_type == "workspace.server.denied"

    def test_invalid_approval_produces_exactly_one_denial_event(self, tmp_path):
        tool = _tool(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)
        approval = _approval(registered.project_id, canonical_path=Path(registered.path), port=9999)

        result = tool.execute({"operation": "serve", "project_id": registered.project_id, "approval": approval, "port": 8000})

        assert not result.ok
        events = _tool_events(tmp_path)
        denied = [event for event in events if event.status == "DENY"]
        assert len(denied) == 1
        assert denied[0].event_type == "workspace.server.denied"


class TestAudit:
    def test_audit_hash_chain_valid(self, tmp_path):
        tool = _tool(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)
        tool.execute({"operation": "open", "project_id": registered.project_id})
        approval = _approval(registered.project_id, canonical_path=Path(registered.path))
        tool.execute({"operation": "serve", "project_id": registered.project_id, "approval": approval, "port": 8000})

        result = verify_chain(tmp_path / "audit.db")
        assert result.valid

    def test_audit_project_id_not_path(self, tmp_path):
        tool = _tool(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)
        tool.execute({"operation": "editor", "project_id": registered.project_id})

        events = _tool_events(tmp_path)
        for event in events:
            assert str(project) not in event.payload_json

    def test_audit_no_exception_leakage(self, tmp_path):
        tool = _tool(tmp_path, process_factory=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("secret path /etc/shadow")))
        project = tmp_path / "project"
        project.mkdir()
        registered = _enroll(tool, project)

        result = tool.execute({"operation": "open", "project_id": registered.project_id})

        assert not result.ok
        events = _tool_events(tmp_path)
        denied = next(event for event in events if event.event_type == "workspace.open.failed")
        assert "/etc/shadow" not in denied.payload_json
