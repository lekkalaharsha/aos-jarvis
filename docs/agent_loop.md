# Agent Loop

The Phase 3 agent loop is intentionally small.

## Flow

1. Classify the user request into a supported intent.
2. Build a structured plan.
3. Validate each proposed tool call against the allowlist registry.
4. Preview each tool call through the existing safe tool surface for normal runs.
5. Stop for approval if a tool call requires approval and `--yes` is not present.
6. Execute through the safe tool layer.
7. Collect observations and synthesize a final answer.
8. Write agent audit events.

## Tool Registry

The registry allows only:

- `fs.list`
- `fs.read`
- `fs.search`
- `fs.write`
- `fs.edit`
- `snapshot.list`
- `snapshot.restore`
- `run.preview`
- `run.apply`

Unknown tool names, missing args, unexpected args, and risk-tier mismatches are rejected before execution.

## Why The Agent Cannot Touch Files Or Shell Directly

The agent layer does not call `open()`, `subprocess`, or `shell=True`. File access is delegated to Phase 1 tools, and command execution is delegated to the Phase 2 shell runner. This preserves path validation, secret blocking, command policy checks, approval behavior, snapshots, and lower-level audits.

## Audit Events

Phase 3 adds:

- `agent.ask`
- `agent.plan`
- `agent.tool.preview`
- `agent.tool.apply`
- `agent.blocked`
- `agent.result`

These events describe the request lifecycle without duplicating full shell output that is already audited by Phase 2.

Dry-run mode validates the structured tool calls but does not invoke lower-level tool preview or execution functions.
