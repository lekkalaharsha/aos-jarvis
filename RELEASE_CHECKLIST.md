# Release / Phase-Freeze Checklist

Use this before declaring any phase complete and merging its branch.

## Documentation

- [ ] `PROJECT_STATE.md` reflects actual completed/in-progress/not-started status.
- [ ] `TASKS.md` has no `In Progress` rows for this phase; everything is `Done`, `Blocked` (with a `BLOCKERS.md` entry), or intentionally deferred.
- [ ] `HANDOFF.md` has a current entry with accurate files changed, tests run, and next worker/task.
- [ ] `CHANGELOG.md` has a dated entry for the work.
- [ ] `BLOCKERS.md` has no unresolved `High` severity items for this phase.

## Code and Tests

- [ ] `pytest -q` passes with zero failures.
- [ ] All commands required by the phase (see the phase's file in `docs/phases/`) work end to end, not just under test.
- [ ] No feature from a later phase was implemented (cross-check the phase's "Out of scope" list).
- [ ] No network calls, shell execution, or real model API calls were added unless the phase explicitly requires them.
- [ ] No secret-reading code was added (`.env`, `~/.ssh`, private keys, cookies, `/etc/shadow`, etc.).

## Review

- [ ] Codex has reviewed and updated `HANDOFF.md`/`BLOCKERS.md`.
- [ ] OpenCode has run the phase locally (Linux/Kali/Ubuntu) and updated `HANDOFF.md`/`BLOCKERS.md`.
- [ ] Human owner has reviewed and is ready to update `PHASE_CONTRACT.md` to open the next phase.

Only after every box is checked does the phase freeze and the next phase become eligible to start.
