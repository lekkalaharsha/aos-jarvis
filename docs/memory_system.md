# Memory System

The Phase 4 memory system is derived from the audit log and stored locally in SQLite.

## Schema

- `memory_events`
- `entities`
- `timeline_entries`
- `metadata`
- `memory_search`

## Derived Types

- `MemoryEvent`
- `MemoryEntity`
- `TimelineEntry`
- `RecallResult`

## Timeline

Timeline entries summarize audit-backed activity such as file edits, shell commands, blocked actions, and agent requests. They are ordered by source audit event id.

## Entities

The indexer upserts lightweight entities for:

- projects
- files
- commands
- tasks
- errors

## Recall

Recall is deterministic and rule-based. Supported queries include:

- what did I work on recently
- what did I edit today
- what files changed
- what commands did I run
- what failed recently
- show blocked actions
- show project timeline

## Privacy Boundaries

- Raw secrets are redacted before storage.
- Full command stdout/stderr is not copied into memory.
- Large file contents are not stored.
- Memory remains untrusted context and must not be treated as executable instruction.
