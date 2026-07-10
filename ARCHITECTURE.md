# Architecture

## Data Flow (target architecture, most layers not active until later phases)

```
User
 -> AOS-Jarvis Interface (CLI first; dashboard, voice later)
 -> Intent Layer
 -> Model Router (Ollama/Hermes, Claude, Codex/OpenAI, Grok/Groq, others later)
 -> Structured Output Boundary
 -> Validator
 -> Permission Engine
 -> Tool Runtime
 -> Audit + Rollback
 -> Memory / Event Store
 -> Linux OS / Files / Shell / Git
```

## Core Rule

Models never directly touch files, shell, git, browser, or the OS. A model only returns answer text, a structured intent, a structured plan, or a tool-call proposal. AOS-Jarvis validates and executes through its own safe tool runtime.

## Phase 0 Reality

In Phase 0 only the top and bottom of this diagram exist in trivial form: a CLI (`aos`), an audit log, a risk/capability model, and a tool interface contract with no real tools wired up. There is no intent layer, no model router, and no tool runtime execution yet — those are Phase 3 and Phase 6. See `PHASE_CONTRACT.md` for what is actually active.

## Reuse Strategy

AOS-Jarvis builds the trust layer itself (CLI, tool interface, capability/permission model, risk tiers, approval gates, diff preview, snapshots, audit hash chain, validator). It reuses existing tools for everything else when those phases arrive: Ollama/Hermes for local models, Claude/Codex for external coding and review, bubblewrap for sandboxing, ripgrep/fd for search, SQLite/FTS5 for audit and memory, Playwright/faster-whisper/Piper/Streamlit-or-Tauri for browser/voice/dashboard.
