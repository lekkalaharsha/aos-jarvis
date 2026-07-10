# Phase 6 — Model Router and Provider System

## Goal

Generalize the single Phase 3 provider into a `ModelProvider` interface with multiple adapters, task-based routing, secret redaction, and a cloud approval gate.

## Why this phase matters

Once more than one provider exists, routing decisions (which provider sees which data, local vs. cloud) become a security question, not just a convenience one. See `MODEL_PROVIDER.md` for provider roles.

## In scope

- `ModelProvider` interface.
- Adapters: Ollama, Hermes (via Ollama), Claude CLI/API, OpenAI/Codex, Grok/Groq.
- Provider config and task-based routing (e.g., planning -> Claude, coding -> Codex, private reasoning -> local).
- Secret redaction before any payload leaves the machine to a cloud provider.
- A cloud approval gate: sending data to a non-local provider is at minimum T1.

## Out of scope

Dashboard (Phase 7), voice (Phase 8), workspace control (Phase 9), browser (Phase 10), screen understanding (Phase 11).

## Deliverables

`aos/models/base.py` — currently a Phase 6 placeholder — replaced with the real `ModelProvider` interface and adapters.

## Commands expected after this phase

Routing is mostly invisible to the user; existing `aos ask` gains a `--provider`/config-driven routing behavior. No new top-level commands are required.

## Security requirements

Secret redaction runs before any payload reaches a non-local provider — this is tested, not assumed. Any cloud call requires approval per `SECURITY.md`'s risk tiers; local-only providers (Ollama/Hermes) can run at T0/T1 depending on what they touch.

## Test requirements

Redaction tests against the secret denylist (`.env`, tokens, keys, cookies), routing tests per task type, adapter contract tests (every adapter implements `ModelProvider` fully).

## Acceptance criteria

Switching providers via config changes routing without code changes; no unredacted secret ever reaches a cloud adapter in tests.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 5 is frozen and `PHASE_CONTRACT.md` names Phase 6 as active.
