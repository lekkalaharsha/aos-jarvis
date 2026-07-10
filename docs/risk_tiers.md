# Risk Tiers

Phase 1 uses the existing risk model. File tools and snapshot operations assign risk tiers via a single source of truth, `classify_file_action()` in `aos/safety/risk.py`, rather than hardcoding tiers per call site.

Phase 2 extends the same `RiskTier` model to shell commands through `classify_command_risk()` in `aos/safety/risk.py`.

## T0

Safe read-only actions. These are allowed after permission checks.

Examples:

- List an approved directory.
- Read a normal approved project text file.
- Search approved project files.
- Run `pwd`, `ls`, `git status`, or version checks such as `python --version`.

## T1

Reversible writes. These require an approved path, diff preview where applicable, audit logging, and explicit CLI approval. Existing files are snapshotted before modification.

Examples:

- Create a file.
- Write a file.
- Edit a file.
- Append-style writes when added later.
- Run project tests such as `pytest`, `python -m pytest`, `npm test`, `git diff`, or `git log`.

## T2

Destructive or high-risk actions. These require strong approval and audit logging. The CLI enforces a two-step confirmation for T2 actions, distinct from the single confirmation used for T1: first a "This is a T2 high-risk action. Continue?" prompt, then a typed `RESTORE` confirmation. `--yes` skips both prompts for tests and scripted local checks.

Examples:

- Restore a snapshot.
- Delete a file if implemented later.
- Overwrite a large file.
- Run commands that execute project code or local builds, such as `python script.py`, `node script.js`, `make build`, or `npm run build`.

## T3

Blocked by default.

Examples:

- System paths.
- Secret files.
- Private keys.
- Credentials.
- Browser cookies.
- Root or system folders.
- `sudo`, root escalation, destructive commands, pipe-to-shell patterns, unsafe cwd, and unknown commands.

## Snapshots and Audit

Snapshots are stored under the AOS-Jarvis data directory, outside the project folder. Snapshot metadata records the snapshot id, original path, snapshot path, timestamp, SHA-256 before the change, size, reason, and creating action.

Restore is T2. Before restore overwrites an existing file, the current file is snapshotted. Snapshot creation and restore write audit events. File tools also audit `fs.list`, `fs.read`, `fs.search`, `fs.write.preview`, `fs.write.apply`, `fs.edit.preview`, `fs.edit.apply`, and `fs.blocked`.
