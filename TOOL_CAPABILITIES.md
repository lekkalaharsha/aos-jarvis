# Tool Capabilities

Every future tool must implement:

- `describe()`
- `dry_run(args)`
- `execute(args)`
- `required_capabilities()`
- `risk_tier()`

Phase 6 adds safe configurable model support. Phase 7 adds the read-only local dashboard (`aos dashboard`). Browser, voice, screen tools, multi-agent systems, embeddings, and autonomous coding remain inactive.

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
- show git branch, git log, and git diff stat through the safe runner
- draft a commit message without modifying the repo

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
- `git.status`
- `git.diff`
- `git.log`
- `git.branch`
- `project.summary`
- `project.commit_draft`
- `model.list`
- `model.show`
- `model.doctor`
- `model.test`
- `model.config`
- `model.ask`

## Phase 9 Workspace Capabilities (Active)

- `workspace.open` — T1, open approved project folder
- `workspace.editor` — T1, launch VS Code in approved project
- `workspace.terminal` — T1, launch terminal in approved project
- `workspace.save` — T1, save workspace state
- `workspace.restore` — T1, restore workspace state
- `workspace.serve` — T2, start a foreground loopback dev server after explicit Human Owner confirmation

All workspace operations require an enrolled project ID, pass PermissionEngine checks, and are audited with project IDs (never paths). Dev-server approval is opaque, expiring, single-use, and consumed durably before process launch. The supported stop method is `ctrl_c_foreground_terminal`; cross-invocation status/stop capabilities are not registered.

All active capabilities require their existing path, command, registry, model-validation, and audit checks. The memory system is derived from audit events and is not a privileged bypass around Phase 1, Phase 2, or Phase 3. The git/project assistant is read-only and must route through the safe shell runner rather than raw subprocess execution. The model layer never executes tools directly.

## Phase 5 Git Policy

- Allowed git reads are limited to status, diff, diff stat, log, and current branch.
- Blocked git operations include push, pull, fetch, clone, commit, reset, clean, checkout, switch, rebase, and merge.
- Commit message drafting is deterministic and does not stage, commit, or modify repository state.
- Agent git/project intents may use only allowlisted git/project tools.

## Phase 6 Model Policy

- Local model support is the default path.
- Cloud model support is disabled by default.
- Cloud API keys must come from environment variables, never config files.
- Cloud prompts pass through secret redaction before provider transport.
- Model output is untrusted and cannot create tools, override risk tiers, or bypass approval gates.
- Structured model tool proposals must validate against the existing tool registry before any tool preview or execution.
