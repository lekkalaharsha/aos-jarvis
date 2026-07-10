# Phase 4: Memory System

Phase 4 adds a local memory layer derived from the append-only audit log. It is not chat memory and it is not model-invented state.

## What Phase 4 Does

- Builds a rebuildable SQLite memory store from audit events.
- Derives memory events, entities, and timeline entries.
- Supports recent activity, file activity, command history, blocked actions, and failure queries.
- Supports rule-based recall without embeddings or cloud services.
- Integrates read-only memory recall into the agent.

## What Phase 4 Does Not Do

Phase 4 does not add voice, dashboard, browser automation, screen tools, model routing, multi-agent behavior, vector search, cloud memory, or autonomous workflows.

## Source Of Truth

The audit log remains the source of truth. Memory is a derived index that can be rebuilt from audit events.

## CLI Examples

```powershell
python -m aos.interfaces.cli.main memory status
python -m aos.interfaces.cli.main memory rebuild
python -m aos.interfaces.cli.main memory recent
python -m aos.interfaces.cli.main memory commands
python -m aos.interfaces.cli.main memory failures
python -m aos.interfaces.cli.main recall "what did I work on recently"
python -m aos.interfaces.cli.main ask "what did I work on recently"
```

## Known Limitations

- No embeddings or vector database.
- No semantic memory yet.
- No dashboard.
- No cross-device sync.
- No cloud memory.
- Recall is rule-based.
- Memory is only as good as the audit events that exist.

