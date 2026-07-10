# Phase 5 — Git and Project Assistant

## Goal

Add read-mostly git awareness (status, diff, log summary) and commit message drafting, built on the Phase 3 agent loop.

## Why this phase matters

Git is the first "real developer workflow" surface AOS-Jarvis touches. It's read-heavy and low-risk, making it a good proving ground before Phase 6 broadens the model surface.

## In scope

- `aos git status`, `aos git diff`, `aos git summarize`.
- Branch detector, project detector.
- Commit message drafting via `aos ask "draft a commit message"`.

## Out of scope

`git push`/`git commit` execution without explicit human action (any write git action is at minimum T2 per `SECURITY.md` and stays that way even after this phase), model routing (Phase 6), voice, dashboard, browser, screen understanding.

## Deliverables

A thin `aos/tools/git.py` wrapping read-only git plumbing through the Phase 2 shell runner's allowlist, not raw subprocess calls.

## Commands expected after this phase

```bash
aos git status
aos git diff
aos git summarize
aos ask "draft a commit message"
```

## Security requirements

All git commands route through the Phase 2 shell runner's allowlist/audit path, not a separate code path. Write operations (`commit`, `push`) are out of scope for this phase entirely.

## Test requirements

Status/diff parsing tests against fixture repos, commit-message-draft tests with the model mocked.

## Acceptance criteria

`aos git status`/`diff`/`summarize` match real `git` output for a fixture repo; commit message drafts are reviewable text, never auto-applied.

## Handoff requirements

Same as prior phases.

## Do not proceed until

Phase 4 is frozen and `PHASE_CONTRACT.md` names Phase 5 as active.
