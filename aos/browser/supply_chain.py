"""Browser binary/version supply-chain verification (contract Sec5c).

Fails closed if the pinned Playwright version does not match what's
installed, or if the managed Chromium binary is absent.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# Pinned exactly, per contract Sec5c -- not a floating range. Update only via
# a normal dependency-update PR, reviewed like any other pyproject.toml change.
PINNED_PLAYWRIGHT_VERSION = "1.61.0"


@dataclass(frozen=True)
class SupplyChainVerificationResult:
    verified: bool
    reason: str
    installed_version: str | None = None


def _installed_playwright_version() -> str | None:
    # Reads installed-package metadata only -- never imports the `playwright`
    # module itself, keeping that import isolated to aos/browser/engine.py
    # (architecture Sec2/Sec4: "the one place Playwright is imported").
    from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

    try:
        return version("playwright")
    except PackageNotFoundError:
        return None


def expected_chromium_executable() -> str | None:
    """Resolves the exact FULL-Chromium binary path the pinned Playwright
    package is expected to launch, WITHOUT importing ``playwright`` or
    launching a driver process (isolation rule: Playwright is imported only
    in aos/browser/engine.py).

    Playwright's installed package ships a ``driver/package/browsers.json``
    manifest naming the exact Chromium revision it expects; the managed
    browser binary is installed at a deterministic path derived from that
    revision under ``PLAYWRIGHT_BROWSERS_PATH`` (default
    ``~/.cache/ms-playwright`` on Linux). This function reads that manifest
    via package metadata file listing only and returns the real binary path
    when it exists.

    Remediation (P10-R1 independent verification Finding 1, requirement 5):
    this is the binding anchor for the binary ACTUALLY launched -- the
    engine verifies both Playwright's reported ``executable_path`` and every
    real ``/proc/<pid>/cmdline`` argv[0] against this exact path. It never
    resolves to the separate ``chromium_headless_shell-*`` registry entry.
    The prior version checked only ``chrome-linux/chrome`` and silently
    mis-bound on registries using the newer ``chrome-linux64/`` layout (the
    layout the pinned v1.61.0 image really uses, per container evidence)."""
    from importlib.metadata import PackageNotFoundError, distribution  # noqa: PLC0415

    try:
        dist = distribution("playwright")
    except PackageNotFoundError:
        return None
    files = dist.files or []
    manifest_path = next((f for f in files if f.name == "browsers.json"), None)
    if manifest_path is None:
        return None
    try:
        located = manifest_path.locate()
        data = json.loads(Path(str(located)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    chromium = next((b for b in data.get("browsers", []) if b.get("name") == "chromium"), None)
    if chromium is None or not chromium.get("revision"):
        return None
    browsers_root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".cache" / "ms-playwright")))
    for layout in ("chrome-linux64", "chrome-linux"):
        candidate = browsers_root / f"chromium-{chromium['revision']}" / layout / "chrome"
        if candidate.is_file():
            return str(candidate)
    return None


def _default_binary_present() -> bool:
    """Remediation (docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md Important #5):
    this runs unconditionally in production -- ``binary_checker`` is only
    for test injection, never a reason to skip the check."""
    return expected_chromium_executable() is not None


def verify_supply_chain(*, version_reader=None, binary_checker=None) -> SupplyChainVerificationResult:
    reader = version_reader or _installed_playwright_version
    checker = binary_checker or _default_binary_present
    installed = reader()
    if installed is None:
        return SupplyChainVerificationResult(False, "playwright package is not installed", None)
    if installed != PINNED_PLAYWRIGHT_VERSION:
        return SupplyChainVerificationResult(
            False,
            f"installed playwright {installed!r} does not match pinned {PINNED_PLAYWRIGHT_VERSION!r}",
            installed,
        )
    if not checker():
        return SupplyChainVerificationResult(False, "managed chromium binary is not present", installed)
    return SupplyChainVerificationResult(True, "supply chain verified", installed)
