# Phase 3 — Minimal AI Agent Loop

## Goal

Wire up exactly one model provider behind the structured-output boundary described in `ARCHITECTURE.md`, and build the first real intent parser, tool router, and validator.

## Why this phase matters

This is the first phase where a model's output can cause an action. Every rule in `MODEL_PROVIDER.md` ("models are providers, not executors") gets tested for real here.

## In scope

- One model provider integration (structured JSON output only).
- `aos ask "<request>"`.
- Intent parser turning free text into a structured proposal.
- Tool router mapping a proposal to a Phase 1/2 tool call.
- Validator rejecting malformed or out-of-contract proposals before they reach the permission engine.
- A simple observe loop (propose -> validate -> permission-check -> execute -> audit -> report).

## Out of scope

Multiple providers/routing (Phase 6), memory system (Phase 4), voice, dashboard, browser, screen understanding.

## Deliverables

`aos/core/intent.py`, `aos/core/router.py`, `aos/core/loop.py` — currently Phase 3 placeholders — replaced with real implementations; `aos/models/base.py` gets its first concrete provider adapter.

## Commands expected after this phase

```bash
aos ask "summarize this project"
aos ask "find TODOs in this repo"
aos ask "run tests"
```

## Security requirements

The validator is a hard gate: any proposal that doesn't match the expected schema, or that requests a tool/capability the model wasn't offered, is rejected before the permission engine ever sees it. Every proposal and its outcome is audited, including rejections.

## Test requirements

Validator rejection tests for malformed/out-of-schema proposals, prompt-injection tests (file content claiming to be an instruction must not change routing), end-to-end `aos ask` tests against Phase 1/2 tools with the model mocked.

## Acceptance criteria

`aos ask` can drive a real Phase 1 or Phase 2 tool end to end, with every step audited and every risky step gated exactly as it would be if invoked directly via `aos fs`/`aos run`.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 2 is frozen and `PHASE_CONTRACT.md` names Phase 3 as active.
