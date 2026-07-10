# Phase 3: Minimal Agent Loop

Phase 3 adds a deterministic agent loop that can handle a small set of natural-language requests without bypassing the existing safety systems from Phase 1 and Phase 2.

## What Phase 3 Does

- Classifies a limited set of intents deterministically.
- Builds structured plans made of validated tool calls.
- Uses only the existing safe file and safe shell tools.
- Supports dry-run planning without execution.
- Preserves approval requirements for writes and test execution.
- Writes agent-level audit events around the request lifecycle.

## What Phase 3 Does Not Do

Phase 3 does not add a real cloud LLM, memory system, model router, browser automation, dashboard, voice, screen tools, or multi-agent workflows. It is not a general-purpose autonomous agent.

## Supported Intents

- `PROJECT_SUMMARY`
- `FIND_TODOS`
- `RUN_TESTS`
- `GIT_STATUS`
- `READ_FILE`
- `CREATE_NOTES`
- `UNKNOWN`

## Dry Run

`aos ask --dry-run ...` shows the detected intent and proposed tool calls, validates them against the registry, and does not invoke lower-level tool preview or apply functions.

## Approval Flow

- Read-only plans can execute directly after validation.
- `RUN_TESTS` requires approval for `run.apply`.
- `CREATE_NOTES` requires approval for `fs.write`.
- Denied commands and denied paths remain blocked even when `--yes` is supplied.

## Known Limitations

- No real LLM is required or used by default.
- The agent only supports a small fixed set of intents.
- Unknown requests are rejected safely.
- No memory system exists yet.
- No model router exists yet.
- No voice, dashboard, browser, or screen support exists yet.

## CLI Examples

```powershell
python -m aos.interfaces.cli.main ask "summarize this project"
python -m aos.interfaces.cli.main ask "find TODOs"
python -m aos.interfaces.cli.main ask "run tests" --dry-run
python -m aos.interfaces.cli.main ask "run tests" --yes
python -m aos.interfaces.cli.main ask "show git status"
python -m aos.interfaces.cli.main ask "read README.md"
python -m aos.interfaces.cli.main ask "create notes.md" --yes
```
