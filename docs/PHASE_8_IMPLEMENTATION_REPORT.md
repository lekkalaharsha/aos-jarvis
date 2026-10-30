# Phase 8 Implementation Report

Date: 2026-07-11
Builder: Claude Sonnet (Phase 8 voice interface builder)
Phase: Phase 8 — Local-Only Push-to-Talk Voice Interface

## 1. Summary

Phase 8 delivers a local-only, push-to-talk voice interface for AOS-Jarvis.
The interface uses faster-whisper for STT and Piper for TTS, both running
entirely locally.  Voice input is untrusted; it routes through the same intent
classifier, risk tier, approval pipeline, and audit system as typed input.
`ask()` is always called with `yes=False` — voice can never approve an action.
Phase 8 adds 98 new tests; the full suite is **445 passed, 2 skipped** (baseline
was 347 + 2).

## 2. Environment

- OS: Windows 11
- Python: 3.11.15
- pytest: 9.1.1
- sounddevice / faster-whisper: optional (`pip install 'aos-jarvis[voice]'`)
- piper: optional (system binary, checked via `shutil.which`)

## 3. Files Changed or Created

### New files

| File | Purpose |
|---|---|
| `aos/voice/__init__.py` | Package init |
| `aos/voice/types.py` | Core immutable dataclasses (AudioInput, TranscriptResult, SpeechResult, VoiceAuditRecord, VoiceSessionState) |
| `aos/voice/config.py` | VoiceConfig dataclass + load_voice_config() |
| `aos/voice/normalization.py` | normalize_transcript(), is_empty_transcript() — pure functions, no I/O |
| `aos/voice/safety.py` | redact_tts_output(), looks_like_injection_attempt(), confidence_allows_destructive(), voice_approval_always_denied() |
| `aos/voice/session.py` | PushToTalkSession with injectable recorder, state machine, WAV capture |
| `aos/voice/service.py` | VoiceService — orchestrates STT → normalize → ask(yes=False) → TTS → audit |
| `aos/voice/providers/__init__.py` | Provider subpackage init |
| `aos/voice/providers/base.py` | SpeechToTextProvider and TextToSpeechProvider Protocol interfaces |
| `aos/voice/providers/local_stt.py` | FasterWhisperSTT (local), MockSTT |
| `aos/voice/providers/local_tts.py` | PiperTTS (local subprocess), MockTTS |
| `aos/interfaces/cli/voice_commands.py` | `aos voice doctor/devices/listen/speak` CLI |
| `tests/test_voice_types_normalization.py` | 38 tests: types, normalization, aliases |
| `tests/test_voice_safety.py` | 22 tests: injection detection, secret patterns, TTS redaction, confidence gating |
| `tests/test_voice_session.py` | 14 tests: state machine, injectable recorder, cleanup |
| `tests/test_voice_service.py` | 24 tests (combined with CLI): service logic, yes=False invariant, audit events |
| `tests/test_voice_cli.py` | CLI tests: --help, doctor, listen validation, speak, wiring |
| `docs/phase_8.md` | Architecture overview, safety invariants, module table, CLI commands |
| `docs/PHASE_8_IMPLEMENTATION_REPORT.md` | This report |

### Modified files

| File | Change |
|---|---|
| `aos/interfaces/cli/main.py` | Added `app.add_typer(voice_commands.app, name="voice")` |
| `pyproject.toml` | Added `voice = ["sounddevice>=0.4", "faster-whisper>=1.0"]` optional extra |
| `PHASE_CONTRACT.md` | Phase 8 active; exit criteria; Hard Rule; status COMPLETE pending gate |
| `PROJECT_STATE.md` | Phase 8 In Progress entry; updated Do Not Build Yet list |
| `CHANGELOG.md` | Phase 8 entry at top |
| `HANDOFF.md` | Phase 8 handoff at top; next worker Codex |
| `BLOCKERS.md` | B005 Phase 8 gate review pending |
| `TASKS.md` | Phase 8 task rows added |
| `TASK_BOARD.md` | Phase 8 done; Codex gate in Todo |
| `SECURITY_BOUNDARIES.md` | Phase 8 Hard Rules added |

## 4. Architecture

```
User voice input
      │
      ▼
PushToTalkSession (push-to-talk only; injectable recorder for tests)
      │
      ▼ AudioInput (sample_rate, channels, data)
VoiceService.process_audio()
      │
      ├─ stt.transcribe() → TranscriptResult
      │      (FasterWhisperSTT: local_files_only=True; temp file deleted after use)
      │
      ├─ normalize_transcript() — filler removal, alias substitution
      │
      ├─ is_empty_transcript() → blocked if empty
      │
      ├─ looks_like_injection_attempt() → flagged in audit metadata
      │
      ├─ ask(text, cwd=cwd, yes=False)   ← ALWAYS yes=False
      │      (same permission / risk / audit pipeline as typed input)
      │
      ├─ audit: voice.session.routed  origin="voice"
      │
      └─ VoiceAgentResult
              │
              ▼ (if spoken response requested)
      VoiceService.speak()
              │
              ├─ redact_tts_output()  — secrets → [REDACTED]; truncate at MAX_TTS_CHARS
              │
              └─ tts.synthesize()    — PiperTTS subprocess or MockTTS
```

## 5. Security Verification Checklist

The following checks were verified by dedicated tests.  All pass.

| # | Property | Test(s) | Result |
|---|---|---|---|
| S1 | `ask()` always called with `yes=False` | `test_service_yes_false_*` (2 parametrized) | PASS |
| S2 | Injection transcript → UNKNOWN intent, no tool executed | `test_service_injection_*` (3 parametrized) | PASS |
| S3 | `voice_approval_always_denied()` returns True | `test_voice_approval_always_denied` | PASS |
| S4 | `sounddevice` not imported at module level in `service.py` | `test_sounddevice_not_in_service_source` | PASS |
| S5 | `sounddevice` not imported at module level in `main.py` | `test_sounddevice_not_in_main_source` | PASS |
| S6 | `VoiceAuditRecord` has no `transcript_text` field | `test_audit_record_no_raw_transcript` | PASS |
| S7 | `VoiceAuditRecord` has no `audio_data` field | `test_audit_record_no_audio_data` | PASS |
| S8 | TTS redacts `sk-` prefix | `test_tts_redact_*` (parametrized) | PASS |
| S9 | TTS redacts `ghp_` prefix | `test_tts_redact_*` (parametrized) | PASS |
| S10 | TTS redacts Bearer token | `test_tts_redact_*` (parametrized) | PASS |
| S11 | TTS redacts `BEGIN PRIVATE KEY` | `test_tts_redact_*` (parametrized) | PASS |
| S12 | TTS output truncated at MAX_TTS_CHARS=500 | `test_tts_truncation` | PASS |
| S13 | TTS truncation appended message present | `test_tts_truncation` | PASS |
| S14 | Confidence None → destructive blocked | `test_confidence_gating` (parametrized) | PASS |
| S15 | Confidence 0.84 → destructive blocked | `test_confidence_gating` (parametrized) | PASS |
| S16 | Confidence 0.85 → destructive allowed | `test_confidence_gating` (parametrized) | PASS |
| S17 | Session: stop-before-start raises RuntimeError | `test_session_stop_before_start` | PASS |
| S18 | Session: double-start raises RuntimeError | `test_session_double_start` | PASS |
| S19 | Session context manager cleans up temp file on exception | `test_session_cleanup_on_exception` | PASS |
| S20 | CLI `--duration 0` rejected with exit 2 | `test_listen_duration_zero` | PASS |
| S21 | CLI `--duration -5` rejected with exit 2 | `test_listen_duration_negative` | PASS |
| S22 | CLI `--duration 121` rejected with exit 2 | `test_listen_duration_too_long` | PASS |
| S23 | CLI missing sounddevice exits 1 with install instructions | `test_listen_missing_sounddevice` | PASS |
| S24 | CLI `aos voice --help` exits 0 without voice deps | `test_voice_help_no_deps` | PASS |
| S25 | CLI `aos --help` includes "voice" without voice deps | `test_voice_wired_in_main` | PASS |
| S26 | `looks_like_injection_attempt()` flags known patterns | `test_injection_detection_*` (6 parametrized) | PASS |
| S27 | `contains_secret_pattern()` flags known patterns | `test_secret_pattern_*` (8 parametrized) | PASS |
| S28 | `is_empty_transcript()` handles whitespace-only strings | `test_empty_transcript_*` (parametrized) | PASS |
| S29 | Alias normalization applies longest-match canonicalization | `test_alias_*` (12 parametrized) | PASS |
| S30 | AudioInput frozen; mutation raises FrozenInstanceError | `test_audio_input_frozen` | PASS |

## 6. Known Limitations / Audit Trail Note

The `ask()` audit events do not carry `origin="voice"` — `ask()` was not
modified (ADR-0005 and the yes=False invariant forbid changing its signature
from the voice layer).  Instead, `VoiceService` records a separate
`voice.session.routed` event with `origin="voice"` immediately after `ask()`
returns.  This is intentional: the ask() events are always present whether
triggered by voice or terminal, and the voice-origin event brackets them for
correlation by session_id.

## 7. Test Results

```
python -m pytest -q
445 passed, 2 skipped in 47.64s
```

- Phase 0–7 regression: PASS (347 existing tests all still pass)
- New Phase 8 tests: 98 (38 types/normalization + 22 safety + 14 session + 24 service/CLI)
- Skips: 2 benign Windows symlink-privilege skips (unchanged from Phase 1)

## 8. Compile Check

```
python -m compileall -q aos tests
```

PASS — no syntax errors.

## 9. F8-4 Remediation (2026-07-11, Claude Sonnet)

After the Codex final gate returned FAIL for F8-4 (missing session lifecycle
audit events), a targeted remediation was applied:

- `VoiceSessionLifecycle` context manager added to `aos/voice/service.py`.
- 5 lifecycle methods added to `VoiceService`: `record_session_started`,
  `record_session_completed`, `record_session_cancelled`, `record_session_timed_out`,
  `record_session_failed`.
- `listen()` updated to call `record_session_started()` after `session.start()`
  succeeds and use `create_lifecycle()` context for exactly-once terminal events.
- 24 new lifecycle tests added; full suite: **476 passed, 2 skipped**.
- F8-1 / F8-2 / F8-3 fixes and all Phase 0–7 guarantees preserved.

See `docs/PHASE_8_F8_4_REMEDIATION_REPORT.md` for the full remediation report.

## 10. Next Step

Independent re-gate (Phase 8, all F8-1 through F8-4):

1. Run `python -m pytest -q` and confirm ≥476 passed / 2 skipped.
2. Verify the security invariants listed in Section 7 above.
3. Verify F8-1: `_record_audit` maps error to `"provider_error"` or `None`.
4. Verify F8-2: TTS redacts short Bearer/Basic values and private-key blocks.
5. Verify F8-3: `sounddevice.rec()` called in `start()`, not `stop()`.
6. Verify F8-4: `voice.session.started` emitted after `session.start()`; exactly
   one terminal event per started session.
7. If all pass, declare Phase 8 AWAITING HUMAN OWNER APPROVAL in HANDOFF.md.
8. Do not begin Phase 9 without Human Owner approval in PHASE_CONTRACT.md.
