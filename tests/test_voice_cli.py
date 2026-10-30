"""Tests for the voice CLI commands.

All optional-dependency checks use monkeypatching — no real audio hardware,
no STT model, no TTS binary.
"""

from __future__ import annotations

import sys
import builtins
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from aos.interfaces.cli.voice_commands import app
from aos.safety.audit import list_events
from aos.voice.session import RecordingTimedOutError
from aos.voice.types import AudioInput, SpeechResult, TranscriptResult, VoiceOutcome

runner = CliRunner()


# ---------------------------------------------------------------------------
# Help / import-time safety
# ---------------------------------------------------------------------------


def test_voice_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "voice" in result.output.lower() or "push-to-talk" in result.output.lower()


def test_voice_help_does_not_activate_microphone() -> None:
    """--help must not import sounddevice or access audio hardware."""
    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        result = runner.invoke(app, ["--help"])
    # If sounddevice was required at import time this would raise ImportError.
    assert result.exit_code == 0


def test_voice_subcommand_help_exits_zero() -> None:
    for cmd in ("doctor", "devices", "listen", "speak"):
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0, f"{cmd} --help failed: {result.output}"


# ---------------------------------------------------------------------------
# doctor — missing deps
# ---------------------------------------------------------------------------


def test_doctor_reports_missing_sounddevice() -> None:
    """doctor reports clearly when sounddevice is not installed."""
    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        result = runner.invoke(app, ["doctor"])

    assert "sounddevice" in result.output.lower()
    assert result.exit_code != 0


def test_doctor_reports_missing_faster_whisper() -> None:
    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        result = runner.invoke(app, ["doctor"])

    assert "faster-whisper" in result.output.lower()


def test_doctor_reports_missing_piper() -> None:
    """doctor reports clearly when piper is not on PATH."""
    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}), patch("shutil.which", return_value=None):
        result = runner.invoke(app, ["doctor"])

    assert "piper" in result.output.lower()


# ---------------------------------------------------------------------------
# listen — guard rails
# ---------------------------------------------------------------------------


def test_listen_rejects_invalid_duration_zero() -> None:
    result = runner.invoke(app, ["listen", "--duration", "0"])
    assert result.exit_code == 2
    assert "duration" in result.output.lower() or "duration" in (result.stderr or "").lower()


def test_listen_rejects_invalid_duration_negative() -> None:
    result = runner.invoke(app, ["listen", "--duration", "-5"])
    assert result.exit_code == 2


def test_listen_rejects_invalid_duration_too_large() -> None:
    result = runner.invoke(app, ["listen", "--duration", "121"])
    assert result.exit_code == 2


def test_listen_reports_missing_sounddevice_clearly() -> None:
    with patch.dict(sys.modules, {"sounddevice": None}):
        result = runner.invoke(app, ["listen", "--duration", "5"])

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "sounddevice" in combined.lower()


# ---------------------------------------------------------------------------
# speak
# ---------------------------------------------------------------------------


def test_speak_reports_missing_piper_clearly() -> None:
    """speak reports clearly when piper is not on PATH."""
    with patch("shutil.which", return_value=None):
        result = runner.invoke(app, ["speak", "hello world"])

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "piper" in combined.lower()


# ---------------------------------------------------------------------------
# CLI wired into main app
# ---------------------------------------------------------------------------


def test_voice_command_in_main_app() -> None:
    from typer.testing import CliRunner as TRunner
    from aos.interfaces.cli.main import app as main_app

    r = TRunner()
    result = r.invoke(main_app, ["voice", "--help"])
    assert result.exit_code == 0
    assert "voice" in result.output.lower() or "push-to-talk" in result.output.lower()


def test_main_app_help_does_not_require_voice_deps() -> None:
    """Main app --help must work even when sounddevice/faster-whisper are absent."""
    original_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name in ("sounddevice", "faster_whisper"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    from typer.testing import CliRunner as TRunner
    from aos.interfaces.cli.main import app as main_app

    r = TRunner()
    with patch("builtins.__import__", side_effect=mock_import):
        result = r.invoke(main_app, ["--help"])

    assert result.exit_code == 0


def _patch_cli_session(monkeypatch: pytest.MonkeyPatch) -> None:
    from aos.voice.session import PushToTalkSession

    monkeypatch.setattr(PushToTalkSession, "start", lambda self: None)
    monkeypatch.setattr(
        PushToTalkSession,
        "stop",
        lambda self: AudioInput(data=b"audio", sample_rate=16000, channels=1),
    )
    monkeypatch.setitem(sys.modules, "sounddevice", MagicMock())


def _isolated_voice_audit(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> object:
    import aos.voice.service as service_module

    audit_path = tmp_path / "voice-audit.db"  # type: ignore[operator]
    monkeypatch.setattr(service_module, "DEFAULT_AUDIT_PATH", audit_path)
    return audit_path


def _lifecycle_events(audit_path: object) -> list[object]:
    return [
        event for event in list_events(audit_path)  # type: ignore[arg-type]
        if event.event_type.startswith("voice.session.")
    ]


def test_listen_stt_timeout_emits_one_transcription_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object,
) -> None:
    from aos.voice.providers.local_stt import FasterWhisperSTT

    _patch_cli_session(monkeypatch)
    audit_path = _isolated_voice_audit(monkeypatch, tmp_path)
    monkeypatch.setattr(
        FasterWhisperSTT,
        "transcribe",
        lambda self, audio: TranscriptResult(
            text="", success=False, error="Bearer secret", outcome=VoiceOutcome.TIMED_OUT
        ),
    )

    result = runner.invoke(app, ["listen", "--no-speak"], input="\n")
    events = _lifecycle_events(audit_path)
    terminal = [
        e for e in events
        if e.event_type in {
            "voice.session.completed", "voice.session.cancelled",
            "voice.session.timed_out", "voice.session.failed",
        }
    ]

    assert result.exit_code == 1
    assert events[0].event_type == "voice.session.started"
    assert [e.event_type for e in terminal] == ["voice.session.timed_out"]
    assert len(terminal) == 1
    assert '"stage":"transcription"' in terminal[0].payload_json
    assert "secret" not in terminal[0].payload_json


def test_listen_tts_timeout_emits_one_synthesis_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object,
) -> None:
    from aos.voice.providers.local_stt import FasterWhisperSTT
    from aos.voice.providers.local_tts import PiperTTS

    _patch_cli_session(monkeypatch)
    audit_path = _isolated_voice_audit(monkeypatch, tmp_path)
    monkeypatch.setattr(FasterWhisperSTT, "transcribe", lambda self, audio: TranscriptResult(text="unknown"))
    monkeypatch.setattr(
        PiperTTS,
        "synthesize",
        lambda self, text, output_path: SpeechResult(
            success=False, error="Bearer secret", outcome=VoiceOutcome.TIMED_OUT
        ),
    )

    result = runner.invoke(app, ["listen"], input="\n")
    events = _lifecycle_events(audit_path)
    terminal = [
        e for e in events
        if e.event_type in {
            "voice.session.completed", "voice.session.cancelled",
            "voice.session.timed_out", "voice.session.failed",
        }
    ]

    assert result.exit_code == 0
    assert events[0].event_type == "voice.session.started"
    assert [e.event_type for e in terminal] == ["voice.session.timed_out"]
    assert len(terminal) == 1
    assert '"stage":"synthesis"' in terminal[0].payload_json
    assert "secret" not in terminal[0].payload_json


def test_listen_recording_timeout_emits_one_recording_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object,
) -> None:
    from aos.voice.session import PushToTalkSession

    _patch_cli_session(monkeypatch)
    audit_path = _isolated_voice_audit(monkeypatch, tmp_path)
    monkeypatch.setattr(
        PushToTalkSession,
        "stop",
        lambda self: (_ for _ in ()).throw(RecordingTimedOutError("Bearer secret")),
    )

    result = runner.invoke(app, ["listen", "--no-speak"], input="\n")
    events = _lifecycle_events(audit_path)
    terminal = [e for e in events if e.event_type != "voice.session.started"]

    assert result.exit_code == 1
    assert [e.event_type for e in events] == ["voice.session.started", "voice.session.timed_out"]
    assert len(terminal) == 1
    assert '"stage":"recording"' in terminal[0].payload_json
