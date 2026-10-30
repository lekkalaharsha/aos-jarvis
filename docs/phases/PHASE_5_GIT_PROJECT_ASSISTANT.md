# Phase 5 - Git and Project Assistant

Phase 5 adds safe repository inspection and deterministic project/git summaries.

## Scope

- `aos git status`
- `aos git diff`
- `aos git diff --stat`
- `aos git log`
- `aos git branch`
- `aos git summarize`
- `aos git draft-commit`
- agent support for safe git/project questions

## Safety

- All git commands route through the Phase 2 safe shell runner.
- No direct subprocess access in `aos/project`.
- No arbitrary git command passthrough.
- No network git operations.
- No destructive git operations.
- Commit drafting is read-only.

## Out of Scope

- push/pull/fetch/clone
- commit/stage
- reset/clean/checkout/switch
- merge/rebase/cherry-pick/stash
- model routing
- voice/dashboard/browser/screen features

## Exit Criteria

- Phase 0/1/2/3/4 tests still pass.
- Phase 5 git, parser, project summary, CLI, agent, and safety tests pass.
- Audit verification still passes.
