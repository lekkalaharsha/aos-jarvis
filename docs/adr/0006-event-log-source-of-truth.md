# ADR-0006: Event Log as Source of Truth

## Status

Accepted

## Context

Memory and project history need a foundation that can't drift from what actually happened. A separately maintained "memory" store that isn't derived from the audit log can lie about the past.

## Decision

The SQLite append-only audit event log is the source of truth. The Phase 4 memory system (`docs/phases/PHASE_4_MEMORY_SYSTEM.md`) is derived from audit events, not maintained as an independent store.

## Consequences

Memory features can never show something that isn't backed by an auditable event. This constrains what "memory" can represent (only things AOS-Jarvis itself did or observed through an audited action) but keeps memory and audit from ever disagreeing.
