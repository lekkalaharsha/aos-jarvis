# Phase 11 — Screen Understanding Plugin

## Goal

Add screenshot capture, OCR, terminal error detection, and screen summarization, with any suggested fix requiring explicit approval before it can run through Phase 1/2 tools.

## Why this phase matters

Screen content is, like browser content, untrusted ambient context (`SECURITY_BOUNDARIES.md`). This phase is also the highest-privacy-sensitivity feature so far — it can see anything on screen, not just what the user directly asked about.

## In scope

- Screenshot capture (explicit user trigger, not continuous/background capture).
- OCR over the captured screenshot.
- Terminal error detection from OCR'd text.
- Screen summary.
- Suggested fix — always routed through the existing approval flow before any Phase 1/2 tool executes it.

## Out of scope

Continuous/background screen monitoring, any action triggered without an explicit capture request, advanced workflows (Phase 12).

## Deliverables

`aos/tools/screen.py` implementing `BaseTool`; OCR text tagged untrusted exactly like browser-extracted text before reaching the model.

## Commands expected after this phase

```bash
aos screen capture
aos screen summarize
aos screen suggest-fix
```

## Security requirements

Screenshots are never captured without an explicit user-triggered command. OCR'd text is untrusted context, never instruction. A suggested fix is a proposal only — it goes through the same validator/permission/approval path as any other tool-call proposal.

## Test requirements

OCR-text-as-untrusted-context tests (a captured error message containing embedded instructions must not alter behavior), suggested-fix approval-gate tests.

## Acceptance criteria

No screen-derived action executes without going through the standard approval flow; screenshots are never taken outside an explicit user request.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 10 is frozen and `PHASE_CONTRACT.md` names Phase 11 as active.
