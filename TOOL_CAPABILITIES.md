# Tool Capabilities

Every future tool must implement:

- `describe()`
- `dry_run(args)`
- `execute(args)`
- `required_capabilities()`
- `risk_tier()`

Phase 1 activates only local safe file tools. Shell, browser, voice, dashboard, model, and autonomous tools remain inactive.

## Risk Tiers

T0 - auto allowed, read-only low risk

T1 - approval required, reversible

T2 - strong approval required, hard to reverse

T3 - denied

## Examples

### T0

- read README inside approved project
- list audit events

### T1

- edit README with snapshot
- create notes file

### T2

- install package
- git push
- network call

### T3

- sudo
- rm -rf /
- access private keys
- modify /etc
- read browser cookies

## Phase 1 Active Capabilities

- `fs.list`
- `fs.read`
- `fs.search`
- `fs.write`
- `fs.edit`
- `snapshot.restore`

All active file capabilities require approved roots and deny secret or dangerous paths.
