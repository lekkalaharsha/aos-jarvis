# Phase 7 — Dashboard for Visibility

## Goal

Build a read-only dashboard over data that already exists from prior phases: audit, permissions, snapshots, project timeline, memory, model usage.

## Why this phase matters

This is the first UI beyond the CLI. It must not become a new execution surface — it only visualizes what the CLI and audit log already know.

## In scope

- Audit viewer, permission viewer, snapshot viewer, project timeline viewer, memory viewer, model usage viewer — all read-only.

## Out of scope

Any write/execute action from the dashboard. Voice (Phase 8), workspace control (Phase 9), browser (Phase 10), screen understanding (Phase 11).

## Deliverables

A dashboard app (framework choice deferred to the Phase 7 spec — see `MODEL_PROVIDER.md`/`ARCHITECTURE.md` for the "reuse existing tools" principle: Streamlit or Tauri, not a custom framework) reading directly from the audit DB and memory store.

## Commands expected after this phase

A way to launch the dashboard, e.g. `aos dashboard` (opens a local read-only view).

## Security requirements

The dashboard must be local-only by default (no exposed network port without explicit opt-in) and must never expose secret-denylist paths/values even if they somehow entered the audit log.

## Test requirements

Read-only enforcement tests (no code path in the dashboard can call `execute()` on any tool), rendering smoke tests against seeded audit/memory data.

## Acceptance criteria

Every viewer reflects real audit/memory data with no mutation path; the dashboard cannot be used to bypass the CLI's permission/audit flow.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 6 is frozen and `PHASE_CONTRACT.md` names Phase 7 as active.
