# Phase Contract

## Active Phase: Phase 4 - Memory System

## Phase Goal

Implement a local, deterministic memory system derived from the append-only audit log. Memory is rebuildable, read-only at query time, and used for timeline and recall features without bypassing any existing safety boundaries.

## Allowed Work

- Maintain all Phase 0, Phase 1, Phase 2, and Phase 3 behavior.
- Implement SQLite-backed derived memory tables for events, entities, and timeline entries.
- Implement memory rebuild/index logic from audit events.
- Implement `aos memory ...` and `aos recall ...` CLI commands.
- Add minimal read-only memory recall integration to the Phase 3 agent.
- Add audit events for memory rebuild, index, query, and recall.

## Forbidden Work

The following remain forbidden in Phase 4:

- voice
- dashboard
- browser automation
- screen understanding
- model router
- multi-agent system
- embeddings or vector databases
- cloud memory
- autonomous workflows
- unrestricted file or shell access

## Exit Criteria

- All existing Phase 0, Phase 1, Phase 2, and Phase 3 tests still pass.
- Phase 4 store, indexer, timeline, recall, CLI, and safety tests pass.
- `aos memory status` works.
- `aos memory rebuild` works.
- `aos memory recent` works.
- `aos memory timeline` works.
- `aos memory commands` works.
- `aos memory failures` works.
- `aos recall "what did I work on recently"` works.
- Agent memory recall uses only memory tools.
- Memory rebuild is idempotent.
- Secrets are redacted from derived memory and memory audit payloads.
- Audit verification still passes.

## Agent Rule

Before doing work, every agent must read:

1. `PHASE_CONTRACT.md`
2. `TASK_BOARD.md`
3. `SECURITY_BOUNDARIES.md`
4. `TOOL_CAPABILITIES.md`
5. `CODING_RULES.md`

No agent may implement work outside the active phase unless the human owner updates `PHASE_CONTRACT.md`.

