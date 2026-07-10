# AOS-Jarvis

AOS-Jarvis is a local-first, secure AI system-control layer intended to run above Linux. Its long-term purpose is to give a personal assistant permissioned access to files, projects, shell commands, git, memory, voice, dashboards, browser tools, and screen tools.

Current status: Phase 0 only. This repository is not yet a full Jarvis assistant.

## Phase 0 Scope

Phase 0 is the trusted foundation. It allows:

- Repository coordination documents
- Phase contract and task board
- CLI skeleton
- Config directory creation checks
- SQLite audit log
- Audit hash-chain verification
- Basic risk tier and capability model
- Tool interface contract
- Evaluation fixture framework

Phase 0 forbids:

- Voice
- Dashboard
- Browser automation
- Screen control or screen understanding
- Shell execution
- Real file editing tools
- Model router
- Multi-agent planner or agent loop
- Linux distro or desktop shell work
- Autonomous system control

## Install

```bash
pip install -e .
```

## Commands

```bash
aos --help
aos version
aos doctor
aos audit list
aos audit verify
aos eval run
```

## Coding Rules

All agents and contributors must follow `CODING_RULES.md`.

Phase 0 code must stay small, safe, testable, and limited to the foundation layer.

## Safety Principle

Every future action must be capability-gated, previewed before execution, sandboxed when needed, logged in an audit log, rollback-aware where technically possible, and blocked if dangerous.

Phase 0 only establishes the coordination and safety foundation. It does not execute user commands, edit real files through tools, browse the web, control the screen, or run an AI agent loop.
