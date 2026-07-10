# Tool Capabilities

Every future tool must implement:

- `describe()`
- `dry_run(args)`
- `execute(args)`
- `required_capabilities()`
- `risk_tier()`

Phase 3 activates the deterministic minimal agent loop on top of the existing safe file tools and policy-gated shell runner. Browser, voice, dashboard, model routing, and autonomous tools remain inactive.

## Risk Tiers

T0 - auto allowed, read-only low risk

T1 - approval required, reversible

T2 - strong approval required, hard to reverse

T3 - denied

## Examples

### T0

- read README inside approved project
- list audit events
- show git status through the safe runner

### T1

- edit README with snapshot
- create notes file
- run pytest through the safe runner

### T2

- restore snapshot
- run approval-gated project scripts

### T3

- sudo
- rm -rf /
- access private keys
- modify /etc
- read browser cookies

## Active Capabilities

- `fs.list`
- `fs.read`
- `fs.search`
- `fs.write`
- `fs.edit`
- `snapshot.restore`
- `run.command`
- `agent.ask`

All active capabilities require existing path or command policy validation. The agent is not a privileged path around those checks; it can only request structured calls into them.

## Phase 3 Agent Policy

- Supported intents are limited and deterministic.
- Unknown requests are rejected safely.
- The agent does not call `open()`, `subprocess`, or `shell=True`.
- Tool calls are validated against an allowlist registry before execution.
- Approval-gated tool calls remain approval-gated when invoked from the agent.

