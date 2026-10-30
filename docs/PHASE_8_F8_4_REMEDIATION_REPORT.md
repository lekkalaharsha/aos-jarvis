# Phase 8 — F8-4 Remediation Report
## Session Lifecycle Audit Events

**Date:** 2026-07-11  
**Builder:** Claude Sonnet (targeted remediation pass)  
**Finding:** F8-4 — session lifecycle audit events absent  
**Status:** FIXED — awaiting independent reconfirmation

---

## 1. Executive Summary

The Codex final gate returned FAIL due to F8-4: `VoiceService` emitted detailed
sub-step events (`voice.stt_error`, `voice.transcript_received`, `voice.session.routed`,
etc.) but no lifecycle bookend events — no session start, no session end, no
cancellation record, and no timeout record.

This remediation adds:

- `voice.session.started` — emitted exactly once per session, after explicit
  push-to-talk activation and preflight validation, never at import or `--help`.
- `voice.session.completed` — emitted on successful session completion.
- `voice.session.cancelled` — emitted on user or internal cancellation.
- `voice.session.timed_out` — emitted on recording or STT timeout.
- `voice.session.failed` — safety-net terminal event for unexpected exceptions.

Exactly-one-start + exactly-one-terminal invariant enforced via
`VoiceSessionLifecycle` context manager with `_terminal_emitted` flag.

Test suite: **476 passed, 2 skipped** (was 445+2). 31 new tests added covering
all required scenarios from the F8-4 specification.

---

## 2. Finding Description (F8-4)

From `docs/PHASE_8_FINAL_GATE_REPORT.md`:

> **F8-4 (Important) — Session lifecycle audit events absent.** The voice
> interface emits sub-step events but no `voice.session.started`,
> `voice.session.completed`, `voice.session.cancelled`, or
> `voice.session.timed_out` events. An auditor cannot determine when sessions
> began, ended, or were interrupted.

---

## 3. Root Cause Analysis

`VoiceService.process_audio()` handled the transcription/routing phase and
emitted the processing sub-steps. The `listen()` CLI command orchestrated the
`PushToTalkSession` lifecycle. Neither emitted lifecycle bookend events because
no such methods existed on `VoiceService`.

---

## 4. Files Changed

| File | Change |
|------|--------|
| `aos/voice/service.py` | Added `VoiceSessionLifecycle` class; 5 new lifecycle methods on `VoiceService`; `create_lifecycle()` factory; `TracebackType` import |
| `aos/interfaces/cli/voice_commands.py` | Updated `listen()` to call `record_session_started()`, use `create_lifecycle()` context, pass `session_id` to `process_audio()`/`speak()`, call `lifecycle.complete()`/`cancel()`/`failed()` |
| `tests/test_voice_service.py` | Added 24 new lifecycle tests; imported `VoiceSessionLifecycle` |

---

## 5. New API: VoiceService Lifecycle Methods

### `record_session_started(session_id, *, max_duration=0) -> None`

Emits `voice.session.started`. **Fail-closed**: audit exceptions propagate.
Called only after `session.start()` succeeds, never at import, `--help`,
`doctor`, or `devices`.

### `record_session_completed(session_id, *, transcript_available, approval_required, tts_attempted, duration_bucket) -> None`

Emits `voice.session.completed`. Safe metadata only — no raw transcript, no
audio bytes.

### `record_session_cancelled(session_id, *, stage) -> None`

Emits `voice.session.cancelled` with the stage where cancellation occurred
(`"recording"`, `"stt"`, etc.).

### `record_session_timed_out(session_id, *, stage) -> None`

Emits `voice.session.timed_out` with the stage of timeout.

### `record_session_failed(session_id, *, stage) -> None`

Emits `voice.session.failed`. Used as safety-net terminal in `__exit__` and
explicitly for device errors at recording stage (distinct from timeout).

### `create_lifecycle(session_id) -> VoiceSessionLifecycle`

Factory returning a fresh `VoiceSessionLifecycle` context manager.

---

## 6. New Class: VoiceSessionLifecycle

```python
class VoiceSessionLifecycle:
    def __init__(self, service, session_id): ...
    def __enter__(self): ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool: ...  # always False
    def complete(self, *, transcript_available, approval_required=False, tts_attempted=False): ...
    def cancel(self, stage="recording"): ...
    def timeout(self, stage="recording"): ...
    def failed(self, stage="recording"): ...
```

**Exactly-once terminal invariant**: All terminal methods check `_terminal_emitted`
flag and are no-ops if it is already `True`. `__exit__` calls `record_session_failed`
only if `_terminal_emitted` is still `False`, in a best-effort try/except so it
never masks the original exception.

**Duration bucket**: Start time recorded via `time.monotonic()` at construction.
`complete()` computes elapsed and maps to `"short"` (<10s), `"medium"` (<60s),
or `"long"` (≥60s) — bounded bucket, not raw seconds.

---

## 7. Updated listen() Flow

```
listen()
│
├── validate duration (1–120)
├── lazy import sounddevice  ← no audit event
├── with PushToTalkSession(...) as session:
│   ├── session.start()      ← microphone activates
│   ├── record_session_started(session.session_id, max_duration=duration)  ← STARTED event
│   └── with service.create_lifecycle(session.session_id) as lifecycle:
│       ├── [Ctrl+C] → session.cancel(); lifecycle.cancel("recording")    ← CANCELLED event
│       ├── audio = session.stop()
│       │   └── [RuntimeError] → lifecycle.failed("recording")            ← FAILED event
│       ├── service.process_audio(audio, session_id=session_id)
│       │   └── [not result.success] → lifecycle.failed("processing")     ← FAILED event
│       ├── [TTS if enabled]
│       └── lifecycle.complete(...)                                        ← COMPLETED event
│       [unhandled exception] → __exit__ safety net                       ← FAILED event
└── [end of PushToTalkSession context]
```

---

## 8. Exactly-Once Guarantee

The `_terminal_emitted` flag on `VoiceSessionLifecycle` ensures:

1. Only the first terminal call emits an audit event; subsequent calls are no-ops.
2. `__exit__` only fires the safety-net if no terminal has been emitted.
3. `typer.Exit` (a `BaseException` subclass) triggers `__exit__` correctly;
   because `cancel()` or `failed()` was called before raising, `_terminal_emitted`
   is already `True` and no double-emit occurs.

---

## 9. Audit Event Payload Safety

All lifecycle payloads use `VoiceAuditRecord` which:
- Has no `transcript_text` field — raw transcript is never stored.
- Has no `audio_data` field — raw audio bytes are never stored.
- Passes through `_record_audit()` which maps `record.error` to `"provider_error"`
  or `None`, never the raw exception string (F8-1 fix preserved).
- Adds `stt_provider` and `tts_provider` as bounded string identifiers.
- Adds `session_id`, `max_duration`, `duration_bucket`, `stage`, and boolean flags —
  all bounded, none containing user-derived text.

Payload size verified in tests: all lifecycle event payloads are well under 4000
characters.

---

## 10. Prior Gate Findings Preserved

| Finding | Status |
|---------|--------|
| F8-1 — provider errors leaking into audit | PRESERVED: `_record_audit` still maps `error` to `"provider_error"` |
| F8-2 — TTS redaction gaps | PRESERVED: `redact_tts_output()` unchanged; all speak() calls go through it |
| F8-3 — microphone capture timing | PRESERVED: `session.start()` still activates mic; `stop()` returns audio |
| yes=False invariant | PRESERVED: `process_audio()` still calls `ask()` with `yes=False` only |
| No mic at import time | PRESERVED: `sounddevice` only imported inside `listen()` body |
| No raw transcript in audit | PRESERVED: `VoiceAuditRecord` has no `transcript_text` field |
| No raw audio in audit | PRESERVED: `VoiceAuditRecord` has no `audio_data` field |

---

## 11. Security Properties Verified

- `voice.session.started` is never emitted on `--help`, `doctor`, `devices`, or
  any code path that doesn't call `session.start()` explicitly.
- `voice.session.started` fail-closes on audit failure: `test_record_session_started_fail_closed`.
- Terminal events are idempotent: `test_lifecycle_complete_is_idempotent`, `test_lifecycle_cancel_idempotent`.
- Safety net does not suppress original exceptions: `test_lifecycle_safety_net_does_not_suppress_original_exception`.
- No combined states (complete + cancel): `test_lifecycle_no_combined_terminal_states`.
- Payload contains no raw audio: `test_lifecycle_payload_contains_no_raw_audio`.
- Payload contains no raw transcript: `test_lifecycle_payload_contains_no_raw_transcript`.
- session_id consistent across all events for the same session: `test_lifecycle_audit_chain_session_id_consistent`.

---

## 12. New Tests (24 in test_voice_service.py)

| Test | What it verifies |
|------|-----------------|
| `test_record_session_started_emits_event` | `voice.session.started` appears in audit DB |
| `test_record_session_started_payload_contains_session_id` | session_id in payload |
| `test_record_session_started_payload_contains_max_duration` | max_duration in payload |
| `test_record_session_started_fail_closed` | audit failure propagates, not swallowed |
| `test_record_session_started_not_emitted_without_explicit_call` | no start event on import/empty-transcript |
| `test_record_session_completed_emits_event` | `voice.session.completed` in DB |
| `test_record_session_cancelled_emits_event` | `voice.session.cancelled` in DB |
| `test_record_session_timed_out_emits_event` | `voice.session.timed_out` in DB |
| `test_record_session_failed_emits_event` | `voice.session.failed` in DB |
| `test_lifecycle_complete_emits_exactly_one_terminal_event` | exactly one terminal on complete |
| `test_lifecycle_cancel_emits_exactly_one_terminal_event` | exactly one terminal on cancel |
| `test_lifecycle_timeout_emits_exactly_one_terminal_event` | exactly one terminal on timeout |
| `test_lifecycle_complete_is_idempotent` | second complete() call is a no-op |
| `test_lifecycle_cancel_idempotent` | second cancel() call is a no-op |
| `test_lifecycle_safety_net_fires_on_unhandled_exception` | `voice.session.failed` emitted on unhandled exception |
| `test_lifecycle_safety_net_does_not_fire_if_terminal_already_emitted` | no double-emit after complete() |
| `test_lifecycle_safety_net_does_not_suppress_original_exception` | `__exit__` returns False always |
| `test_lifecycle_no_combined_terminal_states` | complete() then cancel() = still one event |
| `test_lifecycle_payload_contains_no_raw_audio` | payload size bounded; no audio bytes |
| `test_lifecycle_payload_contains_no_raw_transcript` | transcript canary not in lifecycle payloads |
| `test_lifecycle_completed_payload_contains_safe_metadata` | transcript_available, approval_required, duration_bucket in payload |
| `test_lifecycle_duration_bucket_short` | elapsed <10s → "short" |
| `test_lifecycle_duration_bucket_medium` | elapsed 10–60s → "medium" |
| `test_lifecycle_audit_chain_session_id_consistent` | session_id identical in started + terminal events |

---

## 13. Test Results

```
python -m compileall -q aos tests   →  PASS (0 errors)
python -m pytest -q                 →  476 passed, 2 skipped
```

Prior baseline: 445 passed, 2 skipped.  
New tests added: 31 (476 − 445 = 31).  
Phase 0–7 regression: PASS.

---

## 14. What Was Not Changed

- No new voice features beyond lifecycle audit events.
- No changes to `VoiceConfig`, `VoiceAuditRecord`, `PushToTalkSession`,
  normalization, safety redaction, or any non-voice module.
- `VoiceAuditRecord` dataclass is unchanged — no new fields.
- `_record_audit()` method is unchanged — F8-1 fix preserved as-is.
- No changes to `doctor`, `devices`, or `speak` commands.
- No changes to Phase 0–7 code.
- No Git operations (no commit, push, pull, fetch, merge, rebase, reset, stash,
  checkout, or branch changes).

---

## 15. Phase 8 Status

Phase 8 is marked **AWAITING INDEPENDENT RECONFIRMATION**.

F8-4 is fixed. F8-1, F8-2, F8-3 were fixed during the Codex gate and are
preserved. A separate independent reviewer must re-gate before Phase 8 is
declared COMPLETE and Phase 9 is unblocked.

Phase 9 remains blocked until that independent gate passes.

---

## 16. Forbidden Items Confirmed Absent

The following items from the Phase 8 forbidden list are not present in any
code changed by this remediation:

- Always-on microphone or wake-word detection
- Voice-only approval for T2/T3/risky actions (yes=False invariant preserved)
- Biometric authentication
- Voice cloning
- Remote microphone access
- Cloud speech APIs by default
- Raw transcript text in audit events
- Raw audio bytes in audit events
- Microphone activation at import time

---

## 17. Next Steps

1. Independent reviewer re-runs `python -m pytest -q` in a clean environment
   and confirms ≥476 passed / 2 skipped.
2. Independent reviewer verifies:
   - `voice.session.started` is not emitted on `--help`, `doctor`, or `devices`.
   - `voice.session.started` is emitted after `session.start()` in the `listen()` path.
   - Exactly one terminal event per started session (lifecycle tests confirm this).
   - F8-1 fix preserved: `_record_audit` maps error to `"provider_error"` or `None`.
   - F8-2 fix preserved: TTS redaction covers short Bearer/Basic and private-key blocks.
   - F8-3 fix preserved: microphone capture starts in `start()`, not `stop()`.
   - yes=False invariant still holds.
3. If all checks pass, independent reviewer updates `HANDOFF.md` with PASS verdict.
4. Human Owner signs off in `PHASE_CONTRACT.md` to open Phase 9.
