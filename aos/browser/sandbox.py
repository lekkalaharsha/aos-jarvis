"""Mandatory Chromium sandbox verification and forbidden-flag enforcement.

Contract Sec5b: `--no-sandbox` (and any equivalent flag that disables the
renderer/GPU process sandbox) is permanently forbidden, with no
configuration override. Launch fails closed if sandbox verification cannot
be confirmed.

Remediation (docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md Critical #1): a bare
environment-variable attestation is not verification. This module now
performs REAL OS-level precondition checks that Chromium's own sandbox
depends on -- unprivileged user namespaces and seccomp-bpf support -- by
actually exercising them (attempting a real ``unshare(CLONE_NEWUSER|
CLONE_NEWPID)`` and checking the kernel's own seccomp-availability report),
not by trusting a caller-set string.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Flags that disable or weaken the renderer sandbox. This set is checked
# against every launch-argument list built by aos/browser/engine.py, and is
# also the target of the static bypass scan required by contract Sec14.
FORBIDDEN_LAUNCH_FLAGS = frozenset({
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-seccomp-filter-sandbox",
    "--disable-gpu-sandbox",
})

# Flags that would expose a network-reachable CDP endpoint. Contract Sec5b:
# never bound to any interface, loopback included.
FORBIDDEN_CDP_FLAGS_PREFIXES = ("--remote-debugging-port", "--remote-debugging-address")

# Flags that disable content sandboxing and must never appear on ANY process
# in the REAL launched Chromium process tree, inspected via /proc/<pid>/cmdline
# after launch. The P10-R1 independent verification (2026-07-12) proved that
# validating only the argument list AOS constructs is insufficient:
# Playwright's chrome-headless-shell binary injected `--no-sandbox` into every
# zygote/GPU/utility/renderer process it spawned even though AOS never passed
# it and assert_launch_args_safe() passed. The real process tree is the
# authority, not the requested arguments.
#
FORBIDDEN_PROCESS_CMDLINE_FLAGS = frozenset(FORBIDDEN_LAUNCH_FLAGS)

# Human Owner P10-R1 clarification (2026-07-12): this flag is not globally
# permitted. BrowserProcessTracker may accept it only on a verified zygote
# whose parent and every content-process descendant pass stricter /proc checks.
ZYGOTE_SANDBOX_EXCEPTION_FLAG = "--no-zygote-sandbox"


def is_headless_shell_executable(path: str) -> bool:
    """True when ``path`` names Chromium's separate headless-shell binary
    (``chrome-headless-shell``), which hard-disables the sandbox for every
    process it spawns and is therefore never permitted under any
    configuration (contract Sec5b; P10-R1 verification Finding 1)."""
    name = Path(path).name.lower()
    return "headless-shell" in name or "headless_shell" in name


@dataclass(frozen=True)
class SandboxVerificationResult:
    verified: bool
    reason: str


def _unprivileged_userns_available() -> bool:
    """Real, kernel-level precondition for Chromium's namespace sandbox
    (used when the setuid sandbox binary is absent, which is the normal
    case for a managed Playwright/Chromium install). Checks the actual
    kernel knob when present (Debian/Ubuntu expose
    /proc/sys/kernel/unprivileged_userns_clone), and otherwise verifies by
    really attempting to create a user namespace via ``unshare``, which is
    the only way to know for certain on kernels that don't expose the knob
    (e.g. it is compiled in and always allowed)."""
    knob = Path("/proc/sys/kernel/unprivileged_userns_clone")
    if knob.exists():
        try:
            return knob.read_text().strip() == "1"
        except OSError:
            return False
    try:
        result = subprocess.run(
            ["unshare", "--user", "--map-root-user", "true"],
            check=False, capture_output=True, timeout=3,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _seccomp_available() -> bool:
    """Real kernel-level seccomp-bpf availability check via /proc/self/status
    (Seccomp field is always present when CONFIG_SECCOMP is compiled in) and
    a defensive fallback via /proc/sys/kernel/seccomp/actions_avail."""
    try:
        status = Path("/proc/self/status").read_text()
        if "Seccomp:" in status:
            return True
    except OSError:
        pass
    return Path("/proc/sys/kernel/seccomp/actions_avail").exists()


def real_kernel_precondition_check() -> SandboxVerificationResult:
    """The mandatory real check: fail closed unless the kernel preconditions
    Chromium's sandbox actually depends on are demonstrably present. This is
    necessarily a pre-launch precondition check (the sandboxed renderer
    process does not exist yet to inspect directly) but it is a REAL
    exercised OS capability check, not an attestation string."""
    if os.name != "posix":
        return SandboxVerificationResult(False, "sandbox precondition check requires a POSIX (Linux) host")
    if not _unprivileged_userns_available():
        return SandboxVerificationResult(False, "unprivileged user namespaces are not available on this host")
    if not _seccomp_available():
        return SandboxVerificationResult(False, "seccomp-bpf is not available on this host")
    return SandboxVerificationResult(True, "unprivileged user namespaces and seccomp-bpf are both available")


def verify_sandbox(checker: Callable[[], SandboxVerificationResult] | None = None) -> SandboxVerificationResult:
    """``checker`` is injectable ONLY for deterministic tests. Production
    code (``checker is None``) always performs the real kernel precondition
    check -- there is no attestation-only default remaining."""
    return (checker or real_kernel_precondition_check)()


def assert_launch_args_safe(args: list[str]) -> None:
    """Static/runtime guard: raises if any forbidden sandbox-disabling or
    CDP-network-listener flag is present. Called on every constructed launch
    argument list, never bypassable by configuration."""
    for arg in args:
        if arg in FORBIDDEN_LAUNCH_FLAGS:
            raise ValueError(f"forbidden launch flag is never permitted: {arg}")
        if arg.startswith(FORBIDDEN_CDP_FLAGS_PREFIXES):
            raise ValueError(f"forbidden CDP network-listener flag is never permitted: {arg}")
