# Phase Contract

## Active Phase: Phase 1 - Permission Engine and Safe File Tools

## Phase Goal

Implement permissioned file access for approved project folders. AOS-Jarvis can list, read, search, write, edit, snapshot, and restore files only after path safety checks, risk classification, audit logging, and approval gates where required.

## Allowed Work

- Maintain Phase 0 foundation behavior.
- Implement directory allowlists and capability-based permission checks.
- Implement path traversal, dangerous path, secret file, and symlink escape blocking.
- Implement read-only file tools for approved project text files.
- Implement reversible write/edit tools with diff previews and snapshots.
- Implement snapshot listing and T2 restore with strong approval in the CLI.
- Implement audit events for allowed and blocked Phase 1 file actions.
- Add tests and documentation for Phase 1 safety behavior.

## Forbidden Work

The following remain forbidden in Phase 1:

- AI agent loop
- voice
- dashboard
- browser automation
- screen understanding
- memory system
- model router
- multi-agent system
- shell command runner
- unrestricted filesystem access
- access to secrets or credential stores

## Exit Criteria

- Existing Phase 0 tests still pass.
- Phase 1 permission, path, file tool, snapshot, and safety tests pass.
- `aos fs list` works inside an approved root.
- `aos fs read` works for approved non-secret text files.
- `aos fs search` searches approved project text files.
- `aos fs write` and `aos fs edit` require approval and create snapshots before modifying existing files.
- `aos snapshot list` and `aos snapshot restore` work with restore treated as T2.
- Dangerous paths, secrets, traversal, and symlink escapes are blocked and audited.
- Allowed file actions are audited.
- Documentation explains Phase 1 behavior and limits.

## Agent Rule

Before doing work, every agent must read:

1. `PHASE_CONTRACT.md`
2. `TASK_BOARD.md`
3. `SECURITY_BOUNDARIES.md`
4. `TOOL_CAPABILITIES.md`
5. `CODING_RULES.md`

No agent may implement work outside the active phase unless the human owner updates `PHASE_CONTRACT.md`.
