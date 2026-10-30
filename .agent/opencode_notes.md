# OpenCode Notes

## Local environment
- WSL Ubuntu, Python 3.11.15, pytest 9.1.1, ruff 0.15.21
- `.venv` at `/home/harsh/projects/AOS-Jarvis/.venv`

## Install/run checklist
```bash
wsl -e bash -c "cd /home/harsh/projects/AOS-Jarvis && .venv/bin/python -m pytest -q"
wsl -e bash -c "cd /home/harsh/projects/AOS-Jarvis && .venv/bin/python -m aos.interfaces.cli.main --help"
wsl -e bash -c "cd /home/harsh/projects/AOS-Jarvis && .venv/bin/python -m aos.interfaces.cli.main audit verify"
```

## Phase 9 Implementation Summary

### Files created
- `aos/safety/dev_server.py` — opaque, expiring, single-use dev-server approval

### Files modified
- `aos/tools/shell_runner.py` — added `status()`, improved `stop()` with TIMED_OUT
- `aos/tools/workspace.py` — opaque approval, lifecycle audit, server status/stop
- `aos/interfaces/cli/workspace_commands.py` — server-status/server-stop commands, opaque approval
- `aos/agent/tool_registry.py` — workspace.server_status/server_stop operations
- `aos/safety/permissions.py` — new capability kinds

### Files created (tests)
- `tests/test_phase9_comprehensive.py` — 60 deterministic tests

### Documentation updated
- `docs/PHASE_9_WORKSPACE_APP_CONTROL.md`
- `PROJECT_STATE.md`
- `TASKS.md`
- `TASK_BOARD.md`
- `HANDOFF.md`
- `CHANGELOG.md`
- `BLOCKERS.md`
- `TOOL_CAPABILITIES.md`
- `PHASE_CONTRACT.md`
- `.agent/opencode_notes.md`

## Findings
- Pre-existing symlink test fails in WSL (not caused by Phase 9 changes)
- E702 semicolon style matches existing test patterns
- No mypy configured; ruff used for linting
