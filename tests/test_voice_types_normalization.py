"""Tests for voice types and normalization — no optional deps required."""

from __future__ import annotations

import pytest

from aos.voice.normalization import is_empty_transcript, normalize_transcript
from aos.voice.types import (
    AudioInput,
    SpeechResult,
    TranscriptResult,
    VoiceAuditRecord,
    VoiceSessionState,
)


# ---------------------------------------------------------------------------
# AudioInput
# ---------------------------------------------------------------------------


def test_audio_input_valid() -> None:
    a = AudioInput(data=b"\x00\x01", sample_rate=16000, channels=1)
    assert a.sample_rate == 16000
    assert a.channels == 1
    assert a.format == "wav"
    assert a.source == "push-to-talk"


def test_audio_input_rejects_non_positive_sample_rate() -> None:
    with pytest.raises(ValueError, match="sample_rate"):
        AudioInput(data=b"x", sample_rate=0, channels=1)


def test_audio_input_rejects_non_positive_channels() -> None:
    with pytest.raises(ValueError, match="channels"):
        AudioInput(data=b"x", sample_rate=16000, channels=0)


def test_audio_input_is_frozen() -> None:
    a = AudioInput(data=b"x", sample_rate=16000, channels=1)
    with pytest.raises((AttributeError, TypeError)):
        a.data = b"y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TranscriptResult
# ---------------------------------------------------------------------------


def test_transcript_result_valid_confidence() -> None:
    t = TranscriptResult(text="hello", confidence=0.9)
    assert t.confidence == 0.9


def test_transcript_result_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        TranscriptResult(text="hello", confidence=1.5)


def test_transcript_result_allows_none_confidence() -> None:
    t = TranscriptResult(text="hello", confidence=None)
    assert t.confidence is None


def test_transcript_result_is_frozen() -> None:
    t = TranscriptResult(text="hi")
    with pytest.raises((AttributeError, TypeError)):
        t.text = "bye"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# VoiceSessionState
# ---------------------------------------------------------------------------


def test_session_state_enum_values() -> None:
    assert VoiceSessionState.IDLE.value == "idle"
    assert VoiceSessionState.RECORDING.value == "recording"
    assert VoiceSessionState.CANCELLED.value == "cancelled"


# ---------------------------------------------------------------------------
# VoiceAuditRecord — raw transcript NOT in fields
# ---------------------------------------------------------------------------


def test_voice_audit_record_has_no_transcript_field() -> None:
    record = VoiceAuditRecord(event_type="voice.test", transcript_length=42)
    assert not hasattr(record, "transcript_text"), (
        "VoiceAuditRecord must not store raw transcript text"
    )
    assert not hasattr(record, "audio_data"), (
        "VoiceAuditRecord must not store raw audio bytes"
    )
    assert record.transcript_length == 42


# ---------------------------------------------------------------------------
# normalize_transcript
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("run tests", "run tests"),
        ("Run the tests.", "run tests"),
        ("RUN TESTS!", "run tests"),
        ("show git status", "show git status"),
        ("git status", "show git status"),
        ("what's the git status", "show git status"),
        ("find todos", "find TODOs"),
        ("find to-dos", "find TODOs"),
        ("current branch", "what branch am I on"),
        ("what branch am i on", "what branch am I on"),
        ("draft a commit", "draft a commit message"),
        ("show recent commits", "show recent commits"),
    ],
)
def test_normalize_transcript_aliases(raw: str, expected: str) -> None:
    assert normalize_transcript(raw) == expected


def test_normalize_transcript_strips_fillers() -> None:
    result = normalize_transcript("uh run tests")
    assert "uh" not in result.lower()
    assert "tests" in result.lower()


def test_normalize_transcript_whitespace() -> None:
    result = normalize_transcript("  run   tests  ")
    assert result == "run tests"


def test_normalize_transcript_is_idempotent() -> None:
    once = normalize_transcript("Run the tests.")
    twice = normalize_transcript(once)
    assert once == twice


def test_normalize_transcript_empty_returns_empty() -> None:
    assert normalize_transcript("") == ""
    assert normalize_transcript("   ") == ""


def test_is_empty_transcript_true_for_blank() -> None:
    assert is_empty_transcript("") is True
    assert is_empty_transcript("  ") is True


def test_is_empty_transcript_false_for_text() -> None:
    assert is_empty_transcript("run tests") is False
