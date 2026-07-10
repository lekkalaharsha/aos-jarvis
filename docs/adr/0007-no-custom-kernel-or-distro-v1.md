# ADR-0007: No Custom Kernel or Distro in v1

## Status

Accepted

## Context

"System-control layer above Linux" could be read as an invitation to build a custom kernel, distro, or desktop shell. That would be a multi-year systems project orthogonal to the actual goal: a trustworthy, auditable assistant that uses the existing OS's primitives.

## Decision

AOS-Jarvis v0.1 runs as ordinary user-space software (a CLI, later a dashboard/voice layer) on top of a standard Linux install. It is explicitly not a custom kernel, not a Linux distro, not a desktop shell, and not a full OS replacement (`PROJECT_SCOPE.md`).

## Consequences

All "OS control" features (Phase 9 workspace/app control, sandboxing) are built against existing OS APIs and tools (`bubblewrap`, standard process/file APIs), not a custom low-level layer. Anyone proposing kernel-level or distro-level work must get the human owner to amend this ADR first.
