"""Layer 2 -- real Chromium/Playwright integration tests (contract Sec12,
test plan Sec1a). Runs against a local, loopback-bound fixture HTTP server
only; never a live public website.

These tests require a real, launchable Chromium binary. Remediation
(docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md): the earlier module performed the
real launch probe at IMPORT/COLLECTION time, which could hang or fail the
whole pytest collection phase regardless of whether these tests were even
selected. The probe is now LAZY: it only runs inside the
``real_chromium`` fixture, the first time a test that depends on it
actually executes, and only when explicitly opted in via
``AOS_BROWSER_RUN_REAL_TESTS=1`` (unset by default, so `pytest` alone never
attempts to launch a browser). A skip here is NOT equivalent to these
properties being verified -- see docs/PHASE_10_REMEDIATION_REPORT.md for the
explicit disclosure of whether this layer actually ran to completion in the
environment this remediation pass ran in.
"""
from __future__ import annotations

import http.server
import os
import threading

import pytest

from aos.browser.domains import ApprovedDomainRegistry, DomainEnrollmentAuthority
from aos.browser.egress import EgressVerificationResult
from aos.browser.engine import PlaywrightEngineFactory, build_launch_args
from aos.browser.sandbox import SandboxVerificationResult
from aos.browser.supply_chain import SupplyChainVerificationResult
from aos.browser.task import BrowserTaskRunner
from aos.browser.types import BrowserOperation, BrowserTaskSpec, FieldLocator, OperationEntry, new_task_id


class _FakeProxy:
    def stop(self):
        pass



_OPT_IN_ENV_VAR = "AOS_BROWSER_RUN_REAL_TESTS"


def _real_chromium_launchable() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright is not installed"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=list(build_launch_args()))
            browser.close()
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"real chromium launch failed: {exc.__class__.__name__}"


@pytest.fixture(scope="module")
def real_chromium():
    """Lazily probes for a launchable Chromium exactly once, only when a
    test that depends on this fixture actually runs, and only when the
    operator has explicitly opted in. Never runs at collection time."""
    if os.environ.get(_OPT_IN_ENV_VAR) != "1":
        pytest.skip(f"set {_OPT_IN_ENV_VAR}=1 to run Layer-2 real-Chromium tests")
    ok, reason = _real_chromium_launchable()
    if not ok:
        pytest.fail(f"Layer-2 real Chromium gate cannot run in this environment: {reason}")
    return True


class _FixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 -- stdlib signature
        if self.path == "/":
            body = b"<html><body>hello fixture world</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):  # noqa: A002, ANN001 -- silence stdlib server logging
        pass


@pytest.fixture()
def fixture_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_launch_args_never_contain_no_sandbox():
    args = build_launch_args()
    assert "--no-sandbox" not in args


def test_launch_args_never_contain_remote_debugging_port():
    args = build_launch_args()
    assert not any(a.startswith("--remote-debugging-port") for a in args)


def test_real_engine_launch_creates_fresh_profile_and_cleans_up(tmp_path, real_chromium):
    factory = PlaywrightEngineFactory()
    profile_dir = tmp_path / "profile-1"
    profile_dir.mkdir()
    handle = factory.launch(profile_dir=profile_dir, launch_args=build_launch_args())
    try:
        assert handle.is_alive()
    finally:
        handle.close()
    assert not handle.is_alive()


def test_real_navigation_to_loopback_fixture_and_read(tmp_path, fixture_server, real_chromium):
    host, port = fixture_server
    factory = PlaywrightEngineFactory()
    profile_dir = tmp_path / "profile-2"
    profile_dir.mkdir()
    handle = factory.launch(profile_dir=profile_dir, launch_args=build_launch_args())
    try:
        outcome = handle.navigate(f"http://{host}:{port}/", request_validator=lambda url: True)
        assert outcome.ok
        read = handle.read_visible_text()
        assert "hello fixture world" in read.text
    finally:
        handle.close()


def test_request_validator_blocks_navigation_even_with_real_engine(tmp_path, fixture_server, real_chromium):
    host, port = fixture_server
    factory = PlaywrightEngineFactory()
    profile_dir = tmp_path / "profile-3"
    profile_dir.mkdir()
    handle = factory.launch(profile_dir=profile_dir, launch_args=build_launch_args())
    try:
        outcome = handle.navigate(f"http://{host}:{port}/", request_validator=lambda url: False)
        assert not outcome.ok
    finally:
        handle.close()


def test_resolve_field_denies_password_input_via_real_dom_inspection(tmp_path, real_chromium):
    """Remediation Critical #2: classification must be derived from the
    REAL resolved DOM node, not a caller string -- proven here against a
    genuine Chromium-rendered <input type=password>."""
    factory = PlaywrightEngineFactory()
    profile_dir = tmp_path / "profile-4"
    profile_dir.mkdir()
    handle = factory.launch(profile_dir=profile_dir, launch_args=build_launch_args())
    try:
        handle._page.set_content(  # noqa: SLF001 -- test-only direct content injection, no navigation/network involved
            '<label for="pw">Password</label><input id="pw" type="password" role="textbox" aria-label="Password">'
        )
        resolved = handle.resolve_field(FieldLocator(role="textbox", name="Password"))
        assert resolved.exists is True
        assert resolved.input_type == "password"
    finally:
        handle.close()


def test_task_runner_denies_loopback_even_with_a_real_engine_configured(tmp_path, fixture_server, real_chromium):
    """Hard Rule 7 (contract Sec13) has no per-domain, no per-environment,
    and no test-only override: even with a fully real Chromium engine wired
    up and a real fixture server listening, the full BrowserTaskRunner must
    still deny navigation to a loopback address before the engine is ever
    asked to load it."""
    host, port = fixture_server
    registry = ApprovedDomainRegistry(tmp_path / "domains.json")
    approval = DomainEnrollmentAuthority().approve_one(host, human_owner_confirmed=True, origin="terminal", allow_http=True, allow_ip_literal=True)
    domain = registry.enroll(host, approval=approval)

    factory = PlaywrightEngineFactory()
    runner = BrowserTaskRunner(
        registry=registry, engine_factory=factory,
        audit_path=tmp_path / "audit.db", approvals_consumed_path=tmp_path / "consumed.json",
        profile_root=tmp_path / "profiles",
        egress_checker=lambda targets: (EgressVerificationResult(True, "ok"), _FakeProxy()),
        sandbox_checker=lambda: SandboxVerificationResult(True, "ok"),
        supply_chain_checker=lambda: SupplyChainVerificationResult(True, "ok", "1.61.0"),
    )
    url = f"http://{host}:{port}/"
    task_id = new_task_id()
    spec = BrowserTaskSpec(task_id=task_id, domain_id=domain.domain_id, operations=(OperationEntry(BrowserOperation.NAVIGATE, url=url),))
    result = runner.run(spec, approval_callback=lambda request: True)
    # Denied at validation, before any browser process is even launched --
    # no engine handle should have been created for this loopback attempt.
    assert result.state.value == "denied"
