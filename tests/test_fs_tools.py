import pytest

from aos.safety.audit import list_events
from aos.safety.errors import ApprovalRequired, BinaryFileBlocked, PermissionBlocked
from aos.safety.risk import RiskTier, classify_file_action
from aos.tools import fs_tools
from aos.tools.fs_tools import (
    edit_file,
    list_dir,
    preview_edit,
    read_file,
    search_files,
    write_file,
)


@pytest.fixture()
def isolated_fs(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.db"
    snapshots_dir = tmp_path / "snapshots"
    monkeypatch.setattr(fs_tools, "DEFAULT_AUDIT_PATH", audit_path)
    import aos.safety.snapshots as snapshots

    monkeypatch.setattr(snapshots, "SNAPSHOTS_DIR", snapshots_dir)
    return {"root": tmp_path / "project", "audit": audit_path, "snapshots": snapshots_dir}


def test_allowed_project_file_can_be_read(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    file_path = root / "note.txt"
    file_path.write_text("hello", encoding="utf-8")

    assert read_file(file_path, approved_roots=[root]) == "hello"


def test_write_and_edit_risk_tiers_match_classify_file_action(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    file_path = root / "a.txt"
    file_path.write_text("before", encoding="utf-8")

    write_result = write_file(file_path, "after", approved=True, approved_roots=[root])
    assert write_result.risk_tier == classify_file_action("write") == RiskTier.T1

    file_path.write_text("hello old\n", encoding="utf-8")
    edit_result = edit_file(file_path, "old", "new", approved=True, approved_roots=[root])
    assert edit_result.risk_tier == classify_file_action("edit") == RiskTier.T1


def test_allowed_project_directory_can_be_listed(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")

    assert list_dir(root, approved_roots=[root]) == ["a.txt"]


def test_allowed_project_files_can_be_searched(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    (root / "a.txt").write_text("find me\n", encoding="utf-8")

    results = search_files("find", root=root, approved_roots=[root])

    assert len(results) == 1
    assert results[0][1] == 1


def test_blocked_dangerous_and_secret_paths_are_denied(isolated_fs, tmp_path):
    root = isolated_fs["root"]
    root.mkdir()
    for blocked in ("/etc/passwd", "~/.ssh/id_rsa", root / ".env", root / "secret.pem"):
        with pytest.raises(Exception):
            read_file(blocked, approved_roots=[root])


def test_write_outside_approved_root_is_blocked(isolated_fs, tmp_path):
    root = isolated_fs["root"]
    root.mkdir()
    outside = tmp_path / "outside.txt"

    with pytest.raises(PermissionBlocked):
        write_file(outside, "x", approved=True, approved_roots=[root])

    assert not outside.exists()


def test_write_requires_approval_and_does_not_modify(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    file_path = root / "a.txt"
    file_path.write_text("before", encoding="utf-8")

    with pytest.raises(ApprovalRequired):
        write_file(file_path, "after", approved=False, approved_roots=[root])

    assert file_path.read_text(encoding="utf-8") == "before"


def test_snapshot_is_created_before_write_to_existing_file(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    file_path = root / "a.txt"
    file_path.write_text("before", encoding="utf-8")

    result = write_file(file_path, "after", approved=True, approved_roots=[root])

    assert result.snapshot is not None
    assert file_path.read_text(encoding="utf-8") == "after"
    assert isolated_fs["snapshots"].exists()


def test_snapshot_is_created_before_edit_and_diff_is_generated(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    file_path = root / "a.txt"
    file_path.write_text("hello old\n", encoding="utf-8")

    preview = preview_edit(file_path, "old", "new", approved_roots=[root])
    result = edit_file(file_path, "old", "new", approved=True, approved_roots=[root])

    assert "-hello old" in preview.diff
    assert "+hello new" in preview.diff
    assert result.snapshot is not None
    assert file_path.read_text(encoding="utf-8") == "hello new\n"


def test_binary_file_edit_is_blocked(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    file_path = root / "binary.bin"
    file_path.write_bytes(b"a\x00b")

    with pytest.raises(BinaryFileBlocked):
        edit_file(file_path, "a", "b", approved=True, approved_roots=[root])


def test_failed_edit_when_old_text_missing_does_not_modify_file(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    file_path = root / "a.txt"
    file_path.write_text("content", encoding="utf-8")

    with pytest.raises(ValueError):
        edit_file(file_path, "missing", "new", approved=True, approved_roots=[root])

    assert file_path.read_text(encoding="utf-8") == "content"


def test_audit_events_are_written_for_allowed_and_blocked_actions(isolated_fs):
    root = isolated_fs["root"]
    root.mkdir()
    file_path = root / "a.txt"
    file_path.write_text("content", encoding="utf-8")

    read_file(file_path, approved_roots=[root])
    with pytest.raises(Exception):
        read_file(root / ".env", approved_roots=[root])

    events = list_events(isolated_fs["audit"])
    assert any(event.event_type == "fs.read" for event in events)
    assert any(event.event_type == "fs.blocked" for event in events)
