import sqlite3

from aos.safety.audit import append_event, init_audit_db, list_events, verify_chain


def _make_db(tmp_path):
    db_path = tmp_path / "audit.db"
    init_audit_db(db_path)
    return db_path


def _append(db_path, action, resource="target"):
    return append_event(db_path, "tester", "test_event", action, resource, "T0", "ALLOW")


def test_append_and_list(tmp_path):
    db_path = _make_db(tmp_path)
    _append(db_path, "did a thing", "target1")
    _append(db_path, "did another thing", "target2")

    events = list_events(db_path)
    assert len(events) == 2
    assert events[0].action == "did a thing"
    assert events[1].parent_hash == events[0].event_hash


def test_verify_chain_valid(tmp_path):
    db_path = _make_db(tmp_path)
    for i in range(3):
        _append(db_path, f"action-{i}")

    result = verify_chain(db_path)
    assert result.valid
    assert result.checked_count == 3


def test_verify_chain_detects_tampering(tmp_path):
    db_path = _make_db(tmp_path)
    _append(db_path, "action-0")
    _append(db_path, "action-1")

    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE audit_events SET action = 'tampered' WHERE id = 1")
        conn.commit()

    result = verify_chain(db_path)
    assert not result.valid
    assert result.first_broken_id == 1
