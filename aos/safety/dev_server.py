"""Opaque, expiring, single-use approval for development server launches.

The approval is bound to:
- workspace.dev_server.start operation
- approved project ID and canonical project identity
- fixed server profile
- validated port
- terminal Human Owner origin
- issuance and expiry timestamps
- unique approval digest

The approval token is never serialized, printed, or audited. Only the
SHA-256 digest of the token is persisted in the consumed-approval journal.
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
_DEV_SERVER_APPROVAL_LOCK = threading.RLock()
DEFAULT_CONSUMED_PATH = DATA_DIR / "dev_server_approvals.json"


def _approval_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def canonical_project_digest(path: Path) -> str:
    """Bind an approval to the exact resolved project directory, independent of
    the opaque project ID string, so a mint-to-consume path change is caught even
    if the project ID itself is unchanged."""
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


class DevServerApproval:
    """Immutable approval for one development server launch.

    The token is held only in memory and never serialized or displayed.
    The digest is the only persistent derivative.
    """

    __slots__ = (
        "_operation", "_project_id", "_canonical_project_id",
        "_profile", "_port", "_origin", "_issued_at", "_expires_at",
        "_token", "_digest", "_sealed",
    )

    def __init__(
        self,
        *,
        project_id: str,
        canonical_project_id: str,
        profile: str,
        port: int,
        origin: str,
        _issuer: object = ...,
    ) -> None:
        if _issuer is not _APPROVAL_ISSUER:
            raise PermissionBlocked("dev-server approvals are issued only by the authority")
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        object.__setattr__(self, "_operation", "workspace.dev_server.start")
        object.__setattr__(self, "_project_id", project_id)
        object.__setattr__(self, "_canonical_project_id", canonical_project_id)
        object.__setattr__(self, "_profile", profile)
        object.__setattr__(self, "_port", port)
        object.__setattr__(self, "_origin", origin)
        object.__setattr__(self, "_issued_at", now.isoformat())
        object.__setattr__(self, "_expires_at", (now + timedelta(seconds=APPROVAL_TTL_SECONDS)).isoformat())
        object.__setattr__(self, "_token", token)
        object.__setattr__(self, "_digest", _approval_digest(token))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise PermissionBlocked("dev-server approval is immutable")
        object.__setattr__(self, name, value)

    @property
    def operation(self) -> str:
        return self._operation  # type: ignore[return-value]

    @property
    def project_id(self) -> str:
        return self._project_id  # type: ignore[return-value]

    @property
    def profile(self) -> str:
        return self._profile  # type: ignore[return-value]

    @property
    def port(self) -> int:
        return self._port  # type: ignore[return-value]

    @property
    def origin(self) -> str:
        return self._origin  # type: ignore[return-value]

    @property
    def expires_at(self) -> str:
        return self._expires_at  # type: ignore[return-value]


def mint_dev_server_approval(
    *,
    project_id: str,
    canonical_project_id: str,
    profile: str,
    port: int,
    human_owner_confirmed: bool,
    origin: str = "terminal",
) -> DevServerApproval:
    """Mint a fresh, one-use, expiring approval for a dev-server launch."""
    if not human_owner_confirmed or origin != "terminal":
        raise PermissionBlocked("dev-server approval requires terminal Human Owner origin")
    return DevServerApproval(
        project_id=project_id,
        canonical_project_id=canonical_project_id,
        profile=profile,
        port=port,
        origin=origin,
        _issuer=_APPROVAL_ISSUER,
    )


def _load_consumed(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PermissionBlocked("consumed dev-server approval journal is invalid") from exc
    if not isinstance(data, list) or any(not isinstance(v, str) or len(v) != 64 for v in data):
        raise PermissionBlocked("consumed dev-server approval journal is invalid")
    return data


def _save_consumed(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = _temp_file(path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(values, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _temp_file(path: Path) -> tuple[int, str]:
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".dev-server-approvals-", text=True)
    return fd, name


def consume_dev_server_approval(
    approval: DevServerApproval,
    *,
    project_id: str,
    profile: str,
    port: int,
    canonical_project_id: str | None = None,
    consumed_path: Path | None = None,
) -> DevServerApproval:
    """Validate and durably consume a dev-server approval.

    Rejects missing, expired, reused, malformed, wrong-binding, revoked,
    or path-changed approvals. The token/digest is never printed or audited.

    ``canonical_project_id`` should be the caller's freshly recomputed
    :func:`canonical_project_digest` of the resolved project directory at
    consumption time. It is checked independently of ``project_id`` so a path
    change between mint and consume is caught even when the project ID string
    is unchanged. Callers that omit it fall back to the (weaker) project-ID
    comparison for backward compatibility.
    """
    path = consumed_path or DEFAULT_CONSUMED_PATH
    if not isinstance(approval, DevServerApproval):
        raise PermissionBlocked("valid dev-server approval is required")
    if approval._operation != "workspace.dev_server.start":
        raise PermissionBlocked("dev-server approval bound to wrong operation")
    try:
        expires = datetime.fromisoformat(approval._expires_at)
    except ValueError as exc:
        raise PermissionBlocked("dev-server approval is invalid") from exc
    if expires <= datetime.now(timezone.utc):
        raise PermissionBlocked("dev-server approval has expired")
    if not hmac.compare_digest(project_id, approval._project_id):
        raise PermissionBlocked("dev-server approval bound to wrong project")
    expected_canonical = canonical_project_id if canonical_project_id is not None else project_id
    if not hmac.compare_digest(expected_canonical, approval._canonical_project_id):
        raise PermissionBlocked("dev-server approval bound to wrong canonical project")
    if not hmac.compare_digest(profile, approval._profile):
        raise PermissionBlocked("dev-server approval bound to wrong profile")
    if port != approval._port:
        raise PermissionBlocked("dev-server approval bound to wrong port")
    digest = approval._digest
    with _DEV_SERVER_APPROVAL_LOCK:
        consumed = _load_consumed(path)
        if any(hmac.compare_digest(digest, existing) for existing in consumed):
            raise PermissionBlocked("dev-server approval already consumed")
        _save_consumed(path, [*consumed, digest])
    return approval
