# Phase 5: Git and Project Assistant

Phase 5 adds a safe git and project assistant on top of the existing file, shell, agent, and memory layers.

## What Phase 5 Does

- Adds `aos git status`, `diff`, `log`, `branch`, `summarize`, and `draft-commit`.
- Uses the Phase 2 safe shell runner for all git commands.
- Parses git status, diff stat, log, and branch output into deterministic structured results.
- Adds agent intents for git/project questions such as status, branch, recent commits, change summaries, and commit-message drafting.
- Audits git and project assistant actions without storing full diffs.

## What Phase 5 Does Not Do

Phase 5 does not add network git operations, staging, committing, pushing, pulling, fetching, cloning, rebasing, merging, resetting, cleaning, checkout/switch writes, model routing, voice, dashboard, browser automation, or screen tools.

## Allowed Git Operations

- `git status`
- `git status --short`
- `git diff`
- `git diff --stat`
- `git log`
- `git log --oneline -n <N>`
- `git branch --show-current`

## Blocked Git Operations

- `git push`
- `git pull`
- `git fetch`
- `git clone`
- `git remote`
- `git commit`
- `git reset --hard`
- `git clean`
- `git checkout`
- `git switch`
- `git rebase`
- `git merge`
- `git cherry-pick`
- `git stash`
- `git tag`
- `git submodule update`
- `git config --global`

## CLI Examples

```powershell
python -m aos.interfaces.cli.main git status
python -m aos.interfaces.cli.main git diff --stat
python -m aos.interfaces.cli.main git log --limit 5
python -m aos.interfaces.cli.main git branch
python -m aos.interfaces.cli.main git summarize
python -m aos.interfaces.cli.main git draft-commit
python -m aos.interfaces.cli.main ask "what changed in this repo"
python -m aos.interfaces.cli.main ask "draft a commit message"
```

## Known Limitations

- No git push, pull, fetch, or clone.
- No git commit or staging support.
- No merge, rebase, reset, checkout, or switch operations.
- No semantic LLM git summary.
- Commit messages are deterministic rule-based drafts only.
