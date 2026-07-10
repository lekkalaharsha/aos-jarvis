"""Phase 0 eval runner.

There is no agent loop yet (that is Phase 3), so this does not route through
a real intent pipeline. It runs a tiny, deterministic keyword classifier
against each fixture and checks the outcome matches what the fixture expects.
This is enough to guard the Phase 0 promises: safe commands work, dangerous
or out-of-phase requests are refused/denied, never executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase0_basic.yaml"

_UNSAFE_KEYWORDS = ("rm -rf", "sudo", "format c:")
_OUT_OF_PHASE_KEYWORDS = {
    "voice": "voice_build",
    "dashboard": "dashboard_build",
    "browser": "browser_build",
    "screen": "screen_build",
}


def _classify(user_says: str) -> str:
    text = user_says.lower()

    if any(keyword in text for keyword in _UNSAFE_KEYWORDS):
        return "deny_unsafe"

    for keyword, _ in _OUT_OF_PHASE_KEYWORDS.items():
        if keyword in text:
            return "refuse_out_of_phase"

    if "audit" in text and "verify" in text:
        return "audit_verify"
    if "audit" in text and ("show" in text or "list" in text):
        return "audit_list"

    return "unknown"


@dataclass(frozen=True)
class EvalOutcome:
    eval_id: str
    passed: bool
    detail: str


def run_fixtures(fixture_path: Path = FIXTURE_PATH) -> list[EvalOutcome]:
    fixtures = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    outcomes = []

    for fixture in fixtures:
        actual = _classify(fixture["user_says"])
        expected = fixture["expected_action"]
        passed = actual == expected
        detail = f"expected={expected} actual={actual}"
        outcomes.append(EvalOutcome(eval_id=fixture["id"], passed=passed, detail=detail))

    return outcomes
