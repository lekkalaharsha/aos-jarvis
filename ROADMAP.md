# Roadmap

Full phase plan for AOS-Jarvis. Only the active phase (see `PHASE_CONTRACT.md`) may be implemented; everything else is context for planning, not permission to build ahead.

- **Phase 0 — Foundation + Audit Core**: repo skeleton, CLI, config system, SQLite audit log, hash-chain verification, capability model, risk tiers, tool interface contract, eval fixtures, docs/ADRs, shared memory files.
- **Phase 1 — Permission Engine + Safe File Tools**: directory allowlist, dangerous path/secret denylist, safe file list/read/search/write/edit, snapshots, diff preview, snapshot restore.
- **Phase 2 — Safe Shell Runner**: command allowlist/denylist, working-directory scope, timeout, dry-run preview, approval prompt, sandboxing, per-command audit.
- **Phase 3 — Minimal AI Agent Loop**: one model provider, structured JSON output, `aos ask`, intent parser, tool router, validator, observe loop.
- **Phase 4 — Memory System**: event timeline, project history, file/project entities, `aos memory`/`aos recall`, SQLite FTS5 search.
- **Phase 5 — Git and Project Assistant**: `aos git status/diff/summarize`, branch/project detection, commit message drafting.
- **Phase 6 — Model Router**: `ModelProvider` interface, Ollama/Hermes/Claude/OpenAI/Grok adapters, task-based routing, secret redaction, cloud approval gate.
- **Phase 7 — Dashboard**: read-only viewers for audit, permissions, snapshots, timeline, memory, model usage.
- **Phase 8 — Voice Interface**: push-to-talk, STT, TTS, visible confirmation for risky actions.
- **Phase 9 — Workspace and App Control**: open project/editor/terminal, restore workspace, start dev server with approval.
- **Phase 10 — Browser Tools**: open URL, controlled search, page extraction, research notes, prompt-injection boundary.
- **Phase 11 — Screen Understanding**: screenshot capture, OCR, terminal error detection, screen summary, suggested fix with approval.
- **Phase 12 — Advanced Workflows**: scheduled routines, project routines, workflow templates, plugin system.

No agent may start a phase before the current one is frozen and `PHASE_CONTRACT.md` is updated by the human owner.
