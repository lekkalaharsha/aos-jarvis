# Phase 0 — Foundation + Audit Core

## Goal

Build the trusted foundation: repo skeleton, CLI, config system, SQLite audit log with hash-chain verification, risk-tier/capability model, tool interface contract, eval fixture framework, docs/ADRs, and shared agent memory files.

## Why this phase matters

Every later phase executes actions through this foundation. If the audit chain, risk model, or tool contract are wrong here, every later phase inherits the bug. Audit and permission scaffolding come before any real tool, by design (`ARCHITECTURE.md`, `PERMISSION_MODEL.md`).

## In scope

- `aos` CLI (`--help`, `version`, `doctor`, `config show`, `audit list`, `audit verify`, `eval run`).
- Config loader (`~/.aos-jarvis/config.toml`, safe default if missing).
- SQLite audit log + hash-chain verification + tamper detection.
- Risk tier model (T0-T3) and decision mapping.
- Capability/permission placeholders, deny-by-default.
- Tool interface contract (no real tools).
- Eval fixture framework (YAML fixtures, deterministic keyword classifier).
- Coordination docs and ADRs.

## Out of scope

File editing, shell execution, real model calls, voice, dashboard, browser automation, screen understanding, multi-agent planner, Linux distro/desktop shell work.

## Deliverables

`aos/` package (core, tools, safety, memory, models, config, evals, interfaces/cli placeholders and implementations as scoped above), `tests/` covering the required behaviors, all coordination docs listed in `PROJECT_STATE.md`.

## Commands expected after this phase

```bash
aos --help
aos version
aos doctor
aos config show
aos audit list
aos audit verify
aos eval run
```

## Security requirements

Deny-by-default capability/permission placeholders. No secret access. No shell execution. No network calls. See `SECURITY.md`.

## Test requirements

See `TESTING_STRATEGY.md`'s Phase 0 coverage list — audit append/list/verify/tamper, risk mapping, tool contract, capability serialization, config load, eval fixtures, phase-contract content, CLI doctor/verify, shared-memory-file existence.

## Acceptance criteria

- [x] `pip install -e .` succeeds.
- [x] All required commands work end to end.
- [x] `pytest -q` passes (15/15 as of the last handoff).
- [x] No Phase 1+ feature was implemented.

## Handoff requirements

Update `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md`, `CHANGELOG.md` per the standard shutdown checklist in `AGENTS.md`.

## Do not proceed until

Codex has reviewed the audit schema and Pydantic model conversion, OpenCode has run the suite on real Linux, and the human owner updates `PHASE_CONTRACT.md` to open Phase 1.
