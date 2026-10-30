"""Opaque, expiring, single-use, per-operation approval for T2 browser actions.

Structural twin of aos/safety/dev_server.py, extended per contract Sec3a to
bind to a single operation/field/file rather than once per session. Every
T2 operation entry in a task-spec needs its own approval; none may be
reused for a different operation, field, or file.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aos.config.loader import DATA_DIR
from aos.safety.errors import PermissionBlocked

APPROVAL_TTL_SECONDS = 120
_APPROVAL_ISSUER = object()
_BROWSER_APPROVAL_LOCK = threading.RLock()
DEFAULT_CONSUMED_PATH = DATA_DIR / "browser" / "browser_approvals_consumed.json"


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class BrowserApproval:
    """Immutable, single-operation approval. The token is held only in
    memory and never serialized, printed, or audited (contract Sec3a)."""

    __slots__ = (
        "_operation", "_task_id", "_domain_id", "_url_digest",
        "_locator_identity", "_field_classification", "_file_identity",
        "_origin", "_issued_at", "_expires_at", "_token", "_digest", "_sealed",
    )

    def __init__(
        self,
        *,
        operation: str,
        task_id: str,
        domain_id: str,
        url_digest: str = "",
        locator_identity: str = "",
        field_classification: str = "",
        file_identity: str = "",
        origin: str,
        _issuer: object = ...,
    ) -> None:
        if _issuer is not _APPROVAL_ISSUER:
            raise PermissionBlocked("browser approvals are issued only by the authority")
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        object.__setattr__(self, "_operation", operation)
        object.__setattr__(self, "_task_id", task_id)
        object.__setattr__(self, "_domain_id", domain_id)
        object.__setattr__(self, "_url_digest", url_digest)
        object.__setattr__(self, "_locator_identity", locator_identity)
        object.__setattr__(self, "_field_classification", field_classification)
        object.__setattr__(self, "_file_identity", file_identity)
        object.__setattr__(self, "_origin", origin)
        object.__setattr__(self, "_issued_at", now.isoformat())
        object.__setattr__(self, "_expires_at", (now + timedelta(seconds=APPROVAL_TTL_SECONDS)).isoformat())
        object.__setattr__(self, "_token", token)
        object.__setattr__(self, "_digest", _digest(token))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise PermissionBlocked("browser approval is immutable")
        object.__setattr__(self, name, value)

    @property
    def operation(self) -> str:
        return self._operation  # type: ignore[return-value]

    @property
    def task_id(self) -> str:
        return self._task_id  # type: ignore[return-value]

    @property
    def domain_id(self) -> str:
        return self._domain_id  # type: ignore[return-value]


def mint_browser_approval(
    *,
    operation: str,
    task_id: str,
    domain_id: str,
    url_digest: str = "",
    locator_identity: str = "",
    field_classification: str = "",
    file_identity: str = "",
    human_owner_confirmed: bool,
    origin: str = "terminal",
) -> BrowserApproval:
    """Contract Sec11: voice can never approve any T2 browser action; model
    output alone can never approve a browser action. Only a non-voice,
    terminal-origin, human-confirmed flow may mint."""
    if not human_owner_confirmed or origin != "terminal":
        raise PermissionBlocked("browser approval requires terminal Human Owner origin")
    return BrowserApproval(
        operation=operation, task_id=task_id, domain_id=domain_id,
        url_digest=url_digest, locator_identity=locator_identity,
        field_classification=field_classification, file_identity=file_identity,
        origin=origin, _issuer=_APPROVAL_ISSUER,
    )


def _load_consumed(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PermissionBlocked("consumed browser-approval journal is invalid") from exc
    if not isinstance(data, list) or any(not isinstance(v, str) or len(v) != 64 for v in data):
        raise PermissionBlocked("consumed browser-approval journal is invalid")
    return data


def _save_consumed(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".browser-approvals-", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(values, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def consume_browser_approval(
    approval: BrowserApproval,
    *,
    operation: str,
    task_id: str,
    domain_id: str,
    url_digest: str = "",
    locator_identity: str = "",
    field_classification: str = "",
    file_identity: str = "",
    consumed_path: Path | None = None,
) -> BrowserApproval:
    """Validate and durably consume one per-operation approval.

    Rejects missing, expired, reused, malformed, or wrong-binding approvals.
    A failed action still leaves the approval consumed (contract Sec3a) --
    callers must consume only immediately before the side-effecting action,
    and a subsequent action failure must not attempt to re-consume.
    """
    path = consumed_path or DEFAULT_CONSUMED_PATH
    if not isinstance(approval, BrowserApproval):
        raise PermissionBlocked("valid browser approval is required")
    if not hmac.compare_digest(operation, approval._operation):
        raise PermissionBlocked("browser approval bound to wrong operation")
    if not hmac.compare_digest(task_id, approval._task_id):
        raise PermissionBlocked("browser approval bound to wrong task")
    if not hmac.compare_digest(domain_id, approval._domain_id):
        raise PermissionBlocked("browser approval bound to wrong domain")
    if not hmac.compare_digest(url_digest, approval._url_digest):
        raise PermissionBlocked("browser approval bound to a different url")
    if not hmac.compare_digest(locator_identity, approval._locator_identity):
        raise PermissionBlocked("browser approval bound to a different locator")
    if not hmac.compare_digest(field_classification, approval._field_classification):
        raise PermissionBlocked("browser approval bound to a different field classification")
    if not hmac.compare_digest(file_identity, approval._file_identity):
        raise PermissionBlocked("browser approval bound to a different file")
    try:
        expires = datetime.fromisoformat(approval._expires_at)
    except ValueError as exc:
        raise PermissionBlocked("browser approval is invalid") from exc
    if expires <= datetime.now(timezone.utc):
        raise PermissionBlocked("browser approval has expired")
    digest = approval._digest
    with _BROWSER_APPROVAL_LOCK:
        consumed = _load_consumed(path)
        if any(hmac.compare_digest(digest, existing) for existing in consumed):
            raise PermissionBlocked("browser approval already consumed")
        _save_consumed(path, [*consumed, digest])
    return approval
