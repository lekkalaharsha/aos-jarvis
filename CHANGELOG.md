# CHANGELOG

## 2026-07-10 — Codex (Phase 1 implementation) + Claude Code (verification)
- Codex implemented Phase 1: permission engine (`aos/safety/{permissions,risk,paths,errors}.py`), safe file tools (`aos/tools/fs_tools.py`), snapshot/restore (`aos/safety/snapshots.py`), CLI (`aos fs *`, `aos snapshot *`), tests, and docs (`docs/phase_1.md`, `docs/permissions.md`, `docs/risk_tiers.md`). Updated `PHASE_CONTRACT.md` to declare Phase 1 active.
- Added `AOS_DATA_DIR` env override to `aos/config/loader.py` for local/test data isolation.
- Claude Code independently verified the handoff: `pytest -q -rs` (39 passed, 1 skipped — benign Windows symlink-privilege limitation), plus a manual CLI walkthrough confirming blocked dangerous paths/secrets/traversal/outside-root writes, correct list/read/search/write/edit, snapshot-before-edit, a real restore that correctly reverted content, and full audit coverage with a valid hash chain throughout. Phase 0 commands confirmed unaffected.
- Updated `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md` to record verified (not just claimed) Phase 1 completion.

## 2026-07-10 — Claude Code (project tracking system)
- Created the full project-tracking/phase-management documentation system: PROJECT_SCOPE.md, DEVELOPMENT_WORKFLOW.md, MODEL_PROVIDER.md, TOOL_INTERFACE.md, PERMISSION_MODEL.md, AUDIT_LOG.md, EVALS.md, TESTING_STRATEGY.md, RELEASE_CHECKLIST.md.
- Added 13 per-phase files under `docs/phases/` and 7 new numbered ADRs under `docs/adr/`.
- Added reserved `docs/security/`, `docs/models/`, `docs/tools/`, `docs/workflows/` folders.
- Added `.agent/context.md`, `.agent/antigravity_notes.md`, and `.agent/templates/{handoff,task,blocker,review}_template.md`.
- Extended DECISIONS.md, PROJECT_STATE.md, and TASKS.md to cover the tracking-setup work without erasing the already-completed Phase 0 code history.
- No product code changed in this pass; all 15 existing tests still pass, plus 2 new tests for phase-doc/ADR existence.

## 2026-07-10 — Claude Code
- Created Phase 0 foundation structure, coordination docs, CLI skeleton, SQLite audit log with hash-chain verification, and basic risk/permission/tool-contract/eval scaffolding.
- Adopted the full-context PDF spec: renamed audit event fields to actor/event_type/action/resource/risk_tier/status/payload_json/parent_hash/event_hash, added the config system and `aos config show`, switched eval fixtures to YAML, converted capability/tool models to Pydantic v2, added Rich CLI output.
- Added ROADMAP.md, ARCHITECTURE.md, SECURITY.md, PROJECT_STATE.md, TASKS.md, HANDOFF.md, BLOCKERS.md, `.gitignore`, and `docs/{phase_0,tool_interface,permission_model,audit_log,evals}.md`.
- Set up the repo-as-shared-memory communication system: standardized HANDOFF.md/TASKS.md/BLOCKERS.md templates and added `.agent/{claude,codex,opencode}_notes.md` and `.agent/current_context.md`.
- 15 pytest tests passing; all required Phase 0 commands verified working.
