# Phase 9 Critical Remediation Report

Date: 2026-07-11
Status: FIXED + AWAITING INDEPENDENT RE-VERIFICATION

## Scope

This remediation addresses Claude's C-1, C-2, C-3, I-1, and I-2 findings. It does
not independently verify Phase 9 and does not authorize or implement Phase 10.

## Remediation

- Folder opening uses `FolderLaunchRequest` and internally selected `xdg-open` or
  `explorer.exe` argv with the canonical approved path as a separate element.
- Development servers run loopback-only in the foreground. The only stop guidance is
  `Press Ctrl+C in the terminal that started this server.` and audit records
  `ctrl_c_foreground_terminal`.
- Server approval minting requires `human_owner_confirmed=True`, terminal origin, and
  exact operation/project identity/profile/port/expiry binding. Consumption remains
  durable and occurs before launch.
- Cross-invocation server status/stop commands and tool-registry capabilities were
  removed; old operation names fail closed.
- Workspace denial/failure audit retains safe operation, project ID, origin, risk tier,
  outcome, and lifecycle context without paths, argv, environment, PID, or approval
  material.
- PermissionEngine carries and re-raises the original safe path exception object.
- Weaker legacy workspace launch helper functions were removed so the typed adapter is
  the authoritative Phase 9 process boundary.

## Verification

- Remediation plus Phase 1/9 focused suite: 68 passed.
- Phase 2 runner/policy suite: 38 passed.
- Relevant Phase 3 agent/registry suite: 56 passed.
- Phase 8 voice suite: 137 passed.
- Dashboard ASGI Linux compatibility suite: 106 passed.
- Full suite: 560 passed, 0 failed, 0 skipped.
- Compileall: pass.
- Ruff for every remediation-touched production/test file: pass.
- Type checker: not run; no project type-checker configuration is present.
- External workspace/serve help and isolated audit verification: pass.
- Static bypass scan: subprocess construction appears only in the hardened shell
  runner; calls use `shell=False` and internal argv.
- `git diff --check`: pass.

## Independent Re-review

Claude must perform a fresh read-only review, concentrating on exact approval binding
and consumption order, Ctrl+C cleanup failure handling, exactly-one terminal audit
events, canonical path replacement/revocation handling, and absence of process or
approval secrets in output/audit. Phase 9 remains active until that review passes.
