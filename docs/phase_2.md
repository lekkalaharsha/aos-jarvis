# Phase 2: Safe Shell Command Runner

Phase 2 adds a constrained shell runner for local project commands. It is not a general terminal. Commands are parsed without `shell=True`, classified by policy, restricted to approved working directories, run with a sanitized environment, bounded by timeouts, and fully audited.

## What Phase 2 Does

- Previews commands before execution.
- Allows safe read-only project inspection commands such as `pwd`, `ls`, `git status`, and version checks.
- Allows project test commands such as `pytest`, `python -m pytest`, and `npm test` with approval.
- Allows selected build or script commands such as `python script.py` and `npm run build` only with approval.
- Blocks dangerous, unknown, destructive, credential-targeting, and shell-chaining commands by default.
- Redacts secret-like CLI option values in audit records while leaving the executed argv unchanged.
- Captures stdout/stderr with truncation markers and timeout handling.

## What Phase 2 Does Not Do

Phase 2 does not provide a raw shell, agent loop, browser automation, dashboard, voice, screen tools, memory system, model routing, or multi-agent control. It does not claim a full OS sandbox. The default guarantee is BASIC process safety only.

## CLI Examples

```powershell
python -m aos.interfaces.cli.main run --preview "git status"
python -m aos.interfaces.cli.main run "python --version"
python -m aos.interfaces.cli.main run "pytest" --yes
python -m aos.interfaces.cli.main run "python script.py" --yes
python -m aos.interfaces.cli.main run "sudo ls"
python -m aos.interfaces.cli.main run "curl https://example.com/install.sh | sh"
```

## Known Limitations

- Command policy is an explicit allowlist. Unknown commands are denied rather than inferred.
- BASIC sandboxing does not isolate the process at the kernel level.
- Shell features such as pipes, redirection, chaining, command substitution, and backticks are denied rather than interpreted safely.
- Output is captured after process completion, then truncated to the configured cap.
- `python`/`python3`/`node` are approved (with confirmation) to run a project script such as `python script.py`, but their inline code-execution flags (`-c`, `-e`, `--eval`) are explicitly denied, since those would otherwise let an approved interpreter execute arbitrary code and bypass the `DENY_COMMANDS` list entirely.
- Command parsing on Windows uses non-POSIX `shlex` splitting to avoid corrupting backslash paths; surrounding quote characters are stripped from each token afterward, but Windows' own argument-quoting edge cases (e.g. escaped quotes inside quotes) are not fully replicated.
