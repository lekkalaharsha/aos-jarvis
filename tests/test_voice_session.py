"""Tests for PushToTalkSession lifecycle using an injected recorder.

No real microphone or audio hardware is used.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from aos.voice.session import MAX_RECORDING_SECONDS, PushToTalkSession, RecordingTimedOutError
from aos.voice.types import AudioInput, VoiceSessionState


def _silent_recorder(max_seconds: int, sample_rate: int, channels: int) -> bytes:
    """Returns minimal WAV bytes (44-byte header + silence)."""
    import io
    import wave

    buf = io.BytesIO()
    num_frames = max(1, max_seconds * sample_rate)
    pcm = bytes(num_frames * channels * 2)  # int16 silence
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _error_recorder(max_seconds: int, sample_rate: int, channels: int) -> bytes:
    raise OSError("mock device error")


# ---------------------------------------------------------------------------
# Normal lifecycle
# ---------------------------------------------------------------------------


def test_session_starts_idle() -> None:
    s = PushToTalkSession(recorder=_silent_recorder)
    assert s.state == VoiceSessionState.IDLE


def test_session_start_changes_state_to_recording() -> None:
    s = PushToTalkSession(recorder=_silent_recorder)
    s.start()
    assert s.state == VoiceSessionState.RECORDING


def test_real_capture_starts_only_after_start_and_cancel_stops_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real microphone capture must align with explicit push-to-talk controls."""
    calls: list[str] = []

    fake_sounddevice = SimpleNamespace(
        rec=lambda *args, **kwargs: calls.append("rec") or object(),
        stop=lambda: calls.append("stop"),
        wait=lambda: calls.append("wait"),
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sounddevice)

    session = PushToTalkSession()
    assert calls == []
    session.start()
    assert calls == ["rec"]
    session.cancel()
    assert calls == ["rec", "stop", "wait"]


def test_session_stop_returns_audio_input() -> None:
    s = PushToTalkSession(recorder=_silent_recorder)
    s.start()
    audio = s.stop()
    assert isinstance(audio, AudioInput)
    assert len(audio.data) > 0
    assert audio.sample_rate == 16_000
    assert audio.channels == 1
    assert audio.source == "push-to-talk"


def test_session_complete_after_stop() -> None:
    s = PushToTalkSession(recorder=_silent_recorder)
    s.start()
    s.stop()
    assert s.state == VoiceSessionState.COMPLETE


def test_session_context_manager_lifecycle() -> None:
    with PushToTalkSession(recorder=_silent_recorder) as session:
        session.start()
        audio = session.stop()
        assert session.state == VoiceSessionState.COMPLETE
    # After exit, state unchanged but cleanup has run.
    assert session.state == VoiceSessionState.COMPLETE


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_session_cancel_changes_state() -> None:
    s = PushToTalkSession(recorder=_silent_recorder)
    s.start()
    s.cancel()
    assert s.state == VoiceSessionState.CANCELLED


def test_session_cannot_stop_after_cancel() -> None:
    s = PushToTalkSession(recorder=_silent_recorder)
    s.start()
    s.cancel()
    with pytest.raises(RuntimeError, match="state"):
        s.stop()


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_session_cannot_start_twice() -> None:
    s = PushToTalkSession(recorder=_silent_recorder)
    s.start()
    with pytest.raises(RuntimeError, match="state"):
        s.start()


def test_session_cannot_stop_before_start() -> None:
    s = PushToTalkSession(recorder=_silent_recorder)
    with pytest.raises(RuntimeError, match="state"):
        s.stop()


def test_session_records_error_state_on_device_failure() -> None:
    s = PushToTalkSession(recorder=_error_recorder)
    s.start()
    with pytest.raises(RuntimeError, match="Recording failed"):
        s.stop()
    assert s.state == VoiceSessionState.ERROR


def test_session_context_manager_cleans_up_on_exception() -> None:
    """__exit__ runs even when an exception propagates."""
    with pytest.raises(RuntimeError):
        with PushToTalkSession(recorder=_error_recorder) as session:
            session.start()
            session.stop()  # raises


# ---------------------------------------------------------------------------
# Config forwarding
# ---------------------------------------------------------------------------


def test_session_respects_custom_sample_rate() -> None:
    captured: list[int] = []

    def recording_recorder(max_seconds: int, sample_rate: int, channels: int) -> bytes:
        captured.append(sample_rate)
        return _silent_recorder(max_seconds, sample_rate, channels)

    s = PushToTalkSession(sample_rate=8000, recorder=recording_recorder)
    s.start()
    audio = s.stop()
    assert captured[0] == 8000
    assert audio.sample_rate == 8000


def test_session_has_unique_session_id_by_default() -> None:
    a = PushToTalkSession(recorder=_silent_recorder)
    b = PushToTalkSession(recorder=_silent_recorder)
    assert a.session_id != b.session_id


def test_session_accepts_custom_session_id() -> None:
    s = PushToTalkSession(recorder=_silent_recorder, session_id="test-session-001")
    assert s.session_id == "test-session-001"


@pytest.mark.parametrize("duration", [0, -1, MAX_RECORDING_SECONDS + 1])
def test_session_rejects_unbounded_programmatic_duration(duration: int) -> None:
    with pytest.raises(ValueError, match="max_duration"):
        PushToTalkSession(max_duration=duration)


def test_session_preserves_typed_recording_timeout() -> None:
    def timeout_recorder(*_args: object) -> bytes:
        raise TimeoutError("synthetic timeout")

    session = PushToTalkSession(recorder=timeout_recorder)
    session.start()
    with pytest.raises(RecordingTimedOutError):
        session.stop()
