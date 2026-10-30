# BLOCKERS

## B011 — Host lacks Chromium verification runtime and has lint baseline debt

Status: OPEN (2026-10-30)
Owner: Human Owner / OpenCode environment
Phase: Phase 10
Severity: High

### Problem

The current host has no Podman installation, so the required real-Chromium
Layer-2 verifier cannot run. Repository-wide Ruff also reports 52 findings,
including existing production import/type issues and test-style findings.

### Current evidence

- Focused Phase 10 security suite: **132 passed**.
- Changed-file Ruff: passed.
- `compileall`: passed.
- Full suite baseline: **765 passed, 38 skipped**.

### Next Step

Run the independent verifier in the approved Chromium-capable environment.
Separately decide whether to clean the repository-wide Ruff baseline before the
Phase 10 final gate; do not weaken security tests to make lint pass.

## 2026-10-30 — B010 test checkpoint

The previous full-suite stall was traced to heavyweight optional voice-package
imports in missing-dependency tests. The tests now mask those modules
deterministically. Voice CLI: **16 passed**; full suite: **765 passed, 38
skipped**.

B010 remains open: this does not replace the required real-Chromium Layer-2
security verification or fresh independent Phase 10 gate.

## 2026-10-30 — B010 checkpoint

The deterministic browser suite now collects and passes on Windows after fixing
one test indentation defect and marking Linux-only `/proc` namespace/UID
fixtures with explicit platform reasons: **206 passed, 33 skipped**.

This does not resolve B010. The required real-Chromium Layer-2 verification,
fresh independent P10-R1 environment gate, and remaining Human Owner decisions
are still outstanding. No autonomous planner, persistent browser session,
login automation, unrestricted CDP, P10-R2, or Phase 11 work was started.

## B010 — Phase 10 independent final gate failed

Status: OPEN — P10-R1 VALIDATION GAPS REMEDIATED; FRESH INDEPENDENT VERIFICATION REQUIRED; PHASE 10 FINAL GATE REMAINS BLOCKED (2026-07-12)
Owner: Codex (fresh final gate) / Human Owner for any contract amendment
Phase: Phase 10
Severity: Critical

### Problem

Codex's original 2026-07-11 independent final gate returned **FAIL**. Claude
Sonnet applied a remediation pass, but Codex's fresh read-only re-gate also
returned **FAIL**. A follow-up remediation pass was then applied. Codex's fresh
independent final gate of that follow-up also returned **FAIL**. Phase 10 is
not complete until the remaining findings are remediated and the required
Layer-2 real-Chromium matrix runs successfully in a capable, independently
contained environment.

### Expected

All Critical and Important findings in
`docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md` are remediated, both required test
layers pass, and a fresh independent gate confirms contract compliance.

### Resolution so far

Claude Sonnet's remediation fixed several original Critical issues:
environment-variable attestations were removed, raw selectors/caller-supplied
field classification were replaced with accessibility-tree locators and
engine-derived classification, `--yes` was removed, per-operation approval
callbacks were added, promotion now resolves an enrolled project ID, and upload
binding now includes project ID + inode/device + size + SHA-256. Codex verified
these improvements and reproduced: focused browser suite **152 passed** outside
the sandbox with isolated `AOS_DATA_DIR`; full suite **718 passed, 5 skipped**;
compileall, Ruff, `git diff --check`, audit verify, CLI smoke, and static scans
passed.

Follow-up remediation applied by Codex builder:

- validating-proxy egress enforcement shape plus direct canary verification;
- verified proxy passed into Chromium launch args;
- post-launch sandbox verification hook using `/proc` process tracking;
- bounded process-tree cleanup hook after Playwright shutdown;
- exact single terminal task audit event after cleanup outcome is known;
- quarantine promotion approval bound to file and exact destination;
- upload private-snapshot staging before Playwright `set_input_files`;
- DNS-free Layer-1 URL-policy tests;
- opt-in Layer-2 fails closed when Chromium cannot launch instead of skipping.

Codex follow-up gate verification: focused remediation subset **106 passed**;
default full suite **725 passed, 8 skipped**; compileall, changed Phase 10
Ruff, `git diff --check`, and isolated `aos audit verify` passed. Opt-in
Layer-2 produced **2 passed, 5 errors** because Chromium cannot launch here
(`TargetClosedError`), which is correct fail-closed gate behavior but still a
blocking failure. Remaining findings: the full Layer-2 matrix is incomplete
and unpassed; the reachable-proxy check does not prove an AOS-controlled
validating egress boundary; post-launch sandbox/process verification is not
proven by real Chromium tests; T2 action audit terminal semantics are not
exact; and resource/cleanup guarantees remain partial. See
`docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`.

### Second follow-up remediation (2026-07-11, Claude Sonnet)

Per explicit Human Owner/user direction, this pass fixed the remaining
CODE-LEVEL findings from the "Follow-up Remediation Gate" and deliberately
did NOT re-attempt C-1 (Layer-2 real-Chromium launch), since that is an
environment constraint (missing OS shared libraries, no root access) that
no application-code change can fix in this sandbox:

- **C-2 fixed**: `aos/browser/validating_proxy.py` (new) implements a real
  AOS-spawned, loopback-bound HTTP CONNECT proxy that enforces an exact
  per-task `(host, port)` allowlist with a genuine `403` refusal for
  disallowed targets, verified via actual unmocked CONNECT requests in new
  tests. This replaces the prior "operator declares a URL, we just check
  reachability" model entirely — there is no declared-proxy-URL acceptance
  path left.
- **I-2 fixed**: removed the duplicate `browser.action.denied` audit (was
  emitted both inside `_request_and_consume` and again in `_run_one`'s
  except-handler for the same failure); now exactly one terminal-shaped
  event per denied T2 action, with 3 new regression tests.
- **I-1/I-3 partially addressed**: `BrowserProcessTracker`'s `/proc`-scan
  and SIGTERM/SIGKILL logic is now dependency-injectable and has 9 new
  deterministic unit tests proving the algorithm correct against synthetic
  process trees. This does NOT prove the algorithm against a real Chromium
  process (still blocked by the same environment constraint as C-1) — that
  remains open.

Verification: 741 passed, 5 skipped (full suite); ruff/compileall/git diff
--check/audit verify/static scans all clean; fail-closed CLI smoke
confirmed; Layer-2 opt-in run unchanged at 2 passed, 5 errors
(`TargetClosedError`). See `docs/PHASE_10_REMEDIATION_REPORT.md` (second
follow-up section) for full detail. Not self-certified.

### Next Step

Codex: fresh independent final-gate review of this second remediation
pass. C-1 (Layer-2 launch) remains the primary open blocker and requires
either a Chromium-capable, independently contained environment/root access
to resolve, or a Human Owner decision on how to proceed given that
constraint — no further code change in this sandbox can close it. Phase 11
remains blocked until Phase 10 receives a fresh independent PASS.

### Recovery planning (2026-07-11)

Phase 10 recovery planning complete; no implementation started; Phase 11
remains blocked. See `docs/PHASE_10_GATE_RECOVERY_PLAN.md` (rootless
Podman + pinned Playwright/Chromium environment, container-level egress
enforcement, full Layer-2 test matrix, Human Owner decisions, and a
phased P10-R1..R4 execution plan). This is a read-only planning artifact;
it does not close B010. Awaiting Human Owner decisions before P10-R1 work
begins.

### P10-R1 implemented (2026-07-12, Claude Sonnet) — superseded by failed remediation attempt below

The Human Owner approved P10-R1 only. `ops/phase10/{Containerfile.layer2,
container_check.py,verify_p10r1.sh,fixtures/}` implement the reproducible
rootless-Podman, non-root (fixed UID/GID 10001), digest-pinned, read-only,
no-host-network Chromium verification environment described in
`docs/PHASE_10_GATE_RECOVERY_PLAN.md` §1/§7, reusing
`aos/browser/engine.py` and `aos/browser/sandbox.py` unchanged. 8 new
focused tests; full suite 749 passed, 6 skipped (no regression from 741/5).

This does **not** close B010 or C-1: this implementation sandbox has no
`podman` installed and no passwordless sudo to install it, so
`./ops/phase10/verify_p10r1.sh` could not be run to completion here -- it
correctly failed closed at the rootless-Podman precondition
(`FAIL-CLOSED: podman is not installed`). The pinned base image digest was
independently confirmed correct via a direct MCR registry API query. The
host's own kernel/cgroup v2/subuid posture otherwise looks compatible with
rootless Podman (systemd PID 1, cgroup v2 controllers present,
`/etc/subuid`/`/etc/subgid` already configured), so this is disclosed as a
narrower, more concretely bounded blocker ("Podman not installed in this
session") than the prior "Chromium cannot launch here at all" constraint.
**P10-R1 IMPLEMENTED — AWAITING INDEPENDENT ENVIRONMENT VERIFICATION.**

Superseded current status: Codex subsequently ran the real verifier under
rootless Podman; see the failed-closed remediation attempt below. Only after
P10-R1 passes in an approved posture should P10-R2 (OS/container egress
enforcement) begin. C-1 remains open until then.

### P10-R1 remediation attempt (2026-07-12, Codex) — failed closed

An independent real-environment verification found two P10-R1 defects:
headless-shell/Playwright-injected sandbox-disabling flags and Playwright sync
close from the wrong thread. Codex remediated only those two defects:

- `aos/browser/engine.py` now launches via `channel="chromium"` with
  `chromium_sandbox=True`, while still proving Playwright's reported
  executable and every real `/proc` `argv0` match the exact
  supply-chain-resolved full Chromium binary.
- `aos/browser/sandbox.py` / `BrowserProcessTracker` now reject
  `--no-sandbox` and `--no-zygote-sandbox` anywhere in the real Chromium
  process tree, and still reject headless shell and wrong binaries.
- The owner-thread engine path remains the single sync-Playwright owner for
  launch, operations, and close; close exceptions/timeouts surface and trigger
  independent process-tree cleanup.
- `ops/phase10/verify_p10r1.sh` builds the image without headless shell and
  derives a tailored seccomp profile adding only `chroot`, with no
  `seccomp=unconfined`, no extra capabilities, no privileged mode, and no
  browser sandbox-disabling flags.

The required real verifier was run outside the managed sandbox as the ordinary
rootless user. It pulled the pinned digest, built the image, and launched the
expected full Chromium binary
`/ms-playwright/chromium-1228/chrome-linux64/chrome`, but **FAILED CLOSED**
before usable `/proc` descendant evidence could be collected:
Chromium aborted with `Check failed: sys_chroot("/proc/self/fdinfo/") == 0`.
A minimal same-container probe confirmed `chroot("/proc/self/fdinfo/")` fails
with `EPERM` under `--cap-drop=ALL`. Granting `CAP_SYS_CHROOT` would be a
privilege increase, so it was not done.

Verification after code changes: focused browser/engine/task suite **108
passed, 7 skipped**; compileall clean; Ruff clean; `git diff --check` clean;
full regression suite **774 passed, 7 skipped** outside the managed sandbox.
No P10-R1 Podman containers or conmon processes remained afterward.

Next step: Human Owner/Codex must decide whether a different approved
rootless container posture can satisfy Chromium's sandbox without extra
privileges, or keep P10-R1 blocked. P10-R2/P10-R3/P10-R4 and Phase 11 remain
blocked.

### P10-R1 targeted clarification experiment (2026-07-12, Codex) — failed closed

The Human Owner approved namespaced `CAP_SYS_CHROOT` only and a zygote-only
`--no-zygote-sandbox` exception conditioned on `/proc` verification of the
full binary, parent tree, content-process zero capabilities, `NoNewPrivs`,
seccomp, and namespace evidence. The tracker and verifier were updated to
enforce those conditions. Real rootless Podman verification launched the
approved full Chromium binary: the flagged zygote had the verified browser
parent; GPU and renderer processes had `CapEff=0`, `NoNewPrivs=1`, seccomp
mode 2, and namespace evidence. It nevertheless **FAILED CLOSED** because a
direct `--type=utility` process retained `CapEff=0000000000040000`
(`CAP_SYS_CHROOT`). No capability beyond the approved one, no privileged mode,
and no host mount/network/PID/socket control was used. P10-R1 remains blocked.

### P10-R1 seccomp correction (2026-07-12, Codex) — remediated

Codex identified that appending an unconditional `chroot` rule did not override
Podman's earlier capability-conditional rules. `ops/phase10/seccomp_profile.py`
now removes only `chroot` from each matching source rule, preserves every
other name/property, appends one exact unconditional allow, and proves the
default action and unrelated rules are unchanged. `--cap-add=SYS_CHROOT` was
removed. The rootless real verifier passed: full Chromium, no `--no-sandbox`,
verified zygote-only exception, zero effective capabilities on browser/GPU/
network-service/utility/renderer processes, seccomp/namespace evidence, local
fixture navigation, owner-thread close, in-container checks, and cleanup.
This closes the P10-R1 environment-remediation defect only; B010 and Phase 10
remain open pending a fresh independent environment verification.

## B009 — Phase 10 independent Codex final-gate review pending

Status: RESOLVED BY REVIEW — final gate completed with FAIL; superseded by B010
Owner: Codex
Phase: Phase 10 (implementation complete, not yet independently reviewed)
Severity: Medium

### Problem

Claude Sonnet implemented Phase 10 (`aos/browser/*` and integration
points) against the remediated contract following Human Owner activation
approval. Full suite: 696 passed, 6 skipped. The 6 skipped tests are the
Layer-2 real-Chromium integration tests, which could not execute in the
implementation sandbox: the managed Chromium binary cannot launch there
(missing OS shared libraries, e.g. `libnspr4.so`; no interactive/passwordless
`sudo` available to install them). Several contract-required real-engine
properties (real sandbox launch-flag inspection, real egress-containment
enforcement, real process-tree cleanup) are therefore verified only by code
inspection and the mocked test layer, not by a passing live run. Three real
bugs were found and fixed during implementation (task-id-generated-too-late
approval binding, an IP-literal domain-matching gap, and a URL-digest
mismatch for non-navigation approvals) — see
`docs/PHASE_10_IMPLEMENTATION_REPORT.md` §9 for detail; Codex should
specifically re-verify these fixes.

### Expected

An independent Codex read-only review confirms or refutes the
implementation report's self-assessment, ideally including running
`tests/test_browser_integration_real.py` in an environment with a working
Chromium (e.g. via `playwright install-deps` with root access, or a
container image with the needed shared libraries already present) and
reporting the actual pass/fail result.

### Next Step

Review completed 2026-07-11. See
`docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md` and B010. Phase 10 is not COMPLETE.

## B008 — Phase 10 activation decision pending

Status: RESOLVED (2026-07-11, Human Owner approval recorded in the Phase 10
implementation instruction)
Owner: Human Owner
Phase: Phase 10 (now active — see B009 for the follow-on final-gate blocker)
Severity: Low

### Problem

Phase 10 — Controlled Browser Automation planning (contract, threat model,
test plan, architecture) is complete and has been through one remediation
pass, but two Human Owner decisions remain before it can be implemented:
(1) whether to approve the scope expansion beyond the original
`docs/phases/PHASE_10_BROWSER_TOOLS.md` placeholder (read-only open/search/
extract only) to include field interaction and T2 form-submit/upload/
download; (2) whether to activate Phase 10 at all right now, including
reviewing the design points listed in
`docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` §15 (task-based execution
model, mandatory OS/container egress containment, deferred login, per-field
T2 approval, quarantine/promotion split, mandatory sandbox, and more).

### Resolution so far

Codex's independent contract review (2026-07-11) returned `READY WITH
REQUIRED CONTRACT FIXES`. Claude Sonnet completed a remediation pass the
same day resolving every required finding: replaced the unusable multi-
command session model with a single bounded task per CLI invocation; made
OS/container egress containment (or a locally controlled validating proxy)
a mandatory, fail-closed launch precondition instead of an open design
question; corrected the risk-tier table (no T1; every navigation, field
fill, and external effect is T2); deferred login/credential automation
entirely rather than gating it; strengthened quarantine isolation and made
download promotion its own approved operation; tightened audit privacy and
defined a normative lifecycle state machine; made all resource limits
normative; and required two test layers (mocked + real-browser isolated
integration). See `docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` for the
full record. **No browser code, dependency, CLI command, or test was
written or changed** in either the original drafting pass or this
remediation pass.

### Expected

`PHASE_CONTRACT.md`'s Active Phase line is updated to Phase 10 with the
exact approval statement given in that file's Phase 10 draft section, only
after the Human Owner has reviewed
`docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md`,
`docs/PHASE_10_BROWSER_THREAT_MODEL.md`,
`docs/PHASE_10_BROWSER_TEST_PLAN.md`,
`docs/PHASE_10_BROWSER_ARCHITECTURE.md`, and
`docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md`.

### Next Step

Resolved — see B009 for the current Phase 10 blocker (independent Codex
final-gate review).

## B007 — Phase 9 completion verification pending

Status: CLOSED (2026-07-11, Human Owner sign-off in PHASE_CONTRACT.md)
Owner: Codex (remediation) / Claude (independent verification + follow-up fixes)
Phase: Phase 9
Severity: High (resolved)

### Problem

Claude's independent review failed the prior Phase 9 implementation because folder
opening was absent, detached server management could not work across invocations,
server approval lacked Human Owner confirmation, audit denials lost request context,
and path checks discarded specific safe exception types.

### Expected

Comprehensive deterministic coverage, full-suite verification, CLI/audit smoke
checks, and a final security review before Phase 9 can be declared complete.

### Resolution

Codex completed the authorized remediation and local verification:
- Typed allowlisted folder opening on Linux/WSL and Windows
- Explicit Human Owner confirmation before approval minting
- Foreground loopback server lifecycle with Ctrl+C stop guidance
- Cross-invocation server status/stop commands and registry entries removed
- Denial/failure audit retains operation, project ID, origin, and risk tier
- PermissionEngine preserves original safe path exception subtypes
- Full suite: 560 passed, 0 failed, 0 skipped
- Audit verify: valid (0 events in isolated smoke data)
- Changed-file Ruff, compileall, and diff checks: pass
- Static process-bypass scan: process primitives only in hardened shell runner

Phase 9 status: REMEDIATED + LOCALLY VERIFIED — AWAITING INDEPENDENT RE-VERIFICATION.
B007: FIXED + AWAITING INDEPENDENT RE-VERIFICATION.

### Independent Re-Review (2026-07-11, Claude Sonnet)

Verdict: **PASS WITH NON-BLOCKING FINDINGS**. Fresh read-only review plus live CLI
smoke testing (real enrollment, real folder-open denial via missing `xdg-open`, real
foreground loopback dev-server launch cancelled by SIGINT) confirmed all five prior
findings fixed:
- C-1 folder opening: typed allowlisted launch, revocation/path-replacement denied,
  exactly-one terminal audit event, no launch pre-approval.
- C-2 server lifecycle: no detached/cross-invocation process management, Ctrl+C is
  the only stop path, no orphan process after exit, status/stop commands and
  registry capabilities absent.
- C-3 human confirmation: approval unforgeable outside `dev_server.py`, agent/voice
  path never supplies an approval object, consumption is durable and precedes launch.
- I-1 audit context: denial events retain operation/project/risk/origin, no
  path/argv/PID/token leakage.
- I-2 path exceptions: `SymlinkEscapeBlocked` (and other specific subtypes) now
  propagate through `PermissionEngine.require_path` instead of being erased.

Two non-blocking Important findings were recorded (duplicate DENY audit row on two
`_serve()` rejection paths; `canonical_project_id` duplicating rather than
independently verifying the project-path binding) plus one nice-to-have. All three
were fixed by Claude in the same session and re-verified: full suite went from 560
to **564 passed**, with 4 new regression tests; compileall, ruff, and
`git diff --check` all clean; live-reproduced the full enroll → serve-rejected →
serve-approved real foreground launch → Ctrl+C → clean cancellation flow again.
Full report: `docs/PHASE_9_INDEPENDENT_RECONFIRMATION.md`.

### Next Step

Human Owner sign-off recorded in `PHASE_CONTRACT.md` on 2026-07-11. Phase 9 is
COMPLETE. Phase 10 remains closed until the Human Owner separately authorizes it
there.

## B006 — Phase 8 gate failure: lifecycle audit coverage

Status: FIXED + VERIFIED (2026-07-11, Claude Sonnet re-gate)
Severity: High

F8-4 fixed: `voice.session.started`, `voice.session.completed`,
`voice.session.cancelled`, `voice.session.timed_out`, and `voice.session.failed`
events are now emitted; exactly-one-terminal invariant enforced via
`VoiceSessionLifecycle`. Supplemental verification: 484 passed, 2 skipped; 137
focused voice tests passed.

F8-1–F8-3 fixes preserved. See
`docs/PHASE_8_OPENCODE_TIMEOUT_VERIFICATION.md`.

## B005 — Phase 8 Human Owner approval required

Status: RESOLVED (2026-07-11)
Owner: Human Owner
Phase: Phase 8
Severity: High

### Problem

Re-gate completed by Claude Sonnet (same agent that built F8-4 — see HANDOFF.md
disclosure). Supplemental verification independently reconfirmed all four findings
F8-1 through F8-4 as fixed: 484 passed, 2 skipped, with 137 focused voice tests.
Human Owner approved Phase 8 as COMPLETE and authorized Phase 9.

### Expected

Approval was recorded in `PHASE_CONTRACT.md`.

### Next Step

Begin Phase 9 only within its active contract.

No open Phase 6 product or security blockers. Final gate passed with
non-blocking maintenance items recorded in `docs/PHASE_6_FINAL_GATE_REPORT.md`.

## B003 — Phase 7 read-only and secret-display gate findings

Status: Resolved (2026-07-11, Codex Phase 7 final gate)
Owner: Codex
Phase: Phase 7
Severity: High

### Problem

Dashboard GET paths can initialize storage through existing helper APIs, and
some untrusted display fields are not redacted for secret-shaped values.
Dashboard CLI port values are also not explicitly range-checked.

### Expected

Dashboard reads must never create or modify config/audit/memory storage, every
displayed untrusted value must be safely redacted, and invalid ports must fail
without invoking uvicorn.

### Next Step

Fixed with dashboard-only read-only SQLite/TOML access, recursive bounded
display sanitization, port validation, and bounded audit/payload loading.
Regression result: 347 passed, 2 skipped. See `docs/PHASE_7_FINAL_GATE_REPORT.md`.

## B004 — Fresh independent Phase 7 confirmation required

Status: RESOLVED (2026-07-11, Claude Sonnet independent reconfirmation)
Owner: —
Phase: Phase 7
Severity: —

### Resolution

Independent reconfirmation completed by Claude Sonnet. Verdict: PASS.
347 passed, 2 skipped. All four fixes verified. No production code modified.
See `docs/PHASE_7_INDEPENDENT_RECONFIRMATION.md`.

## B002 — Pytest unavailable in current container

Status: RESOLVED (2026-07-11, Claude Code Phase 6 review)
Owner: —
Phase: Phase 6
Severity: —

### Resolution

Full test suite run in the normal project environment (Python 3.11.15): **228 passed, 2 skipped**. Audit verification passed with 14 events. B002 is closed.

## B001 — Host pytest temp directory permissions

Status: Environment workaround applied
Owner: OpenCode / Human Owner
Phase: Phase 5
Severity: Low

### Problem

Plain `pytest` cannot create `C:\Users\BOSON-229\AppData\Local\Temp\pytest-of-BOSON-229` and fails at fixture setup with `WinError 5`.

### Expected

Pytest should be able to create its temporary directories.

### Next Step

Run pytest with `TEMP` and `TMP` pointed at a writable workspace directory, or repair host temp-directory permissions.

Template for new entries:

```markdown
## B00X — <short title>

Status: Open
Owner: <agent>
Phase: <phase>
Severity: <Low|Medium|High>

### Problem
<what is broken>

### Expected
<what should happen instead>

### Next Step
<concrete next action>
```
