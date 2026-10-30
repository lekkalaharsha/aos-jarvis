# CHANGELOG

## 2026-10-30 — Phase 11 contract activation (Codex)

- Activated Phase 11 in `PHASE_CONTRACT.md` with a bounded read-only
  screen-understanding scope.
- Authorized explicit screenshot capture, bounded OCR, terminal-error
  detection, screen summaries, and approval-gated suggested fixes.
- Kept continuous capture, desktop control, remote control, credentials, and
  automatic screen-derived actions forbidden.
- Kept Phase 10 frozen and pending independent real-Chromium verification.

## 2026-10-30 — Production static cleanup (Codex)

- Removed unused production imports in memory, project-summary, and command
  policy modules.
- Restored the missing `MemoryStatus` type import in the memory indexer.
- `ruff check aos` now passes with zero findings.

## 2026-10-30 — Phase 10 static/security checkpoint (Codex)

- `compileall` passed.
- Ruff passed for the files changed in the current gate.
- Focused browser security suite passed: **132 passed**.
- Podman is unavailable on the current host; real Chromium Layer-2 verification
  remains blocked.
- Repository-wide Ruff reports 52 baseline findings and was not bulk-rewritten.

## 2026-10-30 — Restored complete test baseline (Codex)

- Stabilized voice CLI missing-dependency tests by masking optional modules
  without importing heavyweight audio/ML packages.
- Voice CLI suite: **16 passed**.
- Full project suite: **765 passed, 38 skipped**.
- Real-Chromium Layer-2 and Phase 10 completion remain blocked by the existing
  independent environment gate.

## 2026-10-30 — Phase 10 task planning and deterministic browser gate checkpoint (Codex)

- Updated the existing `TASKS.md` with the autonomous-browser research boundary,
  AOS goal-based boundary proposal, evaluation-matrix task, and gated follow-up
  implementation task. No new Markdown task files were created.
- Completed the research mapping for Browser Use, Skyvern, Nanobrowser,
  UI-TARS/Agent S, BrowserGym/WebArena, and Browser Harness. No autonomous
  runtime behavior was added.
- Corrected indentation in `tests/test_browser_egress_real_socket.py`.
- Added explicit Windows platform skips for Linux-only synthetic `/proc`
  namespace and UID tests. Focused browser result: **206 passed, 33 skipped**.
- Phase 10 remains incomplete because the real-Chromium Layer-2 gate has not
  independently passed.

## 2026-07-12 — P10-R1 fail-closed validation remediation (Codex)

- Strictly validate the supported Podman seccomp schema before/after the lossless `chroot` transformation; malformed rules now deny with `SeccompProfileError`.
- Require explicit Chromium roles and exact browser/content-process `/proc` security state; `--no-zygote-sandbox` now requires a direct verified-browser parent.
- Real verifier passed; focused **129 passed, 8 skipped**; full **795 passed, 8 skipped**. Phase 10/11 remain blocked pending fresh independent verification.

## 2026-07-12 — P10-R1 zero-capability seccomp correction (Codex)

- Added a fail-closed, lossless transformation of Podman's conditional `chroot` rules: only `chroot` is removed from source rules, all other rule properties and the default action are verified unchanged, and exactly one unconditional `SCMP_ACT_ALLOW chroot` rule is added.
- Removed `--cap-add=SYS_CHROOT`; the container remains `--cap-drop=ALL`.
- Real rootless verifier passed full Chromium process-tree evidence, local fixture navigation, owner-thread close, in-container P10-R1 tests, and cleanup. Full regression: **782 passed, 8 skipped**. Phase 10/11 remain blocked pending fresh independent verification.

## 2026-07-12 — P10-R1 targeted Human Owner clarification: fail-closed result (Codex)

- Recorded the approved zygote-only `--no-zygote-sandbox` exception and sole namespaced `CAP_SYS_CHROOT` container capability; `--no-sandbox` remains forbidden everywhere.
- Extended real `/proc` verification to require zygote type/parent proof and content-process zero effective capabilities, `NoNewPrivs`, seccomp, and namespace evidence.
- Real rootless verifier **FAILED CLOSED**: the exception was valid and GPU/renderers dropped capabilities, but a direct utility process retained `CAP_SYS_CHROOT`. No broader privilege or container control was added; Phase 10 and Phase 11 remain blocked.

## 2026-07-12 — P10-R1 remediation attempt: fail-closed real container result (Codex)

- Tightened P10-R1 launch verification only: `PlaywrightEngineFactory` now uses the supported `channel="chromium"` full-Chromium new-headless path with `chromium_sandbox=True`, while still binding the supply-chain-expected full Chromium executable and every real `/proc` `argv0` to that exact binary.
- Tightened real process-tree rejection: `--no-zygote-sandbox` is now forbidden anywhere, same as `--no-sandbox`; headless-shell and wrong-binary process trees still fail closed.
- `verify_p10r1.sh` now derives a temporary Podman seccomp profile from the default profile and adds only `chroot`; it does not use `seccomp=unconfined`, `--privileged`, `--no-sandbox`, host network/PID, or extra capabilities.
- `container_check.py` now prints complete `/proc/<pid>/cmdline` evidence and checks the temporary profile directory is removed after close.
- Verification: focused browser/engine/task suite **108 passed, 7 skipped**; compileall clean; Ruff clean; `git diff --check` clean; full regression suite passed outside the managed sandbox (**774 passed, 7 skipped**).
- Required real P10-R1 verifier was run as rootless Podman and **FAILED CLOSED**: full Chromium binary launched, but Chromium aborted before a usable process tree with `sys_chroot("/proc/self/fdinfo/") == 0` / `Operation not permitted` under `--cap-drop=ALL`. A minimal in-container probe confirmed `chroot("/proc/self/fdinfo/")` fails with `EPERM`. Granting `CAP_SYS_CHROOT` would be a privilege increase, so it was not done.
- Phase 10 and Phase 11 remain blocked. No commit.

## 2026-07-12 — P10-R1: reproducible rootless-Podman Chromium verification environment (Claude Sonnet)

- Added `ops/phase10/Containerfile.layer2`: pins
  `mcr.microsoft.com/playwright/python:v1.61.0-noble` by resolved
  immutable digest, creates a fixed non-root `10001:10001` user, `COPY`s
  source into the image (no host bind mount, no `VOLUME`).
- Added `ops/phase10/container_check.py`: in-container reproducible
  check that launches real Chromium via the existing
  `aos.browser.engine.PlaywrightEngineFactory` (unchanged), confirms it
  is not running as root, confirms no forbidden sandbox-disabling launch
  flag, navigates one static local `file://` fixture, closes Chromium,
  and confirms no process remains. Fails closed on any unmet check.
- Added `ops/phase10/verify_p10r1.sh`: host orchestrator verifying
  rootless Podman and the pinned image digest, then running the
  hardened container with `--read-only`, narrow `tmpfs` only,
  `--network none`, `--cap-drop=ALL`, `--security-opt no-new-privileges`,
  bounded memory/CPU/PIDs/`ulimit`/stop-timeout, no privileged mode, no
  host network/PID, no socket mount, no host project mount, no
  persistent profile -- and confirming full cleanup afterward.
- Added `tests/test_browser_p10r1_environment.py`: 8 new deterministic
  tests plus one test gated by `AOS_BROWSER_P10R1_CONTAINER=1` for
  running inside the built container. Full suite: 749 passed, 6 skipped
  (up from 741 passed, 5 skipped -- no regression).
- Disclosed: this implementation sandbox has no `podman` installed and no
  passwordless sudo to install it, so `verify_p10r1.sh` could not be run
  to completion here; it correctly failed closed at that precondition.
  **P10-R1 IMPLEMENTED — AWAITING INDEPENDENT ENVIRONMENT VERIFICATION.**
  See `docs/PHASE_10_GATE_RECOVERY_PLAN.md` §7.

## 2026-07-11 — Phase 10 second follow-up remediation (Claude Sonnet): AOS-controlled validating proxy, exact action audit terminals, testable process-tracker logic

- Added `aos/browser/validating_proxy.py`: a real, AOS-spawned, loopback
  HTTP CONNECT proxy that enforces an exact per-task `(host, port)`
  allowlist and genuinely refuses (`403`) disallowed targets. Replaces the
  prior operator-declared-proxy-URL egress model, which only checked
  reachability, not enforcement.
- `aos/browser/egress.py` `spawn_and_verify_validating_proxy()` proves
  containment with a real, unmocked HTTP CONNECT request through the
  just-spawned proxy, not a reachability probe.
- `aos/browser/task.py`: derives the proxy's allowlist from the resolved
  domain, threads its URL into the Chromium launch args, and
  unconditionally stops it on every task outcome.
- Fixed a real double-audit bug: `browser.action.denied` was emitted twice
  for the same denied T2 action (once in `_request_and_consume`, once in
  `_run_one`'s except-handler). Now emitted exactly once.
- `BrowserProcessTracker`'s `/proc`-scan and SIGTERM/SIGKILL logic is now
  dependency-injectable; added 9 deterministic unit tests proving the
  algorithm correct against a synthetic process tree.
- Full suite: 741 passed, 5 skipped. Compileall, Ruff, `git diff --check`,
  isolated audit verification, static bypass scans, and a fail-closed CLI
  smoke test all pass. See `docs/PHASE_10_REMEDIATION_REPORT.md`.
- Per explicit direction, the Layer-2 real-Chromium gate (still 2 passed,
  5 errors, `TargetClosedError`) was NOT re-attempted this round — it is a
  missing-shared-library/no-root-access environment constraint, not a
  code defect, and remains the primary open blocker.
- Not self-certified. Phase 10 remains active with status SECOND
  REMEDIATION APPLIED — AWAITING FRESH INDEPENDENT CODEX FINAL GATE; Phase
  11 remains blocked.

## 2026-07-11 — Phase 10 follow-up Codex final gate: FAIL

- Updated `docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`; verdict **FAIL**.
- Verification reproduced: focused follow-up remediation subset **106
  passed**; default full suite **725 passed, 8 skipped**; compileall,
  changed Phase 10 Ruff, `git diff --check`, and isolated `aos audit verify`
  passed.
- Required opt-in Layer-2 gate:
  `AOS_BROWSER_RUN_REAL_TESTS=1 ... tests/test_browser_integration_real.py`
  returned **2 passed, 5 errors** because Chromium cannot launch
  (`TargetClosedError`). This is correct fail-closed behavior but still a
  blocking gate failure.
- Remaining blockers: Layer-2 matrix incomplete/unpassed; reachable-proxy
  check does not prove an AOS-controlled validating egress boundary; post-
  launch sandbox/process verification is not proven by real Chromium tests;
  T2 action terminal audit semantics are not exact; resource/cleanup
  guarantees remain partial.
- Updated coordination docs. No browser production-code or test changes were
  made during this review. Phase 11 remains blocked.

## 2026-07-11 — Phase 10 follow-up remediation applied; awaiting fresh Codex gate

- Implemented follow-up remediation after the fresh Codex FAIL without starting
  Phase 11 and without claiming PASS.
- Egress now requires a reachable declared validating proxy plus blocked direct
  canary and forces the verified proxy into Chromium launch args; a canary-only
  result no longer passes.
- Added `/proc`-based real Chromium process tracking, post-launch sandbox
  verification hook, and bounded process-tree cleanup hook.
- Reworked browser task terminal auditing so cleanup outcome is known before
  exactly one task-terminal event is written; launch failure, operation denial,
  post-launch sandbox failure, cleanup failure, timeout, and cancellation have
  regression tests.
- Promotion approvals now bind exact quarantined file identity plus enrolled
  project ID, canonical root, relative subpath, and canonical destination path;
  hash-only, substitution, traversal, collision, and replay cases deny.
- Upload now uses an AOS-controlled private snapshot before Playwright receives
  a path, narrowing the remaining Playwright path-reopen TOCTOU limitation.
- Layer-1 URL tests now forbid live DNS via an autouse `getaddrinfo` guard.
- Opt-in Layer-2 now fails closed when Chromium cannot launch instead of
  recording required real-Chromium tests as skips.
- Verification: focused subset **106 passed**; browser-focused suite **161
  passed, 8 skipped** in restricted sandbox; real loopback egress socket tests
  **3 passed** outside sandbox; default full suite **725 passed, 8 skipped**;
  opt-in Layer-2 **2 passed, 5 errors** (`TargetClosedError`) in this
  environment; compileall, changed-file Ruff, `git diff --check`, isolated
  audit verify, CLI smoke, and static browser-surface scans passed.
- Phase 10 status: **REMEDIATION APPLIED — AWAITING FRESH INDEPENDENT CODEX
  FINAL GATE**. Phase 11 remains blocked.

## 2026-07-11 — Phase 10 fresh Codex final gate after remediation: FAIL

- Updated `docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`; verdict **FAIL**.
- Verification evidence: compileall passed; targeted Ruff passed; `git diff
  --check` passed; isolated `aos audit verify` passed; browser CLI help
  smoke tests passed; static scans found no live `shell=True`, `os.system`,
  `page.evaluate`, CDP session creation, constructed `--no-sandbox`, or
  Playwright import outside the approved boundary.
- Focused browser suite: sandboxed isolated run was 147 passed / 5 failed
  due to sandbox-blocked local sockets and live DNS; escalated isolated run
  was **152 passed**. Full suite: sandboxed isolated run was 713 passed / 5
  failed / 5 skipped for the same socket/DNS reasons; escalated isolated run
  was **718 passed, 5 skipped**.
- Required Layer 2 remains blocking: opt-in real-Chromium run produced
  **2 passed, 5 skipped** both inside and outside the sandbox
  (`TargetClosedError`). The Layer-2 matrix remains incomplete.
- Remaining findings: egress canary probe is detection, not enforced
  OS/container containment; promotion approvals are not exact-bound to
  destination; post-launch Chromium sandbox verification is absent; audit
  terminal semantics still have failure-path gaps; cleanup/process-tree and
  resource enforcement are incomplete; Layer-1 tests still contain live DNS
  calls; upload TOCTOU is narrowed but not eliminated.
- Updated coordination docs to keep Phase 10 active but failed and Phase 11
  blocked. No implementation code or tests were changed.

## 2026-07-11 — Phase 10 remediation (Claude Sonnet): every Codex Critical/Important finding fixed

- Replaced environment-variable-only egress/sandbox attestation with real
  checks: an actual TCP connection probe against a non-enrollable canary
  address, and a real kernel-capability (user-namespace + seccomp)
  precondition check. New `tests/test_browser_egress_real_socket.py`
  performs real, unmocked loopback socket connects.
- Replaced raw CSS/XPath selectors and caller-supplied field classification
  with a constrained `FieldLocator(role, name, nth)` resolved via
  accessibility-tree lookup; classification is engine-derived and denied
  before any approval is offered. Removed `page.evaluate` from the download
  path.
- Approvals are now minted and consumed one at a time, immediately before
  each T2 side effect (including per-redirect-hop), via a terminal-only
  synchronous callback. Removed `--yes` from the CLI entirely. Quarantine
  promotion now requires its own approval at the store boundary and
  resolves its destination from an enrolled project ID, not an arbitrary
  caller-supplied path.
- Narrowed upload TOCTOU via `O_NOFOLLOW` + inode/size/hash binding and
  immediate revalidation; bound to an enrolled upload project ID.
- Enforced (not merely declared) redirect depth, tab count, response/
  bandwidth budget, and task/idle timeout, with bounded forced-timeout
  cleanup; cleanup failure is now a visible field on the task result.
- Corrected the audit lifecycle: per-action requested/approval_required/
  approved/denied events; cancellation is never recorded as success.
- Fixed live-DNS dependency in Layer-1 tests (fake resolver injected
  everywhere); replaced the Layer-2 module's collection-time Chromium
  launch probe with a lazy, explicit opt-in fixture.
- Found and fixed a real bug during this pass: a cleanup-outcome field was
  computed after the frozen result object had already been returned,
  caught by Ruff.
- Full suite: 718 passed, 5 skipped (Layer-2 real-Chromium tests remain
  unexecutable in this sandbox — disclosed, unchanged environment
  limitation, not a pass). Compileall, targeted Ruff, `git diff --check`,
  isolated audit verification, static bypass scans, and a fail-closed CLI
  smoke test all pass. See `docs/PHASE_10_REMEDIATION_REPORT.md`.
- Not self-certified. Phase 10 remains active with status REMEDIATION
  APPLIED — AWAITING FRESH INDEPENDENT CODEX FINAL GATE; Phase 11 remains
  blocked.

## 2026-07-11 — Phase 10 independent Codex final gate: FAIL

- Added `docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`; verdict **FAIL**.
- Found Critical containment/sandbox attestation, credential-field/locator,
  T2 approval, quarantine-promotion, and upload-TOCTOU gaps, plus Important
  resource-limit, audit-lifecycle, JavaScript, supply-chain, redirect, and test
  coverage gaps.
- Focused non-Chromium Phase 10 verification: 120 passed, 12 failed because
  mocked tests perform live DNS. Layer-2 remains unpassed and incomplete.
- Compileall, targeted Ruff, `git diff --check`, CLI help, and isolated audit
  verification passed; static scan found externally parameterized
  `page.evaluate(...)` in the download path.
- Phase 10 requires remediation; Phase 11 remains blocked. No production code
  changed and no user data was deleted.

## 2026-07-11 — Phase 10 implementation: IMPLEMENTATION COMPLETE, AWAITING CODEX FINAL GATE

- Implemented `aos/browser/{types,domains,url_policy,approval,redaction,
  egress,sandbox,supply_chain,engine,quarantine,task}.py`,
  `aos/tools/browser.py`, `aos/interfaces/cli/browser_commands.py`
  (`aos browser domain add/list/revoke`, `aos browser task <spec>`,
  `aos browser quarantine list/cleanup/promote`).
- Extended `aos/safety/permissions.py` (browser.upload/browser.promote
  capability kinds), `aos/agent/tool_registry.py` (read-only
  `browser.domain_list` T0 entry only — no T2 browser operation is
  agent-reachable, by design), and `pyproject.toml` (`browser` optional
  extra, `playwright==1.61.0` pinned).
- Task-based execution model: one bounded, validated, per-operation-approved,
  launched, executed, audited, torn-down process per `aos browser task`
  invocation; no cross-invocation session/handle/PID; fail-closed
  egress-containment and Chromium-sandbox preconditions (attestation-based,
  absent by default); quarantine isolated outside every approved root with
  a separate exact-file promotion operation; login/credentials denied at
  the schema level (deferred entirely, not gated).
- 132 mocked unit tests + 6 real-Chromium integration tests (138 new
  tests). Full suite: **696 passed, 6 skipped** — the 6 skips are the
  real-Chromium tests, which could not execute in the implementation
  sandbox (missing OS shared libraries, no root access); disclosed as a
  known limitation, not a pass, in `docs/PHASE_10_IMPLEMENTATION_REPORT.md`.
- Three real bugs found and fixed during implementation (task-id-generated-
  too-late approval binding; an IP-literal domain-matching gap; a
  URL-digest mismatch for non-navigation approvals) — see implementation
  report §9.
- `PHASE_CONTRACT.md`'s Active Phase line now names Phase 10. Status:
  **IMPLEMENTATION COMPLETE — AWAITING INDEPENDENT CODEX FINAL GATE**, not
  self-certified as passing the security gate. See
  `docs/PHASE_10_IMPLEMENTATION_REPORT.md` and `BLOCKERS.md` B009.

## 2026-07-11 — Phase 10 contract remediation (not activated)

- Following Codex's independent Phase 10 Contract Review verdict `READY WITH
  REQUIRED CONTRACT FIXES`, revised all four Phase 10 planning documents and
  `PHASE_CONTRACT.md`'s Phase 10 draft section to resolve every required
  finding, and added `docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md`.
- Key changes: task-based execution model replaces the unusable
  multi-command session design; OS/container egress containment (or a
  validating proxy) is now a mandatory fail-closed launch precondition;
  risk tiers corrected (no T1; every navigation/field-fill/external-effect
  action is T2); login and credential automation deferred entirely rather
  than gated; quarantine/download-promotion, upload approval binding, audit
  privacy, and the audit lifecycle state machine all strengthened; all
  resource limits made normative; two required test layers (mocked +
  real-browser isolated integration) specified; browser supply-chain
  controls added; TM-03/TM-04/TM-10/TM-14 threat ratings corrected.
- No `aos/` or `tests/` file was modified; no dependency was added; no CLI
  command was implemented. `PHASE_CONTRACT.md`'s Active Phase line remains
  Phase 9. Phase 10 remains DRAFT, not activated.

## 2026-07-11 — Phase 10 planning drafted (not activated)

- Drafted the full Phase 10 — Controlled Browser Automation contract, threat
  model (20 ranked scenarios), test plan (fully mocked, zero live-network),
  and architecture (Playwright, module layout mirroring Phase 9's reviewed
  pattern) as planning documents only.
- Appended a clearly marked `DRAFT — NOT ACTIVE UNTIL HUMAN OWNER APPROVAL`
  Phase 10 section to `PHASE_CONTRACT.md`, without changing the Active Phase
  declaration (still Phase 9, COMPLETE).
- No `aos/` or `tests/` file was modified; no dependency was added; no CLI
  command was implemented.
- Flagged for Human Owner review: this design expands scope beyond the
  original `docs/phases/PHASE_10_BROWSER_TOOLS.md` placeholder (read-only
  only) to include T1/T2 form interaction, gated behind fresh non-voice
  approval — tracked as B008.

## 2026-07-11 — Phase 9 COMPLETE: Human Owner sign-off

Human Owner recorded approval in `PHASE_CONTRACT.md` completing Phase 9 —
Workspace and App Control, following Claude Sonnet's independent re-review
(clean PASS, all findings fixed and re-verified: 564 passed, compileall/ruff/
`git diff --check` all clean). B007 is CLOSED. Phase 10 remains closed pending
separate Human Owner authorization.

## 2026-07-11 — Phase 9 F-1/F-2/N-1 follow-up fixes

- F-1: `WorkspaceTool._serve()` no longer double-audits a `serve` denial; the
  missing-approval and invalid-approval branches return `ToolResult` directly
  instead of raising, so exactly one `DENY` audit row is recorded per rejected
  request, and the specific denial reason reaches the caller.
- F-2: added `canonical_project_digest()`; `consume_dev_server_approval` now
  accepts an independent `canonical_project_id` bound to the resolved project
  path (not just the opaque project-ID string), catching a path change between
  mint and consume even when the project ID is unchanged. CLI and `_serve()`
  updated to pass real path digests.
- N-1: removed dead `handle_id` branch in `tool_registry.py::_execute_workspace`.
- Added 4 new regression tests. Full suite: **564 passed** (was 560); compileall,
  ruff, and `git diff --check` all clean. Live-reproduced the full enroll →
  serve-rejected → serve-approved → real foreground launch → Ctrl+C → clean
  cancellation flow once more end to end.
- See `docs/PHASE_9_INDEPENDENT_RECONFIRMATION.md` §23.

## 2026-07-11 — Phase 9 independent re-review: PASS WITH NON-BLOCKING FINDINGS

- Claude independently re-verified Codex's C-1/C-2/C-3/I-1/I-2 remediation with a
  fresh read-only review plus live CLI/audit smoke testing (real foreground
  loopback dev-server launch and Ctrl+C cancellation, real enrollment/open/serve
  flows against an isolated `AOS_DATA_DIR`).
- Reproduced 560 passed / 0 failed / 0 skipped full suite; 81 passed focused suite;
  compileall, ruff, `git diff --check`, and static bypass scan all clean.
- No Critical or Important blocking findings. Two non-blocking Important findings
  recorded for optional follow-up: F-1 (duplicate DENY audit row on two `_serve()`
  rejection paths) and F-2 (`canonical_project_id` currently duplicates the
  `project_id` check rather than independently verifying identity). One
  nice-to-have (dead `handle_id` branch in `tool_registry.py`).
- No production code modified during this review. See
  `docs/PHASE_9_INDEPENDENT_RECONFIRMATION.md`.
- B007: FIXED + INDEPENDENTLY VERIFIED. Phase 9 ready for Human Owner sign-off;
  Phase 10 remains closed.

## 2026-07-11 — Phase 9 critical remediation locally verified

- Added typed, allowlisted folder opening with canonical PermissionEngine
  revalidation and fixed Linux/WSL/Windows launcher mappings.
- Replaced unusable detached server management with a foreground loopback lifecycle;
  removed cross-invocation status/stop CLI and registry capabilities.
- Required explicit Human Owner confirmation before exact-bound dev-server approval
  minting and recorded only safe Ctrl+C stop guidance.
- Preserved requested operation/project/origin/risk context in denial audit events and
  preserved specific safe Phase 1 path exception subtypes.
- Removed weaker legacy launch helpers and added deterministic regression/CLI tests.
- Linux/WSL verification: 560 passed, zero failures/skips; compileall, changed-file
  Ruff, audit-chain, static bypass, CLI help, and diff checks passed.
- B007: FIXED + AWAITING INDEPENDENT RE-VERIFICATION by Claude. Phase 9 remains active.

## 2026-07-11 — Phase 9 completion: IMPLEMENTED + LOCALLY VERIFIED

- Replaced boolean dev-server approval with opaque, expiring, single-use
  `DevServerApproval` bound to operation, project ID, profile, port, terminal
  origin. Token never serialized or audited.
- Completed full typed launch lifecycle state machines (start/stop) with
  exactly-one terminal event enforcement.
- Added `status()` method for non-destructive handle inspection.
- Added safe `server-status` and `server-stop` operations through workspace
  tool and CLI.
- Added 60 comprehensive deterministic tests covering approval security,
  editor/terminal lifecycle, server lifecycle, stop/status operations, and
  audit event integrity.
- Full suite: **578 passed, 1 skipped** (pre-existing platform symlink).
- Phase 9 status: IMPLEMENTED + LOCALLY VERIFIED — AWAITING INDEPENDENT REVIEW.
- B007: FIXED + AWAITING INDEPENDENT VERIFICATION.

## 2026-07-11 — Phase 9 typed launch adapter increment

- Added closed typed Phase 2 workspace launches and opaque, project-bound safe
  handles with bounded idempotent stop semantics.
- Fixed cross-platform Windows credential-path normalization and deterministic
  symlink-escape precedence; workspace audit now records project IDs, not paths.
- Verification requiring pytest remains blocked; operation-bound dev-server
  approval and full lifecycle coverage remain in progress. B007 stays open.

## 2026-07-11 — Phase 9 durable enrollment replay protection

- Persisted only a consumed approval-token digest atomically before project
  persistence; approvals are exact-path and exact-operation bound, expire, and
  cannot replay after a registry re-creation or crash window.
- Added deterministic replay, concurrent-consumption, expiry, origin, and
  token-nonleak tests. WSL environment setup is blocked by missing ensurepip/
  venv and package tooling; no Windows venv was used. B007 stays open.

## 2026-07-11 — Phase 9 approved-project bootstrap hardening

- Replaced path/cwd-based workspace authorization with explicit Human Owner
  one-use exact-path enrollment and opaque project-ID workspace operations.
- Kept registry membership separate from PermissionEngine authorization; added
  comprehensive deterministic enrollment-boundary tests and voice-origin gate.
- Compilation and diff checks pass. Full pytest remains pending in the normal
  project environment; Phase 9 remains in progress and B007 remains open.

## 2026-07-11 — Phase 9 initial workspace implementation

- Added the allowlisted `WorkspaceTool`, `aos workspace` CLI, fixed Phase 2 launch
  adapters, and initial deterministic workspace tests (6 passed).
- Phase 9 remains in progress pending comprehensive security coverage and completed
  full-regression verification.

## 2026-07-11 — Human Owner approves Phase 8 completion and Phase 9 start

- Phase 8 is COMPLETE. Human Owner authorized Phase 9 — Workspace and App Control.
- Updated the phase contract and coordination records; no Phase 9 implementation
  was started in this documentation-only transition.

## 2026-07-11 — Phase 8 supplemental timeout verification

- OpenCode independently verified the completed timeout remediation: compile,
  voice CLI checks, audit verification, and Ruff passed; focused voice suite:
  **137 passed**; full suite: **484 passed, 2 skipped**.
- No blocking gaps found. Typed timeout outcomes and all F8-1 through F8-4 fixes
  remain verified. Phase 9 remains blocked pending Human Owner approval.
- Report: `docs/PHASE_8_OPENCODE_TIMEOUT_VERIFICATION.md`.

## 2026-07-11 — Phase 8 live timeout traceability remediation

- Added typed timeout outcomes, live lifecycle routing, bounded programmatic
  recording duration, and end-to-end timeout regression coverage.

## 2026-07-11 — Claude Sonnet F8-4 remediation: session lifecycle audit events

- Added `VoiceSessionLifecycle` context manager with `_terminal_emitted` flag
  enforcing exactly-one-start + exactly-one-terminal per voice session.
- Added 5 new lifecycle methods on `VoiceService`: `record_session_started`,
  `record_session_completed`, `record_session_cancelled`, `record_session_timed_out`,
  `record_session_failed`; plus `create_lifecycle()` factory.
- Updated `listen()` to call `record_session_started()` after `session.start()`
  succeeds; uses `create_lifecycle()` context for exactly-once terminal events;
  passes `session_id` to `process_audio()` and `speak()`.
- All lifecycle payloads: no raw transcript, no raw audio, bounded size.
- Preserved F8-1 (`_record_audit` error sanitization), F8-2 (TTS redaction),
  F8-3 (capture timing), and yes=False invariant.
- 24 new lifecycle tests; full suite: **476 passed, 2 skipped**.
- Phase 8 status: AWAITING INDEPENDENT RECONFIRMATION.
- Report: `docs/PHASE_8_F8_4_REMEDIATION_REPORT.md`.

## 2026-07-11 — Phase 8 Codex final gate: FAIL

- Fixed F8-1 provider-error secret retention, F8-2 TTS redaction, and F8-3
  microphone lifecycle timing during the gate.
- F8-4 lifecycle audit events remain missing; Phase 9 is blocked.

## 2026-07-11 — Claude Sonnet Phase 8 implementation (Voice Interface)

- Implemented Phase 8 local-only push-to-talk voice interface.
- New `aos/voice/` module: types, config, normalization, safety, session,
  service, and provider interfaces (STT/TTS) with mock implementations.
- `FasterWhisperSTT` (local STT) and `PiperTTS` (local TTS subprocess) with
  lazy optional-dep imports; `MockSTT` / `MockTTS` for deterministic tests.
- `PushToTalkSession`: injectable recorder, context-manager cleanup, idle/
  recording/processing/complete/cancelled/error state machine.
- `VoiceService.process_audio()`: always calls `ask()` with `yes=False`;
  records `voice.session.routed` audit event with `origin="voice"`.
- `VoiceService.speak()`: redacts secrets and bounds text before TTS.
- `aos voice doctor/devices/listen/speak` CLI with lazy imports (no microphone
  at import time or --help invocation).
- Added `[voice]` optional extra to `pyproject.toml`.
- 98 new tests across 4 files; full suite: **445 passed, 2 skipped**.
- Phase 0–7 regression: PASS.
- All Phase 8 security invariants verified by dedicated tests.
- Report: (pending Codex final gate).

## 2026-07-11 — Claude Sonnet Phase 7 independent reconfirmation

- Verdict: **PASS**. Recommendation: **PHASE 7 COMPLETE — READY FOR PHASE 8**.
- Reproduced 347 passed, 2 skipped independently.
- Verified all four Important fixes: F7-1 (no storage init on GET), F7-2 (recursive
  secret redaction), F7-3 (port validation before Uvicorn), F7-4 (bounded loading).
- Confirmed XSS: all angle brackets escaped in HTML responses via Jinja2 autoescape.
- Confirmed loopback: `AOS_DASHBOARD_HOST=0.0.0.0` cannot override 127.0.0.1 binding.
- Confirmed read-only: 7 GET-only routes, zero write routes, no mutation in service.
- Ruff: zero findings on dashboard production code.
- No production code modified during this reconfirmation.
- Report: `docs/PHASE_7_INDEPENDENT_RECONFIRMATION.md`.

## 2026-07-11 — Codex Phase 7 final gate review
- Initial final-gate verdict: **FAIL — independent reconfirmation required**.
- Found and fixed Important dashboard issues: implicit storage initialization on
  GET paths, secret-shaped display leakage, missing port validation, and
  unbounded audit/payload loading.
- Added hostile regression coverage for no-write reads, secret-shaped values,
  bounded payloads, valid/invalid ports, environment host non-bypass, and
  missing optional dependencies.
- Verified declared dashboard/dev extras install, compile passes, all seven
  routes are read-only and loopback-only, and the non-empty audit chain is
  valid. Full collection: **347 passed, 2 skipped**.
- Per final-gate fix policy, the production changes require a different
  independent reviewer to reconfirm Phase 7; Phase 8 remains blocked.
- Report: `docs/PHASE_7_FINAL_GATE_REPORT.md`.

## 2026-07-11 — Claude Code Phase 7 implementation (Read-Only Dashboard)

- Implemented Phase 7 read-only dashboard: FastAPI + Jinja2 + uvicorn, loopback-only.
- Seven views: Overview, Audit Timeline, Permission Decisions, Project & Memory Activity,
  Snapshot Metadata, Model Provider Status, Security Events.
- `aos dashboard [--port PORT]` CLI command; binds to 127.0.0.1 only, no --host flag.
- Added `dashboard` optional extra to `pyproject.toml` (fastapi, uvicorn, jinja2).
- 89 new tests: service unit tests, HTTP integration tests (TestClient), security tests
  (XSS, write-method blocking, secret exposure, pagination cap, no-introspection),
  CLI tests (loopback-only binding verified).
- Full suite: **317 passed, 2 skipped** (baseline was 228+2).
- All 20 Phase 7 security checks pass (see `docs/PHASE_7_IMPLEMENTATION_REPORT.md`).
- Phase 0–6 regression: PASS.
- Report: `docs/PHASE_7_IMPLEMENTATION_REPORT.md`.

## 2026-07-11 — Codex Phase 6 final gate review
- Final-gate verdict: **PASS WITH NON-BLOCKING FIXES**; recommendation:
  **PHASE 6 COMPLETE — READY FOR PHASE 7**.
- Reproduced the expected normal-environment validation result: **228 passed,
  2 skipped**; compile passed.
- Generated a non-empty isolated Phase 6 audit chain: `aos audit verify`
  reported valid with 21 events, including all required `model.*` event types;
  no sentinel credential value appeared in audit payloads.
- Confirmed the blocked-redaction regression test and the removed dead headers
  placeholder. Confirmed double redaction is idempotent.
- Recorded non-blocking cloud dry-run UX behavior, redundant redaction, and
  existing lint/type debt. No production code changed.
- Report: `docs/PHASE_6_FINAL_GATE_REPORT.md`.

## 2026-07-11 — Claude Code Phase 6 independent review
- Ran full pytest suite in the normal project environment: **228 passed, 2 skipped** (up from 32 Phase 6 + 195 Phase 0–5).
- Confirmed all 20 Phase 6 security checks pass; no Critical findings.
- Fixed dead `headers` variable in `aos/model/cloud.py` (collapsed to single `real_headers`).
- Added `test_cloud_provider_blocked_redaction_result_returns_error` to `tests/test_model_cloud_adapter.py` covering the `redaction.blocked=True` blocking guard.
- Resolved B002 (pytest unavailable in Codex container — not applicable here).
- Verified Phase 0–5 regression (195 pass, 2 benign skips unchanged), dangerous agent prompts still execute no tools.
- Audit chain verified valid with 14 model events (route, request, error, response all present).
- Recommendation: NOT READY FOR FINAL GATE until Codex confirms 228-pass result.
- Full report: `docs/PHASE_6_CLAUDE_REVIEW.md`.

## 2026-07-11 — Codex Phase 6 implementation
- Recorded Human Owner approval to begin Phase 6 from the implementation instruction.
- Added `aos/model` safe model layer: types, provider interface, local adapter, cloud adapter, config, redaction, router, structured output validation, and model service/audit integration.
- Added `aos model` CLI commands and optional `aos ask --model local|cloud` integration through the controlled agent path.
- Added deterministic mocked Phase 6 tests for config, redaction, routing, providers, validation, CLI, agent integration, and safety.
- Updated Phase 6 docs and safety/capability/coordination files.
- Validation: `python3 -m compileall -q aos tests` passed; model config/redaction/router smoke check passed with writable `AOS_DATA_DIR`; low-level audit chain check returned valid; full pytest/CLI validation blocked because this container has no pytest/pip/project CLI dependencies installed.

## 2026-07-11 — Codex Phase 5 review
- Reviewed the Phase 5 Git and Project Assistant implementation against the active contract.
- Added approved-root validation for agent and CLI git/project working directories; added regression tests.
- Verified 194 tests pass and 2 benign Windows symlink tests skip when pytest temp is redirected to the workspace.
- Verdict: PASS WITH FIXES. See `docs/PHASE_5_IMPLEMENTATION_REPORT.md`.

## 2026-07-10 — OpenCode (Phase 4 independent review)
- Conducted a strict Phase 4 security, correctness, privacy, and architecture review across all 10 areas.
- Verdict: PASS. No critical bugs, data corruption risks, or privacy leaks found.
- All 157 tests pass (2 skipped, benign platform limitations). Audit verify passes.
- Updated `PROJECT_STATE.md` to reflect Phase 4 COMPLETE + REVIEWED status.
- Phase 4 is ready. Phase 5 is NOT STARTED. Do not begin Phase 5 without human owner approval.

## 2026-07-10 — Codex (Phase 1 implementation) + Claude Code (verification)
- Codex implemented Phase 1: permission engine (`aos/safety/{permissions,risk,paths,errors}.py`), safe file tools (`aos/tools/fs_tools.py`), snapshot/restore (`aos/safety/snapshots.py`), CLI (`aos fs *`, `aos snapshot *`), tests, and docs (`docs/phase_1.md`, `docs/permissions.md`, `docs/risk_tiers.md`). Updated `PHASE_CONTRACT.md` to declare Phase 1 active.
- Added `AOS_DATA_DIR` env override to `aos/config/loader.py` for local/test data isolation.
- Claude Code independently verified the handoff: `pytest -q -rs` (39 passed, 1 skipped — benign Windows symlink-privilege limitation), plus a manual CLI walkthrough confirming blocked dangerous paths/secrets/traversal/outside-root writes, correct list/read/search/write/edit, snapshot-before-edit, a real restore that correctly reverted content, and full audit coverage with a valid hash chain throughout. Phase 0 commands confirmed unaffected.
- Updated `PROJECT_STATE.md`, `TASKS.md`, `HANDOFF.md` to record verified (not just claimed) Phase 1 completion.

## 2026-07-10 — Claude Code (project tracking system)
- Created the full project-tracking/phase-management documentation system: PROJECT_SCOPE.md, DEVELOPMENT_WORKFLOW.md, MODEL_PROVIDER.md, TOOL_INTERFACE.md, PERMISSION_MODEL.md, AUDIT_LOG.md, EVALS.md, TESTING_STRATEGY.md, RELEASE_CHECKLIST.md.
- Added 13 per-phase files under `docs/phases/` and 7 new numbered ADRs under `docs/adr/`.
- Added reserved `docs/security/`, `docs/models/`, `docs/tools/`, `docs/workflows/` folders.
- Added `.agent/context.md`, `.agent/antigravity_notes.md`, and `.agent/templates/{handoff,task,blocker,review}_template.md`.
- Extended DECISIONS.md, PROJECT_STATE.md, and TASKS.md to cover the tracking-setup work without erasing the already-completed Phase 0 code history.
- No product code changed in this pass; all 15 existing tests still pass, plus 2 new tests for phase-doc/ADR existence.

## 2026-07-10 — Claude Code
- Created Phase 0 foundation structure, coordination docs, CLI skeleton, SQLite audit log with hash-chain verification, and basic risk/permission/tool-contract/eval scaffolding.
- Adopted the full-context PDF spec: renamed audit event fields to actor/event_type/action/resource/risk_tier/status/payload_json/parent_hash/event_hash, added the config system and `aos config show`, switched eval fixtures to YAML, converted capability/tool models to Pydantic v2, added Rich CLI output.
- Added ROADMAP.md, ARCHITECTURE.md, SECURITY.md, PROJECT_STATE.md, TASKS.md, HANDOFF.md, BLOCKERS.md, `.gitignore`, and `docs/{phase_0,tool_interface,permission_model,audit_log,evals}.md`.
- Set up the repo-as-shared-memory communication system: standardized HANDOFF.md/TASKS.md/BLOCKERS.md templates and added `.agent/{claude,codex,opencode}_notes.md` and `.agent/current_context.md`.
- 15 pytest tests passing; all required Phase 0 commands verified working.
