from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "PHASE_CONTRACT.md"


def test_phase_contract_has_required_sections():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "Active Phase" in text
    assert "Forbidden Work" in text
    assert "Exit Criteria" in text
