from pathlib import Path

import os

import pytest

from aos.safety.errors import DangerousPathBlocked, PathOutsideApprovedRoot, SymlinkEscapeBlocked
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import RiskTier


def test_allowed_project_path_is_allowed(tmp_path):
    file_path = tmp_path / "readme.txt"
    file_path.write_text("hello", encoding="utf-8")

    decision = PermissionEngine([tmp_path]).check_path(file_path, "fs.read", RiskTier.T0)

    assert decision.allowed
    assert decision.path == str(file_path.resolve())


def test_write_outside_approved_root_is_blocked(tmp_path):
    outside = tmp_path.parent / "outside-write.txt"

    decision = PermissionEngine([tmp_path]).check_path(outside, "fs.write", RiskTier.T1)

    assert not decision.allowed
    assert "outside approved roots" in decision.reason


def test_ssh_key_path_is_blocked():
    decision = PermissionEngine([Path.cwd()]).check_path("~/.ssh/id_rsa", "fs.read", RiskTier.T0)

    assert not decision.allowed
    assert decision.risk_tier == RiskTier.T3


def test_unknown_capability_is_denied(tmp_path):
    file_path = tmp_path / "readme.txt"
    file_path.write_text("hello", encoding="utf-8")

    decision = PermissionEngine([tmp_path]).check_path(file_path, "fs.delete", RiskTier.T0)

    assert not decision.allowed
    assert "unknown capability" in decision.reason


def test_snapshot_restore_is_a_known_capability(tmp_path):
    file_path = tmp_path / "readme.txt"
    file_path.write_text("hello", encoding="utf-8")

    decision = PermissionEngine([tmp_path]).check_path(file_path, "snapshot.restore", RiskTier.T2)

    assert decision.allowed


def test_require_path_preserves_symlink_escape_subtype(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("secret", encoding="utf-8")
    link = root / "escape.txt"
    try:
        os.symlink(target, link)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(SymlinkEscapeBlocked):
        PermissionEngine([root]).require_path(link, "fs.read", RiskTier.T0)


def test_require_path_preserves_outside_root_subtype(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(PathOutsideApprovedRoot):
        PermissionEngine([root]).require_path(outside, "fs.read", RiskTier.T0)


def test_require_path_preserves_dangerous_windows_credential_type(tmp_path):
    path = Path("C:/Users/tester/AppData/Roaming/gcloud/legacy_credentials/adc.json")

    with pytest.raises(DangerousPathBlocked):
        PermissionEngine([tmp_path]).require_path(path, "fs.read", RiskTier.T0)
