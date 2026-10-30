# Git and Project Assistant

The Phase 5 git/project assistant is a thin read-only layer over the Phase 2 safe shell runner.

## Safety Model

- All git commands go through the safe shell runner.
- No direct `subprocess` calls are allowed in `aos/project`.
- No `shell=True`.
- No arbitrary git command passthrough.
- Command policy still blocks denied git operations even if the user passes `--yes`.
- Audit records summaries only; full diffs are not copied into audit payloads.

## Implemented Tools

- `git.status`
- `git.diff_stat`
- `git.log`
- `git.branch`
- `project.summarize_changes`
- `project.draft_commit`

## Parsing

The assistant parses:

- short status output into changed files and staged/unstaged/untracked counts
- diff stat output into file counts, insertions, and deletions
- log oneline output into commit hash/title pairs
- branch output into the current branch name

Parsing is deterministic and tolerant of unexpected output.

## Project Summary

`aos git summarize` and the matching agent intent return:

- current branch
- clean/dirty state
- changed files
- diff stat summary
- recent commits
- a short deterministic human summary

## Commit Drafting

`aos git draft-commit` produces a draft message only. It does not:

- stage files
- run `git commit`
- modify files
- modify repository state

## Agent Integration

The agent supports:

- `GIT_STATUS`
- `PROJECT_CHANGES`
- `DRAFT_COMMIT`
- `CURRENT_BRANCH`
- `RECENT_COMMITS`

These intents use only allowlisted git/project tools. User text never becomes a raw git command.

## Audit Events

- `git.status`
- `git.diff`
- `git.log`
- `git.branch`
- `project.summary`
- `project.commit_draft`

Each event records concise metadata such as cwd, branch, changed-file count, success/blocked state, and a short result summary.
