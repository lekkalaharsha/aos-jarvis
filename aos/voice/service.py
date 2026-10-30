"""Voice service: orchestrates STT → normalize → agent → TTS.

Critical invariants enforced here:
  • ``ask()`` is always called with ``yes=False`` — voice input never submits
    approval for risky actions.
  • Audit events carry ``origin="voice"`` so reviewers can distinguish voice
    traffic from terminal traffic.
  • Raw transcript text and audio bytes are never stored in audit payloads.
  • Each started session emits exactly one terminal lifecycle event
    (completed / cancelled / timed_out / failed).
"""

from __future__ import annotations

import time
from types import TracebackType

from aos.agent.loop import ask
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.voice.config import VoiceConfig
from aos.voice.normalization import is_empty_transcript, normalize_transcript
from aos.voice.providers.base import SpeechToTextProvider, TextToSpeechProvider
from aos.voice.safety import (
    contains_secret_pattern,
    looks_like_injection_attempt,
    redact_tts_output,
)
from aos.voice.types import AudioInput, SpeechResult, TranscriptResult, VoiceAuditRecord, VoiceOutcome


class VoiceService:
    """Orchestrates a full voice turn: audio in → agent action → speech out.

    Args:
        stt: speech-to-text provider (must satisfy SpeechToTextProvider).
        tts: text-to-speech provider (must satisfy TextToSpeechProvider).
        config: voice configuration; defaults to VoiceConfig() if omitted.
        audit_path: path to the audit DB; defaults to DEFAULT_AUDIT_PATH.
    """

    def __init__(
        self,
        stt: SpeechToTextProvider,
        tts: TextToSpeechProvider,
        config: VoiceConfig | None = None,
        audit_path: object | None = None,
    ) -> None:
        self._stt = stt
        self._tts = tts
        self._cfg = config or VoiceConfig()
        self._audit_path = audit_path or DEFAULT_AUDIT_PATH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_audio(
        self,
        audio: AudioInput,
        *,
        cwd: str = ".",
        session_id: str = "",
    ) -> "VoiceAgentResult":
        """Transcribe *audio*, route through the agent, and return a result.

        Returns a VoiceAgentResult regardless of success/failure — callers
        never receive a raw exception from this method.
        """
        # 1 — Transcribe
        try:
            transcript = self._stt.transcribe(audio)
        except TimeoutError:
            transcript = TranscriptResult(
                text="",
                success=False,
                error="speech-to-text provider timed out",
                outcome=VoiceOutcome.TIMED_OUT,
            )
        if not transcript.success:
            self._record_audit(
                VoiceAuditRecord(
                    event_type="voice.stt_error",
                    stt_provider=self._stt.name,
                    session_id=session_id,
                    success=False,
                    error=transcript.error,
                )
            )
            return VoiceAgentResult(
                success=False,
                blocked=True,
                answer="Voice recognition failed. Please try again.",
                transcript_available=False,
                error="speech-to-text provider timed out"
                if transcript.outcome == VoiceOutcome.TIMED_OUT
                else "speech-to-text provider error",
                outcome=transcript.outcome,
            )

        # 2 — Normalize
        normalized = normalize_transcript(transcript.text)

        if is_empty_transcript(normalized):
            self._record_audit(
                VoiceAuditRecord(
                    event_type="voice.empty_transcript",
                    stt_provider=self._stt.name,
                    session_id=session_id,
                    success=True,
                )
            )
            return VoiceAgentResult(
                success=True,
                blocked=False,
                answer="Nothing was transcribed.",
                transcript_available=False,
            )

        # 3 — Safety checks on transcript text
        injection_flag = looks_like_injection_attempt(normalized)
        secret_flag = contains_secret_pattern(normalized)

        self._record_audit(
            VoiceAuditRecord(
                event_type="voice.transcript_received",
                stt_provider=self._stt.name,
                transcript_length=len(transcript.text),
                normalized_length=len(normalized),
                confidence=transcript.confidence,
                session_id=session_id,
                success=True,
                extra={
                    "injection_flag": injection_flag,
                    "secret_in_transcript": secret_flag,
                    # Raw transcript text is intentionally not stored.
                },
            )
        )

        # 4 — Route through agent (yes=False — voice NEVER submits approval)
        try:
            result = ask(normalized, cwd=cwd, yes=False, origin="voice")
        except Exception as exc:
            self._record_audit(
                VoiceAuditRecord(
                    event_type="voice.agent_error",
                    stt_provider=self._stt.name,
                    session_id=session_id,
                    success=False,
                    error=str(exc),
                )
            )
            return VoiceAgentResult(
                success=False,
                blocked=True,
                answer="An error occurred processing your request.",
                transcript_available=True,
                error="voice agent processing error",
            )

        # 5 — Record that this result came from voice origin
        self._record_audit(
            VoiceAuditRecord(
                event_type="voice.session.routed",
                origin="voice",
                stt_provider=self._stt.name,
                session_id=session_id,
                success=result.success,
                extra={
                    "agent_blocked": result.blocked,
                    "intent": result.intent.value if result.intent else "unknown",
                    # answer text is not stored in audit; only length for size monitoring
                    "answer_length": len(result.final_answer or ""),
                },
            )
        )

        return VoiceAgentResult(
            success=result.success,
            blocked=result.blocked,
            answer=result.final_answer or "",
            transcript_available=True,
            error=result.error,
        )

    def speak(
        self,
        text: str,
        output_path: str,
        *,
        session_id: str = "",
    ) -> SpeechResult:
        """Synthesize *text* to speech, with redaction applied first.

        The text is redacted and bounded before being sent to the TTS
        provider so secrets cannot be spoken aloud.
        """
        filtered = redact_tts_output(text)

        result = self._tts.synthesize(filtered, output_path)

        self._record_audit(
            VoiceAuditRecord(
                event_type="voice.tts_synthesized",
                tts_provider=self._tts.name,
                session_id=session_id,
                success=result.success,
                error=result.error,
                extra={"text_length": len(filtered)},
            )
        )
        if not result.success:
            return SpeechResult(
                success=False,
                error="text-to-speech provider timed out"
                if result.outcome == VoiceOutcome.TIMED_OUT
                else "text-to-speech provider error",
                outcome=result.outcome,
            )
        return result

    # ------------------------------------------------------------------
    # Session lifecycle audit (F8-4)
    # ------------------------------------------------------------------

    def record_session_started(
        self,
        session_id: str,
        *,
        max_duration: int = 0,
    ) -> None:
        """Emit ``voice.session.started``.

        Called after explicit push-to-talk, after preflight validation passes,
        and after session_id exists.  Fail-closed: propagates audit exceptions.
        NOT called at import, --help, doctor, or device listing.
        """
        self._record_audit(
            VoiceAuditRecord(
                event_type="voice.session.started",
                stt_provider=self._stt.name,
                tts_provider=self._tts.name,
                session_id=session_id,
                success=True,
                extra={
                    "max_duration": max_duration,
                },
            )
        )

    def record_session_completed(
        self,
        session_id: str,
        *,
        transcript_available: bool,
        approval_required: bool,
        tts_attempted: bool,
        duration_bucket: str,
    ) -> None:
        """Emit ``voice.session.completed`` (one terminal event per session)."""
        self._record_audit(
            VoiceAuditRecord(
                event_type="voice.session.completed",
                stt_provider=self._stt.name,
                tts_provider=self._tts.name,
                session_id=session_id,
                success=True,
                extra={
                    "transcript_available": transcript_available,
                    "approval_required": approval_required,
                    "tts_attempted": tts_attempted,
                    "duration_bucket": duration_bucket,
                },
            )
        )

    def record_session_cancelled(
        self,
        session_id: str,
        *,
        stage: str,
    ) -> None:
        """Emit ``voice.session.cancelled`` (one terminal event per session)."""
        self._record_audit(
            VoiceAuditRecord(
                event_type="voice.session.cancelled",
                stt_provider=self._stt.name,
                tts_provider=self._tts.name,
                session_id=session_id,
                success=False,
                extra={"stage": stage},
            )
        )

    def record_session_timed_out(
        self,
        session_id: str,
        *,
        stage: str,
    ) -> None:
        """Emit ``voice.session.timed_out`` (one terminal event per session)."""
        self._record_audit(
            VoiceAuditRecord(
                event_type="voice.session.timed_out",
                stt_provider=self._stt.name,
                tts_provider=self._tts.name,
                session_id=session_id,
                success=False,
                extra={"stage": stage},
            )
        )

    def record_session_failed(
        self,
        session_id: str,
        *,
        stage: str,
    ) -> None:
        """Emit ``voice.session.failed`` (safety-net terminal event)."""
        self._record_audit(
            VoiceAuditRecord(
                event_type="voice.session.failed",
                stt_provider=self._stt.name,
                tts_provider=self._tts.name,
                session_id=session_id,
                success=False,
                extra={"stage": stage},
            )
        )

    def create_lifecycle(self, session_id: str) -> "VoiceSessionLifecycle":
        """Return a VoiceSessionLifecycle context manager for *session_id*."""
        return VoiceSessionLifecycle(self, session_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_audit(self, record: VoiceAuditRecord) -> None:
        payload: dict[str, object] = {
            "origin": record.origin,
            "stt_provider": record.stt_provider,
            "tts_provider": record.tts_provider,
            "session_id": record.session_id,
            "transcript_length": record.transcript_length,
            "normalized_length": record.normalized_length,
            "confidence": record.confidence,
            "success": record.success,
            # Provider exceptions are untrusted diagnostic data and can contain
            # credentials, paths, or audio-derived content.  Preserve only the
            # fact that an error occurred, never its raw text.
            "error": "provider_error" if record.error else None,
            **record.extra,
        }
        append_event(
            self._audit_path,
            actor="voice",
            event_type=record.event_type,
            action=record.event_type,
            resource="voice_interface",
            risk_tier="T0",
            status="ALLOW" if record.success else "DENY",
            payload=payload,
        )


class VoiceSessionLifecycle:
    """Context manager enforcing exactly-one-start / exactly-one-terminal per session.

    Usage::

        service.record_session_started(session_id, max_duration=duration)
        with service.create_lifecycle(session_id) as lifecycle:
            try:
                input("Press Enter to stop…")
            except KeyboardInterrupt:
                lifecycle.cancel(stage="recording")
                raise
            result = service.process_audio(audio, cwd=cwd, session_id=session_id)
            lifecycle.complete(
                transcript_available=result.transcript_available,
                approval_required=False,
                tts_attempted=speak_enabled,
            )

    If ``__exit__`` is reached without a terminal event having been emitted
    (e.g. an unhandled exception bypassed ``complete``/``cancel``/``timeout``),
    a ``voice.session.failed`` event is recorded as a best-effort safety net.
    The safety-net call is swallowed if it raises, so it never masks the
    original exception.
    """

    _DURATION_SHORT = 10.0
    _DURATION_MEDIUM = 60.0

    def __init__(self, service: "VoiceService", session_id: str) -> None:
        self._service = service
        self._session_id = session_id
        self._terminal_emitted = False
        self._start_time = time.monotonic()

    # -- context manager ------------------------------------------------

    def __enter__(self) -> "VoiceSessionLifecycle":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if not self._terminal_emitted:
            try:
                self._service.record_session_failed(
                    self._session_id, stage="exception"
                )
                self._terminal_emitted = True
            except Exception:
                pass  # best-effort; never mask the original exception
        return False  # never suppress

    # -- terminal events ------------------------------------------------

    def complete(
        self,
        *,
        transcript_available: bool,
        approval_required: bool = False,
        tts_attempted: bool = False,
    ) -> None:
        """Mark session as successfully completed (idempotent)."""
        if self._terminal_emitted:
            return
        self._terminal_emitted = True
        self._service.record_session_completed(
            self._session_id,
            transcript_available=transcript_available,
            approval_required=approval_required,
            tts_attempted=tts_attempted,
            duration_bucket=self._duration_bucket(),
        )

    def cancel(self, stage: str = "recording") -> None:
        """Mark session as cancelled (idempotent)."""
        if self._terminal_emitted:
            return
        self._terminal_emitted = True
        self._service.record_session_cancelled(self._session_id, stage=stage)

    def timeout(self, stage: str = "recording") -> None:
        """Mark session as timed out (idempotent)."""
        if self._terminal_emitted:
            return
        self._terminal_emitted = True
        self._service.record_session_timed_out(self._session_id, stage=stage)

    def failed(self, stage: str = "recording") -> None:
        """Mark session as failed (idempotent); distinct from timeout/cancel."""
        if self._terminal_emitted:
            return
        self._terminal_emitted = True
        self._service.record_session_failed(self._session_id, stage=stage)

    # -- helpers --------------------------------------------------------

    def _duration_bucket(self) -> str:
        elapsed = time.monotonic() - self._start_time
        if elapsed < self._DURATION_SHORT:
            return "short"
        if elapsed < self._DURATION_MEDIUM:
            return "medium"
        return "long"


class VoiceAgentResult:
    """Result of a voice→agent turn."""

    def __init__(
        self,
        *,
        success: bool,
        blocked: bool,
        answer: str,
        transcript_available: bool,
        error: str | None = None,
        outcome: VoiceOutcome = VoiceOutcome.SUCCESS,
    ) -> None:
        self.success = success
        self.blocked = blocked
        self.answer = answer
        self.transcript_available = transcript_available
        self.error = error
        self.outcome = outcome

    def __repr__(self) -> str:
        return (
            f"VoiceAgentResult(success={self.success}, blocked={self.blocked}, "
            f"answer={self.answer!r:.40})"
        )
