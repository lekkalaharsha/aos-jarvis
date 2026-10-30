# Phase 8 OpenCode Supplemental Review

Date: 2026-07-11  
Model used: Codex reviewer runtime (requested OpenCode supplemental role; DeepSeek V4 Flash was not available in this session)

## Scope and files reviewed

Review-only. No production code was modified. Reviewed `aos/voice/`,
`aos/interfaces/cli/voice_commands.py`, all five `tests/test_voice_*.py`
files, and the Phase 8 implementation, final-gate, and F8-4 remediation
reports. `docs/voice.md` is absent.

## Commands and results

```
python -m compileall -q aos tests                 PASS
python -m pytest -q tests/test_voice_*.py         129 passed in 4.62s
aos voice --help                                  PASS; no optional imports needed
aos voice doctor                                  clear missing-dependency warnings
aos audit verify                                  valid (1216 events)
python -m pytest -q                               final summary omitted by bridge
```

The reported full-suite `476 passed, 2 skipped` was not independently captured
in this review because the Windows-venv terminal bridge omitted the final line.

## F8-1 — provider errors

**Partially verified.** `_record_audit()` stores `provider_error`, not raw
`VoiceAuditRecord.error`; STT/TTS tests confirm synthetic secrets are absent
from audit payloads and returned service errors. Gap: no test covers a
secret-bearing `result.error` returned by `ask()` on its successful path;
`process_audio()` returns it unchanged.

## F8-2 — TTS redaction

**Partially verified.** Tests cover short Bearer, Basic, `sk-`, GitHub, a full
private-key block, and truncation. Flat text is redacted before synthesis. No
meaningful structured/nested-value test exists because TTS accepts a string.
Patterns do not cover all broader project secret forms (JWTs, DB URLs, cookies,
or generic authorization schemes).

## F8-3 — microphone boundary

**Verified for mocked boundary.** Imports/help are lazy; doctor does not call
device capture; `start()` contains `sounddevice.rec()` and `stop()` only stops
or converts an existing recording. Cancellation stops capture. Real Linux/Kali
hardware compatibility remains unverified.

## F8-4 lifecycle traceability matrix

| Path | Start | Terminal | Duplicate terminal | Raw data absent |
|---|---|---|---|---|
| success | Yes (CLI) | completed | helper tested | Yes |
| cancellation | Yes (CLI) | cancelled | helper tested | Yes |
| recording timeout | Not demonstrated | timeout helper only | helper tested | Yes |
| STT timeout | No timeout handling | failed/exception | not end-to-end | helper only |
| TTS timeout | Yes | **completed, not timed_out** | helper only | helper only |
| provider failure | Yes | failed | CLI path | Yes |
| unexpected exception | Yes | failed safety-net | helper tested | Yes |

### Blocking F8-4 gap

`VoiceSessionLifecycle.timeout()` is tested only directly; live CLI never calls
it. `process_audio()` does not catch STT `TimeoutError`, so it becomes generic
`failed`. Piper returns `"piper synthesis timed out"` as a failed result, but
the CLI still calls `lifecycle.complete()`. STT/TTS timeout paths therefore do
not produce `voice.session.timed_out` as required.

## Other gaps and compatibility

- No end-to-end test proves exactly one start event per real CLI session.
- Programmatic `PushToTalkSession` duration is not bounded; only CLI input is.
- Audio hardware/stream semantics and Linux/Kali players are untested.
- `docs/voice.md` is missing; phase-status wording is stale in coordination docs.

## Recommendation

**BLOCKING GAPS FOUND.** Require end-to-end STT/TTS timeout handling that emits
exactly one `voice.session.timed_out` event before a fresh Codex gate can pass.
Phase 9 remains blocked.
