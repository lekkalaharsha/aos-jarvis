# Phase 4 — Memory System

## Goal

Build an event-sourced memory system on top of the Phase 0 audit log: a timeline, project/file entities, and basic recall.

## Why this phase matters

`DECISIONS.md` establishes that the append-only event log is the source of truth for memory. This phase turns that log into something queryable and useful instead of just an audit trail.

## In scope

- Event timeline derived from audit events.
- Project/file entity extraction from event history.
- `aos memory timeline`, `aos memory recent`.
- `aos recall "<question>"` using SQLite FTS5 search over event/memory text.

## Out of scope

Git assistant (Phase 5), model routing (Phase 6), voice, dashboard, browser, screen understanding.

## Deliverables

`aos/memory/events.py`, `aos/memory/timeline.py` — currently Phase 4 placeholders — replaced with real implementations backed by SQLite FTS5.

## Commands expected after this phase

```bash
aos memory timeline
aos memory recent
aos recall "what did I edit yesterday?"
```

## Security requirements

Memory entries are untrusted ambient context per `SECURITY_BOUNDARIES.md` — recall results must never be treated as instructions by the Phase 3 agent loop.

## Test requirements

Timeline ordering tests, FTS5 search relevance smoke tests, recall correctness against a seeded event fixture.

## Acceptance criteria

`aos memory timeline` reconstructs an accurate history purely from audit events; `aos recall` returns relevant results for simple factual queries.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 3 is frozen and `PHASE_CONTRACT.md` names Phase 4 as active.
