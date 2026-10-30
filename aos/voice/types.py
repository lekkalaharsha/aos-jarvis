"""Immutable data types for the Phase 8 voice interface.

No optional dependencies imported here — this module is safe to import at
application start regardless of whether [voice] extras are installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VoiceSessionState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    ERROR = "error"


class VoiceOutcome(str, Enum):
    """Typed outcome for untrusted local speech providers."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class AudioInput:
    """Raw audio captured during a push-to-talk session."""

    data: bytes
    sample_rate: int
    channels: int
    format: str = "wav"
    source: str = "push-to-talk"

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if self.channels <= 0:
            raise ValueError(f"channels must be positive, got {self.channels}")


@dataclass(frozen=True)
class TranscriptResult:
    """Result from a speech-to-text provider."""

    text: str
    language: str | None = None
    confidence: float | None = None  # 0.0–1.0; None = provider did not report
    success: bool = True
    error: str | None = None
    outcome: VoiceOutcome = VoiceOutcome.SUCCESS

    def __post_init__(self) -> None:
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass(frozen=True)
class SpeechResult:
    """Result from a text-to-speech provider."""

    success: bool
    audio_path: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
    outcome: VoiceOutcome = VoiceOutcome.SUCCESS


@dataclass(frozen=True)
class VoiceAuditRecord:
    """Safe audit payload for a voice session event.

    Raw transcript text and audio bytes are deliberately excluded to prevent
    sensitive speech content from persisting in the audit log.
    """

    event_type: str
    origin: str = "voice"
    transcript_length: int = 0
    normalized_length: int = 0
    confidence: float | None = None
    stt_provider: str = ""
    tts_provider: str = ""
    session_id: str = ""
    success: bool = True
    error: str | None = None
    extra: dict[str, object] = field(default_factory=dict)
