# Project State

Current phase: Phase 1 — Permission Engine + Safe File Tools (implemented by Codex, independently verified by Claude Code)

## Completed

- Repo skeleton (`aos/` package: core, tools, safety, memory, models, config, evals, interfaces/cli)
- Typer CLI: `aos --help`, `version`, `doctor`, `config show`, `audit list`, `audit verify`, `eval run`
- Config system (`~/.aos-jarvis/config.toml`, default-created if missing)
- SQLite audit log with hash-chain verification and tamper detection
- Risk tier model (T0-T3) and decision mapping
- Capability/permission placeholders (deny-by-default, Pydantic models)
- Tool interface contract (`BaseTool`, `ToolResult`, `ToolSchema`, `ToolDiff`)
- Placeholder modules for core/intent/router/loop, memory/events/timeline, models/base (explicitly marked as later phases)
- Eval fixture framework (`phase0_basic.yaml` + runner)
- Coordination docs: README, PHASE_CONTRACT, AGENTS, TASK_BOARD, DECISIONS, RISK_REGISTER, EVAL_SPEC, TOOL_CAPABILITIES, SECURITY_BOUNDARIES, CODING_RULES, ROADMAP, ARCHITECTURE, SECURITY, ADRs
- Shared memory files: PROJECT_STATE.md, TASKS.md, HANDOFF.md, BLOCKERS.md, `.agent/`
- Full project-tracking/doc system: PROJECT_SCOPE.md, DEVELOPMENT_WORKFLOW.md, MODEL_PROVIDER.md, TOOL_INTERFACE.md, PERMISSION_MODEL.md, AUDIT_LOG.md, EVALS.md, TESTING_STRATEGY.md, RELEASE_CHECKLIST.md
- Per-phase docs (`docs/phases/PHASE_0..12_*.md`), extended ADR set (`docs/adr/0001..0007-*.md`), reserved `docs/security/`, `docs/models/`, `docs/tools/`, `docs/workflows/`
- Per-agent notes and templates (`.agent/{claude,codex,opencode,antigravity}_notes.md`, `.agent/templates/`)
- **Phase 1 — Permission engine** (`aos/safety/{permissions,risk,paths,errors}.py`): directory allowlist, capability checks, T0-T3 classification, dangerous-path/secret-file/traversal/symlink-escape blocking, deny-by-default.
- **Phase 1 — Safe file tools** (`aos/tools/fs_tools.py`): `list_dir`, `read_file`, `search_files`, `write_file`, `edit_file`, each audited and risk-gated; `delete_file` intentionally unimplemented.
- **Phase 1 — Snapshot/restore system** (`aos/safety/snapshots.py`): snapshot before every write/edit of an existing file, `list_snapshots`/`get_snapshot`/`restore_snapshot` (restore is T2, snapshots the current state first).
- **Phase 1 — CLI** (`aos/interfaces/cli/{fs_commands,snapshot_commands}.py`): `aos fs list/read/search/write/edit`, `aos snapshot list/restore`, wired into `main.py`.
- **Phase 1 — Docs**: `docs/phase_1.md`, `docs/permissions.md`, `docs/risk_tiers.md`.
- **Phase 1 — Independently verified** (2026-07-10, Claude Code): full `pytest -q -rs` run (39 passed, 1 skipped — the skip is a benign Windows-can't-create-unprivileged-symlinks limitation, covered instead by a resolved-path-escape test); manual CLI walkthrough in a throwaway project directory confirmed blocked paths (`/etc`, `~/.ssh/id_rsa`, `.env`, traversal, outside-approved-root), correct `list/read/search/write/edit`, snapshot-before-edit, and a real restore that correctly reverted file content; `audit list`/`audit verify` confirmed every allowed and blocked action was logged and the hash chain stayed valid; Phase 0 commands (`version`, `doctor`, `eval run`) confirmed unaffected.

## In Progress

- None. Phase 1 code, docs, and verification are complete as of this entry.

## Not Started

- Directory allowlist persistence beyond the CLI's current-working-directory default (`aos fs allow <path>` not yet implemented)
- `delete_file` (intentionally deferred, per Phase 1 scope)
- Shell runner (Phase 2)
- Model provider integration (Phase 3+)

## Do Not Build Yet

- Voice
- Dashboard
- Browser automation
- Screen understanding
- Multi-agent planner
