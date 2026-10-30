"""Deterministic Layer-1 coverage of BrowserProcessTracker's /proc-scanning
and forced-kill logic (Codex fresh gate Important I-1/I-3: this logic was
previously unproven by any passing test at all -- Layer-2 real-Chromium
proof remains blocked by this sandbox's environment, but the scanning/kill
algorithm itself is independently, deterministically testable against a
synthetic /proc-shaped directory tree with no real process involved).
"""
from __future__ import annotations

import os

import pytest

from aos.browser.engine import BrowserProcessTracker


pytestmark = pytest.mark.skipif(
    os.name == "nt",
    reason="synthetic /proc namespace symlinks require Unix procfs semantics and are not available on Windows",
)


def _make_proc_entry(proc_root, pid: int, *, cmdline: str, status: str = "", parent_pid: int = 0) -> None:
    entry = proc_root / str(pid)
    entry.mkdir(parents=True)
    (entry / "cmdline").write_bytes(cmdline.replace(" ", "\x00").encode() + b"\x00")
    (entry / "status").write_text(f"PPid:\t{parent_pid}\n{status}", encoding="utf-8")
    namespace_dir = entry / "ns"
    namespace_dir.mkdir()
    for name in ("user", "pid", "mnt"):
        (namespace_dir / name).symlink_to(f"{name}:[4026532000]")


def test_pids_matches_only_chromium_processes_with_this_profile_dir(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "task-abc-profile"
    _make_proc_entry(proc_root, 100, cmdline=f"/usr/bin/chrome --user-data-dir={profile_dir}")
    _make_proc_entry(proc_root, 200, cmdline="/usr/bin/some-other-process --unrelated")
    _make_proc_entry(proc_root, 300, cmdline=f"/usr/bin/bash --profile {profile_dir}")  # matches dir, not chrome
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.pids() == [100]


def test_pids_ignores_non_numeric_proc_entries(tmp_path):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "self").mkdir()
    (proc_root / "meminfo").write_text("")
    profile_dir = tmp_path / "profile"
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.pids() == []


def test_sandbox_verified_true_for_valid_real_shaped_tree(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(
        proc_root, 111,
        cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --headless",
        status=SECCOMP_ON,
    )
    _make_proc_entry(proc_root, 112, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=zygote", status=SECCOMP_ON, parent_pid=111)
    _make_proc_entry(proc_root, 113, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=renderer", status=SECCOMP_ON, parent_pid=112)
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME)
    assert tracker.sandbox_verified() is True


def test_sandbox_verified_false_when_no_matching_process(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.sandbox_verified() is False


def test_sandbox_verified_false_when_forbidden_flag_present_even_with_seccomp(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(
        proc_root, 222,
        cmdline=f"/usr/bin/chrome --user-data-dir={profile_dir} --no-sandbox",
        status="Seccomp:\t2\n",
    )
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.sandbox_verified() is False


def test_sandbox_verified_false_when_seccomp_disabled(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(
        proc_root, 333,
        cmdline=f"/usr/bin/chrome --user-data-dir={profile_dir}",
        status="Seccomp:\t0\n",
    )
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.sandbox_verified() is False


def test_terminate_tree_true_when_no_matching_processes(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.terminate_tree(timeout_seconds=0.2) is True


def test_terminate_tree_kills_and_removes_matching_processes(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 444, cmdline=f"/usr/bin/chrome --user-data-dir={profile_dir}")
    killed: list[tuple[int, int]] = []

    def fake_killer(pid: int, sig: int) -> None:
        killed.append((pid, sig))
        # Simulate the OS actually terminating the process: its /proc
        # entry disappears, which is exactly what the real terminate_tree
        # polling loop is watching for.
        entry = proc_root / str(pid)
        if entry.exists():
            import shutil
            shutil.rmtree(entry)

    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root, killer=fake_killer)
    assert tracker.terminate_tree(timeout_seconds=2.0) is True
    assert (444, 15) in killed  # SIGTERM tried first
    assert tracker.pids() == []


def test_terminate_tree_false_when_process_never_dies(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 555, cmdline=f"/usr/bin/chrome --user-data-dir={profile_dir}")

    def stubborn_killer(pid: int, sig: int) -> None:
        pass  # never actually removes the /proc entry -- simulates an unkillable process

    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root, killer=stubborn_killer)
    assert tracker.terminate_tree(timeout_seconds=0.2) is False


# --- P10-R1 Finding 1 regressions: the real headless-shell tree observed in
# --- the hardened container (2026-07-12) must be rejected, and the tracker
# --- must inspect EVERY process, bound to the expected full-Chromium binary.

HEADLESS_SHELL = "/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell"
FULL_CHROME = "/ms-playwright/chromium-1228/chrome-linux64/chrome"
SECCOMP_ON = "Seccomp:\t2\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\n"


def test_sandbox_verified_false_for_headless_shell_binary_even_when_flag_clean(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 14, cmdline=f"{HEADLESS_SHELL} --user-data-dir={profile_dir}", status=SECCOMP_ON)
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.sandbox_verified() is False


def test_no_zygote_sandbox_allowed_only_on_verified_zygote(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 15, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir}", status=SECCOMP_ON)
    _make_proc_entry(proc_root, 16, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=zygote --no-zygote-sandbox", status=SECCOMP_ON, parent_pid=15)
    _make_proc_entry(proc_root, 17, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=renderer", status=SECCOMP_ON, parent_pid=16)
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME)
    assert tracker.sandbox_verified() is True


def test_no_zygote_sandbox_rejected_on_renderer(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 16, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=renderer --no-zygote-sandbox", status=SECCOMP_ON)
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.sandbox_verified() is False


def test_no_zygote_sandbox_rejected_without_a_browser_tree_parent(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 16, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=zygote --no-zygote-sandbox", status=SECCOMP_ON, parent_pid=999)
    assert BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME).sandbox_verified() is False


def test_content_process_requires_zero_capabilities_nnp_seccomp_and_namespaces(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 15, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir}", status=SECCOMP_ON)
    _make_proc_entry(proc_root, 16, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=renderer", status="Seccomp:\t2\nNoNewPrivs:\t1\nCapEff:\t0000000000040000\n", parent_pid=15)
    assert BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME).sandbox_verified() is False


def test_sandbox_verified_false_when_any_process_is_seccomp_unconfined(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 15, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir}", status=SECCOMP_ON)
    _make_proc_entry(proc_root, 16, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=renderer", status="Seccomp:\t0\n")
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME)
    assert tracker.sandbox_verified() is False


def test_sandbox_verified_inspects_every_process_not_just_the_first(tmp_path):
    # Regression: the prior implementation returned True at the FIRST
    # seccomp-confined pid, never reaching a later process carrying a
    # forbidden flag.
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 100, cmdline=f"/usr/bin/chrome --user-data-dir={profile_dir}", status=SECCOMP_ON)
    _make_proc_entry(proc_root, 200, cmdline=f"/usr/bin/chrome --user-data-dir={profile_dir} --type=renderer --no-sandbox", status=SECCOMP_ON)
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    assert tracker.sandbox_verified() is False


def test_sandbox_verified_false_when_argv0_differs_from_expected_executable(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 300, cmdline=f"/usr/bin/some-other-chrome --user-data-dir={profile_dir}", status=SECCOMP_ON)
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME)
    assert tracker.sandbox_verified() is False


def test_sandbox_verified_true_when_every_process_runs_expected_binary_flag_clean(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 400, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --headless", status=SECCOMP_ON)
    _make_proc_entry(proc_root, 401, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=zygote", status=SECCOMP_ON, parent_pid=400)
    _make_proc_entry(proc_root, 402, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=renderer", status=SECCOMP_ON, parent_pid=401)
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME)
    assert tracker.sandbox_verified() is True


def test_process_report_exposes_argv0_forbidden_flags_and_seccomp(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    # A RENDERER carrying both flags is rejected: --no-sandbox is globally
    # forbidden and the zygote-only exception does not apply.
    _make_proc_entry(proc_root, 500, cmdline=f"{HEADLESS_SHELL} --user-data-dir={profile_dir} --type=renderer --no-zygote-sandbox --no-sandbox", status=SECCOMP_ON)
    tracker = BrowserProcessTracker(profile_dir, proc_root=proc_root)
    report = tracker.process_report()
    assert len(report) == 1
    proc = report[0]
    assert proc.pid == 500
    assert proc.argv0 == HEADLESS_SHELL
    assert proc.seccomp == "2"
    assert proc.forbidden_flags == ("--no-sandbox",)
    assert proc.has_zygote_sandbox_exception is True


def test_zygote_exception_requires_direct_browser_parent(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 1, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir}", status=SECCOMP_ON)
    _make_proc_entry(proc_root, 2, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=zygote", status=SECCOMP_ON, parent_pid=1)
    _make_proc_entry(proc_root, 3, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=zygote --no-zygote-sandbox", status=SECCOMP_ON, parent_pid=2)
    assert BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME).sandbox_verified() is False


def test_zygote_exception_rejects_utility_parent_and_fake_browser_pid(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 1, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir}", status=SECCOMP_ON)
    _make_proc_entry(proc_root, 2, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=utility", status=SECCOMP_ON, parent_pid=1)
    _make_proc_entry(proc_root, 3, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=zygote --no-zygote-sandbox", status=SECCOMP_ON, parent_pid=2)
    assert BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME).sandbox_verified() is False


def test_browser_requires_exact_security_state_and_namespaces(tmp_path):
    for status in (
        "Seccomp:\t0\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\n",
        "Seccomp:\t1\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\n",
        "Seccomp:\t3\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\n",
        "Seccomp:\t2\nNoNewPrivs:\t0\nCapEff:\t0000000000000000\n",
        "Seccomp:\t2\nNoNewPrivs:\t1\nCapEff:\t0000000000040000\n",
        "Seccomp:\t2\nNoNewPrivs:\t1\n",
    ):
        proc_root = tmp_path / str(abs(hash(status)))
        profile_dir = tmp_path / "profile"
        _make_proc_entry(proc_root, 1, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir}", status=status)
        assert BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME).sandbox_verified() is False


def test_unknown_role_and_malformed_proc_data_fail_closed(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 1, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir} --type=unknown", status=SECCOMP_ON)
    assert BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME).sandbox_verified() is False


def test_browser_missing_namespace_evidence_fails_closed(tmp_path):
    proc_root = tmp_path / "proc"
    profile_dir = tmp_path / "profile"
    _make_proc_entry(proc_root, 1, cmdline=f"{FULL_CHROME} --user-data-dir={profile_dir}", status=SECCOMP_ON)
    (proc_root / "1" / "ns" / "mnt").unlink()
    assert BrowserProcessTracker(profile_dir, proc_root=proc_root, expected_executable=FULL_CHROME).sandbox_verified() is False
