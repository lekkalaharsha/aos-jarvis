"""AOS-controlled validating HTTP CONNECT proxy (contract Sec4a).

Remediation (fresh Codex gate, Critical C-2): a declared, merely-reachable
proxy URL is not a containment boundary -- nothing proved it was
AOS-controlled or that it actually enforced any policy. This module makes
Phase 10 itself the enforcement point: for every task, AOS spawns its own
loopback-only HTTP CONNECT proxy, scoped to an exact allowlist of
``(host, port)`` pairs derived from the enrolled domain being used for that
task, and Chromium is forced to route all traffic through it
(``--proxy-server``). CONNECT to anything not on that exact allowlist --
including the private/loopback/link-local/metadata ranges the application
layer already denies, and including the egress canary target -- is refused
by the proxy itself with a real socket-level response, not merely detected
as "unreachable." This holds even if an application-layer URL check inside
Chromium/Playwright were bypassed (e.g. a compromised renderer), because
the proxy is a separate OS process this module owns end to end, not
something Chromium's own code path could disable.

This is still not a full OS/container network-namespace or firewall
containment layer -- an unprivileged CLI process cannot install iptables
rules or a network namespace without root. It is the strongest containment
this codebase can independently enforce and verify without additional
privileges, per contract Sec4a's "a locally controlled validating proxy"
acceptance criterion.
"""
from __future__ import annotations

import ipaddress
import socket
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

CONNECT_TIMEOUT_SECONDS = 5.0


class _ConnectHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_CONNECT(self) -> None:  # noqa: N802 -- stdlib method name
        host, _, port_str = self.path.partition(":")
        try:
            port = int(port_str) if port_str else 443
        except ValueError:
            self._deny()
            return
        allowed: frozenset[tuple[str, int]] = self.server.allowed_targets  # type: ignore[attr-defined]
        if (host, port) not in allowed:
            self._deny(host, port)
            return
        try:
            connector = self.server.upstream_connector  # type: ignore[attr-defined]
            upstream = connector(host, port) if connector is not None else _connect_verified_target(host, port)
        except OSError:
            self.send_response(502, "Bad Gateway")
            self.end_headers()
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.server.allowed_log.append((host, port))  # type: ignore[attr-defined]
        _splice(self.connection, upstream)

    def do_GET(self) -> None:  # noqa: N802
        self._deny()

    def _deny(self, host: str = "", port: int = 0) -> None:
        self.send_response(403, "Forbidden")
        self.end_headers()
        if host:
            self.server.denied_log.append((host, port))  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 -- stdlib signature
        pass  # silence stdlib server logging; nothing sensitive is logged anyway


def _splice(client_sock: socket.socket, upstream_sock: socket.socket) -> None:
    def forward(src: socket.socket, dst: socket.socket) -> None:
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    t1 = threading.Thread(target=forward, args=(client_sock, upstream_sock), daemon=True)
    t2 = threading.Thread(target=forward, args=(upstream_sock, client_sock), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    upstream_sock.close()


def _connect_verified_target(host: str, port: int) -> socket.socket:
    """Resolve and connect only to globally routable addresses.

    Resolving once and connecting to the returned numeric address avoids the
    DNS-rebinding window created by passing the hostname back to
    ``socket.create_connection`` for a second lookup. Private/local results
    are denied even when the hostname itself is allowlisted.
    """
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise OSError("non-global IP target denied")
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    else:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not infos:
            raise OSError("target did not resolve")
        for _, _, _, _, sockaddr in infos:
            address = ipaddress.ip_address(sockaddr[0])
            if not address.is_global:
                raise OSError("target resolved to a non-global address")
    for family, sock_type, proto, _, sockaddr in infos:
        upstream = socket.socket(family, sock_type, proto)
        try:
            upstream.settimeout(CONNECT_TIMEOUT_SECONDS)
            upstream.connect(sockaddr)
            return upstream
        except OSError:
            upstream.close()
    raise OSError("target connection failed")


@dataclass
class ValidatingProxy:
    """One AOS-owned, loopback-bound, policy-enforcing CONNECT proxy. One
    instance per task, scoped to exactly that task's enrolled domain
    target(s) -- never process-wide, never reused across tasks."""

    allowed_targets: frozenset[tuple[str, int]]
    upstream_connector: Callable[[str, int], socket.socket] | None = field(default=None, repr=False)
    _server: ThreadingHTTPServer | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    def start(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _ConnectHandler)
        server.allowed_targets = self.allowed_targets  # type: ignore[attr-defined]
        server.upstream_connector = self.upstream_connector  # type: ignore[attr-defined]
        server.denied_log = []  # type: ignore[attr-defined]
        server.allowed_log = []  # type: ignore[attr-defined]
        server.daemon_threads = True
        self._server = server
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._thread = thread

    @property
    def address(self) -> tuple[str, int]:
        assert self._server is not None
        return self._server.server_address  # type: ignore[return-value]

    @property
    def url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None


def probe_connect(proxy_url: str, host: str, port: int, *, timeout: float = CONNECT_TIMEOUT_SECONDS) -> int:
    """Issues a REAL HTTP CONNECT through the given proxy and returns the
    status code the proxy itself returned. Used to prove policy enforcement
    (403 for a disallowed target, 200 for an allowed one) with an actual
    request, not an inference from reachability alone."""
    from urllib.parse import urlsplit

    parts = urlsplit(proxy_url)
    with socket.create_connection((parts.hostname, parts.port), timeout=timeout) as sock:
        sock.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
        sock.settimeout(timeout)
        response = sock.recv(1024)
    if not response.startswith(b"HTTP/"):
        return 0
    try:
        return int(response.split(b" ", 2)[1])
    except (IndexError, ValueError):
        return 0
