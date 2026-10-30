# Phase 10 — Codex Independent Final Gate Report

## 2026-07-11 — Follow-up Remediation Gate

Reviewer: Codex  
Scope: Fresh independent final gate of the follow-up remediation recorded in
`docs/PHASE_10_REMEDIATION_REPORT.md` under "2026-07-11 follow-up
remediation after fresh Codex FAIL."  
Verdict: **FAIL**

Phase 10 is not complete. Phase 11 remains blocked.

This review made no browser production-code or test changes. Only
review/coordination records were updated after the verdict.

### Commands Run And Results

- `.venv/bin/python -m compileall -q aos tests`: PASS.
- `.venv/bin/ruff check aos/browser aos/tools/browser.py aos/interfaces/cli/browser_commands.py tests/test_browser_*.py tests/test_agent_tool_registry_browser.py`:
  PASS.
- `git diff --check`: PASS.
- Focused follow-up remediation subset:
  `.venv/bin/python -m pytest -q tests/test_browser_sandbox_egress_supply_chain.py tests/test_browser_quarantine.py tests/test_browser_url_policy.py tests/test_browser_task.py`
  -> **106 passed**.
- Default full suite with isolated data dir:
  `AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-finalgate-full .venv/bin/python -m pytest -q -rs`
  -> **725 passed, 8 skipped**. Skips were 3 sandbox-blocked loopback socket
  tests and 5 default-disabled Layer-2 tests.
- Opt-in Layer-2 gate:
  `AOS_BROWSER_RUN_REAL_TESTS=1 AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-finalgate-layer2 .venv/bin/python -m pytest -q -rs tests/test_browser_integration_real.py`
  -> **2 passed, 5 errors**. The errors are fail-closed gate errors because
  Chromium cannot launch in this environment (`TargetClosedError`).
- Isolated audit verify:
  `AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-finalgate-audit .venv/bin/aos audit verify`
  -> PASS, `valid (0 events)`.

### Blocking Findings

#### C-1 — Required Layer-2 gate still has not passed and the matrix remains incomplete

Evidence:
- `tests/test_browser_integration_real.py:51-60` now correctly fails when
  opted in and Chromium cannot launch, but the required gate still did not
  pass: **2 passed, 5 errors** in this environment.
- The file still contains only seven real-browser tests
  (`tests/test_browser_integration_real.py:93-188`). It still does not cover
  the full required matrix from `docs/PHASE_10_BROWSER_TEST_PLAN.md`: DNS
  rebinding, independent egress blocking with application URL checks bypassed,
  frames/popups, workers/service workers, WebSockets, EventSource, WebRTC,
  prefetch/prerender, timeout/crash cleanup, and orphan-process inspection.

Decision: blocking FAIL. Converting required skips to explicit errors is an
improvement, but the Phase 10 final gate requires the complete Layer-2 matrix
to run and pass in a Chromium-capable, independently contained environment.

#### C-2 — The validating-proxy egress shape is not yet proven as a containment boundary

Evidence:
- `aos/browser/egress.py:86-106` verifies only that direct canary egress is
  blocked and that a declared proxy endpoint accepts a TCP connection.
- `aos/browser/engine.py:53-66` forces `--proxy-server=...` into Chromium
  launch args once that endpoint is declared reachable.
- No code or real-browser test proves that the proxy is AOS-controlled,
  policy-validating, fail-closed for private/local/metadata destinations, or
  effective when application URL checks are bypassed. The real-socket tests in
  `tests/test_browser_egress_real_socket.py` prove listener/refusal behavior,
  not proxy policy enforcement.

The previous canary-only defect is fixed. The remaining gap is that "reachable
proxy" is not equivalent to the contract's OS/container or locally controlled
validating-proxy containment requirement.

### Important Findings

#### I-1 — Post-launch sandbox/process verification is still not proven by Layer 2

Evidence:
- `aos/browser/task.py:255-258` now calls `handle.verify_post_launch_sandbox()`
  before operations run.
- The real implementation in `aos/browser/engine.py:274-289` scans `/proc` for
  Chromium command lines containing the profile directory and accepts any
  matching process with nonzero `Seccomp`.
- No passing real-Chromium test proves this detects the intended browser and
  renderer processes, rejects weakened sandbox state, or survives normal
  Chromium process layout changes.

This is a useful hook, but still unproven as the contract-required
post-launch Chromium sandbox verification.

#### I-2 — T2 action lifecycle still lacks exact terminal semantics

Evidence:
- `_request_and_consume()` can emit `browser.action.denied`
  (`aos/browser/task.py:339-345`), and `_run_one()` emits another
  `browser.action.denied` for the same operation when it catches that
  `PermissionBlocked` (`aos/browser/task.py:431-433`).
- Successful or engine-failed actions emit operation-specific events such as
  `browser.form.draft_filled`, `browser.upload.completed`, or
  `browser.upload.denied`, not a consistent exactly-one
  `browser.action.completed/failed/denied` terminal event.
- The added tests cover exactly-one task-terminal events, but they do not
  prove exactly-one terminal event per T2 action as required by the test plan
  TP-AUDIT-02.

Task-level terminal events improved. Action-level lifecycle semantics still
need either implementation cleanup or a contract/test-plan amendment.

#### I-3 — Resource and cleanup guarantees remain partial without real process tests

Evidence:
- Cleanup now attempts `/proc`-based SIGTERM/SIGKILL for matching Chromium
  processes (`aos/browser/engine.py:291-308`, `552-585`), but no passing Layer-2
  test proves timeout/crash cleanup or absence of orphans.
- Response and bandwidth accounting still rely on `Content-Length`
  (`aos/browser/engine.py:384-389`), and download size is enforced after
  `download.save_as()` completes (`aos/browser/engine.py:473-487`).

These are disclosed limitations and are better surfaced than before, but they
do not yet satisfy the current contract's full resource-limit and cleanup gate.

### Positive Verifications

- Layer-1 URL-policy tests now install an autouse DNS guard and pass without
  live DNS.
- Promotion approval is now bound to quarantined file identity plus project ID,
  canonical root, relative subpath, and destination path at the store boundary.
- Upload now stages an AOS-controlled private snapshot before Playwright sees
  a path, narrowing the prior caller-path TOCTOU issue.
- Task-level terminal auditing now covers launch failure, operation denial,
  post-launch sandbox failure, cleanup failure, timeout, and cancellation in
  focused tests.
- `--yes` remains absent from `aos browser task`.

### Required Next Actions

1. Run and pass the full required Layer-2 matrix in a Chromium-capable,
   independently contained environment with zero required skips/errors.
2. Prove the proxy is an enforced AOS-controlled validating boundary, including
   real Chromium cases where application URL checks are bypassed, or replace it
   with an independently verified OS/container egress policy.
3. Prove post-launch Chromium sandbox status and process-tree cleanup with
   real-browser tests.
4. Normalize T2 action audit lifecycle so each action has exactly one terminal
   action event on success, denial, engine failure, timeout/cancel-induced stop,
   and cleanup-visible failure.
5. Either implement the remaining mid-stream/resource guarantees or have the
   Human Owner explicitly amend the Phase 10 contract to accept the documented
   Playwright/API residuals.

### Phase Decision

Phase 10 is **not COMPLETE**.

Phase 11 **may not start**. B010 remains open.

---

## 2026-07-11 — Prior Fresh Remediation Gate

Date: 2026-07-11  
Reviewer: Codex  
Scope: Fresh read-only final gate review of Claude Sonnet's Phase 10 remediation  
Verdict: **FAIL**

Phase 10 is not complete. Phase 11 remains blocked.

This review made no production-code, test, dependency, commit, or Phase 11 changes.
The only authorized write after the FAIL verdict is this review/coordination update.

## Commands Run And Results

- `git status --short`: dirty worktree confirmed before review; pre-existing
  changes preserved.
- `python3 -m compileall -q aos tests`: PASS.
- `python3 -m ruff check ...`: could not run because system `python3` has no
  `ruff`; reran with the project venv.
- `.venv/bin/ruff check aos/browser aos/tools/browser.py aos/interfaces/cli/browser_commands.py tests/test_browser_*.py tests/test_agent_tool_registry_browser.py`:
  PASS.
- `git diff --check`: PASS.
- Focused browser suite, sandboxed with isolated `AOS_DATA_DIR`:
  `AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-data .venv/bin/python -m pytest -q tests/test_browser_approval.py tests/test_browser_cli.py tests/test_browser_domains.py tests/test_browser_egress_real_socket.py tests/test_browser_quarantine.py tests/test_browser_redaction.py tests/test_browser_sandbox_egress_supply_chain.py tests/test_browser_task.py tests/test_browser_tool.py tests/test_browser_url_policy.py tests/test_agent_tool_registry_browser.py`
  -> **147 passed, 5 failed**. The failures were two local-socket tests blocked
  by sandbox `PermissionError` and three `example.com` DNS-dependent URL-policy
  tests.
- Same focused browser suite rerun outside the sandbox with isolated
  `AOS_DATA_DIR`: **152 passed**.
- Layer 2, opt-in real Chromium, sandboxed:
  `AOS_BROWSER_RUN_REAL_TESTS=1 AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-layer2-data .venv/bin/python -m pytest -q -rs tests/test_browser_integration_real.py`
  -> **2 passed, 5 skipped** (`TargetClosedError`, Chromium not launchable).
- Same Layer-2 command rerun outside the sandbox: **2 passed, 5 skipped**.
- Full suite, sandboxed with isolated `AOS_DATA_DIR`:
  `AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-full-data .venv/bin/python -m pytest -q -rs`
  -> **713 passed, 5 failed, 5 skipped**. The failures matched the focused
  sandbox-only socket/DNS failures.
- Same full suite rerun outside the sandbox with isolated `AOS_DATA_DIR`:
  **718 passed, 5 skipped**. The 5 skipped tests are the opt-in Layer-2 real
  Chromium tests.
- `AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-audit-data .venv/bin/aos audit verify`:
  PASS, `valid (0 events)`.
- `.venv/bin/aos browser --help`, `.venv/bin/aos browser task --help`,
  `.venv/bin/aos browser quarantine promote --help`: PASS. `browser task`
  help no longer exposes `--yes`.
- Static scans:
  - `rg -n "shell=True|os\.system\(" aos tests/test_browser_*.py`: no matches.
  - sandbox-disabling flags appear only in forbidden-flag declarations,
    comments, and tests.
  - no live `evaluate(`, `add_script_tag`, or `new_cdp_session` use found in
    Phase 10 code.
  - Playwright import is confined to `aos/browser/engine.py`; the real
    integration test imports Playwright for its launch probe.

## Critical Findings

### C-1 — Required Layer-2 gate is skipped and materially incomplete

Evidence:
- `tests/test_browser_integration_real.py:51-60` skips all real-Chromium tests
  unless `AOS_BROWSER_RUN_REAL_TESTS=1` is set and Chromium can launch.
- With the opt-in set, both sandboxed and escalated runs produced **2 passed,
  5 skipped** due to `TargetClosedError`.
- The file contains only seven tests (`tests/test_browser_integration_real.py:93-188`).
  It does not cover the required Layer-2 matrix: DNS rebinding, independent
  OS/container egress blocking with the application check bypassed, frames,
  popups, workers, service workers, WebSockets, EventSource, WebRTC,
  prefetch/prerender, post-launch sandbox status, timeout/crash cleanup, or
  orphan process inspection.

Decision: **blocking FAIL**. No environmental exception is accepted. The gate
rule requires complete Layer 2 coverage to run and pass in a suitable
Chromium-capable, independently contained environment before Phase 10 can be
complete.

### C-2 — Egress containment is detected by a single canary probe, not enforced

Evidence:
- `aos/browser/egress.py:80-102` treats inability to connect to
  `1.1.1.1:80` as `verified=True`.
- The check does not inspect or install a network namespace, firewall,
  cgroup rule, forced proxy routing, browser process identity, or deny rules
  for loopback/private/metadata ranges.
- The real-socket tests prove the helper can observe open/refused sockets;
  they do not prove that Chromium is independently contained at the OS or
  container layer.

This is better than the prior environment-variable attestation, but it is
still not the contract-required egress containment control. A host with no
internet route, DNS outage, captive firewall, or port-80 block can pass this
check while still allowing browser egress to private/local services.

### C-3 — Download promotion approval is not exact-bound to destination

Evidence:
- CLI promotion approval is minted with only operation, synthetic task id,
  empty domain id, and file hash (`aos/interfaces/cli/browser_commands.py:166-169`).
- Store-level consumption checks only operation/task/domain/file hash
  (`aos/browser/quarantine.py:217-220`).
- `project_id`, `relative_subpath`, resolved destination path, collision
  policy, and destination project binding are not part of the consumed
  `BrowserApproval`.

The remediation correctly derives the destination root from an enrolled
project ID (`aos/browser/quarantine.py:221-227`), but the approval object is
not bound to the exact destination required by the contract.

## Important Findings

### I-1 — Post-launch Chromium sandbox verification is still missing

Evidence:
- `aos/browser/sandbox.py:83-95` verifies kernel preconditions before launch.
- No code inspects the actual launched Chromium renderer/browser process
  sandbox status after `launch_persistent_context`.
- The remediation report discloses this same residual limitation.

The pre-launch check is useful, but the contract requires fail-closed Chromium
sandbox verification. That remains unproven, and Layer 2 did not run the real
process inspection needed to close it.

### I-2 — Audit lifecycle still fails exact terminal semantics in some paths

Evidence:
- Launch failure audits `browser.session.failed` and returns `FAILED` without
  a `browser.task.failed` terminal event (`aos/browser/task.py:242-247`).
- A post-launch operation-level `PermissionBlocked` is caught as
  `browser.task.denied` (`aos/browser/task.py:383-405`), then the enclosing
  task also audits `browser.task.failed` because the operation result is not
  ok (`aos/browser/task.py:251-259`). That can produce two task-terminal-shaped
  events for one task.
- Existing tests only assert exactly one task terminal for a success path and
  a pre-launch denial path (`tests/test_browser_task.py:520-543`).

The contract requires exactly one correct terminal audit event per task and
per T2 action, including failures, timeout, cancellation, and cleanup failure.

### I-3 — Cleanup and process-tree enforcement remain bounded-reporting, not enforced cleanup

Evidence:
- Cleanup runs `context.close()` / `playwright.stop()` on a daemon thread and
  waits 15 seconds (`aos/browser/engine.py:454-484`).
- If close hangs, the code raises `TimeoutError` but explicitly does not kill
  the underlying process tree (`aos/browser/engine.py:475-484`).
- No Layer-2 orphan-process tests ran or exist for timeout/crash cleanup.
- The current cleanup-failure unit test does not actually force a failing
  cleanup path; it mutates the handle after the run has already completed and
  only asserts the happy-path result (`tests/test_browser_task.py:555-568`).

### I-4 — Runtime resource limits remain incomplete

Evidence:
- Response/body/bandwidth accounting uses `Content-Length` response headers
  only (`aos/browser/engine.py:292-300`).
- Downloads are saved to disk first and read after completion before enforcing
  `max_download_bytes` (`aos/browser/engine.py:380-395`), so the required
  mid-stream download cap and partial-byte discard are not implemented.
- CPU, memory, file descriptor budgets, real process-tree cleanup, and
  real timeout/orphan behavior are not independently enforced by the code or
  covered by Layer 2.

### I-5 — Layer 1 still contains live DNS-dependent tests

Evidence:
- `tests/test_browser_url_policy.py:36-38`, `70-74`, and `107-113` call
  `validate_url(...)` without an injected resolver.
- In the managed sandbox those tests failed with `socket.gaierror` for
  `example.com`; the escalated run passed only because DNS was available.

Layer 1 is required to be deterministic and external-network-free.

### I-6 — Upload TOCTOU is narrowed, not eliminated

Evidence:
- The code binds project ID, inode/device, size, and SHA-256, and revalidates
  immediately before use (`aos/browser/task.py:520-543`, `547-570`).
- The actual Playwright upload still calls `set_input_files(str(file_path))`,
  which reopens by path (`aos/browser/engine.py:401-404`).

This is an honest residual limitation, not the previous unbound path-only
bug. It still does not meet the stronger contract wording that the same
validated open file object is what gets uploaded.

## Non-blocking Findings

1. Several Phase 10 planning documents still carry stale
   `DRAFT — NOT ACTIVE UNTIL HUMAN OWNER APPROVAL` headers even though
   `PHASE_CONTRACT.md` records Phase 10 activation.
2. The disclosed inert test-data artifact under
   `~/.aos-jarvis/browser/approved_domains.json` was not touched. Human Owner
   authorization is still required for any cleanup.

## Positive Verifications

- Raw selector and caller-supplied field-classification paths appear removed.
  `FieldLocator` is constrained and engine resolution uses
  `page.get_by_role(...)`.
- Credential/sensitive field denial is now derived from the resolved field
  attributes before approval is requested.
- `--yes` is removed from `aos browser task`.
- Per-operation approval callback flow exists for navigation, fill/clear,
  submit, download, upload, and cross-domain redirects.
- Cross-domain redirects now request fresh approval in the application-layer
  validator.
- Quarantine promotion resolves destination root from `ApprovedProjectRegistry`.
- Static scans found no live `page.evaluate`, no `shell=True` / `os.system`,
  no constructed `--no-sandbox`, and no CDP session creation.

## Required Next Actions

1. Complete the full Layer-2 matrix and run it successfully in a Chromium-
   capable, independently contained environment. Skips remain blocking.
2. Replace the single canary probe with a verifiable enforced OS/container
   egress policy or forced validating proxy, and prove private/local/metadata
   egress blocking with real Chromium tests, including app-check-bypass cases.
3. Add post-launch Chromium sandbox-status verification or an equivalent
   independently verified containment proof.
4. Bind download promotion approvals to exact destination project ID,
   relative path/resolved destination, file identity, collision policy, and
   origin; consume only that exact-bound approval.
5. Fix task/action audit lifecycle so every task and T2 action has exactly
   one correct terminal event on success, denial, launch failure, operation
   failure, timeout, cancellation, and cleanup failure.
6. Implement enforceable process-tree cleanup/orphan detection and resource
   limits, or amend the contract if specific Playwright limits are accepted
   as residual risk.
7. Remove all live DNS/external-network dependency from Layer 1.
8. Add cross-capability quarantine-isolation tests covering filesystem,
   shell, memory, model, agent, dashboard, and workspace access denial.

## Phase Decision

Phase 10 is **not COMPLETE**.

Phase 11 **may not start**. Phase 11 remains blocked until Phase 10 receives a
fresh independent PASS under the approved gate rule, or until the Human Owner
explicitly amends the Phase 10 contract and the amended gate is independently
passed.
## Builder follow-up evidence reference (2026-07-11)

Builder remediation after this FAIL is recorded in
`docs/PHASE_10_REMEDIATION_REPORT.md` under "2026-07-11 follow-up
remediation after fresh Codex FAIL." This addition is an evidence pointer only;
it does not alter the Codex verdict/findings in this report.
