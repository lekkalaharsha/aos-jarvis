"""Read-only data service for the AOS-Jarvis dashboard.

All methods return plain data structures.  Nothing here mutates system state.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aos import __version__
from aos.config.loader import DATA_DIR
from aos.safety.audit import DEFAULT_AUDIT_PATH, GENESIS_HASH, AuditEvent, _compute_event_hash

MAX_ROWS: int = 200
MAX_AUDIT_VERIFY_EVENTS: int = 10_000

_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "api_key", "token", "secret", "password", "key", "auth",
    "authorization", "credential", "bearer", "private",
})

_MAX_DISPLAY_CHARS = 4096
_SECRET_VALUE_PATTERN = re.compile(
    r"(?is)(?:\bsk-[^\s]+|\bgh[pousr]_[^\s]+|\bbearer\s+\S+|"
    r"\bauthorization\s*:\s*(?:basic|bearer)\s+\S+|"
    r"\baws_secret_access_key\s*=\s*\S+|"
    r"-----begin(?: [a-z ]+)? private key-----|"
    r"\b(?:password|api[_-]?key|token|secret|credential)\s*[:=]\s*\S+|"
    r"(?:^|[\\/])\.env(?:$|[\\/])|(?:^|[\\/])\.ssh(?:$|[\\/]))"
)


def _is_sensitive_key(key: str) -> bool:
    return any(s in key.lower() for s in _SENSITIVE_KEYS)


def _sanitize_display(value: Any, *, key: str = "") -> Any:
    """Return bounded, recursively redacted data safe for HTML display."""
    if key and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, str):
        text = value[:_MAX_DISPLAY_CHARS]
        if _SECRET_VALUE_PATTERN.search(text):
            return "[REDACTED]"
        return text
    if isinstance(value, dict):
        return {str(k): _sanitize_display(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_display(item) for item in value[:MAX_ROWS]]
    if isinstance(value, tuple):
        return tuple(_sanitize_display(item) for item in value[:MAX_ROWS])
    return value


def _redact_payload(payload_json: str) -> dict[str, Any]:
    """Parse payload JSON and redact fields with sensitive-sounding names."""
    if len(payload_json) > _MAX_DISPLAY_CHARS:
        return {"payload": "[TRUNCATED]"}
    try:
        data: Any = json.loads(payload_json) if payload_json else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return _sanitize_display(data)


@dataclass(frozen=True)
class DashboardAuditRow:
    id: int
    timestamp: str
    actor: str
    event_type: str
    action: str
    resource: str
    risk_tier: str
    status: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OverviewData:
    version: str
    data_dir: str
    config: dict[str, Any]
    audit_chain_valid: bool
    audit_chain_count: int
    audit_chain_reason: str


@dataclass(frozen=True)
class SnapshotRow:
    snapshot_id: str
    original_path: str
    timestamp: str
    sha256_before: str
    size_bytes: int
    reason: str
    created_by_action: str


@dataclass(frozen=True)
class ModelStatusData:
    default_provider: str
    allow_cloud: bool
    local_enabled: bool
    cloud_enabled: bool


@dataclass(frozen=True)
class ActivityData:
    indexed_event_count: int
    entity_count: int
    timeline_count: int
    last_indexed_audit_event: int
    schema_version: str
    timeline: list[dict[str, str]] = field(default_factory=list)


class DashboardService:
    """Aggregates read-only data views for the AOS-Jarvis dashboard."""

    def __init__(
        self,
        audit_db: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self._audit_db = audit_db or DEFAULT_AUDIT_PATH
        self._data_dir = data_dir or DATA_DIR

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    def get_overview(self) -> OverviewData:
        chain_valid, chain_count, chain_reason = self._verify_audit_chain()
        try:
            config = self._read_config()
        except Exception:
            config = {}
        return OverviewData(
            version=__version__,
            data_dir=str(_sanitize_display(str(self._data_dir))),
            config=config,
            audit_chain_valid=chain_valid,
            audit_chain_count=chain_count,
            audit_chain_reason=chain_reason,
        )

    # ------------------------------------------------------------------
    # Audit events (internal helper + public API)
    # ------------------------------------------------------------------

    def _read_config(self) -> dict[str, Any]:
        config_path = self._data_dir / "config.toml"
        if not config_path.is_file():
            return {}
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
        return _sanitize_display(data)

    def _read_events(self, *, where: str = "", params: tuple[object, ...] = (), limit: int = MAX_ROWS) -> list[AuditEvent]:
        """Read audit rows without initializing or repairing the audit database."""
        limit = max(1, min(limit, MAX_ROWS))
        if not self._audit_db.is_file():
            return []
        query = (
            "SELECT id, timestamp, actor, event_type, action, resource, risk_tier, "
            "status, payload_json, parent_hash, event_hash FROM audit_events"
        )
        if where:
            query += f" WHERE {where}"
        query += " ORDER BY id DESC LIMIT ?"
        try:
            with sqlite3.connect(f"{self._audit_db.resolve().as_uri()}?mode=ro", uri=True) as conn:
                rows = conn.execute(query, (*params, limit)).fetchall()
        except (OSError, sqlite3.Error, ValueError):
            return []
        return [AuditEvent(*row) for row in rows]

    def _verify_audit_chain(self) -> tuple[bool, int, str]:
        """Verify the existing chain without creating an empty audit database."""
        if not self._audit_db.is_file():
            return True, 0, ""
        try:
            with sqlite3.connect(f"{self._audit_db.resolve().as_uri()}?mode=ro", uri=True) as conn:
                rows = conn.execute(
                    "SELECT id, timestamp, actor, event_type, action, resource, risk_tier, "
                    "status, payload_json, parent_hash, event_hash FROM audit_events "
                    "ORDER BY id ASC LIMIT ?",
                    (MAX_AUDIT_VERIFY_EVENTS + 1,),
                ).fetchall()
        except (OSError, sqlite3.Error, ValueError):
            return False, 0, "audit data unavailable"
        if len(rows) > MAX_AUDIT_VERIFY_EVENTS:
            return False, MAX_AUDIT_VERIFY_EVENTS, "audit verification limit reached"
        parent_hash = GENESIS_HASH
        for row in rows:
            event = AuditEvent(*row)
            if event.parent_hash != parent_hash:
                return False, event.id, "broken audit chain"
            payload = {
                "timestamp": event.timestamp,
                "actor": event.actor,
                "event_type": event.event_type,
                "action": event.action,
                "resource": event.resource,
                "risk_tier": event.risk_tier,
                "status": event.status,
                "payload_json": event.payload_json,
            }
            if _compute_event_hash(payload, parent_hash) != event.event_hash:
                return False, event.id, "invalid audit event"
            parent_hash = event.event_hash
        return True, len(rows), ""

    def _rows_from_events(self, events: list[AuditEvent]) -> list[DashboardAuditRow]:
        rows: list[DashboardAuditRow] = []
        for ev in events:
            rows.append(DashboardAuditRow(
                id=ev.id,
                timestamp=_sanitize_display(ev.timestamp),
                actor=_sanitize_display(ev.actor),
                event_type=_sanitize_display(ev.event_type),
                action=_sanitize_display(ev.action),
                resource=_sanitize_display(ev.resource),
                risk_tier=_sanitize_display(ev.risk_tier),
                status=_sanitize_display(ev.status),
                payload=_redact_payload(ev.payload_json),
            ))
        return rows

    def get_audit_events(self, limit: int = MAX_ROWS) -> list[DashboardAuditRow]:
        limit = max(1, min(limit, MAX_ROWS))
        return self._rows_from_events(self._read_events(limit=limit))

    def get_permission_events(self, limit: int = MAX_ROWS) -> list[DashboardAuditRow]:
        limit = max(1, min(limit, MAX_ROWS))
        return self._rows_from_events(self._read_events(
            where="status IN ('ALLOW', 'DENY', 'BLOCK', 'BLOCKED') OR lower(event_type) LIKE '%permission%'",
            limit=limit,
        ))

    def get_security_events(self, limit: int = MAX_ROWS) -> list[DashboardAuditRow]:
        limit = max(1, min(limit, MAX_ROWS))
        return self._rows_from_events(self._read_events(
            where="status IN ('DENY', 'BLOCK', 'BLOCKED') OR lower(event_type) LIKE '%blocked%' OR risk_tier = 'T3'",
            limit=limit,
        ))

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def get_snapshots(self, limit: int = MAX_ROWS) -> list[SnapshotRow]:
        limit = max(1, min(limit, MAX_ROWS))
        try:
            from aos.safety.snapshots import list_snapshots
            snaps = list_snapshots(snapshots_dir=self._data_dir / "snapshots")
        except Exception:
            return []
        result: list[SnapshotRow] = []
        for s in snaps[:limit]:
            result.append(SnapshotRow(
                snapshot_id=_sanitize_display(s.snapshot_id),
                original_path=_sanitize_display(s.original_path),
                timestamp=_sanitize_display(s.timestamp),
                sha256_before=_sanitize_display(s.sha256_before),
                size_bytes=s.size_bytes,
                reason=str(_sanitize_display(s.reason) or ""),
                created_by_action=_sanitize_display(s.created_by_action),
            ))
        return result

    # ------------------------------------------------------------------
    # Model status
    # ------------------------------------------------------------------

    def get_model_status(self) -> ModelStatusData:
        try:
            from aos.model.config import cloud_api_key_present, model_config_from_dict
            cfg = model_config_from_dict(self._read_config())
            cloud_key_present = cloud_api_key_present(cfg)
            return ModelStatusData(
                default_provider=cfg.default_provider.value,
                allow_cloud=cfg.allow_cloud,
                local_enabled=True,
                cloud_enabled=cfg.allow_cloud and cloud_key_present,
            )
        except Exception:
            return ModelStatusData(
                default_provider="local",
                allow_cloud=False,
                local_enabled=True,
                cloud_enabled=False,
            )

    # ------------------------------------------------------------------
    # Memory / project activity
    # ------------------------------------------------------------------

    def get_activity(self, limit: int = MAX_ROWS) -> ActivityData:
        limit = max(1, min(limit, MAX_ROWS))
        try:
            memory_db = self._data_dir / "memory" / "memory.db"
            if not memory_db.is_file():
                raise FileNotFoundError(memory_db)
            with sqlite3.connect(f"{memory_db.resolve().as_uri()}?mode=ro", uri=True) as conn:
                indexed = conn.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0]
                entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
                total_timeline = conn.execute("SELECT COUNT(*) FROM timeline_entries").fetchone()[0]
                metadata = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
                timeline = conn.execute(
                    "SELECT timestamp, title, description, category FROM timeline_entries ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            tl_rows: list[dict[str, str]] = [
                {
                    "timestamp": _sanitize_display(t[0]),
                    "title": _sanitize_display(t[1]),
                    "description": _sanitize_display(t[2]),
                    "category": _sanitize_display(t[3]),
                }
                for t in timeline
            ]
            return ActivityData(
                indexed_event_count=int(indexed),
                entity_count=int(entities),
                timeline_count=int(total_timeline),
                last_indexed_audit_event=int(metadata.get("last_indexed_audit_event", 0)),
                schema_version=_sanitize_display(metadata.get("schema_version", "unknown")),
                timeline=tl_rows,
            )
        except Exception:
            return ActivityData(
                indexed_event_count=0,
                entity_count=0,
                timeline_count=0,
                last_indexed_audit_event=0,
                schema_version="unknown",
                timeline=[],
            )
