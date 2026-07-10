# Phase 8 — Voice Interface

## Goal

Add push-to-talk voice input/output on top of the existing `aos ask` pipeline, with visible confirmation before any risky action.

## Why this phase matters

Voice is explicitly the last interface layer, not the first — see `ARCHITECTURE.md` ("Jarvis voice layer comes later. The safety layer comes first."). It must not shortcut the approval flow: a spoken command is still just text fed into the same validated pipeline.

## In scope

- Push-to-talk activation (no always-listening mode in this phase).
- Speech-to-text (reuse `faster-whisper`, per `ARCHITECTURE.md` reuse strategy).
- Text-to-speech (reuse `Piper`).
- Voice command routed through the existing `aos ask` pipeline, not a parallel code path.
- Visible (on-screen) confirmation for any T1+ action, even when triggered by voice.

## Out of scope

Always-listening/wake-word activation, workspace control (Phase 9), browser (Phase 10), screen understanding (Phase 11).

## Deliverables

A voice front-end that transcribes to text and calls the same `aos ask` entry point Phase 3 built — no new intent/validator/permission code path.

## Commands expected after this phase

A way to start push-to-talk mode, e.g. `aos listen`.

## Security requirements

A risky (T1+) action triggered by voice must still show a visible approval prompt — voice approval alone ("yes") is not sufficient without an on-screen confirmation the user can review.

## Test requirements

Transcription-to-intent tests (mocked STT), confirmation-gate tests proving a T1+ voice-triggered action cannot execute without the visible prompt being answered.

## Acceptance criteria

A voice command produces the same audited, permission-checked outcome as the equivalent typed `aos ask` command.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 7 is frozen and `PHASE_CONTRACT.md` names Phase 8 as active.
