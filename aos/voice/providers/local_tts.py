"""Local text-to-speech provider backed by Piper.

The ``piper-tts`` package is an optional dependency.  This module never
imports it at class-definition time — only inside ``synthesize()``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from aos.voice.types import SpeechResult, VoiceOutcome


class PiperTTS:
    """TTS provider using the Piper neural TTS engine.

    Piper is invoked as a subprocess (``piper`` CLI) rather than being
    imported as a library, which keeps the interface stable across Piper
    versions and avoids loading model weights into the Python process.
    """

    def __init__(self, model_path: str = "") -> None:
        self._model_path = model_path

    # ------------------------------------------------------------------
    # TextToSpeechProvider protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        model_name = Path(self._model_path).stem if self._model_path else "default"
        return f"piper/{model_name}"

    def is_available(self) -> bool:
        """Return True if the ``piper`` executable is on PATH."""
        import shutil

        return shutil.which("piper") is not None

    def synthesize(self, text: str, output_path: str) -> SpeechResult:
        if not self.is_available():
            return SpeechResult(
                success=False,
                error=(
                    "piper is not installed or not on PATH. "
                    "Run: pip install 'aos-jarvis[voice]' and ensure piper is on PATH."
                ),
            )

        cmd = ["piper", "--output_file", output_path]
        if self._model_path:
            cmd += ["--model", self._model_path]

        try:
            subprocess.run(  # noqa: S603  # piper is a known safe binary
                cmd,
                input=text.encode(),
                capture_output=True,
                timeout=30,
                check=True,
            )
            return SpeechResult(success=True, audio_path=output_path)
        except subprocess.CalledProcessError as exc:
            return SpeechResult(success=False, error=exc.stderr.decode(errors="replace").strip())
        except subprocess.TimeoutExpired:
            return SpeechResult(
                success=False,
                error="piper synthesis timed out",
                outcome=VoiceOutcome.TIMED_OUT,
            )
        except Exception as exc:
            return SpeechResult(success=False, error=str(exc))


class MockTTS:
    """Deterministic mock TTS provider for tests.

    Does not invoke any subprocess or write any audio file.
    """

    def __init__(
        self,
        success: bool = True,
        error: str | None = None,
        outcome: VoiceOutcome = VoiceOutcome.SUCCESS,
    ) -> None:
        self._success = success
        self._error = error
        self._outcome = outcome

    @property
    def name(self) -> str:
        return "mock_tts"

    def is_available(self) -> bool:
        return True

    def synthesize(self, text: str, output_path: str) -> SpeechResult:
        if self._success:
            return SpeechResult(success=True, audio_path=output_path)
        return SpeechResult(
            success=False,
            error=self._error or "mock TTS error",
            outcome=self._outcome if self._outcome != VoiceOutcome.SUCCESS else VoiceOutcome.FAILED,
        )
