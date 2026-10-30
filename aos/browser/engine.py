"""Browser engine adapter. Playwright is imported ONLY in this module.

Contract architecture Sec2: `engine.py` is "the one place Playwright is
imported." Every other aos/browser/* module and every caller (aos/tools/
browser.py, aos/agent/tool_registry.py, aos/interfaces/cli/browser_commands.py)
must depend only on the BrowserEngineFactory protocol defined here, never on
`playwright` directly.

Remediation (docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md):
- Important #1: no raw CSS/XPath selector or arbitrary JavaScript reaches
  Playwright. Every field reference is a :class:`FieldLocator` resolved via
  ``page.get_by_role`` (accessibility-tree resolution only). Downloads are
  triggered by clicking a resolved locator inside ``expect_download()``, not
  by ``page.evaluate`` with a caller-supplied URL.
- Important #2: normative resource limits (redirect depth, tab count,
  buffered response count/bytes, task bandwidth) are enforced here, not
  merely declared.
"""
from __future__ import annotations

import os
import queue
import re
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from aos.browser.sandbox import (
    FORBIDDEN_LAUNCH_FLAGS,
    FORBIDDEN_PROCESS_CMDLINE_FLAGS,
    ZYGOTE_SANDBOX_EXCEPTION_FLAG,
    assert_launch_args_safe,
    is_headless_shell_executable,
)
from aos.browser.supply_chain import expected_chromium_executable
from aos.browser.types import DEFAULT_RESOURCE_LIMITS, FieldLocator, ResolvedField, ResourceLimits

# Fixed, reviewed launch-argument set. This list is the target of the
# contract Sec14 static bypass scan (grep for `--no-sandbox`) -- it must
# never contain a flag in FORBIDDEN_LAUNCH_FLAGS or a CDP network listener.
BASE_LAUNCH_ARGS: tuple[str, ...] = (
    "--disable-extensions",
    "--disable-component-extensions-with-background-pages",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-translate",
    "--disable-default-apps",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-features=Translate,OptimizationHints,MediaRouter,ServiceWorker,PreloadMediaEngagementData,AutofillServerCommunication,WebRtcHideLocalIpsWithMdns",
    "--disable-prerender-local-predictor",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-webrtc-hw-encoding",
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--disable-quic",
)


def build_launch_args(*, proxy_url: str = "") -> list[str]:
    """Constructs the fixed launch-argument list and asserts it is safe
    before returning -- this is the single choke point every launch path
    must go through (contract Sec5b/Sec5c)."""
    args = list(BASE_LAUNCH_ARGS)
    if proxy_url:
        args.extend((
            f"--proxy-server={proxy_url}",
            "--proxy-bypass-list=<-loopback>",
        ))
    assert_launch_args_safe(args)
    for forbidden in FORBIDDEN_LAUNCH_FLAGS:
        assert forbidden not in args
    return args


@dataclass(frozen=True)
class NavigationOutcome:
    ok: bool
    final_url: str = ""
    status: int | None = None
    redirect_hosts: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class ReadOutcome:
    ok: bool
    text: str = ""
    truncated: bool = False
    title: str = ""
    error: str | None = None


@dataclass(frozen=True)
class DownloadOutcome:
    ok: bool
    local_path: str = ""
    size_bytes: int = 0
    sha256: str = ""
    declared_content_type: str = ""
    error: str | None = None


class EngineHandle(Protocol):
    def navigate(self, url: str, *, request_validator: Callable[[str], bool]) -> NavigationOutcome: ...
    def resolve_field(self, locator: FieldLocator) -> ResolvedField: ...
    def read_visible_text(self) -> ReadOutcome: ...
    def fill(self, locator: FieldLocator, value: str) -> bool: ...
    def clear(self, locator: FieldLocator) -> bool: ...
    def submit(self, locator: FieldLocator) -> bool: ...
    def download(self, locator: FieldLocator, dest_dir: Path, *, request_validator: Callable[[str], bool]) -> DownloadOutcome: ...
    def upload(self, locator: FieldLocator, file_path: Path) -> bool: ...
    def close(self) -> None: ...
    def is_alive(self) -> bool: ...
    def verify_post_launch_sandbox(self) -> bool: ...


class BrowserEngineFactory(Protocol):
    def launch(self, *, profile_dir: Path, launch_args: list[str], limits: ResourceLimits = DEFAULT_RESOURCE_LIMITS) -> EngineHandle: ...


@dataclass
class FakeEngineHandle:
    """Deterministic in-memory test double. No real network, no real process.
    Used by every Layer-1 mocked unit test (test plan Sec1a).

    Fixture shape per URL:
        {
            "text": "...", "title": "...", "status": 200,
            "redirects": ["https://..."],
            "fields": {"<role>:<name>:<nth>": {"input_type": "password", "autocomplete": "current-password"}},
            "downloads": {"<role>:<name>:<nth>": {"download_bytes": b"...", "filename": "f.pdf", "content_type": "application/pdf"}},
        }
    """

    fixture_pages: dict[str, dict] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)
    closed: bool = False
    navigations: list[str] = field(default_factory=list)
    submissions: list[str] = field(default_factory=list)
    limits: ResourceLimits = DEFAULT_RESOURCE_LIMITS

    def navigate(self, url: str, *, request_validator: Callable[[str], bool]) -> NavigationOutcome:
        if not request_validator(url):
            return NavigationOutcome(ok=False, error="request_denied_by_validator")
        self.navigations.append(url)
        page = self.fixture_pages.get(url)
        if page is None:
            return NavigationOutcome(ok=True, final_url=url, status=200)
        redirects = page.get("redirects", [])
        if len(redirects) > self.limits.max_redirect_depth:
            return NavigationOutcome(ok=False, error="redirect_depth_exceeded")
        current = url
        for hop in redirects:
            if not request_validator(hop):
                return NavigationOutcome(ok=False, error="redirect_denied_by_validator", redirect_hosts=tuple(redirects))
            current = hop
        return NavigationOutcome(ok=True, final_url=current, status=page.get("status", 200), redirect_hosts=tuple(redirects))

    def _current_page(self) -> dict:
        if not self.navigations:
            return {}
        return self.fixture_pages.get(self.navigations[-1], {})

    def resolve_field(self, locator: FieldLocator) -> ResolvedField:
        meta = self._current_page().get("fields", {}).get(locator.identity())
        if meta is None:
            return ResolvedField(role=locator.role, accessible_name=locator.name, exists=False)
        return ResolvedField(
            role=locator.role, accessible_name=locator.name, exists=True,
            input_type=meta.get("input_type", ""), autocomplete=meta.get("autocomplete", ""),
        )

    def read_visible_text(self) -> ReadOutcome:
        if not self.navigations:
            return ReadOutcome(ok=False, error="no_page_loaded")
        page = self._current_page()
        text = page.get("text", "")
        limit = 4096
        truncated = len(text) > limit
        return ReadOutcome(ok=True, text=text[:limit], truncated=truncated, title=page.get("title", ""))

    def fill(self, locator: FieldLocator, value: str) -> bool:
        self.fields[locator.identity()] = value
        return True

    def clear(self, locator: FieldLocator) -> bool:
        self.fields.pop(locator.identity(), None)
        return True

    def submit(self, locator: FieldLocator) -> bool:
        self.submissions.append(locator.identity())
        return True

    def download(self, locator: FieldLocator, dest_dir: Path, *, request_validator: Callable[[str], bool]) -> DownloadOutcome:
        entry = self._current_page().get("downloads", {}).get(locator.identity())
        if entry is None:
            return DownloadOutcome(ok=False, error="no_fixture_download")
        synthetic_url = entry.get("url", f"https://fixture.invalid/{locator.identity()}")
        if not request_validator(synthetic_url):
            return DownloadOutcome(ok=False, error="request_denied_by_validator")
        content: bytes = entry["download_bytes"]
        if len(content) > self.limits.max_download_bytes:
            return DownloadOutcome(ok=False, error="exceeds_size_cap")
        import hashlib
        dest_dir.mkdir(parents=True, exist_ok=True)
        local_path = dest_dir / entry.get("filename", "download.bin")
        local_path.write_bytes(content)
        return DownloadOutcome(
            ok=True, local_path=str(local_path), size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            declared_content_type=entry.get("content_type", "application/octet-stream"),
        )

    def upload(self, locator: FieldLocator, file_path: Path) -> bool:
        if not file_path.exists():
            return False
        self.fields[locator.identity()] = f"__uploaded__:{file_path.name}"
        return True

    def close(self) -> None:
        self.closed = True

    def is_alive(self) -> bool:
        return not self.closed

    def verify_post_launch_sandbox(self) -> bool:
        return True


class FakeEngineFactory:
    """Test factory. Each launch returns a fresh handle (mirrors a fresh
    process/profile per task) unless a shared fixture set is injected."""

    def __init__(self, fixture_pages: dict[str, dict] | None = None) -> None:
        self._fixture_pages = fixture_pages or {}
        self.launched_handles: list[FakeEngineHandle] = []
        self.launch_calls: list[list[str]] = []

    def launch(self, *, profile_dir: Path, launch_args: list[str], limits: ResourceLimits = DEFAULT_RESOURCE_LIMITS) -> EngineHandle:
        assert_launch_args_safe(launch_args)
        self.launch_calls.append(launch_args)
        handle = FakeEngineHandle(fixture_pages=self._fixture_pages, limits=limits)
        self.launched_handles.append(handle)
        return handle


@dataclass(frozen=True)
class TrackedProcess:
    """One real Chromium process observed on /proc (evidence record)."""

    pid: int
    argv0: str
    cmdline: str
    seccomp: str
    parent_pid: int = 0
    cap_eff: str = ""
    no_new_privs: str = ""
    user_namespace: str = ""
    pid_namespace: str = ""
    mount_namespace: str = ""

    @property
    def seccomp_confined(self) -> bool:
        return self.seccomp not in ("", "0")

    @property
    def forbidden_flags(self) -> tuple[str, ...]:
        """Sandbox-disabling flags present on this real process. The real
        /proc process tree is authoritative; every listed flag is forbidden
        anywhere, including Playwright-injected flags AOS did not request."""
        return tuple(flag for flag in sorted(FORBIDDEN_PROCESS_CMDLINE_FLAGS) if flag in self.cmdline)

    @property
    def process_type(self) -> str:
        for arg in self.cmdline.split():
            if arg.startswith("--type="):
                return arg.removeprefix("--type=")
        return "browser"

    @property
    def role(self) -> str:
        process_type = self.process_type
        if process_type in {"browser", "zygote", "renderer"}:
            return process_type
        if process_type == "gpu-process":
            return "gpu"
        if process_type == "utility":
            if "--utility-sub-type=network.mojom.NetworkService" in self.cmdline:
                return "network-service utility"
            if "--utility-sub-type=storage.mojom.StorageService" in self.cmdline:
                return "storage utility"
            return "other utility"
        return "unknown"

    @property
    def has_zygote_sandbox_exception(self) -> bool:
        return ZYGOTE_SANDBOX_EXCEPTION_FLAG in self.cmdline

    @property
    def content_sandbox_verified(self) -> bool:
        return (
            self.cap_eff == "0000000000000000"
            and self.no_new_privs == "1"
            and self.seccomp == "2"
            and all(_valid_namespace(value) for value in (self.user_namespace, self.pid_namespace, self.mount_namespace))
        )


class BrowserProcessTracker:
    """Linux /proc based process-tree tracker for one Chromium profile.

    Playwright's sync persistent-context API does not expose a stable public
    Chromium PID. Phase 10 still needs post-launch sandbox evidence and bounded
    cleanup, so the supported mechanism is an OS-level scan for Chromium
    descendants whose command line contains this task's unique profile dir.
    """

    def __init__(self, profile_dir: Path, *, proc_root: Path = Path("/proc"), killer: Callable[[int, int], None] | None = None, expected_executable: str | None = None) -> None:
        self.profile_dir = str(profile_dir)
        # ``proc_root``/``killer`` are injectable ONLY so this scanning and
        # forced-kill logic can be exercised by deterministic Layer-1 unit
        # tests against a synthetic directory tree, without needing real
        # Chromium processes or kill permissions (Codex Important I-1/I-3:
        # this logic was previously unproven by any passing test at all).
        # Production code always uses the real ``/proc`` and ``os.kill``.
        self._proc_root = proc_root
        self._killer = killer or os.kill
        # P10-R1 Finding 1 requirement 5: when set, every real process's
        # argv[0] must be exactly this supply-chain-verified full-Chromium
        # binary -- a headless-shell or any other substitute fails closed.
        self.expected_executable = expected_executable

    def pids(self) -> list[int]:
        proc = self._proc_root
        if not proc.exists():
            return []
        matches: list[int] = []
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            try:
                raw = (entry / "cmdline").read_bytes()
            except (OSError, ValueError):
                continue
            if not raw:
                continue
            cmd = raw.replace(b"\x00", b" ").decode("utf-8", "ignore")
            lowered = cmd.lower()
            if self.profile_dir in cmd and ("chrome" in lowered or "chromium" in lowered):
                matches.append(pid)
        return sorted(matches)

    def process_report(self) -> list[TrackedProcess]:
        """Evidence snapshot of every matched real Chromium process: pid,
        argv[0], full cmdline, and kernel-reported Seccomp mode."""
        report: list[TrackedProcess] = []
        for pid in self.pids():
            try:
                raw = (self._proc_root / str(pid) / "cmdline").read_bytes()
                status = (self._proc_root / str(pid) / "status").read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            # argv[0] extraction must handle BOTH layouts: a normal
            # NUL-separated /proc cmdline, AND Chromium's zygote/renderer
            # processes, which rewrite their own process title into a single
            # SPACE-joined string (so the whole command line lands in the
            # first NUL-delimited field). Split on the first NUL, then on the
            # first space, to get the real executable path either way
            # (P10-R1 remediation: without this, the title-rewritten
            # processes made argv0 == the entire command line and every
            # sandbox check spuriously failed).
            first_field = raw.split(b"\x00", 1)[0]
            argv0 = first_field.split(b" ", 1)[0].decode("utf-8", "ignore")
            cmd = raw.replace(b"\x00", b" ").decode("utf-8", "ignore").strip()
            report.append(TrackedProcess(
                pid=pid,
                argv0=argv0,
                cmdline=cmd,
                seccomp=_status_value(status, "Seccomp"),
                parent_pid=int(_status_value(status, "PPid") or "0"),
                cap_eff=_status_value(status, "CapEff"),
                no_new_privs=_status_value(status, "NoNewPrivs"),
                user_namespace=_namespace_value(self._proc_root, pid, "user"),
                pid_namespace=_namespace_value(self._proc_root, pid, "pid"),
                mount_namespace=_namespace_value(self._proc_root, pid, "mnt"),
            ))
        return report

    def sandbox_verified(self) -> bool:
        """Every matched process must be clean; any single violation fails
        the whole tree.

        Remediation (P10-R1 independent verification Finding 1): the prior
        version returned True on the FIRST seccomp-confined pid without
        inspecting the rest, and never looked at which binary was running.
        It now requires, for EVERY process in the tree: no globally forbidden
        sandbox-disabling flag (`--no-sandbox`, etc.), never the
        chrome-headless-shell binary, argv[0] exactly equal to the
        supply-chain-verified full-Chromium binary when one is bound, and
        seccomp confinement (mode != 0). The sole zygote-only exception is
        separately checked with parent and content-process evidence. Empty
        tree fails closed."""
        report = self.process_report()
        if not report or len(report) != len(self.pids()) or not self.expected_executable:
            return False
        by_pid = {proc.pid: proc for proc in report}
        browser_pids = {proc.pid for proc in report if proc.role == "browser"}
        if len(browser_pids) != 1:
            return False
        for proc in report:
            if proc.forbidden_flags:
                return False
            if is_headless_shell_executable(proc.argv0):
                return False
            if proc.argv0 != self.expected_executable or proc.role == "unknown":
                return False
            if proc.role in {"browser", "renderer", "gpu", "network-service utility", "storage utility", "other utility"} and not proc.content_sandbox_verified:
                return False
            parent = by_pid.get(proc.parent_pid)
            if proc.role != "browser" and parent is None:
                return False
            if proc.has_zygote_sandbox_exception and (
                proc.role != "zygote"
                or parent is None
                or parent.role != "browser"
                or parent.pid not in browser_pids
                or parent.argv0 != self.expected_executable
            ):
                return False
            if proc.role == "zygote" and parent is not None and parent.role not in {"browser", "zygote"}:
                return False
            if proc.role in {"renderer", "gpu", "storage utility"} and (parent is None or parent.role != "zygote"):
                return False
            if proc.role == "network-service utility" and (parent is None or parent.role != "browser"):
                return False
            if proc.role == "other utility" and (parent is None or parent.role not in {"browser", "zygote"}):
                return False
        return True

    def terminate_tree(self, *, timeout_seconds: float = 10.0) -> bool:
        pids = self.pids()
        if not pids:
            return True
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid in self.pids():
                try:
                    self._killer(pid, sig)
                except ProcessLookupError:
                    pass
                except OSError:
                    pass
            deadline = time.monotonic() + (timeout_seconds / 2)
            while time.monotonic() < deadline:
                if not self.pids():
                    return True
                time.sleep(0.05)
        return not self.pids()


def _status_value(status: str, key: str) -> str:
    prefix = f"{key}:"
    for line in status.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip().split()[0]
    return ""


def _namespace_value(proc_root: Path, pid: int, name: str) -> str:
    try:
        return os.readlink(proc_root / str(pid) / "ns" / name)
    except OSError:
        return ""


def _valid_namespace(value: str) -> bool:
    return bool(re.fullmatch(r"(?:user|pid|mnt):\[\d+\]", value))


class _ResourceBudget:
    """Tracks buffered-response count/bytes and total task bandwidth across
    one browser handle's lifetime; once exceeded, every further request is
    aborted regardless of domain validation (contract Sec5a)."""

    def __init__(self, limits: ResourceLimits) -> None:
        self.limits = limits
        self.response_count = 0
        self.bandwidth_bytes = 0
        self.exceeded = False

    def record_response(self, content_length: int) -> None:
        self.response_count += 1
        self.bandwidth_bytes += max(content_length, 0)
        if (
            self.response_count > self.limits.max_buffered_responses
            or content_length > self.limits.max_response_body_bytes
            or self.bandwidth_bytes > self.limits.max_task_bandwidth_bytes
        ):
            self.exceeded = True


class PlaywrightEngineHandle:
    """Real Chromium engine handle. Every request is validated through
    ``request_validator`` before Playwright is permitted to let it proceed
    -- this is the application-layer defense-in-depth control described in
    contract Sec4a. It is NOT a substitute for the mandatory OS/container
    egress-containment precondition checked before this class is ever
    constructed (aos/browser/task.py enforces that ordering)."""

    def __init__(self, playwright, context, page, *, limits: ResourceLimits = DEFAULT_RESOURCE_LIMITS, process_tracker: BrowserProcessTracker | None = None) -> None:  # noqa: ANN001 -- playwright types, kept local to this module
        self._playwright = playwright
        self._context = context
        self._page = page
        self._closed = False
        self._limits = limits
        self._budget = _ResourceBudget(limits)
        self._route_installed = False
        self._process_tracker = process_tracker
        self._install_tab_guard()

    def _install_tab_guard(self) -> None:
        def on_new_page(new_page):  # noqa: ANN001
            # Contract Sec5a max_tabs: no hidden/background tab may persist.
            if len(self._context.pages) > self._limits.max_tabs:
                try:
                    new_page.close()
                except Exception:  # noqa: BLE001
                    pass
        self._context.on("page", on_new_page)

    def _install_route_guard(self, request_validator: Callable[[str], bool]) -> None:
        if self._route_installed:
            return
        self._route_installed = True

        def handler(route):  # noqa: ANN001
            if self._budget.exceeded:
                route.abort("blockedbyclient")
                return
            if request_validator(route.request.url):
                route.continue_()
            else:
                route.abort("blockedbyclient")

        def on_response(response):  # noqa: ANN001
            try:
                length = int(response.headers.get("content-length", "0"))
            except (TypeError, ValueError):
                length = 0
            self._budget.record_response(length)

        self._context.route("**/*", handler)
        self._page.on("response", on_response)

    def navigate(self, url: str, *, request_validator: Callable[[str], bool]) -> NavigationOutcome:
        if not request_validator(url):
            return NavigationOutcome(ok=False, error="request_denied_by_validator")
        self._install_route_guard(request_validator)
        redirect_hosts: list[str] = []

        def on_redirect_response(resp):  # noqa: ANN001
            if 300 <= resp.status < 400:
                redirect_hosts.append(resp.url)

        self._page.on("response", on_redirect_response)
        try:
            response = self._page.goto(url, wait_until="load", timeout=self._limits.task_timeout_seconds * 1000)
        except Exception:  # noqa: BLE001 -- any engine failure becomes a safe typed outcome
            return NavigationOutcome(ok=False, error="navigation_failed")
        if self._budget.exceeded:
            return NavigationOutcome(ok=False, error="resource_budget_exceeded")
        if response is None:
            return NavigationOutcome(ok=False, error="no_response")
        if len(redirect_hosts) > self._limits.max_redirect_depth:
            return NavigationOutcome(ok=False, error="redirect_depth_exceeded", redirect_hosts=tuple(redirect_hosts))
        return NavigationOutcome(
            ok=True, final_url=self._page.url, status=response.status,
            redirect_hosts=tuple(redirect_hosts),
        )

    def resolve_field(self, locator: FieldLocator) -> ResolvedField:
        try:
            element = self._page.get_by_role(locator.role, name=locator.name, exact=True).nth(locator.nth)
            element.wait_for(state="attached", timeout=3000)
            input_type = element.get_attribute("type") or ""
            autocomplete = element.get_attribute("autocomplete") or ""
        except Exception:  # noqa: BLE001
            return ResolvedField(role=locator.role, accessible_name=locator.name, exists=False)
        return ResolvedField(role=locator.role, accessible_name=locator.name, input_type=input_type, autocomplete=autocomplete, exists=True)

    def read_visible_text(self) -> ReadOutcome:
        try:
            text = self._page.inner_text("body")
            title = self._page.title()
        except Exception:  # noqa: BLE001
            return ReadOutcome(ok=False, error="read_failed")
        limit = 4096
        truncated = len(text) > limit
        return ReadOutcome(ok=True, text=text[:limit], truncated=truncated, title=title[:512])

    def _locator(self, locator: FieldLocator):  # noqa: ANN001
        return self._page.get_by_role(locator.role, name=locator.name, exact=True).nth(locator.nth)

    def fill(self, locator: FieldLocator, value: str) -> bool:
        try:
            self._locator(locator).fill(value)
            return True
        except Exception:  # noqa: BLE001
            return False

    def clear(self, locator: FieldLocator) -> bool:
        try:
            self._locator(locator).fill("")
            return True
        except Exception:  # noqa: BLE001
            return False

    def submit(self, locator: FieldLocator) -> bool:
        try:
            self._locator(locator).click()
            return True
        except Exception:  # noqa: BLE001
            return False

    def download(self, locator: FieldLocator, dest_dir: Path, *, request_validator: Callable[[str], bool]) -> DownloadOutcome:
        # Remediation Important #1: no page.evaluate with a caller-supplied
        # URL. The download is triggered only by clicking a resolved,
        # role/name-based locator; the network request it produces is
        # validated by the same context-wide route guard as every other
        # request (installed in navigate()).
        self._install_route_guard(request_validator)
        import hashlib
        try:
            with self._page.expect_download(timeout=self._limits.task_timeout_seconds * 1000) as download_info:
                self._locator(locator).click()
            download = download_info.value
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / download.suggested_filename
            download.save_as(str(dest))
        except Exception:  # noqa: BLE001
            return DownloadOutcome(ok=False, error="download_failed")
        if self._budget.exceeded:
            dest.unlink(missing_ok=True)
            return DownloadOutcome(ok=False, error="resource_budget_exceeded")
        data = dest.read_bytes()
        if len(data) > self._limits.max_download_bytes:
            dest.unlink(missing_ok=True)
            return DownloadOutcome(ok=False, error="exceeds_size_cap")
        return DownloadOutcome(
            ok=True, local_path=str(dest), size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def upload(self, locator: FieldLocator, file_path: Path) -> bool:
        try:
            self._locator(locator).set_input_files(str(file_path))
            return True
        except Exception:  # noqa: BLE001
            return False

    def close(self) -> None:
        """Graceful close of the persistent context and the Playwright
        driver. MUST run on the thread that created them -- Playwright's
        sync API is greenlet-bound to its creating thread and raises
        ``greenlet.error`` from any other thread (P10-R1 Finding 2). In
        production this method only ever executes on the owner thread,
        via :class:`ThreadOwnedEngineHandle`."""
        if self._closed:
            return
        try:
            self._context.close()
        finally:
            try:
                self._playwright.stop()
            finally:
                self._closed = True

    def is_alive(self) -> bool:
        return not self._closed

    def verify_post_launch_sandbox(self) -> bool:
        if self._process_tracker is None:
            return False
        return self._process_tracker.sandbox_verified()


_CLOSE_SENTINEL = "__close__"


@dataclass
class _OwnerCommand:
    method: str
    args: tuple
    kwargs: dict
    reply: "queue.Queue[tuple[str, Any]]"


def _owner_loop(inner: EngineHandle, commands: "queue.Queue[_OwnerCommand]") -> None:
    """Runs on the single owner thread. Executes each command against the
    inner (Playwright-backed) handle and replies with the outcome -- an
    exception is replied as a value, never swallowed. The loop exits after
    the close sentinel is processed."""
    while True:
        cmd = commands.get()
        if cmd.method == _CLOSE_SENTINEL:
            try:
                inner.close()
            except BaseException as exc:  # noqa: BLE001 -- surfaced to the caller, never swallowed
                cmd.reply.put(("error", exc))
            else:
                cmd.reply.put(("ok", None))
            return
        try:
            result = getattr(inner, cmd.method)(*cmd.args, **cmd.kwargs)
        except BaseException as exc:  # noqa: BLE001 -- surfaced to the caller
            cmd.reply.put(("error", exc))
        else:
            cmd.reply.put(("ok", result))


class ThreadOwnedEngineHandle:
    """Executes every engine operation on the ONE thread that created the
    Playwright driver.

    Remediation (P10-R1 independent verification Finding 2): Playwright's
    sync API is greenlet-bound to the thread that created it; invoking any
    of its objects from another thread raises ``greenlet.error: Cannot
    switch to a different thread`` (observed against real Chromium in the
    hardened container). The previous close path did exactly that -- it ran
    ``context.close()`` on a fresh background thread, and its
    completion-flag logic masked the resulting exception. This proxy is the
    fix: one dedicated owner thread receives typed commands (including
    close) through a bounded queue, so launch, every operation, and
    graceful close all execute on the same owning thread. Bounded cleanup
    is preserved by an INDEPENDENT outer watchdog on the calling thread: if
    the owner thread does not answer within the deadline, the caller
    force-terminates the real process tree via /proc + SIGKILL (never
    through Playwright) and raises -- the failure is surfaced to
    BrowserTaskResult/audit by task.py, not swallowed."""

    def __init__(self, *, commands: "queue.Queue[_OwnerCommand]", owner: threading.Thread, tracker: BrowserProcessTracker | None, call_timeout_seconds: float, close_timeout_seconds: float) -> None:
        self._commands = commands
        self._owner = owner
        self._tracker = tracker
        self._call_timeout_seconds = call_timeout_seconds
        self._close_timeout_seconds = close_timeout_seconds
        self._closed = False

    @classmethod
    def spawn(cls, bootstrap: Callable[[], EngineHandle], *, tracker: BrowserProcessTracker | None = None, call_timeout_seconds: float = 660.0, close_timeout_seconds: float = 15.0, launch_timeout_seconds: float = 120.0) -> "ThreadOwnedEngineHandle":
        """Starts the owner thread, runs ``bootstrap`` ON that thread (so the
        Playwright driver is created by the thread that will own it for its
        whole life), and returns the proxy handle. A bootstrap exception is
        re-raised here on the calling thread; a bootstrap that never answers
        within ``launch_timeout_seconds`` triggers the forced /proc cleanup
        path and raises TimeoutError (fail closed, no half-launched handle)."""
        commands: queue.Queue[_OwnerCommand] = queue.Queue(maxsize=4)
        boot_reply: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

        def _owner_main() -> None:
            try:
                inner = bootstrap()
            except BaseException as exc:  # noqa: BLE001 -- re-raised on the calling thread
                boot_reply.put(("error", exc))
                return
            boot_reply.put(("ok", None))
            _owner_loop(inner, commands)

        owner = threading.Thread(target=_owner_main, name="aos-browser-engine-owner", daemon=True)
        owner.start()
        try:
            kind, payload = boot_reply.get(timeout=launch_timeout_seconds)
        except queue.Empty:
            if tracker is not None:
                tracker.terminate_tree(timeout_seconds=10.0)
            raise TimeoutError("browser engine bootstrap did not complete within the bounded timeout") from None
        if kind == "error":
            raise payload
        return cls(commands=commands, owner=owner, tracker=tracker, call_timeout_seconds=call_timeout_seconds, close_timeout_seconds=close_timeout_seconds)

    def _force_cleanup(self) -> bool:
        return self._tracker.terminate_tree(timeout_seconds=10.0) if self._tracker is not None else True

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        if self._closed:
            raise RuntimeError("browser engine handle is closed")
        reply: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)
        try:
            self._commands.put(_OwnerCommand(method, args, dict(kwargs), reply), timeout=5.0)
        except queue.Full:
            self._closed = True
            forced_ok = self._force_cleanup()
            raise TimeoutError(f"browser engine owner thread is not accepting commands (forced process cleanup {'succeeded' if forced_ok else 'FAILED'})") from None
        try:
            kind, payload = reply.get(timeout=self._call_timeout_seconds)
        except queue.Empty:
            # The owner thread is wedged inside the driver. Independent
            # watchdog path: never touch Playwright from this thread; kill
            # the real process tree and surface the timeout.
            self._closed = True
            forced_ok = self._force_cleanup()
            raise TimeoutError(f"browser engine call {method!r} did not complete within the bounded timeout (forced process cleanup {'succeeded' if forced_ok else 'FAILED'})") from None
        if kind == "error":
            raise payload
        return payload

    # --- EngineHandle protocol -------------------------------------------

    def navigate(self, url: str, *, request_validator: Callable[[str], bool]) -> NavigationOutcome:
        return self._call("navigate", url, request_validator=request_validator)

    def resolve_field(self, locator: FieldLocator) -> ResolvedField:
        return self._call("resolve_field", locator)

    def read_visible_text(self) -> ReadOutcome:
        return self._call("read_visible_text")

    def fill(self, locator: FieldLocator, value: str) -> bool:
        return self._call("fill", locator, value)

    def clear(self, locator: FieldLocator) -> bool:
        return self._call("clear", locator)

    def submit(self, locator: FieldLocator) -> bool:
        return self._call("submit", locator)

    def download(self, locator: FieldLocator, dest_dir: Path, *, request_validator: Callable[[str], bool]) -> DownloadOutcome:
        return self._call("download", locator, dest_dir, request_validator=request_validator)

    def upload(self, locator: FieldLocator, file_path: Path) -> bool:
        return self._call("upload", locator, file_path)

    def is_alive(self) -> bool:
        return not self._closed

    def verify_post_launch_sandbox(self) -> bool:
        # Pure /proc inspection on the calling thread -- no Playwright object
        # is touched, so this works even while the owner thread is busy.
        return self._tracker.sandbox_verified() if self._tracker is not None else False

    def close(self) -> None:
        """Graceful close ON the owner thread, bounded by an independent
        outer watchdog. Exceptions and timeouts are raised to the caller
        (task.py records cleanup_failed + a failed terminal event) -- never
        silently swallowed."""
        if self._closed:
            return
        self._closed = True
        reply: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)
        graceful_done = False
        graceful_exc: BaseException | None = None
        try:
            self._commands.put(_OwnerCommand(_CLOSE_SENTINEL, (), {}, reply), timeout=5.0)
        except queue.Full:
            pass  # owner thread wedged -- fall through to the forced path
        else:
            try:
                kind, payload = reply.get(timeout=self._close_timeout_seconds)
            except queue.Empty:
                pass  # graceful close exceeded its deadline
            else:
                graceful_done = True
                if kind == "error":
                    graceful_exc = payload
        # Independent outer watchdog sweep: runs on the calling thread
        # against the real /proc tree, never through Playwright, so it works
        # even when the owner thread is wedged. After a successful graceful
        # close the tree is already empty and this returns True immediately.
        forced_ok = self._force_cleanup()
        if not graceful_done:
            detail = "" if forced_ok else "; forced process-tree cleanup also FAILED"
            raise TimeoutError(f"graceful browser close did not complete within the bounded timeout{detail}")
        if graceful_exc is not None:
            raise graceful_exc
        if not forced_ok:
            raise TimeoutError("browser process tree still existed after forced cleanup")


class PlaywrightEngineFactory:
    """Real engine factory. One fresh FULL-Chromium process (never the
    chrome-headless-shell binary) + one fresh temporary profile per
    ``launch()`` call (contract Sec5b), owned end to end by one dedicated
    thread.

    Remediation (P10-R1 independent verification Finding 1): the original
    launch had TWO compounding defects, both proven on the real /proc
    cmdlines in the hardened container (2026-07-12):
      1. A bare ``headless=True`` makes Playwright 1.61 select the separate
         ``chrome-headless-shell`` binary, which force-disables the sandbox.
      2. Playwright's ``chromium_sandbox`` parameter DEFAULTS TO FALSE, so
         Playwright injects ``--no-sandbox`` itself regardless of the binary.
    The supported Playwright mechanism is ``channel="chromium"`` plus
    ``chromium_sandbox=True`` in new headless mode. None of that is trusted
    on faith: launch additionally (a) resolves the supply-chain-expected
    full-Chromium executable up front, (b) verifies Playwright reports
    exactly that executable, and (c) verifies the REAL post-launch /proc
    process tree -- every process must run the expected binary with no
    forbidden flag -- before any handle is returned. Any mismatch closes the
    browser and the launch fails closed. Never, under any configuration, is
    a sandbox-disabling flag added to make Chromium launch."""

    def launch(self, *, profile_dir: Path, launch_args: list[str], limits: ResourceLimits = DEFAULT_RESOURCE_LIMITS) -> EngineHandle:
        assert_launch_args_safe(launch_args)
        expected_executable = expected_chromium_executable()
        if expected_executable is None:
            raise ValueError("supply chain could not resolve the pinned full-Chromium executable (fail closed)")
        if is_headless_shell_executable(expected_executable):
            raise ValueError("resolved executable is the forbidden headless-shell binary (fail closed)")
        tracker = BrowserProcessTracker(profile_dir, expected_executable=expected_executable)

        def bootstrap() -> EngineHandle:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415 -- isolated import point

            playwright = sync_playwright().start()
            try:
                reported = str(playwright.chromium.executable_path or "")
                if Path(reported) != Path(expected_executable):
                    raise ValueError("playwright would launch a different executable than the supply-chain-verified full-Chromium binary (fail closed)")
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    channel="chromium",  # full Chromium new-headless mode, never chrome-headless-shell fallback
                    chromium_sandbox=True,  # ENABLE the sandbox; Playwright defaults this to False (=> --no-sandbox)
                    headless=True,  # new headless mode on the full binary
                    args=launch_args,
                    service_workers="block",
                    accept_downloads=True,
                )
            except BaseException:
                playwright.stop()
                raise
            page = context.new_page() if not context.pages else context.pages[0]
            inner = PlaywrightEngineHandle(playwright, context, page, limits=limits, process_tracker=tracker)
            if not tracker.sandbox_verified():
                evidence = "; ".join(
                    f"pid={p.pid} type={p.process_type} ppid={p.parent_pid} argv0={p.argv0} "
                    f"forbidden={','.join(p.forbidden_flags) or 'none'} zygote_exception={p.has_zygote_sandbox_exception} "
                    f"capeff={p.cap_eff or '?'} nnp={p.no_new_privs or '?'} seccomp={p.seccomp or '?'} "
                    f"ns={p.user_namespace or '?'}/{p.pid_namespace or '?'}/{p.mount_namespace or '?'}"
                    for p in tracker.process_report()
                ) or "no matching process found on /proc"
                try:
                    inner.close()
                finally:
                    tracker.terminate_tree(timeout_seconds=10.0)
                raise ValueError(f"post-launch process-tree verification failed (fail closed): {evidence}")
            return inner

        return ThreadOwnedEngineHandle.spawn(
            bootstrap,
            tracker=tracker,
            call_timeout_seconds=limits.task_timeout_seconds + 60.0,
            close_timeout_seconds=15.0,
        )
