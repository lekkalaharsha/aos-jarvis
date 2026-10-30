import pytest

from aos.agent.tool_registry import default_registry
from aos.agent.types import ToolCall
from aos.safety.errors import PermissionBlocked


def test_known_tool_is_accepted(tmp_path):
    registry = default_registry()
    call = ToolCall("fs.read", {"path": "README.md"}, "T0", False)
    registry.validate(call, cwd=tmp_path)


def test_unknown_tool_is_rejected(tmp_path):
    registry = default_registry()
    call = ToolCall("banana.tool", {}, "T0", False)
    with pytest.raises(PermissionBlocked):
        registry.validate(call, cwd=tmp_path)


def test_malformed_args_are_rejected(tmp_path):
    registry = default_registry()
    call = ToolCall("fs.read", {}, "T0", False)
    with pytest.raises(PermissionBlocked):
        registry.validate(call, cwd=tmp_path)


def test_dangerous_direct_shell_tool_is_rejected(tmp_path):
    registry = default_registry()
    call = ToolCall("subprocess.run", {"command": "pwd"}, "T0", False)
    with pytest.raises(PermissionBlocked):
        registry.validate(call, cwd=tmp_path)


def test_direct_filesystem_tool_is_rejected(tmp_path):
    registry = default_registry()
    call = ToolCall("open", {"path": "README.md"}, "T0", False)
    with pytest.raises(PermissionBlocked):
        registry.validate(call, cwd=tmp_path)


def test_memory_recall_tool_is_accepted(tmp_path):
    registry = default_registry()
    call = ToolCall("memory.recall", {"query": "what did I work on recently", "limit": 5}, "T0", False)
    registry.validate(call, cwd=tmp_path)


def test_git_status_tool_is_accepted(tmp_path):
    registry = default_registry()
    call = ToolCall("git.status", {"cwd": "."}, "T0", False)
    registry.validate(call, cwd=tmp_path)


def test_project_draft_commit_tool_is_accepted(tmp_path):
    registry = default_registry()
    call = ToolCall("project.draft_commit", {"cwd": "."}, "T0", False)
    registry.validate(call, cwd=tmp_path)


def test_workspace_tool_accepts_only_opaque_project_id(tmp_path):
    registry = default_registry()
    registry.validate(ToolCall("workspace.open", {"project_id": "a" * 32}, "T1", True), cwd=tmp_path)
    with pytest.raises(PermissionBlocked):
        registry.validate(ToolCall("workspace.open", {"project": str(tmp_path)}, "T1", True), cwd=tmp_path)


def test_workspace_foreground_registry_does_not_expose_status_or_stop(tmp_path):
    registry = default_registry()
    assert "workspace.server_status" not in registry.list_tools()
    assert "workspace.server_stop" not in registry.list_tools()
    with pytest.raises(PermissionBlocked):
        registry.validate(ToolCall("workspace.server_status", {"project_id": "a" * 32, "handle_id": "handle"}, "T2", False), cwd=tmp_path)
    with pytest.raises(PermissionBlocked):
        registry.validate(ToolCall("workspace.server_stop", {"project_id": "a" * 32, "handle_id": "handle"}, "T2", False), cwd=tmp_path)
