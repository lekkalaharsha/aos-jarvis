"""Unit tests for aos.dashboard.service — all read-only, no server required."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos.dashboard.service import (
    MAX_ROWS,
    ActivityData,
    DashboardAuditRow,
    DashboardService,
    ModelStatusData,
    OverviewData,
    SnapshotRow,
    _sanitize_display,
    _redact_payload,
)
from aos.safety.audit import append_event, init_audit_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(tmp_path: Path) -> DashboardService:
    audit_db = tmp_path / "audit" / "audit.db"
    init_audit_db(audit_db)
    return DashboardService(audit_db=audit_db, data_dir=tmp_path)


def _add_event(tmp_path: Path, **kwargs) -> None:
    audit_db = tmp_path / "audit" / "audit.db"
    defaults = dict(
        actor="test",
        event_type="test.event",
        action="test action",
        resource="res",
        risk_tier="T0",
        status="ALLOW",
    )
    defaults.update(kwargs)
    append_event(audit_db, **defaults)


# ---------------------------------------------------------------------------
# _redact_payload
# ---------------------------------------------------------------------------


def test_redact_payload_redacts_api_key():
    result = _redact_payload(json.dumps({"api_key": "sk-secret", "text": "hello"}))
    assert result["api_key"] == "[REDACTED]"
    assert result["text"] == "hello"


def test_redact_payload_redacts_token():
    result = _redact_payload(json.dumps({"token": "abc123", "count": 5}))
    assert result["token"] == "[REDACTED]"
    assert result["count"] == 5


def test_redact_payload_handles_invalid_json():
    result = _redact_payload("not-json{{{")
    assert result == {}


def test_redact_payload_handles_empty():
    assert _redact_payload("") == {}


def test_redact_payload_handles_non_dict_json():
    assert _redact_payload(json.dumps([1, 2, 3])) == {}


def test_redact_payload_truncates_oversized_metadata():
    assert _redact_payload("x" * 10_000) == {"payload": "[TRUNCATED]"}


@pytest.mark.parametrize("value", [
    "sk-test-secret",
    "Bearer abcdef",
    "Authorization: Basic xyz",
    "AWS_SECRET_ACCESS_KEY=example",
    "ghp_exampletoken",
    "-----BEGIN PRIVATE KEY-----",
    "password=example",
    "api_key=example",
])
def test_display_sanitizer_redacts_secret_shaped_values(value: str):
    assert _sanitize_display(value) == "[REDACTED]"


def test_redact_payload_redacts_nested_secret_values():
    result = _redact_payload(json.dumps({"metadata": {"provider_error": "Bearer abcdef"}}))
    assert result["metadata"]["provider_error"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# get_overview
# ---------------------------------------------------------------------------


def test_get_overview_returns_version(tmp_path: Path):
    svc = _make_service(tmp_path)
    overview = svc.get_overview()
    assert isinstance(overview, OverviewData)
    assert overview.version  # non-empty string


def test_get_overview_chain_valid_on_empty_db(tmp_path: Path):
    svc = _make_service(tmp_path)
    overview = svc.get_overview()
    assert overview.audit_chain_valid is True
    assert overview.audit_chain_count == 0


def test_get_overview_chain_count_matches_events(tmp_path: Path):
    _add_event(tmp_path)
    _add_event(tmp_path)
    svc = _make_service(tmp_path)
    overview = svc.get_overview()
    assert overview.audit_chain_count == 2


def test_dashboard_reads_do_not_initialize_missing_storage(tmp_path: Path):
    audit_db = tmp_path / "audit" / "audit.db"
    svc = DashboardService(audit_db=audit_db, data_dir=tmp_path)

    svc.get_overview()
    svc.get_audit_events()
    svc.get_permission_events()
    svc.get_security_events()
    svc.get_snapshots()
    svc.get_model_status()
    svc.get_activity()

    assert not audit_db.exists()
    assert not (tmp_path / "config.toml").exists()
    assert not (tmp_path / "memory" / "memory.db").exists()


# ---------------------------------------------------------------------------
# get_audit_events
# ---------------------------------------------------------------------------


def test_get_audit_events_returns_rows(tmp_path: Path):
    _add_event(tmp_path, action="action one")
    svc = _make_service(tmp_path)
    rows = svc.get_audit_events()
    assert len(rows) == 1
    assert isinstance(rows[0], DashboardAuditRow)
    assert rows[0].action == "action one"


def test_get_audit_events_limit_cap_enforced(tmp_path: Path):
    for i in range(10):
        _add_event(tmp_path, action=f"action {i}")
    svc = _make_service(tmp_path)
    rows = svc.get_audit_events(limit=100_000)
    assert len(rows) <= MAX_ROWS


def test_get_audit_events_limit_applied(tmp_path: Path):
    for i in range(10):
        _add_event(tmp_path, action=f"action {i}")
    svc = _make_service(tmp_path)
    rows = svc.get_audit_events(limit=3)
    assert len(rows) == 3


def test_get_audit_events_most_recent_first(tmp_path: Path):
    _add_event(tmp_path, action="first")
    _add_event(tmp_path, action="second")
    svc = _make_service(tmp_path)
    rows = svc.get_audit_events()
    assert rows[0].action == "second"
    assert rows[1].action == "first"


def test_get_audit_events_payload_api_key_redacted(tmp_path: Path):
    audit_db = tmp_path / "audit" / "audit.db"
    init_audit_db(audit_db)
    append_event(
        audit_db,
        actor="test",
        event_type="test.event",
        action="act",
        resource="res",
        risk_tier="T0",
        status="ALLOW",
        payload={"api_key": "sk-topsecret", "model": "gpt-4"},
    )
    svc = DashboardService(audit_db=audit_db, data_dir=tmp_path)
    rows = svc.get_audit_events()
    assert rows[0].payload.get("api_key") == "[REDACTED]"
    assert rows[0].payload.get("model") == "gpt-4"


def test_get_audit_events_redacts_secret_shaped_display_columns(tmp_path: Path):
    _add_event(
        tmp_path,
        actor="Bearer abcdef",
        event_type="ghp_exampletoken",
        action="password=example",
        resource="sk-test-secret",
    )
    row = _make_service(tmp_path).get_audit_events()[0]
    assert row.actor == row.event_type == row.action == row.resource == "[REDACTED]"


# ---------------------------------------------------------------------------
# get_permission_events
# ---------------------------------------------------------------------------


def test_get_permission_events_filters_allow_deny(tmp_path: Path):
    _add_event(tmp_path, status="ALLOW", action="read file")
    _add_event(tmp_path, status="DENY", action="blocked write")
    _add_event(tmp_path, status="INFO", action="unrelated")
    svc = _make_service(tmp_path)
    rows = svc.get_permission_events()
    statuses = {r.status for r in rows}
    assert "ALLOW" in statuses
    assert "DENY" in statuses
    info_rows = [r for r in rows if r.status == "INFO"]
    assert not info_rows


# ---------------------------------------------------------------------------
# get_security_events
# ---------------------------------------------------------------------------


def test_get_security_events_filters_denied_only(tmp_path: Path):
    _add_event(tmp_path, status="ALLOW", action="allowed")
    _add_event(tmp_path, status="DENY", action="denied")
    _add_event(tmp_path, status="BLOCK", action="blocked")
    svc = _make_service(tmp_path)
    rows = svc.get_security_events()
    assert all(r.status in ("DENY", "BLOCK", "BLOCKED") or r.risk_tier == "T3" for r in rows)
    allow_rows = [r for r in rows if r.status == "ALLOW" and r.risk_tier != "T3"]
    assert not allow_rows


# ---------------------------------------------------------------------------
# get_snapshots
# ---------------------------------------------------------------------------


def test_get_snapshots_empty_when_dir_missing(tmp_path: Path):
    svc = _make_service(tmp_path)
    rows = svc.get_snapshots()
    assert rows == []


def test_get_snapshots_returns_list(tmp_path: Path):
    svc = _make_service(tmp_path)
    result = svc.get_snapshots()
    assert isinstance(result, list)


def test_get_snapshots_reads_metadata_and_redacts_reason(tmp_path: Path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / "one.json").write_text(json.dumps({
        "snapshot_id": "one",
        "original_path": "/project/file.txt",
        "snapshot_path": "/snapshots/one.snapshot",
        "timestamp": "2026-07-11T00:00:00+00:00",
        "sha256_before": "a" * 64,
        "size_bytes": 1,
        "reason": "password=example",
        "created_by_action": "fs.write",
    }), encoding="utf-8")
    rows = _make_service(tmp_path).get_snapshots()
    assert len(rows) == 1
    assert rows[0].reason == "[REDACTED]"


# ---------------------------------------------------------------------------
# get_model_status
# ---------------------------------------------------------------------------


def test_get_model_status_defaults_when_no_config(tmp_path: Path):
    svc = _make_service(tmp_path)
    status = svc.get_model_status()
    assert isinstance(status, ModelStatusData)
    assert status.default_provider == "local"
    assert status.allow_cloud is False
    assert status.local_enabled is True
    assert status.cloud_enabled is False


# ---------------------------------------------------------------------------
# get_activity
# ---------------------------------------------------------------------------


def test_get_activity_returns_activity_data(tmp_path: Path):
    svc = _make_service(tmp_path)
    act = svc.get_activity()
    assert isinstance(act, ActivityData)
    assert isinstance(act.timeline, list)


def test_get_activity_graceful_when_memory_db_missing(tmp_path: Path):
    svc = _make_service(tmp_path)
    act = svc.get_activity()
    assert act.indexed_event_count == 0
    assert act.schema_version in ("unknown", "1.0")


def test_get_activity_limit_cap_enforced(tmp_path: Path):
    svc = _make_service(tmp_path)
    act = svc.get_activity(limit=100_000)
    assert isinstance(act, ActivityData)
