# Phase 8 — Voice Interface

## Goal

Provide a local-only, push-to-talk voice interface.  Voice input is untrusted;
it never authorizes high-risk actions and always routes through the existing
permission, risk, and audit pipeline.

## Architecture

```
User push-to-talk (PushToTalkSession)
  ↓
AudioInput (bytes, sample_rate, channels)
  ↓
SpeechToTextProvider.transcribe() → TranscriptResult
  ↓
normalize_transcript() — deterministic, pure function
  ↓
looks_like_injection_attempt() / contains_secret_pattern() — flag for audit
  ��
ask(transcript, yes=False) — ALWAYS yes=False
  ↓
Agent loop (Phase 3 intent classifier + tool registry + permission gate)
  ↓
VoiceAgentResult → audit event with origin="voice"
  ↓
redact_tts_output() → TextToSpeechProvider.synthesize()
  ↓
_play_audio() → local audio playback
```

## Safety invariants

1. **`yes=False` always**: voice input cannot submit approval for any action.
2. **origin="voice"**: every agent turn triggered by voice has a `voice.session.routed`
   audit event with `origin="voice"`.
3. **No microphone at import time**: `sounddevice` is imported only inside the
   functions that need it, not at module level.
4. **Untrusted input**: transcript text is treated as data, not instruction.
   Injection patterns are flagged in audit metadata; the agent's intent
   classifier handles unknown inputs safely (UNKNOWN intent, no tools executed).
5. **TTS redaction**: secret-shaped strings are redacted from response text
   before any TTS synthesis.  Response text is bounded to 500 characters.
6. **No raw transcript in audit**: `VoiceAuditRecord` stores only lengths and
   metadata — never the raw transcript or audio bytes.
7. **Confidence conservatism**: `confidence_allows_destructive()` requires ≥0.85
   confidence; unknown confidence (None) is always treated as False.
8. **T2/T3 require terminal approval**: blocked results surface a clear message
   directing the user to the terminal.

## Module structure

```
aos/voice/
├── __init__.py
├── types.py           — immutable dataclasses (AudioInput, TranscriptResult, etc.)
├── config.py          — VoiceConfig dataclass + TOML loader
├── normalization.py   — pure transcript normalization functions
├── safety.py          — TTS redaction, injection detection, confidence gating
├── session.py         — PushToTalkSession (injectable recorder for tests)
├── service.py         — VoiceService: orchestrates STT→normalize→agent→TTS
└── providers/
    ├── base.py        — SpeechToTextProvider, TextToSpeechProvider (Protocols)
    ├���─ local_stt.py   — FasterWhisperSTT + MockSTT
    └── local_tts.py   — PiperTTS + MockTTS
aos/interfaces/cli/voice_commands.py — CLI: doctor, devices, listen, speak
```

## Optional dependencies

```
pip install 'aos-jarvis[voice]'
```

Installs: `sounddevice>=0.4`, `faster-whisper>=1.0`.

Piper TTS must be installed separately and placed on PATH.  Models are NOT
downloaded automatically — run `pip install faster-whisper` and then let
Whisper cache the selected model before first use.

## CLI commands

| Command | Description |
|---------|-------------|
| `aos voice doctor` | Check deps, devices, model availability |
| `aos voice devices` | List audio input/output devices |
| `aos voice listen [--duration N]` | Push-to-talk: record, transcribe, route |
| `aos voice speak "text"` | Synthesize and play text via TTS |
