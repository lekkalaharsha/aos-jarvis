"""Mandatory OS/container egress-containment verification.

Contract Sec4a: application-layer URL/host checks (aos/browser/url_policy.py)
are defense in depth, NOT sufficient SSRF/DNS-rebinding containment on their
own. Independent OS/container egress filtering or a locally controlled
validating proxy is a mandatory, fail-closed precondition to launching any
browser process.

Remediation (fresh Codex gate, Critical C-2): a caller-declared, merely-
reachable proxy URL does not prove AOS controls or enforces anything at
that endpoint -- a caller could point ``AOS_BROWSER_EGRESS_PROXY_URL`` at
any reachable service and pass the check. This module now spawns and owns
its own validating proxy (``aos/browser/validating_proxy.py``) per task,
scoped to an exact allowlist derived from that task's enrolled domain, and
PROVES enforcement with a real CONNECT attempt to a disallowed target
through the proxy itself (expecting a real 403 from AOS's own code), not
merely a reachability probe. There is no operator-declared-proxy-URL
acceptance path left -- the proxy is always AOS's own process.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Callable

from aos.browser.validating_proxy import ValidatingProxy, probe_connect

# A fixed, well-known public IP:port that is never an enrollable Phase 10
# navigation target (it is not, and can never become, an approved domain --
# TEST-NET-1 documentation range would not even resolve; this uses a real
# always-on public anycast address deliberately outside any plausible
# enrollment). Overridable only for test injection, never for production
# bypass (the override still requires a REAL connection attempt to whatever
# address is configured).
DEFAULT_CANARY_HOST = "1.1.1.1"
DEFAULT_CANARY_PORT = 80
CANARY_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class EgressVerificationResult:
    verified: bool
    reason: str
    proxy_url: str = ""


def _attempt_connect(host: str, port: int, timeout: float) -> bool:
    """Returns True if a live TCP connection succeeds (egress is open),
    False if it is refused/times out/unreachable (egress appears blocked)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def spawn_and_verify_validating_proxy(
    allowed_targets: frozenset[tuple[str, int]],
    *,
    canary_host: str = DEFAULT_CANARY_HOST,
    canary_port: int = DEFAULT_CANARY_PORT,
    direct_connector: Callable[[str, int, float], bool] | None = None,
    proxy_connect_prober: Callable[[str, str, int], int] | None = None,
    proxy_factory: Callable[[frozenset[tuple[str, int]]], ValidatingProxy] | None = None,
) -> tuple[EgressVerificationResult, ValidatingProxy | None]:
    """The mandatory real check for one task: fail closed unless BOTH (a)
    a live outbound connection to a non-enrollable canary address is
    demonstrably blocked, AND (b) AOS's own just-spawned validating proxy
    demonstrably refuses (with a real 403 from its own code, verified via
    an actual CONNECT attempt) a request to that same disallowed canary
    target.

    On success, returns the started, still-running :class:`ValidatingProxy`
    -- the caller (``aos/browser/task.py``) is responsible for routing
    Chromium through its URL and stopping it in task cleanup. On any
    failure, the proxy (if one was started) is stopped before returning
    and ``None`` is returned in its place -- there is no orphaned proxy on
    a failed precondition.

    ``direct_connector`` / ``proxy_connect_prober`` / ``proxy_factory`` are
    injectable ONLY for deterministic tests; production code always uses
    the real socket-based implementations.
    """
    direct_probe = direct_connector or _attempt_connect
    direct_open = direct_probe(canary_host, canary_port, CANARY_TIMEOUT_SECONDS)
    if direct_open:
        return EgressVerificationResult(
            False,
            "a live outbound TCP connection to a non-enrollable canary "
            "address succeeded -- egress is not contained; browser launch "
            "must fail closed (contract Sec4a)",
        ), None

    factory = proxy_factory or (lambda targets: ValidatingProxy(allowed_targets=targets))
    prober = proxy_connect_prober or probe_connect
    proxy = factory(allowed_targets)
    proxy.start()
    denied_status = prober(proxy.url, canary_host, canary_port)
    if denied_status != 403:
        proxy.stop()
        return EgressVerificationResult(
            False,
            f"AOS-controlled validating proxy did not enforce policy against "
            f"a disallowed target (status={denied_status!r}) -- containment "
            "is not proven; browser launch must fail closed",
        ), None
    return EgressVerificationResult(
        True,
        "direct egress to the canary is blocked and AOS's own validating "
        "proxy demonstrably refused a real CONNECT to that same disallowed "
        "target",
        proxy_url=proxy.url,
    ), proxy


def verify_egress_containment(
    allowed_targets: frozenset[tuple[str, int]],
    checker: Callable[[frozenset[tuple[str, int]]], tuple[EgressVerificationResult, ValidatingProxy | None]] | None = None,
) -> tuple[EgressVerificationResult, ValidatingProxy | None]:
    """Fail-closed egress-containment precondition check for one task's
    allowlist. ``checker`` is injectable so tests can simulate both the
    present and absent case without touching real environment/network
    state. Production code (``checker is None``) always performs the real
    spawn-and-verify flow -- there is no attestation-only default
    remaining."""
    return (checker or spawn_and_verify_validating_proxy)(allowed_targets)
