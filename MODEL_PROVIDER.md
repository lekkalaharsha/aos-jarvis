# Model Provider Rules

Models are providers, not executors. This rule is load-bearing for the whole project's trust story — see `ARCHITECTURE.md`.

## Bad

```text
Claude CLI directly edits files
Codex directly runs shell
Ollama directly executes tools
```

## Good

```text
Model returns a structured JSON proposal
AOS-Jarvis validates it
AOS-Jarvis checks permission
AOS-Jarvis executes through the safe tool runtime
AOS-Jarvis audits the action
```

A model only ever returns: answer text, a structured intent, a structured plan, or a tool-call proposal. It never touches files, shell, git, browser, or the OS directly.

## Provider Roles (future phases)

- **Ollama / Hermes** — local/private reasoning and structured JSON output.
- **Claude** — architecture, planning, documentation.
- **Codex / OpenAI** — coding, tests, debugging.
- **Grok / Groq** — fast alternate reasoning.
- **Gemini** — document/vision, later.

## Phase 0 Status

No model provider is wired up yet. `aos/models/base.py` is an explicit Phase 6 placeholder. Model routing, provider adapters, and any real LLM calls are Phase 6 work (see `docs/phases/PHASE_6_MODEL_ROUTER.md`).
