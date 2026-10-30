"""Local speech-to-text provider backed by faster-whisper.

The ``faster-whisper`` package is an optional dependency.  This module never
imports it at class-definition time — only when ``transcribe()`` is called
and the model has been explicitly loaded.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from aos.voice.types import AudioInput, TranscriptResult, VoiceOutcome


class FasterWhisperSTT:
    """STT provider using faster-whisper (CTranslate2 backend).

    Raises ``RuntimeError`` with installation instructions if the package is
    not installed.  Does NOT download models automatically — the model must
    already be cached locally.
    """

    def __init__(self, model_name: str = "tiny.en", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model: object | None = None

    # ------------------------------------------------------------------
    # SpeechToTextProvider protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return f"faster_whisper/{self._model_name}"

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def transcribe(self, audio: AudioInput) -> TranscriptResult:
        if not self.is_available():
            return TranscriptResult(
                text="",
                success=False,
                error=(
                    "faster-whisper is not installed. "
                    "Run: pip install 'aos-jarvis[voice]'"
                ),
            )

        try:
            model = self._get_model()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(audio.data)

            try:
                segments, info = model.transcribe(  # type: ignore[attr-defined]
                    str(tmp_path),
                    language=None,
                    beam_size=5,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
                language = getattr(info, "language", None)
                # faster-whisper reports language_probability, not per-word confidence.
                confidence: float | None = None
                lang_prob = getattr(info, "language_probability", None)
                if lang_prob is not None:
                    confidence = float(lang_prob)
            finally:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

            return TranscriptResult(
                text=text,
                language=language,
                confidence=confidence,
                success=True,
            )

        except TimeoutError:
            return TranscriptResult(
                text="", success=False, error="speech-to-text provider timed out",
                outcome=VoiceOutcome.TIMED_OUT,
            )
        except Exception as exc:
            return TranscriptResult(text="", success=False, error=str(exc), outcome=VoiceOutcome.FAILED)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_model(self) -> object:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type="int8",
                # download_root=None keeps the default cache location;
                # models are NOT downloaded here — they must pre-exist.
                local_files_only=True,
            )
        return self._model


class MockSTT:
    """Deterministic mock STT provider for tests.

    Returns a configurable fixed transcript without accessing audio hardware
    or loading any model.
    """

    def __init__(
        self,
        transcript: str = "",
        confidence: float | None = 0.95,
        success: bool = True,
        error: str | None = None,
        outcome: VoiceOutcome = VoiceOutcome.SUCCESS,
    ) -> None:
        self._transcript = transcript
        self._confidence = confidence
        self._success = success
        self._error = error
        self._outcome = outcome

    @property
    def name(self) -> str:
        return "mock_stt"

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio: AudioInput) -> TranscriptResult:
        return TranscriptResult(
            text=self._transcript,
            language="en",
            confidence=self._confidence,
            success=self._success,
            error=self._error,
            outcome=self._outcome,
        )
