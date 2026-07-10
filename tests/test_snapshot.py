from aos.safety.audit import list_events
from aos.safety.snapshots import create_snapshot, get_snapshot, list_snapshots, restore_snapshot


def test_snapshot_restore_works_and_audits(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    file_path = root / "a.txt"
    file_path.write_text("before", encoding="utf-8")
    snapshots_dir = tmp_path / "snapshots"
    audit_path = tmp_path / "audit.db"

    snapshot = create_snapshot(
        file_path,
        reason="test",
        created_by_action="test",
        approved_roots=[root],
        snapshots_dir=snapshots_dir,
        audit_path=audit_path,
    )
    file_path.write_text("after", encoding="utf-8")

    restored = restore_snapshot(
        snapshot.snapshot_id,
        approved_roots=[root],
        snapshots_dir=snapshots_dir,
        audit_path=audit_path,
    )

    assert restored.snapshot_id == snapshot.snapshot_id
    assert file_path.read_text(encoding="utf-8") == "before"
    assert get_snapshot(snapshot.snapshot_id, snapshots_dir=snapshots_dir).original_path == str(file_path.resolve())
    assert len(list_snapshots(snapshots_dir=snapshots_dir)) == 2
    assert any(event.event_type == "snapshot.restore" for event in list_events(audit_path))
