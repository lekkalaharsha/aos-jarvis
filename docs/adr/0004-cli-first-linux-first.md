# ADR-0004: CLI-First, Linux-First

## Status

Accepted

## Context

AOS-Jarvis needs a small, testable control surface before any dashboard, voice, or agent loop exists, and cross-platform support doubles the security surface (path handling, shell semantics, sandboxing primitives) before the core trust model is even proven.

## Decision

Build the CLI first (`aos`), and target Linux first for anything touching the filesystem, shell, or sandboxing. Other interfaces (dashboard, voice) and other platforms are explicitly later-phase or out-of-scope-for-v0.1 concerns (`PROJECT_SCOPE.md`).

## Consequences

Development and testing in this session happened on Windows for convenience, but any Phase 1+ feature that depends on Linux-specific primitives (`bubblewrap` sandboxing, `/etc`/`/proc`/`/sys` path handling) must be verified on real Linux by OpenCode before being considered done — see `RELEASE_CHECKLIST.md`.
