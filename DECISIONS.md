# Decisions

## DEC-001: CLI first

Reason: CLI is easier to test, secure, and audit.

## DEC-002: Audit log before tools

Reason: Every future action must be logged.

## DEC-003: Single-agent before multi-agent

Reason: Multi-agent too early creates debugging chaos.

## DEC-004: Linux first

Reason: Cross-platform security doubles complexity.

## DEC-005: Event log as source of truth

Reason: Memory and project history should be derived from audited events.

## Program Direction Decisions

These restate/extend DEC-001..005 in the numbering used by the wider project-tracking docs (`PROJECT_SCOPE.md`, ADRs). Kept alongside the DEC-00X series rather than replacing it — both refer to the same decisions.

- **D001** — AOS-Jarvis is an Agentic System Control Plane, not a custom OS kernel. See `docs/adr/0007-no-custom-kernel-or-distro-v1.md`.
- **D002** — v0.1 is CLI-first and Linux-first. See `docs/adr/0004-cli-first-linux-first.md`.
- **D003** — Audit and permissions are foundational. See `docs/adr/0002-audit-first-design.md`, `docs/adr/0003-capability-security.md`.
- **D004** — Models are providers, not executors. See `docs/adr/0005-models-are-not-executors.md`, `MODEL_PROVIDER.md`.
- **D005** — SQLite append-only event log is the source of truth. See `docs/adr/0006-event-log-source-of-truth.md`.
- **D006** — No voice, dashboard, browser, screen control, or multi-agent in Phase 0. See `PHASE_CONTRACT.md`.
- **D007** — Existing tools should be reused where possible (Ollama, bubblewrap, ripgrep/fd, SQLite/FTS5, Playwright, faster-whisper, Piper, Streamlit/Tauri) rather than rebuilding them. See `ARCHITECTURE.md`.
