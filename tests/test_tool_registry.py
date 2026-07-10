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
