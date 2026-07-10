# Tool Capabilities

Every future tool must implement:

- `describe()`
- `dry_run(args)`
- `execute(args)`
- `required_capabilities()`
- `risk_tier()`

Phase 4 adds a local memory system derived from the audit log. Browser, voice, dashboard, model routing, and autonomous tools remain inactive.

## Risk Tiers

T0 - auto allowed, read-only low risk

T1 - approval required, reversible

T2 - strong approval required, hard to reverse

T3 - denied

## Examples

### T0

- read README inside approved project
- show git status through the safe runner
- recall recent memory from the derived store

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
- `memory.read`

All active capabilities require their existing path, command, registry, and audit checks. The memory system is derived from audit events and is not a privileged bypass around Phase 1, Phase 2, or Phase 3.

## Phase 4 Memory Policy

- Memory is local-only and rebuildable from the audit log.
- Memory queries are read-only T0 operations.
- Recall is rule-based and grounded only in stored derived memory.
- The agent may use only read-only memory tools for memory recall.

