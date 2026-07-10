"""Snapshot storage for Phase 1 reversible file operations."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aos.config.loader import SNAPSHOTS_DIR
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.safety.errors import PermissionBlocked
from aos.safety.paths import validate_path
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import classify_file_action


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    original_path: str
    snapshot_path: str
    timestamp: str
    sha256_before: str
    size_bytes: int
    reason: str | None
    created_by_action: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_path(snapshot_id: str, snapshots_dir: Path) -> Path:
    return snapshots_dir / f"{snapshot_id}.json"


def _from_metadata(data: dict) -> Snapshot:
    return Snapshot(
        snapshot_id=data["snapshot_id"],
        original_path=data["original_path"],
        snapshot_path=data["snapshot_path"],
        timestamp=data["timestamp"],
        sha256_before=data["sha256_before"],
        size_bytes=int(data["size_bytes"]),
        reason=data.get("reason"),
        created_by_action=data["created_by_action"],
    )


def create_snapshot(
    file_path: str | Path,
    reason: str | None = None,
    *,
    created_by_action: str = "unknown",
    approved_roots: list[str | Path] | None = None,
    snapshots_dir: Path | None = None,
    audit_path: Path | None = None,
) -> Snapshot:
    snapshots_dir = snapshots_dir or SNAPSHOTS_DIR
    audit_path = audit_path or DEFAULT_AUDIT_PATH
    original = validate_path(file_path, approved_roots)
    if not original.exists() or not original.is_file():
        raise FileNotFoundError(f"cannot snapshot missing file: {original}")

    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = uuid.uuid4().hex
    snapshot_path = snapshots_dir / f"{snapshot_id}.snapshot"
    shutil.copy2(original, snapshot_path)

    snapshot = Snapshot(
        snapshot_id=snapshot_id,
        original_path=str(original),
        snapshot_path=str(snapshot_path),
        timestamp=datetime.now(timezone.utc).isoformat(),
        sha256_before=_sha256(original),
        size_bytes=original.stat().st_size,
        reason=reason,
        created_by_action=created_by_action,
    )
    _metadata_path(snapshot_id, snapshots_dir).write_text(
        json.dumps(snapshot.__dict__, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    append_event(
        audit_path,
        actor="fs",
        event_type="snapshot.create",
        action="snapshot.create",
        resource=str(original),
        risk_tier=classify_file_action("create").value,
        status="ALLOW",
        payload=snapshot.__dict__,
    )
    return snapshot


def list_snapshots(*, snapshots_dir: Path | None = None) -> list[Snapshot]:
    snapshots_dir = snapshots_dir or SNAPSHOTS_DIR
    if not snapshots_dir.exists():
        return []
    snapshots: list[Snapshot] = []
    for metadata_path in sorted(snapshots_dir.glob("*.json")):
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        snapshots.append(_from_metadata(data))
    return snapshots


def get_snapshot(snapshot_id: str, *, snapshots_dir: Path | None = None) -> Snapshot:
    snapshots_dir = snapshots_dir or SNAPSHOTS_DIR
    metadata_path = _metadata_path(snapshot_id, snapshots_dir)
    if not metadata_path.exists():
        raise FileNotFoundError(f"snapshot not found: {snapshot_id}")
    return _from_metadata(json.loads(metadata_path.read_text(encoding="utf-8")))


def restore_snapshot(
    snapshot_id: str,
    *,
    approved_roots: list[str | Path] | None = None,
    snapshots_dir: Path | None = None,
    audit_path: Path | None = None,
) -> Snapshot:
    snapshots_dir = snapshots_dir or SNAPSHOTS_DIR
    audit_path = audit_path or DEFAULT_AUDIT_PATH
    snapshot = get_snapshot(snapshot_id, snapshots_dir=snapshots_dir)
    restore_risk = classify_file_action("restore")
    original = PermissionEngine(approved_roots).require_path(
        snapshot.original_path, "snapshot.restore", restore_risk
    )
    snapshot_file = Path(snapshot.snapshot_path)
    if not snapshot_file.exists():
        raise FileNotFoundError(f"snapshot payload missing: {snapshot.snapshot_path}")

    current_snapshot_id = None
    if original.exists():
        current = create_snapshot(
            original,
            reason=f"pre-restore {snapshot_id}",
            created_by_action="snapshot.restore",
            approved_roots=approved_roots,
            snapshots_dir=snapshots_dir,
            audit_path=audit_path,
        )
        current_snapshot_id = current.snapshot_id

    if not original.parent.exists():
        raise PermissionBlocked(f"restore target parent does not exist: {original.parent}")

    shutil.copy2(snapshot_file, original)
    append_event(
        audit_path,
        actor="fs",
        event_type="snapshot.restore",
        action="snapshot.restore",
        resource=str(original),
        risk_tier=restore_risk.value,
        status="ALLOW",
        payload={
            "snapshot_id": snapshot.snapshot_id,
            "path": str(original),
            "pre_restore_snapshot_id": current_snapshot_id,
            "sha256_after": _sha256(original),
        },
    )
    return snapshot
