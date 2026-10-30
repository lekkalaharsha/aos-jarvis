"""Fail-closed approved-domain registry and Human Owner enrollment bootstrap.

Structural twin of aos/safety/approved_projects.py. Registry membership is
not a permission grant -- see docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md
Sec4 "A URL never grants its own authorization." A one-use approval is an
opaque capability for exactly one canonical host and is consumed durably
before a domain entry is persisted, so an interrupted enrollment fails closed.
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

from aos.browser.url_policy import canonicalize_host
from aos.config.loader import DATA_DIR
from aos.safety.errors import PermissionBlocked

SCHEMA_VERSION = 1
DEFAULT_REGISTRY_PATH = DATA_DIR / "browser" / "approved_domains.json"
APPROVAL_TTL_SECONDS = 300
_ENROLLMENT_ISSUER = object()
_REGISTRY_LOCK = threading.RLock()


@dataclass(frozen=True)
class ApprovedDomain:
    domain_id: str
    host: str  # canonical, punycode-normalized
    created_at: str
    revoked: bool = False
    allow_http: bool = False
    allow_ip_literal: bool = False
    extra_ports: tuple[int, ...] = ()


class DomainEnrollmentApproval:
    """Opaque approval; its random token is never serialized or displayed."""

    __slots__ = ("_canonical_host", "_token", "_expires_at", "_operation", "_allow_http", "_allow_ip_literal", "_sealed")

    def __init__(
        self,
        canonical_host: str,
        token: str,
        expires_at: str,
        *,
        allow_http: bool,
        allow_ip_literal: bool,
        _issuer: object,
    ) -> None:
        if _issuer is not _ENROLLMENT_ISSUER:
            raise PermissionBlocked("domain enrollment approvals are issued only by the Human Owner authority")
        object.__setattr__(self, "_canonical_host", canonical_host)
        object.__setattr__(self, "_token", token)
        object.__setattr__(self, "_expires_at", expires_at)
        object.__setattr__(self, "_operation", "browser.domain.enroll")
        object.__setattr__(self, "_allow_http", allow_http)
        object.__setattr__(self, "_allow_ip_literal", allow_ip_literal)
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise PermissionBlocked("domain enrollment approval is immutable")
        object.__setattr__(self, name, value)


def _approval_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class DomainEnrollmentAuthority:
    """Only the direct terminal Human Owner flow can mint a domain approval."""

    def approve_one(
        self,
        host: str,
        *,
        human_owner_confirmed: bool,
        origin: str,
        allow_http: bool = False,
        allow_ip_literal: bool = False,
    ) -> DomainEnrollmentApproval:
        if origin != "terminal" or not human_owner_confirmed:
            raise PermissionBlocked("direct Human Owner terminal approval is required")
        canonical_host = canonicalize_host(host)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=APPROVAL_TTL_SECONDS)
        return DomainEnrollmentApproval(
            canonical_host,
            secrets.token_urlsafe(32),
            expires_at.isoformat(),
            allow_http=allow_http,
            allow_ip_literal=allow_ip_literal,
            _issuer=_ENROLLMENT_ISSUER,
        )


class ApprovedDomainRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_REGISTRY_PATH

    def _empty(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, "domains": [], "consumed_approval_digests": []}

    def _read(self) -> dict:
        if not self.path.exists():
            return self._empty()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PermissionBlocked("approved-domain registry is invalid") from exc
        if set(data) != {"schema_version", "domains", "consumed_approval_digests"} or data["schema_version"] != SCHEMA_VERSION:
            raise PermissionBlocked("approved-domain registry schema is invalid")
        try:
            for item in data["domains"]:
                ApprovedDomain(
                    domain_id=item["domain_id"], host=item["host"], created_at=item["created_at"],
                    revoked=item["revoked"], allow_http=item["allow_http"],
                    allow_ip_literal=item["allow_ip_literal"], extra_ports=tuple(item["extra_ports"]),
                )
        except (TypeError, ValueError, KeyError) as exc:
            raise PermissionBlocked("approved-domain registry entries are invalid") from exc
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".approved-domains-", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def enroll(self, host: str, *, approval: DomainEnrollmentApproval) -> ApprovedDomain:
        if not isinstance(approval, DomainEnrollmentApproval):
            raise PermissionBlocked("fresh domain enrollment approval is required")
        if approval._operation != "browser.domain.enroll":
            raise PermissionBlocked("enrollment approval is bound to a different operation")
        try:
            expires_at = datetime.fromisoformat(approval._expires_at)
        except ValueError as exc:
            raise PermissionBlocked("domain enrollment approval is invalid") from exc
        if expires_at <= datetime.now(timezone.utc):
            raise PermissionBlocked("domain enrollment approval has expired")
        canonical_host = canonicalize_host(host)
        if not hmac.compare_digest(canonical_host, approval._canonical_host):
            raise PermissionBlocked("enrollment approval is bound to a different canonical host")
        digest = _approval_digest(approval._token)
        with _REGISTRY_LOCK:
            data = self._read()
            if any(hmac.compare_digest(digest, existing) for existing in data["consumed_approval_digests"]):
                raise PermissionBlocked("fresh enrollment approval is required")
            data["consumed_approval_digests"].append(digest)
            self._write(data)  # durable first: crash here leaves the approval spent.
            data = self._read()
            if any(item["host"] == canonical_host and not item["revoked"] for item in data["domains"]):
                raise PermissionBlocked("domain already enrolled")
            domain = ApprovedDomain(
                domain_id=uuid.uuid4().hex, host=canonical_host,
                created_at=datetime.now(timezone.utc).isoformat(),
                allow_http=approval._allow_http, allow_ip_literal=approval._allow_ip_literal,
            )
            data["domains"].append({
                "domain_id": domain.domain_id, "host": domain.host, "created_at": domain.created_at,
                "revoked": domain.revoked, "allow_http": domain.allow_http,
                "allow_ip_literal": domain.allow_ip_literal, "extra_ports": list(domain.extra_ports),
            })
            self._write(data)
            return domain

    def list(self) -> list[ApprovedDomain]:
        return [
            ApprovedDomain(
                domain_id=item["domain_id"], host=item["host"], created_at=item["created_at"],
                revoked=item["revoked"], allow_http=item["allow_http"],
                allow_ip_literal=item["allow_ip_literal"], extra_ports=tuple(item["extra_ports"]),
            )
            for item in self._read()["domains"]
        ]

    def resolve(self, domain_id: str) -> ApprovedDomain:
        item = next((item for item in self.list() if item.domain_id == domain_id and not item.revoked), None)
        if item is None:
            raise PermissionBlocked("approved domain is unavailable")
        return item

    def resolve_by_host(self, host: str) -> ApprovedDomain:
        """Deny-by-default: any host not an active registry entry is denied
        before any network connection is attempted (contract Sec4)."""
        canonical_host = canonicalize_host(host)
        item = next((item for item in self.list() if item.host == canonical_host and not item.revoked), None)
        if item is None:
            raise PermissionBlocked("domain is not enrolled")
        return item

    def revoke(self, domain_id: str) -> None:
        with _REGISTRY_LOCK:
            data = self._read()
            for item in data["domains"]:
                if item["domain_id"] == domain_id:
                    item["revoked"] = True
                    self._write(data)
                    return
        raise PermissionBlocked("approved domain is unavailable")
