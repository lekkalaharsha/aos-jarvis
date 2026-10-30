# Phase 8 Live Timeout Traceability Remediation

## Root cause and result contract

Lifecycle timeout support existed but live paths did not call it. Added typed
`VoiceOutcome` values (`success`, `failed`, `timed_out`) and typed recording
timeout handling.

## Behavior

- STT timeout → `voice.session.timed_out`, stage `transcription`.
- TTS timeout → `voice.session.timed_out`, stage `synthesis`, without changing
  the already-completed underlying request result.
- Recording timeout → `voice.session.timed_out`, stage `recording`.
- No overall session timeout exists; no `session` stage is invented.
- Programmatic recording duration is now bounded 1–120 seconds.

## Validation and recommendation

Focused voice suite: **137 passed**. F8-1–F8-3 safeguards remain. This is
**READY FOR OPENCODE SUPPLEMENTAL VERIFICATION**, not final-gate approval.
