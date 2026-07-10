# ADR-0002: Audit-First Design

## Status

Accepted

## Context

Future tools will need durable records for review, verification, and incident analysis. Retrofitting an audit trail onto tools built without one tends to produce gaps exactly where they matter most (the exact action that went wrong).

## Decision

Implement the audit log and its hash-chain verification (`AUDIT_LOG.md`) before implementing any real tool. Every tool built from Phase 1 onward audits every `execute()` call, success or failure.

## Consequences

Phase 0 has no user-facing tools but does have a fully tested audit system. Every later phase inherits an audit path instead of inventing its own, keeping the schema and verification logic in one place.
