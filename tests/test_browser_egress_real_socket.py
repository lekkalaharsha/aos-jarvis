"""Real-socket egress-containment proof (Codex remediation requirement:
"integration tests that prove containment with real connection attempts").

These tests perform ACTUAL TCP connects and ACTUAL HTTP CONNECT requests
through a real, locally spawned AOS validating proxy -- no mocked
connector, no mocked proxy behavior -- but only ever against loopback
sockets this test process itself starts and stops, so there is no live
external-network dependency (Layer-1 test isolation, Codex Important #6).
"""
from __future__ import annotations

import socket
import threading

import pytest

from aos.browser.egress import spawn_and_verify_validating_proxy
from aos.browser.validating_proxy import ValidatingProxy, probe_connect


def _listening_socket() -> socket.socket:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError as exc:
        pytest.skip(f"current sandbox does not permit loopback socket tests: {exc}")
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
    except PermissionError as exc:
        sock.close()
        pytest.skip(f"current sandbox does not permit loopback socket tests: {exc}")
    return sock


def test_real_probe_denies_containment_when_direct_canary_egress_succeeds():
    server = _listening_socket()
    host, port = server.getsockname()

    def accept_loop():
        try:
            conn, _ = server.accept()
            conn.close()
        except OSError:
            pass

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    try:
        result, proxy = spawn_and_verify_validating_proxy(
            frozenset({("example.com", 443)}), canary_host=host, canary_port=port,
        )
        assert result.verified is False
        assert proxy is None
    finally:
        server.close()
        thread.join(timeout=2)


def test_real_validating_proxy_actually_refuses_a_real_connect_to_disallowed_target():
    """The core containment claim: AOS's own proxy code, exercised with a
    real HTTP CONNECT request (not a mock), returns 403 for a target that
    is not on the allowlist -- proving policy enforcement, not mere
    reachability."""
    proxy = ValidatingProxy(allowed_targets=frozenset({("allowed.example", 443)}))
    proxy.start()
    try:
        status = probe_connect(proxy.url, "not-allowed.example", 443)
        assert status == 403
    finally:
        proxy.stop()


def test_real_validating_proxy_allows_a_real_connect_to_an_allowed_target():
    upstream = _listening_socket()
    upstream_host, upstream_port = upstream.getsockname()

    def accept_loop():
        try:
            conn, _ = upstream.accept()
            conn.close()
        except OSError:
            pass

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    try:
        # The production proxy rejects private resolved addresses.  This
        # test injects the local fixture connector explicitly so it can
        # exercise the HTTP CONNECT splice without weakening production.
        proxy = ValidatingProxy(
            allowed_targets=frozenset({(upstream_host, upstream_port)}),
            upstream_connector=lambda host, port: socket.create_connection((host, port), timeout=2),
        )
        proxy.start()
        try:
            status = probe_connect(proxy.url, upstream_host, upstream_port)
            assert status == 200
        finally:
            proxy.stop()
    finally:
        upstream.close()
        thread.join(timeout=2)


def test_spawn_and_verify_succeeds_when_direct_egress_blocked_and_proxy_enforces():
    """End-to-end: direct canary egress blocked (real refused-port probe)
    AND the just-spawned AOS proxy really refuses a real CONNECT to that
    same canary -- both real, unmocked checks -- yields a verified
    containment result with a live, running proxy the caller must stop."""
    canary_probe = _listening_socket()
    canary_host, canary_port = canary_probe.getsockname()
    canary_probe.close()  # now refused -- a real blocked direct path

    result, proxy = spawn_and_verify_validating_proxy(
        frozenset({("allowed.example", 443)}), canary_host=canary_host, canary_port=canary_port,
    )
    try:
        assert result.verified is True
        assert proxy is not None
        assert result.proxy_url == proxy.url
        # Re-prove enforcement directly against the same running proxy.
        assert probe_connect(proxy.url, canary_host, canary_port) == 403
    finally:
        if proxy is not None:
            proxy.stop()


def test_spawn_and_verify_denies_and_stops_proxy_if_proxy_fails_to_enforce():
    canary_probe = _listening_socket()
    canary_host, canary_port = canary_probe.getsockname()
    canary_probe.close()

    class _PermissiveProxy:
        """Simulates a broken/bypassable proxy that allows everything --
        used only to prove spawn_and_verify_validating_proxy denies and
        cleans up when its own real CONNECT probe does not get a 403."""

        def __init__(self, allowed_targets):
            self._server = None
            import http.server
            self._server = http.server.HTTPServer(("127.0.0.1", 0), _AllowAllHandler)

        def start(self):
            thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            thread.start()

        @property
        def url(self):
            host, port = self._server.server_address
            return f"http://{host}:{port}"

        def stop(self):
            self._server.shutdown()
            self._server.server_close()

    import http.server

    class _AllowAllHandler(http.server.BaseHTTPRequestHandler):
        def do_CONNECT(self):  # noqa: N802
            self.send_response(200, "Connection Established")
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A002
            pass

    result, proxy = spawn_and_verify_validating_proxy(
        frozenset({("allowed.example", 443)}), canary_host=canary_host, canary_port=canary_port,
        proxy_factory=lambda targets: _PermissiveProxy(targets),
    )
    assert result.verified is False
    assert proxy is None
