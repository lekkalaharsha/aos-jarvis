# Phase 2 — Safe Shell Command Runner

## Goal

Add a shell runner that can execute a tightly scoped set of commands with full preview, approval, sandboxing where available, and audit.

## Why this phase matters

Shell execution is the highest-blast-radius capability in the whole roadmap short of raw disk access. It must inherit every guarantee built in Phase 0 (audit) and Phase 1 (permission engine, approval UX) before a single real command runs.

## In scope

- Command allowlist and denylist (see `SECURITY.md` blocked commands: `sudo`, `rm -rf`, `chmod -R /`, `mkfs`, `dd`, `curl | sh`, etc.).
- Working-directory scope (commands only run inside an allowed project directory).
- Timeout and output capture.
- Dry-run preview before execution.
- Approval prompt showing the exact command, working directory, risk tier, and sandbox status.
- `bubblewrap` sandboxing when available on the host.
- Audit event for every command, allowed or denied.

## Out of scope

Model calls, voice, dashboard, browser, screen understanding, multi-agent.

## Deliverables

`aos/tools/shell.py` implementing `BaseTool`; denylist matcher covering the blocked-command patterns; sandbox wrapper with a documented fallback when `bubblewrap` isn't present.

## Commands expected after this phase

```bash
aos run "git status"
aos run "pytest"
aos run "python --version"
```

## Security requirements

Any command matching the denylist is T3 and never executes, even inside dry-run. Everything else defaults to T1/T2 depending on reversibility — see `SECURITY.md`. No command may escape the configured working directory.

## Test requirements

Denylist match tests for every blocked pattern, working-directory escape tests, timeout enforcement test, sandbox-present and sandbox-absent code paths, audit event emitted for every command including denials.

## Acceptance criteria

A denylisted command is blocked and logged, never executed, under any phrasing or flag combination covered by tests; an allowed command runs, captures output, and is audited.

## Handoff requirements

Same as Phase 0/1.

## Do not proceed until

Phase 1 is frozen, its snapshot/permission engine is proven in real use, and `PHASE_CONTRACT.md` names Phase 2 as active.
