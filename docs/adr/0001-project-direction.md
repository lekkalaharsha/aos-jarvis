# ADR-0001: Project Direction

## Status

Accepted

## Context

AOS-Jarvis needs a clear identity before any code is written, or every later decision (architecture, security, phase order) has no anchor to check itself against.

## Decision

AOS-Jarvis is a local-first, secure Agentic System Control Plane. Long-term it should feel like a Jarvis-like personal assistant; short-term the MVP is a CLI-first, Linux-first, auditable filesystem and command assistant. See `PROJECT_SCOPE.md` for the full is/is-not list.

## Consequences

Every phase and every tool is evaluated against this identity. Features that don't serve "auditable, permissioned, local-first system control" (a general chat UI, an unrelated SaaS integration, etc.) are out of scope regardless of how easy they'd be to add.
