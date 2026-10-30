"""Phase 1 safety exceptions for permissioned file access."""

from __future__ import annotations


class SafetyError(Exception):
    """Base class for safety failures that should be shown without tracebacks."""


class PermissionBlocked(SafetyError):
    """Raised when a file action is denied by the permission engine."""


class DangerousPathBlocked(PermissionBlocked):
    """Raised when a path targets known system or credential locations."""


class SecretPathBlocked(PermissionBlocked):
    """Raised when a path matches secret file deny rules."""


class PathOutsideApprovedRoot(PermissionBlocked):
    """Raised when a path is not inside an approved project root."""


class SymlinkEscapeBlocked(PermissionBlocked):
    """Raised when a symlink resolves outside an approved project root."""


class BinaryFileBlocked(PermissionBlocked):
    """Raised when a text-only operation is requested for binary data."""


class ApprovalRequired(SafetyError):
    """Raised when a write action is attempted without explicit approval."""


class CommandPolicyBlocked(PermissionBlocked):
    """Raised when a shell command is denied by command policy."""


class CommandExecutionFailed(SafetyError):
    """Raised when a shell command could not be started or completed safely."""


class ProjectToolError(SafetyError):
    """Raised when a project/git assistant action cannot complete safely."""
