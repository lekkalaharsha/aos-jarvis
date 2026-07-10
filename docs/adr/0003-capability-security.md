# ADR-0003: Capability-Based Security

## Status

Accepted

## Context

A general permission system that grants broad access by default is the fastest way to make an "auditable" system meaningless — audit tells you what happened, but only a capability model tells you what was allowed to happen.

## Decision

Every tool declares `required_capabilities()`, every capability maps to a risk tier (`PERMISSION_MODEL.md`), and every risk tier maps to a decision (`ALLOW`/`REQUIRE_APPROVAL`/`REQUIRE_STRONG_APPROVAL`/`DENY`) via `decision_for_risk()`. Deny-by-default: an unknown or unmapped risk tier is treated as `T3`.

## Consequences

Adding a new tool means declaring its capabilities and risk tier up front, not writing ad hoc permission checks. This is more upfront design work per tool but keeps the security model in exactly one place (`aos/safety/risk.py`, `aos/safety/permissions.py`).
