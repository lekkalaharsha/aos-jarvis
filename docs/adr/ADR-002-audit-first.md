# ADR-002: Audit First

## Status

Accepted

## Context

Future tools will need durable records for review, verification, and incident analysis.

## Decision

Implement audit storage before implementing real tools.

## Consequences

All later execution pathways can be designed around auditability instead of adding logs after behavior already exists.
