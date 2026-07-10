# Phase Contract

## Active Phase: Phase 3 - Minimal Agent Loop

## Phase Goal

Implement a deterministic agent loop that classifies a small set of user intents, proposes structured tool calls, validates them, and executes them only through the existing safe file and safe shell tools.

## Allowed Work

- Maintain all Phase 0, Phase 1, and Phase 2 behavior.
- Implement deterministic intent classification and rule-based planning.
- Implement a structured tool registry that delegates only to existing safe tools.
- Implement the `aos ask` CLI command and supporting tests/docs.
- Add agent audit events for request, plan, tool preview/apply, blocked, and result.

## Forbidden Work

The following remain forbidden in Phase 3:

- memory system
- voice
- dashboard
- browser automation
- screen understanding
- model router
- multi-agent system
- unrestricted shell access
- arbitrary filesystem access
- direct subprocess use by the agent
- direct file reads/writes by the agent
- cloud model integration beyond a minimal local adapter interface

## Exit Criteria

- Existing Phase 0, Phase 1, and Phase 2 tests still pass.
- Phase 3 intent, planner, registry, loop, CLI, and safety tests pass.
- `aos ask --dry-run "run tests"` works.
- `aos ask "summarize this project"` works.
- `aos ask "find TODOs"` works.
- `aos ask "show git status"` works.
- `aos ask "run tests"` requires approval.
- `aos ask "read .env"` is blocked.
- Unknown requests execute no tools.
- Agent audit events are written and audit verification still passes.

## Agent Rule

Before doing work, every agent must read:

1. `PHASE_CONTRACT.md`
2. `TASK_BOARD.md`
3. `SECURITY_BOUNDARIES.md`
4. `TOOL_CAPABILITIES.md`
5. `CODING_RULES.md`

No agent may implement work outside the active phase unless the human owner updates `PHASE_CONTRACT.md`.

