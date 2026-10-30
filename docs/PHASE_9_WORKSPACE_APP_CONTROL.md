# Phase 9 — Workspace and App Control

## Goal

Let AOS-Jarvis open and arrange the user's local development environment:
approved project folders, editor, terminal, and explicitly approved dev servers.

## Architecture

```
CLI (workspace_commands.py)
  └─ WorkspaceTool (workspace.py)
       ├─ ApprovedProjectRegistry (approved_projects.py)
       ├─ DevServerApproval (dev_server.py)
       ├─ WorkspaceLaunchAdapter (shell_runner.py)
       └─ PermissionEngine (permissions.py)
```

## Key Components

### Approved Project Registry (`aos/safety/approved_projects.py`)

- One-use, exact-path enrollment via `HumanOwnerEnrollmentAuthority`
- Opaque project IDs (UUID hex) — never paths in agent/CLI calls
- Registry and PermissionEngine are separate concerns

### Dev-Server Approval (`aos/safety/dev_server.py`)

- Opaque, expiring, single-use approval for dev-server launches
- Minting requires explicit Human Owner confirmation; terminal origin alone is insufficient
- Bound to: operation, project ID/current identity, profile, port, terminal origin, expiry
- Token is never serialized, printed, or audited — only SHA-256 digest persisted
- 120-second TTL; consumed atomically before process launch
- Rejected if: expired, reused, wrong binding, voice/model-origin, revoked project

### WorkspaceLaunchAdapter (`aos/tools/shell_runner.py`)

- Closed typed process boundary — no generic subprocess API
- Fixed folder mappings: `xdg-open <canonical-project-path>` on Linux/WSL and `explorer.exe <canonical-project-path>` on Windows
- Fixed argv profiles: `["code", cwd]` (editor), `["x-terminal-emulator"]` (terminal), `[sys.executable, "-m", "http.server", port, "--bind", "127.0.0.1"]` (server)
- `shell=False`, sanitized environment, `DEVNULL` stdio
- Unsupported folder-launch platforms fail closed
- Server runs in the foreground until exit or Ctrl+C; cleanup is bounded
- Internal handles never cross the CLI boundary and provide no PID authority

### Lifecycle States

**States:** REQUESTED → VALIDATED → APPROVAL_REQUIRED → STARTING → RUNNING → STOPPED | DENIED | FAILED | TIMED_OUT | CANCELLED

Exactly one terminal event per lifecycle. Ctrl+C yields a typed cancelled/stopped outcome, and cleanup failure remains visible.

### WorkspaceTool (`aos/tools/workspace.py`)

Operations: status, open, editor, terminal, save, restore, serve

- OPEN, EDITOR, TERMINAL: T1 (reversible)
- SERVE: T2 (explicit confirmation plus opaque approval required)
- All operations audited with project IDs (never paths)
- Audit payloads include only safe metadata

## Security Invariants

1. No workspace launch bypasses PermissionEngine or audit
2. Dev-server approval consumed durably before process start
3. Approval minting requires `human_owner_confirmed=True`; origin alone is rejected
4. Voice/model cannot issue or consume server approval
5. PID, process object, argv, and environment never enter output or audit
6. The only supported stop guidance is `Press Ctrl+C in the terminal that started this server.`
7. Cross-invocation status/stop commands do not exist and old operations fail closed
8. Failed/timed-out launches still consume approval
9. Dry-run neither consumes approval nor launches
10. Token/digest never printed or audited

## CLI Commands

```bash
aos workspace enroll <path> --approve
aos workspace list
aos workspace status
aos workspace open <project-id>
aos workspace editor <project-id> [--editor vscode]
aos workspace terminal <project-id> [--terminal default]
aos workspace save <project-id> [--editor vscode] [--terminal default]
aos workspace restore
aos workspace serve <project-id> [--port 8000] [--approve]
```

Without `--approve`, `serve` displays the bounded project/profile/port preview and
uses an interactive confirmation prompt. Rejection mints no approval and launches
nothing. The server is loopback-only and remains attached to the invoking terminal.
Audit and output use the safe stop-method identifier
`ctrl_c_foreground_terminal`; no separate invocation can manage it.

## Agent Integration

- `workspace.open`, `workspace.editor`, `workspace.terminal`: T1, requires project_id
- `workspace.serve`: T2, requires project_id and terminal Human Owner confirmation
- Project IDs validated as opaque 32-char hex in tool registry
- Unknown fields rejected; model cannot provide executable or command
