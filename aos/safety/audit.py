"""Append-only, hash-chained audit log backed by SQLite.

event_hash = sha256(canonical_json_of_event_without_event_hash + parent_hash)
Canonical JSON uses sort_keys=True so hashing is deterministic.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aos.config.loader import DATA_DIR

GENESIS_HASH = "0" * 64
DEFAULT_AUDIT_PATH = DATA_DIR / "audit" / "audit.db"


@dataclass(frozen=True)
class AuditEvent:
    id: int
    timestamp: str
    actor: str
    event_type: str
    action: str
    resource: str
    risk_tier: str
    status: str
    payload_json: str
    parent_hash: str
    event_hash: str


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _compute_event_hash(payload_without_hash: dict, parent_hash: str) -> str:
    canonical = _canonical_json(payload_without_hash)
    return hashlib.sha256((canonical + parent_hash).encode("utf-8")).hexdigest()


def init_audit_db(db_path: Path = DEFAULT_AUDIT_PATH) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                risk_tier TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                parent_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL
            )
            """
        )
        conn.commit()
    return db_path


def _last_event_hash(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else GENESIS_HASH


def append_event(
    db_path: Path,
    actor: str,
    event_type: str,
    action: str,
    resource: str,
    risk_tier: str,
    status: str,
    payload: dict | None = None,
) -> AuditEvent:
    init_audit_db(db_path)
    payload_json = _canonical_json(payload or {})
    timestamp = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        parent_hash = _last_event_hash(conn)
        payload_for_hash = {
            "timestamp": timestamp,
            "actor": actor,
            "event_type": event_type,
            "action": action,
            "resource": resource,
            "risk_tier": risk_tier,
            "status": status,
            "payload_json": payload_json,
        }
        event_hash = _compute_event_hash(payload_for_hash, parent_hash)

        cursor = conn.execute(
            """
            INSERT INTO audit_events
                (timestamp, actor, event_type, action, resource, risk_tier,
                 status, payload_json, parent_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                actor,
                event_type,
                action,
                resource,
                risk_tier,
                status,
                payload_json,
                parent_hash,
                event_hash,
            ),
        )
        conn.commit()
        event_id = cursor.lastrowid

    return AuditEvent(id=event_id, parent_hash=parent_hash, event_hash=event_hash, **payload_for_hash)


def list_events(db_path: Path) -> list[AuditEvent]:
    init_audit_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, timestamp, actor, event_type, action, resource, risk_tier,
                   status, payload_json, parent_hash, event_hash
            FROM audit_events ORDER BY id ASC
            """
        ).fetchall()
    return [AuditEvent(*row) for row in rows]


@dataclass(frozen=True)
class ChainVerificationResult:
    valid: bool
    checked_count: int
    first_broken_id: int | None = None
    reason: str | None = None


def verify_chain(db_path: Path) -> ChainVerificationResult:
    events = list_events(db_path)
    parent_hash = GENESIS_HASH

    for event in events:
        if event.parent_hash != parent_hash:
            return ChainVerificationResult(
                valid=False,
                checked_count=event.id,
                first_broken_id=event.id,
                reason="broken parent_hash continuity",
            )

        payload_for_hash = {
            "timestamp": event.timestamp,
            "actor": event.actor,
            "event_type": event.event_type,
            "action": event.action,
            "resource": event.resource,
            "risk_tier": event.risk_tier,
            "status": event.status,
            "payload_json": event.payload_json,
        }
        expected_hash = _compute_event_hash(payload_for_hash, parent_hash)
        if expected_hash != event.event_hash:
            return ChainVerificationResult(
                valid=False,
                checked_count=event.id,
                first_broken_id=event.id,
                reason="event data does not match event_hash",
            )

        parent_hash = event.event_hash

    return ChainVerificationResult(valid=True, checked_count=len(events))
