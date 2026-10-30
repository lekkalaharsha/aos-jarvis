"""Abstract provider interfaces for STT and TTS.

Uses typing.Protocol so concrete providers can be swapped (including test
mocks) without subclassing.  No optional dependencies are imported here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from aos.voice.types import AudioInput, SpeechResult, TranscriptResult


@runtime_checkable
class SpeechToTextProvider(Protocol):
    """Speech-to-text provider interface."""

    @property
    def name(self) -> str:
        """Short identifier reported in audit events and doctor output."""
        ...

    def is_available(self) -> bool:
        """Return True if the provider's deps and model files are present."""
        ...

    def transcribe(self, audio: AudioInput) -> TranscriptResult:
        """Convert raw audio to a transcript result."""
        ...


@runtime_checkable
class TextToSpeechProvider(Protocol):
    """Text-to-speech provider interface."""

    @property
    def name(self) -> str:
        """Short identifier reported in audit events and doctor output."""
        ...

    def is_available(self) -> bool:
        """Return True if the provider's deps and model files are present."""
        ...

    def synthesize(self, text: str, output_path: str) -> SpeechResult:
        """Synthesize *text* and write audio to *output_path*."""
        ...
