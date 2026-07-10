# Phase 12 — Advanced Workflows and Automation

## Goal

Add scheduled routines, project routines, workflow templates, and safe recurring automations, plus a plugin system now that several real tools exist to design a plugin contract around.

## Why this phase matters

This is the first phase where AOS-Jarvis can act without a human present in the loop for each individual action (recurring automation). Every safety property from every prior phase has to hold even when nobody is watching in real time.

## In scope

- Scheduled routines (e.g., "run tests every morning").
- Project routines and workflow templates composing existing Phase 1-11 tools.
- Safe recurring automations, each still individually risk-tiered and audited.
- A plugin system, built only after enough real tools exist to generalize a stable contract from (do not design this speculatively before Phase 12).

## Out of scope

Any new fundamental capability not already introduced in Phases 0-11 — this phase composes and schedules existing tools, it does not add new categories of system access.

## Deliverables

A scheduler that invokes existing tool calls through the full validator/permission/audit path exactly as an interactive `aos ask` would, plus a documented plugin interface.

## Commands expected after this phase

```bash
aos routine create <name>
aos routine list
aos routine run <name>
```

## Security requirements

A scheduled/unattended action gets the same risk-tier treatment as an interactive one — a T2 action still requires approval, which means most useful unattended automations are necessarily built from T0/T1 tool calls only, by design.

## Test requirements

Scheduler-to-tool-call audit tests, unattended-T2-action-blocks-without-approval tests, plugin contract conformance tests.

## Acceptance criteria

No recurring automation can perform a T2/T3 action without a human having pre-approved that specific action; every scheduled run is fully audited.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 11 is frozen and `PHASE_CONTRACT.md` names Phase 12 as active.
