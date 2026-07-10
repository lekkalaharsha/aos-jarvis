# Command Runner

Phase 2 introduces a policy-gated shell runner with preview-first execution.

## Policy Categories

- `ALLOW_READONLY`
  Safe inspection commands such as `pwd`, `ls`, `dir`, `git status`, `git diff`, `git log`, `python --version`, `node --version`, `npm --version`, and `pytest --version`.
- `ALLOW_PROJECT_TEST`
  Project-local test commands such as `pytest`, `python -m pytest`, `npm test`, `npm run test`, `cargo test`, and `go test ./...`.
- `ALLOW_WITH_APPROVAL`
  Commands that may execute project code or write local cache/build artifacts, such as `python script.py`, `node script.js`, `npm run build`, `make test`, and `make build`.
- `DENY`
  Dangerous commands such as `sudo`, `su`, `cmd`, `bash`, `sh`, `rm`, `curl | sh`, `wget | sh`, remote shell tools, commands targeting secrets or dangerous paths, and inline code-execution flags (`python -c`, `node -e`/`--eval`) that would otherwise let an approved interpreter run arbitrary code instead of a project script.
- `UNKNOWN`
  Any command not explicitly allowed. Unknown commands are blocked by default.

## Working Directory Restriction

Commands only run when the requested `cwd` resolves inside an approved root. Dangerous locations and secret-bearing paths are blocked using the same path safety layer used by Phase 1 file tools.

## Environment Sanitization

Only a small safe environment is preserved by default, including `PATH`, home/temp variables, active virtualenv context, and Python/runtime basics. Secret-like environment variables are stripped, including API keys, tokens, password variables, and secret variables.

## Timeout and Output Capture

- Default timeout: 30 seconds
- Output cap: 200 KB each for stdout and stderr
- Timed-out commands are killed and audited as `run.timeout`
- Oversized output is truncated and audited as `run.output_truncated`

## Audit Events

The runner emits:

- `run.preview`
- `run.apply`
- `run.blocked`
- `run.timeout`
- `run.output_truncated`

Each event records a redacted command string, redacted argv, working directory, risk tier, policy category, approval state, and execution outcome metadata. Secret-like CLI option values such as `--token=...`, `--api-key=...`, and `--password ...` are replaced with `[REDACTED]` in the audited copy only.

## BASIC Sandbox Meaning

Phase 2 defaults to `BASIC` sandbox mode. That means:

- `shell=False`
- command policy enforcement
- approved-root cwd restriction
- sanitized environment
- timeout enforcement
- dangerous command blocking

It does not mean containerization, namespace isolation, seccomp, or a guaranteed OS-level jail. Optional detection for `bubblewrap` and `firejail` exists for future hardening, but tests and current behavior do not depend on them.
