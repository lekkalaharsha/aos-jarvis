import os

import pytest

from aos.tools import fs_tools
from aos.safety.errors import DangerousPathBlocked, SymlinkEscapeBlocked
from aos.tools.fs_tools import read_file, write_file


@pytest.fixture(autouse=True)
def isolated_phase1_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "DEFAULT_AUDIT_PATH", tmp_path / "audit.db")


def test_path_traversal_like_ssh_key_is_blocked(tmp_path):
    root = tmp_path / "project"
    root.mkdir()

    with pytest.raises(DangerousPathBlocked):
        read_file("../../.ssh/id_rsa", approved_roots=[root])


def test_symlink_escape_outside_approved_root_is_blocked(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "note.txt"
    secret.write_text("outside", encoding="utf-8")
    link = root / "escape.txt"
    try:
        os.symlink(secret, link)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(SymlinkEscapeBlocked):
        read_file(link, approved_roots=[root])


def test_blocked_action_does_not_modify_file(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    target = root / ".env"

    with pytest.raises(Exception):
        write_file(target, "SECRET=1", approved=True, approved_roots=[root])

    assert not target.exists()
