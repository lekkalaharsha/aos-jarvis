"""Canonical host/URL validation, private-network denial, and redirect policy.

Contract Sec4 (base rules) and Sec4a/Sec4b (mandatory egress containment,
redirect policy). This module implements the APPLICATION-LAYER checks only.
Per contract Sec4a, these checks are defense in depth, NOT sufficient SSRF /
DNS-rebinding containment on their own -- see aos/browser/egress.py for the
mandatory OS/container precondition this module cannot itself provide.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

from aos.browser.types import DEFAULT_RESOURCE_LIMITS
from aos.safety.errors import PermissionBlocked

ALLOWED_SCHEMES = frozenset({"https", "http"})
DEFAULT_PORTS = {"https": 443, "http": 80}


def canonicalize_host(host: str) -> str:
    """Lowercase and IDN/punycode-normalize a hostname before any comparison
    or display, so a homograph domain cannot collide with an approved entry
    (contract Sec4 IDN/punycode handling)."""
    if not host or not host.strip():
        raise PermissionBlocked("host must not be empty")
    stripped = host.strip().rstrip(".")
    try:
        encoded = stripped.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise PermissionBlocked("host cannot be IDN/punycode-normalized") from exc
    return encoded.lower()


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _is_private_or_local(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Contract Sec13 Hard Rule 7: deny private, loopback, link-local,
    unique-local, metadata, multicast, unspecified, reserved, and otherwise
    non-global-unicast targets. Operates on parsed address objects, not
    string prefix matching (closes the IPv4-mapped-IPv6 bypass class)."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
        or addr.is_reserved
        or not addr.is_global
    )


def check_not_private_or_local(host_or_ip: str) -> None:
    """Deny a raw IP literal target that is private/loopback/link-local/etc."""
    try:
        addr = ipaddress.ip_address(host_or_ip.strip("[]"))
    except ValueError:
        return  # not an IP literal; hostname-vs-DNS-resolution handled elsewhere
    if _is_private_or_local(addr):
        raise PermissionBlocked("private/loopback/link-local navigation target is permanently denied")


def check_resolved_addresses_not_private(host: str, *, resolver=None) -> None:
    """Post-DNS-resolution address check (contract Sec4 DNS rebinding note).

    ``resolver`` is injectable so tests never perform a real DNS lookup. The
    default resolver uses socket.getaddrinfo, which real deployments should
    pair with the mandatory OS/container egress layer (aos/browser/egress.py)
    -- this function alone is defense in depth, not sufficient containment
    (contract Sec4a).
    """
    lookup = resolver or (lambda h: [info[4][0] for info in socket.getaddrinfo(h, None)])
    try:
        addresses = lookup(host)
    except OSError as exc:
        raise PermissionBlocked("host could not be resolved") from exc
    for raw in addresses:
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if _is_private_or_local(addr):
            raise PermissionBlocked("resolved address is private/loopback/link-local (denied)")


@dataclass(frozen=True)
class ValidatedUrl:
    scheme: str
    host: str  # canonical punycode form
    port: int
    path: str
    had_query: bool
    had_fragment: bool
    is_ip_literal: bool


def validate_url(
    url: str,
    *,
    domain_host: str,
    allow_http: bool,
    allow_ip_literal: bool,
    extra_ports: tuple[int, ...] = (),
    resolver=None,
) -> ValidatedUrl:
    """Full application-layer validation of one URL against one enrolled
    domain entry. Raises PermissionBlocked on any violation. Never trusts
    the URL string itself as a capability grant (contract Sec4)."""
    if len(url) > DEFAULT_RESOURCE_LIMITS.max_url_length:
        raise PermissionBlocked("url exceeds length limit")
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise PermissionBlocked(f"scheme is denied: {parts.scheme!r}")
    if parts.scheme == "http" and not allow_http:
        raise PermissionBlocked("plain http is denied unless the domain enrolled allow_http")
    if not parts.hostname:
        raise PermissionBlocked("url has no host")

    is_ip_literal = _is_ip_literal(parts.hostname)
    if is_ip_literal:
        if not allow_ip_literal:
            raise PermissionBlocked("ip-literal host is denied unless the domain enrolled allow_ip_literal")
        check_not_private_or_local(parts.hostname)
        # An IP-literal enrollment binds to exactly the one enrolled literal
        # -- without this comparison, enrolling ANY ip-literal domain would
        # silently authorize navigation to every other ip-literal target,
        # collapsing the per-domain enrollment model for this class of entry.
        normalized_literal = str(ipaddress.ip_address(parts.hostname.strip("[]")))
        if normalized_literal != domain_host:
            raise PermissionBlocked("ip-literal host does not match the enrolled literal")
        canonical_host = parts.hostname
    else:
        canonical_host = canonicalize_host(parts.hostname)
        if len(canonical_host) > DEFAULT_RESOURCE_LIMITS.max_host_length:
            raise PermissionBlocked("host exceeds length limit")
        if canonical_host != domain_host:
            raise PermissionBlocked("host does not match the enrolled canonical domain (no substring/suffix match)")
        check_resolved_addresses_not_private(canonical_host, resolver=resolver)

    port = parts.port or DEFAULT_PORTS[parts.scheme]
    if port != DEFAULT_PORTS[parts.scheme] and port not in extra_ports:
        raise PermissionBlocked("non-default port is denied unless explicitly whitelisted at enrollment")

    path = parts.path or "/"
    if len(path) > DEFAULT_RESOURCE_LIMITS.max_path_length:
        raise PermissionBlocked("path exceeds length limit")

    return ValidatedUrl(
        scheme=parts.scheme, host=canonical_host, port=port, path=path,
        had_query=bool(parts.query), had_fragment=bool(parts.fragment),
        is_ip_literal=is_ip_literal,
    )


def is_cross_domain_redirect(original_host: str, redirect_url: str) -> bool:
    """Contract Sec4b: same-domain vs cross-domain redirect classification,
    applied identically to server-side and script-initiated navigation."""
    parts = urlsplit(redirect_url)
    if not parts.hostname:
        return True
    try:
        target_host = canonicalize_host(parts.hostname) if not _is_ip_literal(parts.hostname) else parts.hostname
    except PermissionBlocked:
        return True
    return target_host != original_host
