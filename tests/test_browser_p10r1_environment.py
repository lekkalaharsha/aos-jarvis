"""Focused P10-R1 coverage: the reproducible Chromium verification
environment (docs/PHASE_10_GATE_RECOVERY_PLAN.md Sec6 P10-R1).

Two kinds of test here:

- Deterministic, no-podman, no-Chromium checks that run in the normal
  suite everywhere: the pinned-digest/Containerfile hardening posture and
  ``ops/phase10/container_check.py``'s pure helper functions.
- One opt-in real integration check (``test_container_check_passes_inside_
  hardened_container``), skipped unless ``AOS_BROWSER_P10R1_CONTAINER=1``,
  meant to run ONLY inside the container built from
  ``ops/phase10/Containerfile.layer2`` -- it exercises real Chromium and
  will fail (correctly) anywhere else.

This does not implement or exercise the full Layer-2 matrix
(docs/PHASE_10_GATE_RECOVERY_PLAN.md Sec3); that remains P10-R3 scope.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_DIR = REPO_ROOT / "ops" / "phase10"

spec = importlib.util.spec_from_file_location("p10r1_container_check", OPS_DIR / "container_check.py")
container_check = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(container_check)

seccomp_spec = importlib.util.spec_from_file_location("p10r1_seccomp_profile", OPS_DIR / "seccomp_profile.py")
seccomp_profile = importlib.util.module_from_spec(seccomp_spec)
assert seccomp_spec.loader is not None
seccomp_spec.loader.exec_module(seccomp_profile)


def _profile(*rules: dict) -> dict:
    return {
        "defaultAction": "SCMP_ACT_ERRNO", "defaultErrnoRet": 1, "defaultErrno": "EPERM",
        "archMap": [{"architecture": "SCMP_ARCH_X86_64", "subArchitectures": ["SCMP_ARCH_X86"]}],
        "syscalls": list(rules),
    }


def _conditional_chroot_rule(*names: str) -> dict:
    return {
        "names": list(names),
        "action": "SCMP_ACT_ALLOW",
        "args": [],
        "comment": "",
        "includes": {"caps": ["CAP_SYS_CHROOT"]},
        "excludes": {},
    }


@pytest.mark.skipif(os.name == "nt", reason="os.getuid and Linux /proc status semantics are unavailable on Windows")
def test_read_uid_reads_own_process_uid():
    # read_uid() reads a fixed "/proc/<pid>/status" path; the running test
    # process itself is always a valid pid to read back the real kernel-
    # reported Uid line against os.getuid().
    assert container_check.read_uid(os.getpid()) == str(os.getuid())


def test_read_uid_returns_empty_for_nonexistent_pid():
    assert container_check.read_uid(999_999_999) == ""


def test_expected_title_matches_fixture_file():
    fixture = OPS_DIR / "fixtures" / "nav_fixture.html"
    assert fixture.exists()
    assert container_check.EXPECTED_TITLE in fixture.read_text()


def test_containerfile_pins_base_image_by_digest():
    containerfile = (OPS_DIR / "Containerfile.layer2").read_text()
    assert "FROM mcr.microsoft.com/playwright/python@sha256:" in containerfile
    assert ":v1.61.0-noble\n" not in containerfile.splitlines()[0]  # never a floating tag on FROM


def test_containerfile_runs_as_fixed_non_root_uid():
    containerfile = (OPS_DIR / "Containerfile.layer2").read_text()
    assert "USER ${AOS_UID}:${AOS_GID}" in containerfile
    assert "AOS_UID=10001" in containerfile
    assert "AOS_GID=10001" in containerfile


def test_containerfile_does_not_mount_host_repo():
    containerfile = (OPS_DIR / "Containerfile.layer2").read_text()
    assert "COPY" in containerfile
    assert "VOLUME" not in containerfile


def test_verify_script_never_uses_privileged_or_host_network_or_host_pid():
    script = (OPS_DIR / "verify_p10r1.sh").read_text()
    forbidden = ("--privileged", "--network=host", "--network host", "--pid=host", "--pid host", "/var/run/docker.sock", "/run/podman/podman.sock")
    for token in forbidden:
        assert token not in script, f"forbidden runtime flag/mount present: {token}"
    assert "--network none" in script
    assert "--cap-drop=ALL" in script
    assert "--security-opt no-new-privileges" in script
    assert "--read-only" in script
    assert "--user 10001:10001" in script
    assert "--cap-add=SYS_CHROOT" not in script


def test_verify_script_bounds_resources():
    script = (OPS_DIR / "verify_p10r1.sh").read_text()
    assert "--pids-limit=" in script
    assert "--memory=" in script
    assert "--cpus=" in script
    assert "--stop-timeout" in script


# --- P10-R1 remediation Finding 1: forbidden headless-shell launch ---------


def test_engine_launches_full_binary_with_sandbox_enabled_never_bare_default():
    # Two real defects (proven on /proc cmdlines, 2026-07-12): bare
    # headless=True picks chrome-headless-shell, and Playwright's
    # chromium_sandbox defaults to False (=> it injects --no-sandbox). The
    # fix pins executable_path to the full binary AND enables the sandbox.
    engine_source = (REPO_ROOT / "aos" / "browser" / "engine.py").read_text()
    # The supported mechanism is the full-Chromium channel plus
    # chromium_sandbox=True; the actual binary is still verified against
    # Playwright's reported executable and every real /proc argv0.
    assert 'channel="chromium"' in engine_source
    assert "chromium_sandbox=True" in engine_source


def test_containerfile_removes_headless_shell_binary():
    containerfile = (OPS_DIR / "Containerfile.layer2").read_text()
    assert "rm -rf /ms-playwright/chromium_headless_shell-*" in containerfile
    # and the build fails closed if the full Chromium binary is absent:
    assert "test -x /ms-playwright/chromium-*/chrome-linux*/chrome" in containerfile


def test_headless_shell_executable_is_rejected_as_expected_binary():
    from aos.browser.sandbox import is_headless_shell_executable

    assert is_headless_shell_executable(
        "/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell"
    )
    assert is_headless_shell_executable("/opt/headless_shell/headless_shell")
    assert not is_headless_shell_executable("/ms-playwright/chromium-1228/chrome-linux64/chrome")


def test_no_sandbox_is_a_forbidden_process_flag():
    from aos.browser.sandbox import FORBIDDEN_LAUNCH_FLAGS, FORBIDDEN_PROCESS_CMDLINE_FLAGS

    # --no-sandbox (the real disabler) is forbidden on every real process.
    assert "--no-sandbox" in FORBIDDEN_PROCESS_CMDLINE_FLAGS
    assert FORBIDDEN_LAUNCH_FLAGS <= FORBIDDEN_PROCESS_CMDLINE_FLAGS


def test_no_zygote_sandbox_is_a_tracker_verified_zygote_only_exception():
    from aos.browser.engine import TrackedProcess
    from aos.browser.sandbox import FORBIDDEN_PROCESS_CMDLINE_FLAGS, ZYGOTE_SANDBOX_EXCEPTION_FLAG

    assert ZYGOTE_SANDBOX_EXCEPTION_FLAG not in FORBIDDEN_PROCESS_CMDLINE_FLAGS
    zygote = TrackedProcess(pid=1, argv0="/x/chrome", cmdline="/x/chrome --type=zygote --no-zygote-sandbox", seccomp="2")
    assert zygote.forbidden_flags == ()
    assert zygote.has_zygote_sandbox_exception is True
    renderer = TrackedProcess(pid=2, argv0="/x/chrome", cmdline="/x/chrome --type=renderer --no-zygote-sandbox", seccomp="2")
    assert renderer.has_zygote_sandbox_exception is True


def test_verify_script_runs_the_in_container_pytest_gate():
    script = (OPS_DIR / "verify_p10r1.sh").read_text()
    assert "AOS_BROWSER_P10R1_CONTAINER=1" in script
    assert "tests/test_browser_p10r1_environment.py" in script


def test_verify_script_uses_a_chromium_tailored_seccomp_profile_not_unconfined():
    # P10-R1 remediation: full Chromium's namespace sandbox needs the chroot
    # syscall, whose base-profile capability condition must be replaced rather
    # than appended after it. Chromium then receives the capability only in
    # its nested user namespace, never from the container runtime.
    script = (OPS_DIR / "verify_p10r1.sh").read_text()
    assert "seccomp=unconfined" not in script
    assert "--security-opt" in script
    assert "seccomp=${SECCOMP_PROFILE}" in script
    assert "transform_chroot_rule" in script
    assert "P10-R1 seccomp profile validated" in script


def test_conditional_chroot_only_rule_is_replaced_losslessly():
    source = _profile(_conditional_chroot_rule("chroot"))
    result = seccomp_profile.transform_chroot_rule(source)
    assert result["syscalls"] == [seccomp_profile.CHROOT_RULE]
    assert result["defaultAction"] == source["defaultAction"]


def test_mixed_chroot_rule_preserves_other_names_and_properties():
    mixed = _conditional_chroot_rule("chroot", "pivot_root")
    mixed["comment"] = "preserve-me"
    source = _profile(mixed)
    result = seccomp_profile.transform_chroot_rule(source)
    assert result["syscalls"][0] == {**mixed, "names": ["pivot_root"]}
    assert result["syscalls"][1] == seccomp_profile.CHROOT_RULE


def test_multiple_conditional_chroot_rules_are_replaced_with_one_exact_rule():
    source = _profile(
        _conditional_chroot_rule("chroot"),
        _conditional_chroot_rule("clone", "chroot"),
        {"names": ["read"], "action": "SCMP_ACT_ALLOW", "args": [], "comment": "", "includes": {}, "excludes": {}},
    )
    result = seccomp_profile.transform_chroot_rule(source)
    assert result["syscalls"] == [
        {**source["syscalls"][1], "names": ["clone"]},
        source["syscalls"][2],
        seccomp_profile.CHROOT_RULE,
    ]


def test_duplicate_or_unexpected_unconditional_chroot_rule_fails_closed():
    source = _profile(seccomp_profile.CHROOT_RULE, seccomp_profile.CHROOT_RULE)
    with pytest.raises(seccomp_profile.SeccompProfileError, match="unconditionally"):
        seccomp_profile.transform_chroot_rule(source)


def test_malformed_seccomp_profile_fails_closed():
    with pytest.raises(seccomp_profile.SeccompProfileError):
        seccomp_profile.transform_chroot_rule({"defaultAction": "SCMP_ACT_ERRNO", "syscalls": [{"names": "chroot"}]})


@pytest.mark.parametrize("rule", [
    {"names": ["chroot"]},
    {"names": [], "action": "SCMP_ACT_ALLOW", "args": [], "comment": "", "includes": {}, "excludes": {}},
    {"names": [1], "action": "SCMP_ACT_ALLOW", "args": [], "comment": "", "includes": {}, "excludes": {}},
    {"names": ["chroot"], "action": "SCMP_ACT_ALLOW", "args": "bad", "comment": "", "includes": {}, "excludes": {}},
    {"names": ["chroot"], "action": "SCMP_ACT_ALLOW", "args": [], "comment": "", "includes": {"caps": "bad"}, "excludes": {}},
    {"names": ["chroot"], "action": "SCMP_ACT_ALLOW", "args": [], "comment": "", "includes": {}, "excludes": []},
    {"names": ["chroot"], "action": "SCMP_ACT_KILL", "args": [], "comment": "", "includes": {}, "excludes": {}},
])
def test_malformed_rule_shapes_fail_closed(rule):
    with pytest.raises(seccomp_profile.SeccompProfileError):
        seccomp_profile.transform_chroot_rule(_profile(rule))


def test_valid_podman_profile_transforms_successfully():
    import json
    profile_path = next((path for path in (Path("/usr/share/containers/seccomp.json"), Path("/etc/containers/seccomp.json")) if path.exists()), None)
    source = json.loads(profile_path.read_text()) if profile_path else _profile(_conditional_chroot_rule("chroot"))
    result = seccomp_profile.transform_chroot_rule(source)
    seccomp_profile.validate_chroot_transformation(source, result)


def test_generated_profile_has_one_unconditional_chroot_allow_and_no_other_change():
    other = {"names": ["read", "write"], "action": "SCMP_ACT_ALLOW", "args": [], "comment": "", "includes": {}, "excludes": {}}
    source = _profile(other, _conditional_chroot_rule("chroot"))
    result = seccomp_profile.transform_chroot_rule(source)
    assert result["syscalls"].count(seccomp_profile.CHROOT_RULE) == 1
    assert result["syscalls"][0] == other
    seccomp_profile.validate_chroot_transformation(source, result)


# --- in-container real-Chromium gate tests ---------------------------------

_IN_CONTAINER = pytest.mark.skipif(
    os.environ.get("AOS_BROWSER_P10R1_CONTAINER") != "1",
    reason="P10-R1 real-Chromium check only runs inside the ops/phase10/Containerfile.layer2 container",
)


@_IN_CONTAINER
def test_container_check_passes_inside_hardened_container():
    # main() returns normally (after printing PASSED) on success, and
    # raises FailClosed (a SystemExit subclass) on any failed check.
    container_check.main()


@_IN_CONTAINER
def test_outer_chroot_is_denied_but_nested_user_namespace_chroot_succeeds():
    with pytest.raises(PermissionError):
        os.chroot("/proc/self/fdinfo")
    probe = "import os; os.chroot('/proc/self/fdinfo'); print('nested-chroot-ok')"
    result = subprocess.run(
        ["unshare", "--user", "--map-root-user", "--fork", "python", "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "nested-chroot-ok"


@_IN_CONTAINER
def test_launched_process_tree_is_flag_clean_inside_container(tmp_path):
    """P10-R1 Finding 1 requirement 7: the COMPLETE real launched process
    tree contains no forbidden sandbox flag and runs only the
    supply-chain-verified full-Chromium binary."""
    from aos.browser.engine import BrowserProcessTracker, PlaywrightEngineFactory, build_launch_args
    from aos.browser.sandbox import is_headless_shell_executable
    from aos.browser.supply_chain import expected_chromium_executable

    container_check.ensure_writable_home()
    expected = expected_chromium_executable()
    assert expected is not None
    assert not is_headless_shell_executable(expected)

    profile_dir = tmp_path / "profile"
    handle = PlaywrightEngineFactory().launch(profile_dir=profile_dir, launch_args=build_launch_args())
    tracker = BrowserProcessTracker(profile_dir, expected_executable=expected)
    try:
        report = tracker.process_report()
        assert report, "no real Chromium process found on /proc"
        observed_types = {proc.process_type for proc in report}
        assert {"browser", "renderer", "gpu-process", "utility"} <= observed_types
        for proc in report:
            assert proc.argv0 == expected, f"pid {proc.pid} runs {proc.argv0!r}"
            assert not proc.forbidden_flags, f"pid {proc.pid} carries {proc.forbidden_flags}"
            assert "--no-sandbox" not in proc.cmdline
            if "--no-zygote-sandbox" in proc.cmdline:
                assert proc.process_type == "zygote"
                assert proc.parent_pid in {item.pid for item in report}
            if proc.process_type in {"browser", "renderer", "gpu-process", "utility"}:
                assert proc.content_sandbox_verified
        assert tracker.sandbox_verified() is True
        assert handle.verify_post_launch_sandbox() is True
    finally:
        handle.close()
    assert tracker.pids() == [], "orphan Chromium process(es) remained after close"
