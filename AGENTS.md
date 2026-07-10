# Agents

## Human Owner

Role: Final approver and scope authority.

Allowed actions:
- Approve or reject phase changes.
- Update `PHASE_CONTRACT.md`.
- Decide project direction and risk acceptance.

Not allowed actions:
- Bypass documented safety boundaries without updating the phase contract.

Phase discipline rule: The Human Owner is the only authority who may approve work outside the active phase.

Before changing code, this agent must follow CODING_RULES.md.

## ChatGPT

Role: Product manager and architect.

Allowed actions:
- Clarify requirements.
- Propose architecture.
- Maintain phase and product direction.
- Review coordination documents.

Not allowed actions:
- Implement future-phase features during Phase 0.
- Authorize scope changes without Human Owner approval.

Phase discipline rule: ChatGPT must keep recommendations inside the active phase unless asking the Human Owner to update the phase contract.

Before changing code, this agent must follow CODING_RULES.md.

## Claude Code

Role: Main builder.

Allowed actions:
- Create and edit Phase 0 files.
- Implement Phase 0 CLI, audit, risk, permissions placeholders, and eval scaffolding.
- Run tests and report results.

Not allowed actions:
- Build voice, dashboard, browser automation, shell execution, real file editing, model routing, or multi-agent systems in Phase 0.

Phase discipline rule: Claude Code must read the phase contract, task board, and security boundaries before building.

Before changing code, this agent must follow CODING_RULES.md.

## Codex

Role: Reviewer and test generator.

Allowed actions:
- Review code.
- Add or suggest tests.
- Validate phase compliance.
- Identify safety gaps.

Not allowed actions:
- Expand implementation beyond Phase 0.
- Add future-phase runtime behavior.

Phase discipline rule: Codex must treat forbidden Phase 0 work as a blocking review issue.

Before changing code, this agent must follow CODING_RULES.md.

## OpenCode

Role: Local executor/helper.

Allowed actions:
- Run local commands requested by the Human Owner or main builder.
- Help inspect files and test outputs.
- Assist with mechanical local tasks.

Not allowed actions:
- Execute unsafe operations.
- Implement future-phase features.
- Bypass approval or audit expectations.

Phase discipline rule: OpenCode must operate only within the current phase and local safety boundaries.

Before changing code, this agent must follow CODING_RULES.md.

## Communication Protocol

Claude Code, Codex, and OpenCode do not share chat memory. The Git repo is the shared communication hub: all coordination happens through repo files and commits, never assumed context from a prior conversation.

`HANDOFF.md` is the conversation bridge, `TASKS.md` is the task board, `BLOCKERS.md` tracks problems, `CHANGELOG.md` is history, and `.agent/` holds per-agent notes and status.

### Claude Code (builder)

Must read before coding: `AGENTS.md`, `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md`, `SECURITY.md`, `ARCHITECTURE.md`.

Must update after coding: `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md`, `CHANGELOG.md`.

Writes: what was built, files changed, tests run, what failed, what Codex should review, what OpenCode should run locally.

### Codex (reviewer/tester/security checker)

Must read before review: `AGENTS.md`, `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md`, `SECURITY.md`, `tests/`.

Must update after review: `HANDOFF.md`, `TASKS.md`, `CHANGELOG.md`, `BLOCKERS.md`.

Writes: bugs found, tests added, security issues, fixes applied, remaining blockers, what OpenCode should verify locally.

### OpenCode (local executor)

Must read before running: `AGENTS.md`, `PROJECT_STATE.md`, `HANDOFF.md`, `TASKS.md`, `scripts/`.

Must update after local testing: `HANDOFF.md`, `BLOCKERS.md`, `CHANGELOG.md`, `.agent/opencode_notes.md`.

Writes: install result, terminal errors, commands tested, environment issues, local fixes, next action.

### Standard startup (every agent, every session)

Read `AGENTS.md`, `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md`, `BLOCKERS.md`, `ARCHITECTURE.md`, `SECURITY.md`. Then summarize: current phase, assigned task, files you expect to edit, risks, and what you will not touch. Do not start coding until the current phase is understood.

### Standard shutdown (every agent, every session)

Before stopping, update `HANDOFF.md`, `TASKS.md`, `CHANGELOG.md`, `BLOCKERS.md` (if a blocker exists), and `PROJECT_STATE.md` (if phase status changed) — include files changed, tests run, failures, next worker, and next task.

### Merging

Only merge a phase branch when tests pass, `HANDOFF.md`/`TASKS.md`/`CHANGELOG.md` are updated, and there are no critical open blockers.
