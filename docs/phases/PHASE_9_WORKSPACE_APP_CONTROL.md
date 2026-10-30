# Phase 9 — Workspace and App Control

## Goal

Let AOS-Jarvis open and arrange the user's local dev environment: project folders, editor, terminal, and dev servers.

## Why this phase matters

This is the first phase that launches other applications rather than just reading/writing files or running scoped shell commands. It reuses the Phase 2 shell runner rather than inventing a new execution path.

## In scope

- Open project folder, open VS Code, open terminal in project.
- Restore last workspace.
- Start a dev server, gated by explicit approval (T2 — a running server is a standing side effect until stopped).

## Out of scope

Browser tools (Phase 10), screen understanding (Phase 11), any action outside the already-allowed project directories from Phase 1.

## Deliverables

`aos/tools/workspace.py` implemented as a `BaseTool`, routing actual process launches through the Phase 2 shell runner's audited execution path.

## Commands expected after this phase

```bash
aos workspace open <project>
aos workspace editor
aos workspace terminal
aos workspace restore
aos workspace dev-server --approve
```

(Exact command names finalized in the Phase 9 spec; must stay consistent with the `aos <noun> <verb>` pattern used elsewhere.)

## Security requirements

Starting a long-running process (dev server) is T2: explicit approval, and the audit event must record how to stop it. Opening an editor/terminal is T1 (reversible, no lasting system effect beyond the open window).

### Approved-project bootstrap

`aos workspace enroll <exact-path> --approve` is a direct Human Owner action
that creates a one-use approval for the exact canonical directory. It does not
consult registry membership or an approved parent. Workspace commands then take
only the resulting opaque project ID. The cwd, registry listing, home, root,
system paths, secret paths, and broad roots never implicitly authorize a project.
The registry atomically persists only a digest of a consumed approval before it
persists membership. An interruption therefore spends the approval rather than
allowing replay; a re-enrollment always needs a newly issued approval.

Launches use closed typed requests inside the Phase 2 runner: platform-allowlisted
folder opening, VS Code, the platform default terminal, and the fixed loopback
server profile. The server remains in the invoking foreground terminal. The only
supported stop guidance is `Press Ctrl+C in the terminal that started this server.`;
there is no cross-invocation process manager or PID authority.

## Test requirements

Approval-gate tests for dev server start, working-directory scope tests reusing Phase 1/2 allowlist logic, workspace-restore idempotency tests.

## Acceptance criteria

Every launched process is scoped to an allowed project directory and audited; a dev server cannot start without explicit approval.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 8 is frozen and `PHASE_CONTRACT.md` names Phase 9 as active.
