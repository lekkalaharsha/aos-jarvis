"""Fail-closed approved-project registry and Human Owner enrollment bootstrap.

Registry membership is not a permission grant.  A one-use approval is an opaque
capability for exactly one canonical directory and is consumed durably before a
project entry is persisted, so an interrupted enrollment fails closed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aos.config.loader import DATA_DIR
from aos.safety.errors import PermissionBlocked
from aos.safety.paths import check_dangerous_path, check_secret_path

SCHEMA_VERSION = 2
DEFAULT_REGISTRY_PATH = DATA_DIR / "approved_projects.json"
APPROVAL_TTL_SECONDS = 300
_ENROLLMENT_ISSUER = object()
_REGISTRY_LOCK = threading.RLock()


@dataclass(frozen=True)
class ApprovedProject:
    project_id: str
    path: str
    created_at: str
    revoked: bool = False


class EnrollmentApproval:
    """Opaque approval; its random token is never serialized or displayed."""

    __slots__ = ("_canonical_path", "_requested_path", "_token", "_expires_at", "_operation", "_sealed")

    def __init__(self, canonical_path: str, requested_path: str, token: str, expires_at: str, *, _issuer: object) -> None:
        if _issuer is not _ENROLLMENT_ISSUER:
            raise PermissionBlocked("enrollment approvals are issued only by the Human Owner authority")
        object.__setattr__(self, "_canonical_path", canonical_path)
        object.__setattr__(self, "_requested_path", requested_path)
        object.__setattr__(self, "_token", token)
        object.__setattr__(self, "_expires_at", expires_at)
        object.__setattr__(self, "_operation", "project.enroll")
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise PermissionBlocked("enrollment approval is immutable")
        object.__setattr__(self, name, value)


def _canonical_enrollment_path(path: str | Path) -> tuple[Path, Path]:
    requested = Path(path).expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    try:
        canonical = requested.resolve(strict=True)
    except OSError as exc:
        raise PermissionBlocked("approved project must be an existing directory") from exc
    if not canonical.is_dir():
        raise PermissionBlocked("approved project must be an existing directory")
    check_dangerous_path(requested, canonical)
    check_secret_path(requested, canonical)
    if canonical == Path(canonical.anchor) or canonical == Path.home().resolve() or canonical == Path.cwd().resolve():
        raise PermissionBlocked("overly broad project root is not eligible for enrollment")
    return requested, canonical


def _approval_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class HumanOwnerEnrollmentAuthority:
    """Only the direct terminal Human Owner flow can mint an enrollment approval."""

    def approve_one(self, path: str | Path, *, human_owner_confirmed: bool, origin: str) -> EnrollmentApproval:
        if origin != "terminal" or not human_owner_confirmed:
            raise PermissionBlocked("direct Human Owner terminal approval is required")
        requested, canonical = _canonical_enrollment_path(path)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=APPROVAL_TTL_SECONDS)
        return EnrollmentApproval(str(canonical), str(requested), secrets.token_urlsafe(32), expires_at.isoformat(), _issuer=_ENROLLMENT_ISSUER)


class ApprovedProjectRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_REGISTRY_PATH

    def _empty(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, "projects": [], "consumed_approval_digests": []}

    @property
    def _consumed_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.consumed")

    def _read_consumed(self) -> list[str]:
        if not self._consumed_path.exists():
            return []
        try:
            values = json.loads(self._consumed_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PermissionBlocked("consumed-approval journal is invalid") from exc
        if not isinstance(values, list) or any(not isinstance(value, str) or len(value) != 64 for value in values):
            raise PermissionBlocked("consumed-approval journal is invalid")
        return values

    def _read(self) -> dict:
        if not self.path.exists():
            return self._empty()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PermissionBlocked("approved-project registry is invalid") from exc
        if set(data) != {"schema_version", "projects", "consumed_approval_digests"} or data["schema_version"] != SCHEMA_VERSION or not isinstance(data["projects"], list) or not isinstance(data["consumed_approval_digests"], list):
            raise PermissionBlocked("approved-project registry schema is invalid")
        try:
            if any(not isinstance(value, str) or len(value) != 64 for value in data["consumed_approval_digests"]):
                raise ValueError
            for item in data["projects"]:
                if set(item) != {"project_id", "path", "created_at", "revoked"}:
                    raise ValueError
                ApprovedProject(**item)
        except (TypeError, ValueError) as exc:
            raise PermissionBlocked("approved-project registry entries are invalid") from exc
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".approved-projects-", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _write_consumed(self, values: list[str]) -> None:
        path = self._consumed_path
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=".approved-consumed-", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(values, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _consume(self, approval: EnrollmentApproval) -> None:
        digest = _approval_digest(approval._token)
        data = self._read()
        consumed = self._read_consumed()
        # compare_digest avoids a token-derived equality shortcut.
        if any(hmac.compare_digest(digest, existing) for existing in [*consumed, *data["consumed_approval_digests"]]):
            raise PermissionBlocked("fresh enrollment approval is required")
        self._write_consumed([*consumed, digest])
        data["consumed_approval_digests"].append(digest)
        self._write(data)  # durable first: crash here leaves the approval spent.

    def enroll(self, path: str | Path, *, approval: EnrollmentApproval) -> ApprovedProject:
        if not isinstance(approval, EnrollmentApproval):
            raise PermissionBlocked("fresh enrollment approval is required")
        if approval._operation != "project.enroll":
            raise PermissionBlocked("enrollment approval is bound to a different operation")
        try:
            expires_at = datetime.fromisoformat(approval._expires_at)
        except ValueError as exc:
            raise PermissionBlocked("enrollment approval is invalid") from exc
        if expires_at <= datetime.now(timezone.utc):
            raise PermissionBlocked("enrollment approval has expired")
        requested, canonical = _canonical_enrollment_path(path)
        if not hmac.compare_digest(str(requested), approval._requested_path) or not hmac.compare_digest(str(canonical), approval._canonical_path):
            raise PermissionBlocked("enrollment approval is bound to a different canonical path")
        with _REGISTRY_LOCK:
            self._consume(approval)
            # A path can change after approval and after token consumption.  Check
            # it again immediately before persistence and fail safely if it moved.
            requested, canonical = _canonical_enrollment_path(path)
            if not hmac.compare_digest(str(requested), approval._requested_path) or not hmac.compare_digest(str(canonical), approval._canonical_path):
                raise PermissionBlocked("approved project path changed before persistence")
            data = self._read()
            if any(item["path"] == str(canonical) and not item["revoked"] for item in data["projects"]):
                raise PermissionBlocked("project already registered")
            project = ApprovedProject(uuid.uuid4().hex, str(canonical), datetime.now(timezone.utc).isoformat())
            data["projects"].append(project.__dict__)
            self._write(data)
            return project

    def list(self) -> list[ApprovedProject]:
        return [ApprovedProject(**item) for item in self._read()["projects"]]

    def resolve(self, project_id: str) -> Path:
        item = next((item for item in self.list() if item.project_id == project_id and not item.revoked), None)
        if item is None:
            raise PermissionBlocked("approved project is unavailable")
        _, resolved = _canonical_enrollment_path(item.path)
        if str(resolved) != item.path:
            raise PermissionBlocked("approved project path changed")
        return resolved

    def revoke(self, project_id: str) -> None:
        with _REGISTRY_LOCK:
            data = self._read()
            for item in data["projects"]:
                if item["project_id"] == project_id:
                    item["revoked"] = True
                    self._write(data)
                    return
        raise PermissionBlocked("approved project is unavailable")
