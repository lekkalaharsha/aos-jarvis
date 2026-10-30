"""Push-to-talk recording session.

The session object is a context manager.  It must be started explicitly —
no microphone activation occurs on import or at construction time.

The ``recorder`` parameter accepts an injectable callable so the full
session lifecycle can be tested without hardware.  Production code that
omits ``recorder`` uses the real ``sounddevice`` capture path.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aos.voice.types import AudioInput, VoiceSessionState


# Type alias for the recorder callable injected in tests.
RecorderCallable = Callable[[int, int, int], bytes]
# signature: recorder(max_seconds, sample_rate, channels) -> raw_pcm_bytes


MAX_RECORDING_SECONDS = 120


class RecordingTimedOutError(RuntimeError):
    """Typed recording timeout used by the CLI lifecycle boundary."""


class PushToTalkSession:
    """Context-manager-based push-to-talk recording session.

    Usage::

        with PushToTalkSession(config) as session:
            session.start()
            # ... user presses stop or max_duration elapses ...
            audio = session.stop()

    The session ensures that temporary audio files are deleted in
    ``__exit__``, even if an exception occurs mid-recording.
    """

    def __init__(
        self,
        *,
        max_duration: int = 30,
        sample_rate: int = 16_000,
        channels: int = 1,
        recorder: RecorderCallable | None = None,
        session_id: str | None = None,
    ) -> None:
        if not 1 <= max_duration <= MAX_RECORDING_SECONDS:
            raise ValueError(
                f"max_duration must be between 1 and {MAX_RECORDING_SECONDS} seconds"
            )
        self._max_duration = max_duration
        self._sample_rate = sample_rate
        self._channels = channels
        self._recorder = recorder  # None → real sounddevice at runtime
        self._state: VoiceSessionState = VoiceSessionState.IDLE
        self._tmp_path: Path | None = None
        self._sounddevice: Any | None = None
        self._frames: Any | None = None
        self.session_id: str = session_id or str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "PushToTalkSession":
        return self

    def __exit__(self, *_args: Any) -> None:
        self._cleanup()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> VoiceSessionState:
        return self._state

    def start(self) -> None:
        """Begin recording.  Activates the microphone for the first time."""
        if self._state != VoiceSessionState.IDLE:
            raise RuntimeError(f"Cannot start: session is in state {self._state.value}")
        self._state = VoiceSessionState.RECORDING
        if self._recorder is not None:
            return

        # The real recorder begins only after an explicit start request.  It
        # remains non-blocking until stop() or cancel() is called.
        try:
            import sounddevice as sd

            self._sounddevice = sd
            self._frames = sd.rec(
                int(self._max_duration * self._sample_rate),
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
            )
        except TimeoutError as exc:
            self._state = VoiceSessionState.ERROR
            raise RecordingTimedOutError("Recording timed out") from exc
        except Exception as exc:
            self._state = VoiceSessionState.ERROR
            self._sounddevice = None
            self._frames = None
            raise RuntimeError(f"Recording failed to start: {exc}") from exc

    def stop(self) -> AudioInput:
        """Stop recording and return the captured audio.

        The raw bytes are held only in memory.  The temporary file (if any)
        is created for provider compatibility but deleted in ``__exit__``.
        """
        if self._state != VoiceSessionState.RECORDING:
            raise RuntimeError(f"Cannot stop: session is in state {self._state.value}")

        self._state = VoiceSessionState.PROCESSING

        try:
            raw_bytes = self._capture()
        except RecordingTimedOutError:
            self._state = VoiceSessionState.ERROR
            raise
        except TimeoutError as exc:
            self._state = VoiceSessionState.ERROR
            raise RecordingTimedOutError("Recording timed out") from exc
        except Exception as exc:
            self._state = VoiceSessionState.ERROR
            raise RuntimeError(f"Recording failed: {exc}") from exc

        self._state = VoiceSessionState.COMPLETE
        return AudioInput(
            data=raw_bytes,
            sample_rate=self._sample_rate,
            channels=self._channels,
            format="wav",
            source="push-to-talk",
        )

    def cancel(self) -> None:
        """Discard the current recording without returning audio."""
        self._stop_real_capture()
        self._state = VoiceSessionState.CANCELLED
        self._cleanup()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _capture(self) -> bytes:
        if self._recorder is not None:
            # Injected recorder (tests or custom integrations).
            return self._recorder(self._max_duration, self._sample_rate, self._channels)

        if self._sounddevice is None or self._frames is None:
            raise RuntimeError("Recording was not started")
        self._stop_real_capture()
        frames = self._frames
        self._frames = None
        return self._frames_to_wav(frames, self._sample_rate)

    def _stop_real_capture(self) -> None:
        if self._sounddevice is None:
            return
        try:
            self._sounddevice.stop()
            self._sounddevice.wait()
        except Exception:
            # Cleanup must never mask the caller's primary cancellation/error.
            pass
        finally:
            self._sounddevice = None

    @staticmethod
    def _frames_to_wav(frames: Any, sample_rate: int) -> bytes:
        """Convert a float32 NumPy array to a minimal WAV byte string."""
        import io
        import wave

        import numpy as np

        # Convert float32 [-1, 1] → int16
        pcm = (frames * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    def _cleanup(self) -> None:
        self._stop_real_capture()
        if self._tmp_path is not None and self._tmp_path.exists():
            try:
                self._tmp_path.unlink()
            except OSError:
                pass
            self._tmp_path = None
