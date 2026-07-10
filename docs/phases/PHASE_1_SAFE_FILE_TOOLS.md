# Phase 1 — Permission Engine + Safe File Tools

## Goal

Turn the Phase 0 capability/risk placeholders into a real, enforced permission engine, and add the first real tools: safe file list/read/search/write/edit with snapshots and diff preview.

## Why this phase matters

This is the first phase where AOS-Jarvis actually touches the filesystem. Every safety property promised in `SECURITY.md` (deny by default, snapshot before write, diff before approval) has to be proven here before any shell execution (Phase 2) is even considered.

## In scope

- Directory allowlist (`aos fs allow <path>`).
- Dangerous path blocker and secret denylist enforcement (see `SECURITY.md` blocked paths).
- Safe file `list`/`read`/`search`.
- Safe file `write`/`edit` — snapshot before every write, diff preview, explicit approval for T1+.
- Snapshot `list`/`restore`.

## Out of scope

Shell execution, model calls, voice, dashboard, browser, screen understanding, multi-agent.

## Deliverables

`aos/tools/fs.py` (or similar) implementing `BaseTool`; `aos/safety/snapshots.py` replacing its Phase 1 `NotImplementedError` stubs with real snapshot create/restore; permission engine enforcing the allowlist/denylist against every file tool call; audit events for every file action.

## Commands expected after this phase

```bash
aos fs allow ~/projects/aos-jarvis
aos fs list .
aos fs read README.md
aos fs search "TODO"
aos fs write notes.md --content "hello"
aos fs edit README.md
aos snapshot list
aos snapshot restore <snapshot_id>
```

## Security requirements

Every write is T1 (reversible, snapshot + approval) unless proven otherwise. Any path matching the blocked-path list in `SECURITY.md` is T3 (denied), full stop. No path outside an explicitly allowed directory is readable or writable.

## Test requirements

Path traversal tests (`../`, symlink escape, absolute paths outside allowlist), secret-path denial tests, snapshot create/restore round-trip, diff preview correctness, audit event emitted for every file action.

## Acceptance criteria

All commands above work; a blocked path is denied and logged, not silently skipped; a snapshot restore reverts a file exactly.

## Handoff requirements

Same as Phase 0 — update `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md`, `CHANGELOG.md`.

## Do not proceed until

Phase 0 is frozen and `PHASE_CONTRACT.md` names Phase 1 as active.
