"""P10-R1 reproducible verification command.

Runs inside the hardened rootless-Podman container built from
``ops/phase10/Containerfile.layer2`` (non-root UID/GID, read-only root
filesystem, no host network, no persistent profile). Launches real FULL
Chromium (never chrome-headless-shell) through the existing production
``aos.browser.engine`` code, confirms it is not running as root, confirms
every real process in the tree runs the supply-chain-verified binary with
no forbidden sandbox flag (including ``--no-sandbox``); any
``--no-zygote-sandbox`` use must satisfy the verified zygote-only exception,
prints the actual ``/proc/<pid>/cmdline`` evidence, navigates one static
local fixture file, closes Chromium gracefully on the engine's owner
thread, and confirms no Chromium process remains.

Scope: P10-R1 only -- reproducible environment plus the minimal launch/
navigation/cleanup smoke checks needed to validate it. This is not the
full Layer-2 matrix (docs/PHASE_10_GATE_RECOVERY_PLAN.md Sec3) and it does
not implement or claim OS/container egress containment (P10-R2 scope).

Fails closed: any unmet precondition or check prints ``FAIL-CLOSED: ...``
to stderr and exits non-zero. There is no bypass flag.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aos.browser.engine import BrowserProcessTracker, PlaywrightEngineFactory, build_launch_args
from aos.browser.sandbox import is_headless_shell_executable, verify_sandbox
from aos.browser.supply_chain import expected_chromium_executable
from aos.browser.types import DEFAULT_RESOURCE_LIMITS

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "nav_fixture.html"
EXPECTED_TITLE = "AOS Phase 10 P10-R1 Fixture"


class FailClosed(SystemExit):
    def __init__(self, reason: str) -> None:
        print(f"FAIL-CLOSED: {reason}", file=sys.stderr)
        super().__init__(1)


def read_uid(pid: int) -> str:
    """Real /proc/<pid>/status Uid (real UID field), '' if unreadable."""
    try:
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return ""
    for line in status.splitlines():
        if line.startswith("Uid:"):
            parts = line.split()
            return parts[1] if len(parts) > 1 else ""
    return ""


def ensure_writable_home() -> None:
    """Point HOME (and XDG dirs) at a writable location on the container's
    writable tmpfs if the default HOME is not writable.

    P10-R1 remediation (Finding 1 fallout): under a read-only root
    filesystem, full Chrome-for-Testing's crashpad handler needs a writable
    HOME; the image's /home/aos is not writable by the non-root runtime user
    once the root fs is read-only (or its tmpfs is root-owned), which
    manifested as a crashpad ``--database is required`` SIGTRAP before the
    browser even started. Repointing HOME to the writable /tmp tmpfs is a
    container-environment fix, not an app-logic or sandbox change."""
    current = os.environ.get("HOME", "")
    if current and os.access(current, os.W_OK):
        return
    new_home = Path(tempfile.gettempdir()) / "aos-browser-home"
    (new_home / ".config").mkdir(parents=True, exist_ok=True)
    (new_home / ".cache").mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(new_home)
    os.environ.setdefault("XDG_CONFIG_HOME", str(new_home / ".config"))
    os.environ.setdefault("XDG_CACHE_HOME", str(new_home / ".cache"))
    print(f"repointed HOME to writable {new_home}")


def check_not_root() -> None:
    if os.getuid() == 0 or os.getgid() == 0:
        raise FailClosed(f"verification process itself is running as root (uid={os.getuid()}, gid={os.getgid()})")


def check_kernel_preconditions() -> None:
    result = verify_sandbox()
    if not result.verified:
        raise FailClosed(f"sandbox kernel preconditions not verified: {result.reason}")


def print_and_check_process_evidence(tracker: BrowserProcessTracker, expected_executable: str, label: str) -> None:
    """Prints the real /proc/<pid>/cmdline evidence for every Chromium
    descendant and fails closed on any forbidden flag, wrong binary, or
    root-owned process. The tracker also validates the narrowly approved
    zygote-only exception and content-process sandbox state."""
    report = tracker.process_report()
    if not report:
        raise FailClosed(f"no Chromium process found on /proc ({label})")
    print(f"--- real /proc process-tree evidence ({label}): {len(report)} process(es) ---")
    for proc in report:
        uid = read_uid(proc.pid)
        print(
            f"pid={proc.pid} ppid={proc.parent_pid} type={proc.process_type} uid={uid or '?'} "
            f"seccomp={proc.seccomp or '?'} capeff={proc.cap_eff or '?'} nnp={proc.no_new_privs or '?'} "
            f"zygote_exception={proc.has_zygote_sandbox_exception} forbidden={','.join(proc.forbidden_flags) or 'none'}"
        )
        print(f"  namespaces: user={proc.user_namespace or '?'} pid={proc.pid_namespace or '?'} mnt={proc.mount_namespace or '?'}")
        print(f"  cmdline: {proc.cmdline}")
        if uid in ("", "0"):
            raise FailClosed(f"Chromium process {proc.pid} is running as uid {uid or 'unknown'}, not a fixed non-root uid ({label})")
        if proc.forbidden_flags:
            raise FailClosed(f"forbidden sandbox flag(s) {proc.forbidden_flags} on real process {proc.pid} ({label})")
        if is_headless_shell_executable(proc.argv0):
            raise FailClosed(f"process {proc.pid} is running the forbidden chrome-headless-shell binary ({label})")
        if proc.argv0 != expected_executable:
            raise FailClosed(f"process {proc.pid} runs {proc.argv0!r}, not the supply-chain-verified binary ({label})")


def main() -> None:
    check_not_root()
    ensure_writable_home()
    check_kernel_preconditions()

    if not FIXTURE_PATH.exists():
        raise FailClosed(f"local fixture missing: {FIXTURE_PATH}")

    expected_executable = expected_chromium_executable()
    if expected_executable is None:
        raise FailClosed("supply chain could not resolve the pinned full-Chromium executable")
    if is_headless_shell_executable(expected_executable):
        raise FailClosed(f"resolved executable is the forbidden headless-shell binary: {expected_executable}")
    print(f"supply-chain-verified full-Chromium executable: {expected_executable}")

    profile_path: Path | None = None
    with tempfile.TemporaryDirectory(prefix="aos-p10r1-profile-") as profile_dir:
        profile_path = Path(profile_dir)
        launch_args = build_launch_args()  # no proxy_url: P10-R1 has no network, egress is P10-R2 scope

        try:
            handle = PlaywrightEngineFactory().launch(
                profile_dir=profile_path, launch_args=launch_args, limits=DEFAULT_RESOURCE_LIMITS,
            )
        except Exception as exc:  # noqa: BLE001 -- any launch failure must fail closed, not crash uncaught
            raise FailClosed(f"Chromium failed to launch: {exc}") from exc

        tracker = BrowserProcessTracker(profile_path, expected_executable=expected_executable)
        print_and_check_process_evidence(tracker, expected_executable, "post-launch")

        if not tracker.sandbox_verified():
            handle.close()
            raise FailClosed("post-launch sandbox verification failed for the launched Chromium process tree")

        if not handle.verify_post_launch_sandbox():
            handle.close()
            raise FailClosed("post-launch sandbox verification (engine handle) failed")

        fixture_url = f"file://{FIXTURE_PATH}"
        outcome = handle.navigate(fixture_url, request_validator=lambda _url: True)
        if not outcome.ok:
            handle.close()
            raise FailClosed(f"local fixture navigation failed: {outcome.error}")

        read = handle.read_visible_text()
        if not read.ok or EXPECTED_TITLE not in read.title:
            handle.close()
            raise FailClosed(f"local fixture content mismatch: title={read.title!r}")

        # Re-inspect after navigation: renderers spawned for the page must
        # also be flag-clean and run the expected binary.
        print_and_check_process_evidence(tracker, expected_executable, "post-navigation")

        try:
            handle.close()
        except Exception as exc:  # noqa: BLE001 -- a close failure (timeout, greenlet/thread error, driver error) is a FAIL, never swallowed
            raise FailClosed(f"graceful Chromium close failed: {type(exc).__name__}: {exc}") from exc

        if tracker.pids():
            raise FailClosed("Chromium process(es) still present after close()")
    if profile_path is not None and profile_path.exists():
        raise FailClosed(f"temporary Chromium profile still exists after cleanup: {profile_path}")

    print(
        "P10-R1 in-container verification PASSED: non-root, sandboxed, "
        "real FULL Chromium launched (never headless-shell), no forbidden "
        "flag on any real process, navigated a local fixture, closed "
        "gracefully on the owner thread, and left no process tree behind."
    )


if __name__ == "__main__":
    main()
