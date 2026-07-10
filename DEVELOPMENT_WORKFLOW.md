# Development Workflow

## Roles

- **ChatGPT** — product manager/architect: creates phase specs, maintains direction.
- **Claude Code** — main builder: implements the assigned phase/task, updates shared memory files.
- **Codex** — reviewer/tester/security checker: reviews, adds tests, validates phase compliance, updates shared memory files.
- **OpenCode** — local executor: runs the repo on real Linux/Kali/Ubuntu, reports terminal errors, updates `HANDOFF.md`/`BLOCKERS.md`.
- **Antigravity** — secondary assistant/reviewer; follows the same read/update discipline as other agents (see `AGENTS.md`).
- **Human Owner** — final approver; the only authority who may unlock work outside the active phase by updating `PHASE_CONTRACT.md`.

## The Cycle

1. ChatGPT (or the human owner) creates or confirms the phase spec.
2. Claude Code reads shared memory files, then builds only the assigned phase/task.
3. Claude Code updates `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md`, `CHANGELOG.md`.
4. Codex reviews, tests, and security-checks the change.
5. Codex updates `HANDOFF.md`, `TASKS.md`, `CHANGELOG.md`, `BLOCKERS.md`.
6. OpenCode runs the result locally on Linux/Kali/Ubuntu.
7. OpenCode updates `HANDOFF.md` and `BLOCKERS.md`.
8. The human owner reviews.
9. The phase is frozen.
10. The human owner updates `PHASE_CONTRACT.md` to open the next phase.

## Shared Memory Discipline

The Git repo is the shared communication hub — no agent depends on chat memory. See the "Communication Protocol" section of `AGENTS.md` for the exact read-before/update-after list per agent, and the standard startup/shutdown checklists.

## Branching (optional, for multi-agent parallel work)

```bash
git checkout -b phase-0-foundation
# per-tool branches if working in parallel:
git checkout -b claude/phase-0-foundation
git checkout -b codex/phase-0-review
git checkout -b opencode/phase-0-local-test
```

Solo work can stay on a single `phase-N-name` branch off `main`. Only merge when tests pass, `HANDOFF.md`/`TASKS.md`/`CHANGELOG.md` are updated, and there are no critical open blockers.
