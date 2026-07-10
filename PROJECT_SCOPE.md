# Project Scope

## What AOS-Jarvis Is

AOS-Jarvis is a local-first, secure Agentic System Control Plane. Long-term it should feel like a Jarvis-like personal AI assistant. Short-term, v0.1 is a CLI-first, Linux-first, auditable filesystem and command assistant.

v0.1 is:

- CLI-first
- Linux-first
- Python-first
- single-agent
- audit-first
- permission-first
- safe file tools (Phase 1)
- safe shell runner (Phase 2)
- one model provider first (Phase 3+)

## What AOS-Jarvis Is Not

v0.1 is not:

- a custom kernel
- a Linux distro
- a desktop shell
- a Windows product
- a multi-agent swarm
- a voice-first assistant
- a browser automation system
- a screen-control agent
- an unrestricted shell wrapper

## Non-Negotiable Safety Properties

Every risky action must be permission-gated, previewed, audited, rollback-aware where possible, and executed only through safe AOS-Jarvis tools. See `SECURITY.md` for risk tiers and blocked paths/commands.

## Phase Discipline

Only the active phase (declared in `PHASE_CONTRACT.md`) may be implemented. See `ROADMAP.md` for the full plan and `docs/phases/` for per-phase detail. No agent may implement ahead of the active phase without the human owner updating `PHASE_CONTRACT.md`.
