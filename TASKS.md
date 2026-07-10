# TASKS

Status values: `Todo`, `In Progress`, `Review`, `Blocked`, `Done`.

## Pre-Phase 0 — Project Tracking Setup

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P-000 | Pre-Phase 0 | Create project tracking files | Claude | Done | High | Root docs (PROJECT_SCOPE, ARCHITECTURE, ROADMAP, SECURITY, DEVELOPMENT_WORKFLOW, etc.) |
| P-001 | Pre-Phase 0 | Create phase documents | Claude | Done | High | docs/phases/PHASE_0..12_*.md |
| P-002 | Pre-Phase 0 | Create ADRs | Claude | Done | Medium | docs/adr/0001..0007-*.md |
| P-003 | Pre-Phase 0 | Create shared agent memory files | Claude | Done | High | .agent/*_notes.md, .agent/templates/ |
| P-004 | Pre-Phase 0 | Review documentation consistency | Codex | Todo | Medium | cross-check phase files against ROADMAP/PHASE_CONTRACT |
| P-005 | Pre-Phase 0 | Prepare Phase 0 implementation prompt | Claude | Done | High | Phase 0 was already implemented in a prior session — see below |

## Phase 0 — Foundation + Audit

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P0-001 | Phase 0 | Create repo skeleton | Claude | Done | High | aos/ package with core, tools, safety, memory, models, config, evals, interfaces/cli |
| P0-002 | Phase 0 | Add Typer CLI | Claude | Done | High | aos --help, version, doctor work |
| P0-003 | Phase 0 | Add config loader | Claude | Done | Medium | ~/.aos-jarvis/config.toml created on demand; aos config show works |
| P0-004 | Phase 0 | Add SQLite audit log | Claude | Done | High | actor/event_type/action/resource/risk_tier/status/payload_json/parent_hash/event_hash schema |
| P0-005 | Phase 0 | Add audit hash-chain verification | Claude | Done | High | aos audit verify detects broken parent_hash and modified rows |
| P0-006 | Phase 0 | Add audit tamper detection tests | Claude | Done | High | tests/test_audit.py covers tampering and broken continuity |
| P0-007 | Phase 0 | Add risk tier and capability model | Claude | Done | Medium | Pydantic-based Capability/PermissionDecision, deny-by-default |
| P0-008 | Phase 0 | Add tool interface contract | Claude | Done | Medium | BaseTool/ToolResult/ToolSchema/ToolDiff in aos/tools/base.py |
| P0-009 | Phase 0 | Add eval fixture framework | Claude | Done | Medium | phase0_basic.yaml + runner, aos eval run works |
| P0-010 | Phase 0 | Add Phase 0 docs and ADRs | Claude | Done | Medium | ROADMAP, ARCHITECTURE, SECURITY, docs/*.md, ADRs |
| P0-011 | Phase 0 | Set up shared memory / communication system | Claude | Done | High | HANDOFF/TASKS/BLOCKERS/CHANGELOG templates, .agent/ notes files |
| P0-012 | Phase 0 | Review schema rename and Pydantic conversion | Codex | Done | High | superseded — Codex built directly on this schema for Phase 1 without issue |
| P0-013 | Phase 0 | Run locally on Ubuntu/Kali | OpenCode | Todo | Medium | still pending; folded into P1-008 below |

## Phase 1 — Permission Engine + Safe File Tools

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P1-001 | Phase 1 | Permission engine (allowlist, capability checks, risk tiers) | Codex | Done | High | aos/safety/{permissions,risk,paths,errors}.py |
| P1-002 | Phase 1 | Dangerous path / secret file / traversal / symlink-escape blocking | Codex | Done | High | verified: /etc, ~/.ssh/id_rsa, .env, traversal, outside-root all blocked |
| P1-003 | Phase 1 | Safe file tools (list/read/search/write/edit) | Codex | Done | High | aos/tools/fs_tools.py |
| P1-004 | Phase 1 | Snapshot create/list/get/restore | Codex | Done | High | aos/safety/snapshots.py; restore is T2 and snapshots current state first |
| P1-005 | Phase 1 | CLI: `aos fs *`, `aos snapshot *` | Codex | Done | High | aos/interfaces/cli/{fs_commands,snapshot_commands}.py |
| P1-006 | Phase 1 | Phase 1 tests | Codex | Done | High | 39 passed, 1 skipped (benign Windows symlink limitation) |
| P1-007 | Phase 1 | Phase 1 docs | Codex | Done | Medium | docs/phase_1.md, docs/permissions.md, docs/risk_tiers.md |
| P1-008 | Phase 1 | Independent verification of Codex's Phase 1 work | Claude | Done | High | full test run + manual CLI/audit walkthrough, see PROJECT_STATE.md and HANDOFF.md |
| P1-009 | Phase 1 | Run locally on Ubuntu/Kali | OpenCode | Todo | Medium | verification so far is Windows-only |
| P1-010 | Phase 1 | Persistent directory allowlist (`aos fs allow <path>`) | Unassigned | Todo | Low | currently defaults to CWD; noted as a known limitation, not a blocker |
