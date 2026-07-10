# ADR-0005: Models Are Providers, Not Executors

## Status

Accepted

## Context

If a model (Claude, Codex, Ollama, etc.) can directly edit files, run shell commands, or call tools, then every safety property built into the permission engine and audit log can be bypassed simply by asking the model to do the risky thing directly, outside AOS-Jarvis's own execution path.

## Decision

Models only ever return answer text, a structured intent, a structured plan, or a tool-call proposal. AOS-Jarvis validates the proposal, checks permission, executes through its own tool runtime, and audits the result. See `MODEL_PROVIDER.md` for the bad/good pattern.

## Consequences

Every model integration (Phase 3 onward) is an adapter that produces structured output, never a direct executor. This adds a translation layer (structured output boundary + validator) but means no model provider, however capable, can act outside the permission/audit system.
