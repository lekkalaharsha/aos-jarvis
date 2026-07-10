"""Permissioned Phase 1 file tools."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path

from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.safety.errors import ApprovalRequired, BinaryFileBlocked
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import RiskTier, classify_file_action
from aos.safety.snapshots import Snapshot, create_snapshot

MAX_DISPLAY_BYTES = 1024 * 1024


@dataclass(frozen=True)
class WritePreview:
    path: str
    risk_tier: RiskTier
    existed: bool
    snapshot: Snapshot | None
    diff: str
    sha256_before: str | None


@dataclass(frozen=True)
class WriteResult:
    path: str
    risk_tier: RiskTier
    snapshot: Snapshot | None
    sha256_before: str | None
    sha256_after: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _audit(action: str, path: str, risk: RiskTier, allowed: bool, **payload: object) -> None:
    append_event(
        DEFAULT_AUDIT_PATH,
        actor="fs",
        event_type=action,
        action=action,
        resource=path,
        risk_tier=risk.value,
        status="ALLOW" if allowed else "DENY",
        payload={"path": path, "allowed": allowed, "risk_tier": risk.value, **payload},
    )


def _require_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data:
        raise BinaryFileBlocked(f"binary file blocked: {path}")
    if len(data) > MAX_DISPLAY_BYTES:
        raise BinaryFileBlocked(f"file too large for safe text display: {path}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BinaryFileBlocked(f"non-utf8 file blocked: {path}") from exc


def _engine(approved_roots: list[str | Path] | None = None) -> PermissionEngine:
    return PermissionEngine(approved_roots=approved_roots)


def list_dir(path: str | Path, *, approved_roots: list[str | Path] | None = None) -> list[str]:
    risk = classify_file_action("list")
    try:
        resolved = _engine(approved_roots).require_path(path, "fs.list", risk)
        if not resolved.is_dir():
            raise NotADirectoryError(str(resolved))
        result = sorted(child.name for child in resolved.iterdir())
        _audit("fs.list", str(resolved), risk, True, capability="fs.list", reason="allowed")
        return result
    except Exception as exc:
        _audit("fs.blocked", str(path), RiskTier.T3, False, capability="fs.list", reason="blocked", error=str(exc))
        raise


def read_file(path: str | Path, *, approved_roots: list[str | Path] | None = None) -> str:
    risk = classify_file_action("read")
    try:
        resolved = _engine(approved_roots).require_path(path, "fs.read", risk)
        text = _require_text(resolved)
        _audit("fs.read", str(resolved), risk, True, capability="fs.read", reason="allowed")
        return text
    except Exception as exc:
        _audit("fs.blocked", str(path), RiskTier.T3, False, capability="fs.read", reason="blocked", error=str(exc))
        raise


def search_files(
    query: str,
    root: str | Path = ".",
    *,
    approved_roots: list[str | Path] | None = None,
) -> list[tuple[str, int, str]]:
    risk = classify_file_action("search")
    results: list[tuple[str, int, str]] = []
    try:
        resolved_root = _engine(approved_roots).require_path(root, "fs.search", risk)
        for path in resolved_root.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = read_file(path, approved_roots=approved_roots)
            except Exception:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if query in line:
                    results.append((str(path), line_number, line))
        _audit("fs.search", str(resolved_root), risk, True, capability="fs.search", reason="allowed", query=query)
        return results
    except Exception as exc:
        _audit("fs.blocked", str(root), RiskTier.T3, False, capability="fs.search", reason="blocked", error=str(exc))
        raise


def preview_write(
    path: str | Path,
    content: str,
    *,
    approved_roots: list[str | Path] | None = None,
    action: str = "fs.write.preview",
) -> WritePreview:
    risk = classify_file_action("write")
    try:
        resolved = _engine(approved_roots).require_path(path, "fs.write", risk)
        existed = resolved.exists()
        before = _require_text(resolved) if existed else ""
        sha_before = _sha256(resolved) if existed else None
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=str(resolved),
                tofile=str(resolved),
            )
        )
        _audit(action, str(resolved), risk, True, capability="fs.write", reason="preview", sha256_before=sha_before)
        return WritePreview(str(resolved), risk, existed, None, diff, sha_before)
    except Exception as exc:
        _audit("fs.blocked", str(path), RiskTier.T3, False, capability="fs.write", reason="blocked", error=str(exc))
        raise


def write_file(
    path: str | Path,
    content: str,
    *,
    approved: bool = False,
    approved_roots: list[str | Path] | None = None,
) -> WriteResult:
    preview = preview_write(path, content, approved_roots=approved_roots)
    if not approved:
        raise ApprovalRequired("write requires explicit approval")
    resolved = Path(preview.path)
    snapshot = None
    if resolved.exists():
        snapshot = create_snapshot(
            resolved,
            reason="write_file",
            created_by_action="fs.write.apply",
            approved_roots=approved_roots,
            audit_path=DEFAULT_AUDIT_PATH,
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(content.encode("utf-8"))
    sha_after = _sha256(resolved)
    _audit(
        "fs.write.apply",
        str(resolved),
        preview.risk_tier,
        True,
        capability="fs.write",
        reason="applied",
        snapshot_id=snapshot.snapshot_id if snapshot else None,
        sha256_before=preview.sha256_before,
        sha256_after=sha_after,
    )
    return WriteResult(str(resolved), preview.risk_tier, snapshot, preview.sha256_before, sha_after)


def preview_edit(
    path: str | Path,
    old_text: str,
    new_text: str,
    *,
    approved_roots: list[str | Path] | None = None,
) -> WritePreview:
    risk = classify_file_action("edit")
    try:
        resolved = _engine(approved_roots).require_path(path, "fs.edit", risk)
        before = _require_text(resolved)
        if old_text not in before:
            raise ValueError("old_text not found; file was not modified")
        after = before.replace(old_text, new_text, 1)
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=str(resolved),
                tofile=str(resolved),
            )
        )
        sha_before = _sha256(resolved)
        _audit("fs.edit.preview", str(resolved), risk, True, capability="fs.edit", reason="preview", sha256_before=sha_before)
        return WritePreview(str(resolved), risk, True, None, diff, sha_before)
    except Exception as exc:
        _audit("fs.blocked", str(path), RiskTier.T3, False, capability="fs.edit", reason="blocked", error=str(exc))
        raise


def edit_file(
    path: str | Path,
    old_text: str,
    new_text: str,
    *,
    approved: bool = False,
    approved_roots: list[str | Path] | None = None,
) -> WriteResult:
    preview = preview_edit(path, old_text, new_text, approved_roots=approved_roots)
    if not approved:
        raise ApprovalRequired("edit requires explicit approval")
    resolved = Path(preview.path)
    before = _require_text(resolved)
    snapshot = create_snapshot(
        resolved,
        reason="edit_file",
        created_by_action="fs.edit.apply",
        approved_roots=approved_roots,
        audit_path=DEFAULT_AUDIT_PATH,
    )
    resolved.write_bytes(before.replace(old_text, new_text, 1).encode("utf-8"))
    sha_after = _sha256(resolved)
    _audit(
        "fs.edit.apply",
        str(resolved),
        preview.risk_tier,
        True,
        capability="fs.edit",
        reason="applied",
        snapshot_id=snapshot.snapshot_id,
        sha256_before=preview.sha256_before,
        sha256_after=sha_after,
    )
    return WriteResult(str(resolved), preview.risk_tier, snapshot, preview.sha256_before, sha_after)


def delete_file(path: str | Path) -> None:
    raise NotImplementedError("delete_file is T2 and is not implemented in Phase 1 CLI.")
