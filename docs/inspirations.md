# Inspirations & Prior Art

Direction from the Human Owner / architect (2026-07-10). We take **inspiration, architecture patterns, and selected tools** from these projects — never their whole product. AOS-Jarvis is the **control plane** that safely manages all agents/tools.

## Core rule

```text
Models are providers, not executors.
Agents are workers, not owners.
AOS owns permission, execution, audit, snapshots, rollback, and memory.
```

Claude Code, Codex, OpenCode, Hermes-like agents, or OpenClaw-like assistants can plug in later, but they must go through AOS.

## What AOS builds itself (never outsourced — this is the product)

`aos/audit`, `aos/permissions`, `aos/safety`, `aos/fs_tools`, `aos/shell_runner`, `aos/snapshots`, `aos/memory`, `aos/model_router`.

## What to take from each project

| Project | What to take | Where it fits |
| --- | --- | --- |
| **Hermes Agent** | Long-term memory, preference learning, skill creation from repeated actions, multi-session continuity | Phase 4 Memory, Phase 12 automation |
| **OpenClaw** | Jarvis-style UX, voice/chat channels, multi-device flow, dashboard/canvas interaction | Phase 7 Dashboard, Phase 8 Voice, Phase 9 Workspace |
| **AgentScope Runtime** | Tool sandboxing, runtime observability, agent-as-service, clear agent/tool boundary | Phase 2 Shell, Phase 3 Agent loop |
| **OpenShell** | Real OS-level sandboxing: filesystem/process/network restrictions (Landlock, seccomp) | Phase 2 command runner hardening |
| **permit0** | Risk scoring, deterministic pre-execution authorization, allow / human-review / deny routing | Phase 1 Permissions, Phase 2 command policy |
| **OpenHands** | Isolated coding-agent workspace, task loop, containerized dev environment | Phase 3–5 coding assistant |
| **Open Interpreter** | Natural-language local execution UX (plan → show → approve → run) | Phase 3 CLI assistant UX |
| **Aider** | Git-aware editing, clean diffs, commit-message drafting, repo-map context | Phase 5 Git assistant |
| **Cline / Roo / Kilo** | Approval-gated workflows, visible diffs before approval, human-in-loop UX | Phase 3–5 approvals |
| **LangGraph** | Stateful workflows, resumable tasks, checkpoints (pattern only — the dependency is banned) | Phase 3 loop, Phase 12 workflows |
| **Claude Code / Codex** | Terminal coding-agent UX, tool permission model, sandbox/approval split | Phase 3–5 UX reference |
| **Cursor / Windsurf / Antigravity** | AI IDE experience, project-context UX | Later integrations |

## Key patterns

### Policy pipeline (from permit0) — the strongest idea to copy

```text
Model proposes action → AOS normalizes → policy engine scores risk →
  T0 allow | T1 preview + approve | T2 strong approve | T3 deny → only then execute
```

Examples: read README → T0; edit README → T1 diff + approve; delete file → T2; read ~/.ssh → T3 deny; `curl | sh` → T3 deny.

### Approval UX (from Cline/Roo)

Show the actual diff, risk tier, and snapshot status in the approval prompt — never just a description:

```text
I want to edit docs/phase_2.md.
Risk: T1   Snapshot: created
Diff: [- old / + new]
Approve? yes/no
```

### Real sandboxing (from OpenShell)

Don't rely only on Python checks. Escalation path for the shell runner: bubblewrap → firejail → seccomp/Landlock → container sandbox; network off by default; read-only filesystem where possible. Minimum bar (already Phase 2): allowed cwd only, timeout, no sudo, no shell control operators, no dangerous paths, audit every command, approval before risky commands.

### Learned skills (from Hermes) — suggested, never auto-created

AOS notices repeated action sequences (e.g. pytest → fix → diff → commit) and *proposes* a named workflow. Skills are approved by the user, never self-created with high permissions.

## Approved tool/library stack

- **Core:** Python, Typer, Rich, SQLite, Pydantic, pytest, ruff, mypy/pyright (SQLModel/SQLAlchemy if the raw-SQLite layer outgrows itself)
- **Sandbox:** bubblewrap, firejail, seccomp/Landlock (later), Docker/Podman for isolated agent workspaces
- **File/git:** shell git or GitPython, difflib/unidiff, pathspec, watchdog, ripgrep
- **Models (Phase 6+):** LiteLLM (router), Ollama (local), OpenAI/Anthropic APIs, MCP as tool/plugin protocol
- **Voice/dashboard (Phase 7+):** faster-whisper, Piper/Kokoro, FastAPI, Streamlit or Next.js, WebSocket

Note: LangChain/AutoGen/CrewAI remain banned (CODING_RULES.md). LangGraph is pattern-inspiration only unless the Human Owner amends the rules.

## Do NOT copy too early

Always-on assistant, full desktop control, browser control, screen control, self-modifying skills, multi-agent swarm, voice-first interface, cloud-first memory, root/system control. These come only after the safety core is proven.

## Study order

1. permit0 (permission/risk engine) → 2. OpenShell (sandboxing) → 3. Hermes Agent (memory/skills) → 4. OpenClaw (Jarvis UX) → 5. Aider (git-aware editing) → 6. Cline/Roo (approval workflow)
