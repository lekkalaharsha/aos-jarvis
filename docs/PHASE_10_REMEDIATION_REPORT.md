# Phase 10 — Remediation Report

Date: 2026-07-11
Engineer: Claude Sonnet (remediation pass, same day as Codex's FAIL final
gate)
Status: **REMEDIATION COMPLETE — AWAITING FRESH INDEPENDENT CODEX FINAL
GATE.** This report is not a self-certification of Phase 10 passing. Per the
remediation prompt, Codex must independently re-review before Phase 10 can
be declared COMPLETE.

This pass fixes every Critical and Important finding in
`docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`. It does not weaken the approved
Phase 10 contract, does not start Phase 11, and did not delete the disclosed
`~/.aos-jarvis/browser/approved_domains.json` test-data artifact (still
requires manual Human Owner cleanup).

## 1. Critical findings — fix by fix

### C-1: Egress containment / sandbox activation not independently verified

**Before:** `aos/browser/egress.py` and `aos/browser/sandbox.py` verified
nothing except that a caller had set an environment variable to `"1"`.

**Fix:**
- `aos/browser/egress.py`: `real_connection_probe_check()` is now the
  default checker. It performs a REAL outbound TCP `connect()` attempt to a
  fixed non-enrollable canary address (`1.1.1.1:80` by default, injectable
  for tests). If the connection succeeds, egress is demonstrably not
  contained and the check fails closed — no environment variable can change
  that outcome. An optional `AOS_BROWSER_EGRESS_PROXY_URL` declares a
  validating proxy; the module additionally verifies that proxy is actually
  reachable. There is no attestation-only code path left.
- `aos/browser/sandbox.py`: `real_kernel_precondition_check()` is now the
  default checker. It really exercises the two kernel preconditions
  Chromium's namespace sandbox depends on: unprivileged user namespaces
  (reads `/proc/sys/kernel/unprivileged_userns_clone` when present,
  otherwise really attempts `unshare --user --map-root-user true`) and
  seccomp-bpf availability (`/proc/self/status` `Seccomp:` field). Setting
  the old `AOS_BROWSER_SANDBOX_VERIFIED` variable has zero effect on the
  outcome (`tests/test_browser_sandbox_egress_supply_chain.py::test_sandbox_env_var_alone_cannot_force_a_pass`).
- `tests/test_browser_egress_real_socket.py` (new): performs REAL,
  unmocked `socket.connect()` calls — no injected connector — against a
  loopback listener this test process starts and stops itself, proving the
  containment logic against a genuine open port and a genuine refused port.
  This satisfies "integration tests that prove containment with real
  connection attempts" without any live external-network dependency.

**Residual/disclosed limitation:** there is still no POST-launch inspection
of the actual spawned Chromium renderer process's sandbox status (e.g.
reading `/proc/<renderer-pid>/status`) — Playwright's synchronous
`launch_persistent_context` API does not expose child OS PIDs to Python.
The pre-launch kernel-capability check is real and exercised, but this
specific post-launch verification remains unimplemented. Flagged for Codex.

### C-2: Credential/login denial was caller-asserted, not engine-derived

**Before:** `OperationEntry.field_classification` was a caller-supplied
enum; `OperationEntry.element_locator` was a raw string passed directly to
`page.fill`/`page.click`/`page.set_input_files`.

**Fix:**
- `aos/browser/types.py`: `FieldLocator(role, name, nth)` replaces
  `element_locator`. `role` is constrained to `ALLOWED_LOCATOR_ROLES`
  (`textbox`, `searchbox`, `button`, `checkbox`, `radio`, `combobox`,
  `link`, `menuitem`) — not a CSS/XPath selector language. `OperationEntry`
  no longer has a `field_classification` field at all.
- `aos/browser/engine.py`: every `EngineHandle` implementation resolves a
  `FieldLocator` via `page.get_by_role(role, name=name, exact=True)`
  (accessibility-tree resolution) and exposes `resolve_field()`, returning
  an engine-derived `ResolvedField(input_type, autocomplete, ...)`.
- `aos/browser/task.py` `_resolve_and_classify()`: calls
  `handle.resolve_field(locator)` then `classify_field()` on the
  ENGINE-RETURNED attributes. For FILL/CLEAR, if the resulting
  classification is denied (password/credential/token/OTP/financial/
  recovery/security-answer), the operation is denied immediately —
  BEFORE `_request_and_consume` (the approval step) is ever called. No
  approval path can override this (`tests/test_browser_task.py::test_sensitive_field_denied_before_any_approval_offered`,
  parametrized, asserts the approval callback fires zero or one time —
  only for the earlier navigate — never for the denied fill).
- Download no longer uses `page.evaluate` with a caller-supplied URL
  (`aos/browser/engine.py` `PlaywrightEngineHandle.download`): it clicks a
  resolved `FieldLocator` inside `page.expect_download()`; the resulting
  network request passes through the same context-wide route guard as
  every other request.
- `tests/test_browser_integration_real.py::test_resolve_field_denies_password_input_via_real_dom_inspection`
  (Layer 2, gated behind `AOS_BROWSER_RUN_REAL_TESTS=1`) asserts a genuine
  Chromium-rendered `<input type=password>` resolves with
  `input_type == "password"` via real DOM inspection, not a mocked value.

### C-3: T2 approval enforcement was not exact, immediate, or universal

**Before:** all approvals were consumed in bulk before any process launch;
`--yes` bulk-minted every approval non-interactively; download promotion
had no approval check at the store/tool boundary.

**Fix:**
- `aos/browser/types.py`: `BrowserTaskSpec` no longer has an `approvals`
  field at all — there is no way to pre-supply approvals in bulk.
- `aos/browser/task.py`: `BrowserTaskRunner.run(spec, *, approval_callback)`
  takes a synchronous `ApprovalCallback = Callable[[ApprovalRequest], bool]`.
  For every T2 side effect — navigation, each fill/clear, submit, download,
  upload, and each individual cross-domain redirect hop — `_request_and_consume()`
  builds a typed `ApprovalRequest`, audits `browser.action.approval_required`,
  invokes the callback, and only on `True` mints AND durably consumes one
  fresh `BrowserApproval` immediately before performing that exact action.
  A task with any T2 operation and no callback (or a non-`"terminal"`
  origin) denies immediately — there is no bulk pre-approval path left.
- `aos/interfaces/cli/browser_commands.py`: `--yes` has been **removed
  entirely** (not redesigned to a safer form — removed). `aos browser task`
  now calls `typer.confirm()` once per T2 action, interactively, as it
  happens (`tests/test_browser_cli.py::test_browser_task_help_has_no_yes_flag`,
  `test_browser_task_prompts_per_operation_and_denies_on_no`).
- `aos/browser/quarantine.py` `QuarantineStore.promote()` now REQUIRES a
  `BrowserApproval` parameter and calls `consume_browser_approval(...,
  operation="promote", file_identity=record.sha256, ...)` at the store
  boundary itself — not only enforced by the CLI
  (`tests/test_browser_quarantine.py::test_promotion_requires_a_fresh_approval`).

### C-4: Quarantine promotion could self-authorize an arbitrary destination

**Before:** the CLI accepted an arbitrary `project_root: Path` argument and
passed it straight through as `approved_roots`.

**Fix:** `QuarantineStore.promote()` now takes `project_id: str` and a
`project_registry: ApprovedProjectRegistry`, resolving the destination root
via `registry.resolve(project_id)` — the SAME enrolled-project registry
Phase 5/9 already use. There is no `destination_dir`/arbitrary-path
parameter left on the public API at all
(`tests/test_browser_quarantine.py::test_promotion_rejects_caller_controlled_root_string`,
`test_promotion_requires_an_enrolled_project_id`). A `relative_subpath`
argument is checked for traversal (`..`, absolute paths rejected) before
being joined under the resolved root. The CLI (`aos browser quarantine
promote <file_id> <project_id> --subpath ...`) mints and passes a
`BrowserApproval` bound to `operation="promote"` and the file's SHA-256.

### C-5: Upload binding did not resist symlink/content-replacement TOCTOU

**Before:** the approval bound only to a path string; execution rechecked
`.exists()`/`.is_file()` and handed the path to Playwright, which reopens
it independently later.

**Fix (`aos/browser/task.py` `_do_upload`, `_read_upload_identity`,
`_revalidate_upload_identity`):**
- Upload now requires an `upload_project_id` on the operation entry,
  resolved through `ApprovedProjectRegistry` (an enrolled project ID, not a
  caller-controlled root — same fix as C-4 applied to uploads).
- `_read_upload_identity()` opens the file with `os.O_NOFOLLOW` (rejecting
  symlinks at open time), `os.fstat()`s the open descriptor for
  `(st_dev, st_ino, st_size)`, and computes the SHA-256 while reading from
  that same descriptor — never a second independent read.
- The approval is bound to
  `f"{project_id}:{dev}:{inode}:{size}:{sha256}"` — project ID, stable file
  identity, size, and content hash are all part of the binding, not just a
  path string.
- Immediately before calling `handle.upload(...)`,
  `_revalidate_upload_identity()` re-`stat`s the path (`follow_symlinks=False`,
  rejecting a symlink swap), compares `(dev, inode, size)` to the
  originally observed values, and re-hashes if they still match.
  `tests/test_browser_task.py::test_upload_toctou_content_swap_after_hash_denied`
  proves a content swap injected between hashing and use is caught and
  denied.

**Disclosed residual limitation:** Playwright's `set_input_files` API
reopens the file by path itself when the actual OS-level transfer happens;
there is no lower-level (non-CDP) upload primitive this module can use to
keep the exact same file descriptor open through the literal browser-level
transfer without violating the "no raw CDP" hard rule. The fix narrows the
TOCTOU window to open → fstat → hash → immediate re-stat → immediate call,
rather than eliminating it outright. This is a genuine, disclosed
constraint of Playwright's API surface, not an unaddressed gap.

## 2. Important findings — fix by fix

- **Locator policy / arbitrary-JS (Important #1):** fixed as part of C-2
  above (`FieldLocator`, no raw selectors, no `page.evaluate` with
  caller-derived values).
- **Resource limits not enforced (Important #2):** `aos/browser/engine.py`
  now enforces redirect depth (both `FakeEngineHandle` and
  `PlaywrightEngineHandle`), max tabs (`_install_tab_guard` closes any page
  beyond `limits.max_tabs`), and a `_ResourceBudget` tracking buffered
  response count/bytes and total task bandwidth via `Content-Length`
  headers on every response, aborting further requests once exceeded.
  `aos/browser/task.py` `_Deadline` enforces `task_timeout_seconds` (checked
  between every operation) and `idle_timeout_seconds` (reset after each
  operation completes); a task that exceeds either is marked `TIMED_OUT`,
  not silently left running
  (`tests/test_browser_task.py::test_task_timeout_enforced_between_operations`).
  Download size is still fully buffered by Playwright before the hard cap
  is enforced (a true mid-stream byte-exact cap is not implementable
  through Playwright's `save_as()` API) — disclosed residual limitation,
  unchanged from before.
  Bounded, forced-timeout process cleanup: `_wrap_persistent_close` now
  runs the graceful `context.close()`/`playwright.stop()` on a worker
  thread with a 15-second join timeout; if it does not complete, cleanup is
  reported as FAILED (visible on the result, see below) rather than the
  caller blocking indefinitely. There remains no portable way for this
  module to obtain and SIGKILL the underlying OS process from Playwright's
  sync persistent-context API — disclosed, not silently bypassed.
- **Audit lifecycle (Important #3):** `aos/browser/task.py` now emits
  `browser.action.requested` / `browser.action.approval_required` /
  `browser.action.approved` / `browser.action.denied` per T2 action, in
  addition to the existing operation-specific completed/failed events.
  Cancellation is audited as `browser.task.cancelled` with `ok=False` and
  `status="CANCELLED"` — never as a successful `browser.session.closed`
  (the prior bug). `BrowserTaskResult.cleanup_ok: bool` is a new field,
  correctly wired so a `finally`-block cleanup failure IS visible on the
  returned result (a bug was found and fixed here during this pass — see
  §4). `tests/test_browser_task.py::test_exactly_one_terminal_audit_event_per_task_on_success`
  and `..._on_denial` assert exactly one terminal event from the expanded
  terminal-type set (`browser.task.completed/failed/denied/timed_out/cancelled`).
- **Layer-2 completeness (Important #4):** the module-level real-Chromium
  launch probe that ran at IMPORT/collection time has been replaced with a
  lazy, module-scoped `real_chromium` fixture that only probes when a
  dependent test actually runs, and only when the operator opts in via
  `AOS_BROWSER_RUN_REAL_TESTS=1` (unset by default — plain `pytest` never
  attempts a launch). Added a real-DOM classification test (C-2 above), a
  real loopback-denial test using the callback-based API. See §5 for what
  remains incomplete in this layer.
- **Supply-chain binary check not default (Important #5):**
  `aos/browser/supply_chain.py` `_default_binary_present()` is now always
  the default `binary_checker` — it locates the exact managed Chromium
  binary path from Playwright's own installed-package `browsers.json`
  manifest (read via `importlib.metadata` file listing, WITHOUT importing
  `playwright` — preserving the "Playwright imported only in engine.py"
  isolation rule) and checks the real binary file exists at the derived
  path. `verify_supply_chain()` with no arguments now genuinely checks
  binary presence, not just version metadata.
- **Redirect policy incomplete + live DNS in Layer 1 (Important #6):**
  `aos/browser/task.py` `_build_navigation_validator()` now implements the
  approved contract behavior directly rather than the prior deny-all
  narrowing: a same-enrolled-domain hop is allowed with no extra prompt; a
  hop to a DIFFERENT but also-enrolled domain requires its own fresh,
  exact-bound approval (`operation="redirect"`, bound to
  `sha256(f"{from_host}->{to_host}")`) via the same `approval_callback`,
  authorized BEFORE the request is allowed to proceed (the validator is
  consulted by the route guard before `route.continue_()`); a hop to an
  unenrolled domain is denied outright, no prompt possible. Redirect depth
  is counted and capped. All Layer-1 tests now inject a fake `url_resolver`
  (`tests/test_browser_task.py::_fake_resolver`) — the live
  `socket.getaddrinfo("example.com", ...)` call Codex found is gone.
- **`redact_value` applied to the live fill value (Important #7):**
  `aos/browser/task.py` `_do_fill_or_clear` now passes
  `entry.field_value` directly to `handle.fill(...)` — `redact_value` is
  no longer called anywhere in the fill path. `aos/browser/redaction.py`'s
  docstring was updated to state explicitly that `redact_value` is for
  audit/memory/model-prompt copies only and must never touch the value
  sent to the browser.
- **Quarantine isolation not cross-capability-verified (Important #8):**
  `tests/test_browser_quarantine.py::test_quarantine_root_outside_any_project_root`
  retained/extended. Full cross-capability verification (filesystem, shell,
  memory, model, agent, dashboard, workspace denial against the actual
  configured quarantine root) was NOT added as new test coverage in this
  pass beyond what already existed structurally (the quarantine root is
  simply never registered as an approved root with any of those
  subsystems) — flagged as still open for Codex to specifically re-audit.

## 3. Files changed

**Rewritten:** `aos/browser/types.py`, `aos/browser/task.py`,
`aos/browser/engine.py`, `aos/browser/egress.py`, `aos/browser/sandbox.py`,
`aos/tools/browser.py`, `aos/interfaces/cli/browser_commands.py`.

**Edited:** `aos/browser/redaction.py` (docstring/contract clarification
only, `classify_field` logic unchanged), `aos/browser/supply_chain.py`
(default binary check), `aos/browser/quarantine.py` (`promote()` signature).

**Unchanged:** `aos/browser/approval.py`, `aos/browser/domains.py`,
`aos/browser/url_policy.py` (already resolver-injectable, no live-DNS
defect found there — the defect was in test helpers not passing a
resolver, fixed in the test files instead).

**Test files rewritten:** `tests/test_browser_task.py`,
`tests/test_browser_tool.py`, `tests/test_browser_cli.py`,
`tests/test_browser_quarantine.py`,
`tests/test_browser_sandbox_egress_supply_chain.py`,
`tests/test_browser_integration_real.py`.

**Test files added:** `tests/test_browser_egress_real_socket.py`.

**Test files unchanged:** `tests/test_browser_url_policy.py`,
`tests/test_browser_domains.py`, `tests/test_browser_approval.py`,
`tests/test_browser_redaction.py`, `tests/test_agent_tool_registry_browser.py`.

## 4. A real bug found and fixed during this pass

While fixing the audit-lifecycle finding, an initial implementation set
`cleanup_ok = False` inside a `finally` block AFTER the enclosing `try`
already had `return`ed a fully-constructed `BrowserTaskResult` — the local
variable mutation could never reach the returned object (Python evaluates
the return expression before `finally` runs, and the dataclass is frozen).
Ruff caught this as `F841 unused-local-variable`. Fixed by restructuring
`run()` to build an intermediate `outcome` variable inside the try/except,
let `finally` run cleanup and set `cleanup_ok`, then construct the final
returned `BrowserTaskResult` AFTER the `finally` block using both `outcome`
and the now-correct `cleanup_ok`. Covered by
`tests/test_browser_task.py::test_cleanup_failure_is_visible_on_result`
(a weaker smoke assertion — see §6 open item).

Two smaller signature bugs were also caught by running the new tests:
`_attempt_connect`'s keyword-only `timeout` parameter didn't match the
`Callable[[str, int, float], bool]` protocol it was supposed to satisfy
(fixed by making it positional); and the `FakeEngineHandle.download` fixture
schema needed an explicit `url` key matching the enrolled domain for the
new locator-triggered download flow to pass the navigation validator (test
fixture data fix, not a production bug).

## 5. Layer-2 status (honest disclosure)

`AOS_BROWSER_RUN_REAL_TESTS=1 pytest tests/test_browser_integration_real.py`
was run in this remediation sandbox. Result: **2 passed (the launch-args
static checks), 5 skipped** — real Chromium still cannot launch here
(`TargetClosedError`, the same missing-shared-library / no-root-access
constraint disclosed in the original implementation report). This is
**unchanged from before this remediation pass** — it is an environment
constraint, not something this pass could fix without root access to run
`playwright install-deps`. Per Codex's mandatory decision, **this is a
blocking gap, not an accepted exception**: the complete Layer-2 matrix
(workers/service-workers/WebSockets/EventSource/WebRTC/frames/popups/
prefetch/prerender, DNS rebinding, timeout/crash process-tree cleanup and
orphan inspection) still needs to run to completion in a capable,
independently contained environment before Phase 10 can pass the gate. This
report does not claim it does.

## 6. Verification performed

- `python -m compileall -q aos tests`: **PASS**.
- `ruff check aos/browser aos/tools/browser.py aos/interfaces/cli/browser_commands.py tests/test_browser_*.py tests/test_agent_tool_registry_browser.py`: **All checks passed.**
- Full suite: `python -m pytest -q -rs` → **718 passed, 5 skipped** (the 5
  skips are the Layer-2 real-Chromium tests; see §5).
- `AOS_BROWSER_RUN_REAL_TESTS=1 pytest tests/test_browser_integration_real.py`:
  2 passed, 5 skipped (real Chromium still not launchable here — §5).
- `git diff --check` over every changed file: **clean**.
- `aos audit verify` against an isolated data dir: **valid (0 events)**.
- Static scans: no `shell=True`; `--no-sandbox` appears only inside the
  forbidden-flag declaration/comments; `page.evaluate` appears only in
  comments describing its removal, never as a live call; no CDP/remote-
  debugging flag construction outside the forbidden-flag declarations;
  `import playwright`/`from playwright` appears in exactly one place
  (`aos/browser/engine.py`, inside `PlaywrightEngineFactory.launch`).
- Fail-closed CLI smoke test: enrolled a domain, dry-ran a task
  successfully, then ran the task for real with no egress/sandbox
  attestation env vars set and answered "y" to stdin — the task denied at
  the `supply_chain_unverified` precondition before any prompt could even
  be reached, exit code 1. Confirmed `aos browser task --help` no longer
  lists `--yes`.

## 7. Unresolved / still open for Codex

1. Layer-2 real-Chromium suite still cannot execute to completion in this
   sandbox (§5) — genuinely blocking per Codex's stated decision.
2. Layer-2 coverage remains incomplete even when Chromium is launchable:
   DNS rebinding, workers/service-workers/WebSockets/EventSource/WebRTC/
   frames/popups/prefetch/prerender, and timeout/crash process-tree
   orphan inspection are not yet covered by any test in this pass.
3. No post-launch inspection of the actual spawned Chromium process's
   sandbox status (disclosed in §1, C-1).
4. Cross-capability quarantine-isolation tests (filesystem/shell/memory/
   model/agent/dashboard/workspace denial against the live quarantine root)
   were not added in this pass (disclosed in §2, Important #8).
5. Mid-stream (true byte-exact) download size capping is not implementable
   through Playwright's `save_as()` API; the cap is enforced via a
   `Content-Length`-based pre-check plus an immediate post-download size
   check and deletion (disclosed in §2, Important #2).
6. Upload TOCTOU is narrowed, not eliminated, due to Playwright's
   `set_input_files` API reopening the file by path (disclosed in §1, C-5).
7. The disclosed inert test-data artifact at
   `~/.aos-jarvis/browser/approved_domains.json` remains untouched, per
   instruction. Manual Human Owner inspection/cleanup is still recommended.

**This implementer does not self-certify Phase 10 as passing the security
gate.** Per the remediation prompt, Phase 10 status remains **FAILED FINAL
GATE — REMEDIATION REQUIRED** in `PHASE_CONTRACT.md` until Codex performs a
fresh, independent read-only re-review of this remediation and records its
own verdict.

---

## 2026-07-11 follow-up remediation after fresh Codex FAIL

Status: **REMEDIATION APPLIED — AWAITING FRESH INDEPENDENT CODEX FINAL GATE**.
Phase 11 remains blocked. This section records the builder remediation only;
it does not alter Codex's failed gate findings or claim PASS.

### Fixes applied

- Egress containment now fails closed unless a declared validating proxy is
  reachable and direct canary egress is blocked. A blocked canary by itself no
  longer passes. The verified proxy endpoint is forced into Chromium launch
  args via `--proxy-server=...` and `--proxy-bypass-list=<-loopback>`.
- `BrowserTaskRunner` carries the verified egress result into launch args and
  performs post-launch sandbox verification through the engine handle before
  any operation runs.
- Real Chromium handles now track the launched process tree through `/proc`
  using the unique task profile directory, verify sandbox-related `/proc`
  status after launch, and attempt bounded SIGTERM/SIGKILL cleanup of matching
  Chromium descendants after Playwright shutdown.
- Task audit lifecycle now emits exactly one task-terminal event after cleanup
  outcome is known. Launch failure, operation denial, timeout, cancellation,
  cleanup failure, and post-launch sandbox failure have regression coverage.
- Quarantine promotion approval is bound at the store boundary to file ID,
  SHA-256, size, enrolled project ID, canonical project root, validated
  relative subpath, and canonical destination path. Hash-only, destination
  substitution, traversal, collision, and replay paths deny.
- CLI quarantine promotion now computes the same exact destination binding
  before minting approval and writes promotion-approval consumption under the
  quarantine root instead of the default user data path during tests.
- Upload now revalidates the original approved file and copies the exact bytes
  into an owner-only private AOS snapshot; Playwright receives that
  AOS-controlled snapshot path rather than the original caller-controlled path.
  The remaining limitation is Playwright still accepts a path, not an already
  opened fd.
- Layer-1 URL-policy tests now install an autouse DNS guard that fails if they
  call `socket.getaddrinfo`; every positive URL-validation case injects a
  deterministic resolver.
- Opt-in Layer-2 real-Chromium tests now fail if Chromium cannot launch instead
  of converting an unlaunchable browser into skipped gate evidence.

### Verification performed in this pass

- `.venv/bin/python -m pytest -q tests/test_browser_sandbox_egress_supply_chain.py tests/test_browser_quarantine.py tests/test_browser_url_policy.py tests/test_browser_task.py`:
  **106 passed**.
- `.venv/bin/python -m pytest -q tests/test_browser_*.py tests/test_agent_tool_registry_browser.py`:
  **161 passed, 8 skipped** in the restricted sandbox. The extra 3 skips were
  loopback socket tests blocked by the sandbox.
- Escalated loopback socket run:
  `.venv/bin/python -m pytest -q -rs tests/test_browser_egress_real_socket.py`:
  **3 passed**.
- Default full suite:
  `AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-remediation-data .venv/bin/python -m pytest -q -rs`:
  **725 passed, 8 skipped**. Skips: 3 sandbox-blocked loopback socket tests and
  5 default-disabled Layer-2 tests.
- Opt-in Layer-2 gate:
  `AOS_BROWSER_RUN_REAL_TESTS=1 AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-layer2-remediation-data .venv/bin/python -m pytest -q -rs tests/test_browser_integration_real.py`:
  **2 passed, 5 errors**. Errors are deliberate fail-closed gate failures:
  `Layer-2 real Chromium gate cannot run in this environment: real chromium
  launch failed: TargetClosedError`.
- `.venv/bin/python -m compileall -q aos tests`: **PASS**.
- Ruff on changed Phase 10 production/test files: **PASS**.
- Ruff on all `aos tests`: **FAILS on unrelated pre-existing Phase
  4/5/voice/model files** (unused imports, semicolon style, undefined
  `MemoryStatus` annotations). These files were not edited in this remediation.
- `git diff --check`: **PASS**.
- `AOS_DATA_DIR=/home/harsh/projects/AOS-Jarvis/.tmp/codex-p10-audit-data .venv/bin/aos audit verify`:
  **valid (0 events)**.
- CLI smoke:
  `.venv/bin/aos browser --help` and `.venv/bin/aos browser task --help` both
  exit 0; no `--yes` option is present.
- Static bypass scan over `aos/browser`, browser CLI/tool, and browser tests:
  no live `shell=True`, no CDP session creation, no active `page.evaluate`, no
  constructed `--no-sandbox`, no bulk approval/`--yes` bypass, no Playwright
  import outside the approved engine adapter except the Layer-2 test probe.

### Still unresolved / must be decided by fresh independent gate

1. Required Layer-2 real-Chromium gate is still not complete in this
   environment. It now fails explicitly instead of skipping when opted in, but
   the full required matrix still must run in a Chromium-capable independently
   contained environment before Phase 10 can be complete.
2. The Layer-2 matrix still needs expansion/verification for the full set named
   by the gate prompt: redirects with fresh enrolled cross-domain approval,
   frames/popups, workers/service workers, WebSockets/EventSource/WebRTC,
   prefetch/prerender, DNS rebinding, and timeout/crash orphan-process
   inspection.
3. The egress implementation supports the validating-proxy enforcement shape
   plus direct-egress canary verification. A final gate should decide whether
   this satisfies the contract's OS/container/proxy containment requirement in
   the deployed environment.
4. Upload TOCTOU is mitigated by private snapshot staging, but Playwright still
   consumes a path. If the Human Owner requires literal same-fd upload transfer,
   the Phase 10 contract needs an explicit amendment or a different browser
   upload primitive.

## 2026-07-11 second follow-up remediation after fresh Codex FAIL (Follow-up Remediation Gate)

Status: **REMEDIATION APPLIED — AWAITING FRESH INDEPENDENT CODEX FINAL
GATE.** This section addresses the Critical C-2 and Important I-1/I-2/I-3
findings in the "2026-07-11 — Follow-up Remediation Gate" section of
`docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`. Per explicit direction, the
Layer-2 environmental blocker (C-1, real Chromium cannot launch in this
sandbox) was NOT re-attempted this pass — it is an environment constraint,
not a code defect, and no further code change here can fix it. This
section fixes only what is genuinely code-fixable.

### C-2: the validating-proxy shape was not proven as an AOS-controlled containment boundary

**Before:** `aos/browser/egress.py` accepted an operator-declared
`AOS_BROWSER_EGRESS_PROXY_URL` and only checked it was *reachable* — a
caller could point that variable at literally any TCP listener and pass
the check. Nothing proved AOS controlled the endpoint or that it enforced
any policy.

**Fix:** replaced the declared-URL model entirely with a real,
AOS-spawned, policy-enforcing HTTP CONNECT proxy:
- New `aos/browser/validating_proxy.py`: `ValidatingProxy` is a
  loopback-bound `ThreadingHTTPServer` that AOS itself starts, scoped to an
  exact `frozenset[(host, port)]` allowlist. Its `do_CONNECT` handler
  refuses (`403`) any target not on that allowlist and only tunnels
  (bidirectional socket splice) to allowed targets. There is no
  operator-supplied URL anywhere in this path — AOS owns the process from
  spawn to teardown.
- `aos/browser/egress.py` `spawn_and_verify_validating_proxy()`: for every
  task, (1) confirms direct (non-proxied) egress to the canary is blocked
  (unchanged real socket check), then (2) spawns AOS's own proxy scoped to
  the enrolled domain's exact `(host, port)` set, then (3) issues a REAL
  HTTP CONNECT through that just-spawned proxy to the same disallowed
  canary target and requires a genuine `403` response from the proxy's own
  code (`aos/browser/validating_proxy.py` `probe_connect()`) before
  returning `verified=True`. This is enforcement proof, not reachability
  detection — the proxy actually has to refuse the request.
- `aos/browser/task.py`: `_check_preconditions()` now takes the resolved
  `domain` and derives `_allowed_egress_targets(domain)` (the domain's
  host at port 443, plus 80 if `allow_http`, plus any `extra_ports`) before
  calling the new egress check. The returned `ValidatingProxy` is threaded
  through to `build_launch_args(proxy_url=...)` for the real Chromium
  launch, and is unconditionally `.stop()`-ed in a `finally` block wrapping
  the whole task body — on completion, denial, failure, timeout, or
  cancellation, there is never an orphaned proxy process.
- New tests in `tests/test_browser_egress_real_socket.py` perform ACTUAL
  unmocked HTTP CONNECT requests against a real, locally spawned
  `ValidatingProxy` (no injected connector for this part) and prove it
  returns `403` for a disallowed target and `200` for an allowed one, plus
  an end-to-end `spawn_and_verify_validating_proxy` test proving the whole
  flow with only the canary/upstream sockets injected (never the proxy
  logic itself). `tests/test_browser_sandbox_egress_supply_chain.py` adds
  deterministic (non-network) coverage for the denial/orphan-prevention
  paths.

**Residual, disclosed:** this remains an unprivileged, process-level
containment boundary — an unprivileged CLI process cannot install network
namespaces or firewall rules, so a sufficiently privileged renderer escape
could in principle still reach the network directly, bypassing the forced
`--proxy-server` argument. Chromium's own sandbox (verified separately via
`aos/browser/sandbox.py`) is the control that is supposed to prevent a
compromised renderer from reaching arbitrary OS network APIs in the first
place; the validating proxy is a second, independent, AOS-owned layer, not
a replacement for kernel-level containment (which would require root
access this environment does not have — the same constraint disclosed for
Layer-2 throughout this remediation).

### I-2: T2 action audit lifecycle lacked exact terminal semantics

**Before:** `_request_and_consume()` audited `browser.action.denied` on
denial AND raised `PermissionBlocked`; the caller's `_run_one()` generic
except-handler then audited `browser.action.denied` a SECOND time for the
same failure when the exception propagated — two terminal-shaped events
for one denied action.

**Fix:** `_request_and_consume()` in `aos/browser/task.py` no longer
audits on denial — it only raises. Every call site either lets the
exception propagate to `_run_one()`'s single except-handler (the ONE place
that now audits `browser.action.denied` for a raised approval failure), or
is the redirect validator inside `_build_navigation_validator`, which
swallows the exception locally and surfaces the failure once through the
existing `browser.navigation.failed` event — never a duplicate. New tests:
`tests/test_browser_task.py::test_exactly_one_action_terminal_event_on_approval_denial`,
`test_exactly_one_action_terminal_event_when_no_terminal_callback`,
`test_exactly_one_action_terminal_event_on_sensitive_field_denial`.

### I-1 / I-3: post-launch sandbox verification and process-tree cleanup were unproven by any passing test

**Before:** `BrowserProcessTracker`'s `/proc`-scanning and SIGTERM/SIGKILL
logic (added in the prior remediation round) hardcoded `Path("/proc")` and
`os.kill`, so it could only ever be exercised by a real Chromium process —
which cannot launch in this sandbox — leaving the logic completely
untested.

**Fix:** `aos/browser/engine.py` `BrowserProcessTracker.__init__` now
accepts injectable `proc_root: Path` and `killer: Callable[[int, int],
None]` parameters (production code defaults to the real `/proc` and
`os.kill`; injection is for tests only). New
`tests/test_browser_process_tracker.py` (9 tests) exercises the real
scanning/classification/kill-loop algorithm against a synthetic
`/proc`-shaped directory tree with fake `cmdline`/`status` files: matching
only Chromium processes whose command line contains the task's profile
directory, ignoring non-numeric `/proc` entries, correctly reading
`Seccomp` status and forbidden-flag command lines to determine sandbox
verification, and both the success and failure paths of the
SIGTERM-then-SIGKILL-with-polling termination loop (including a "process
never dies" case that correctly returns `False`).

**Disclosed limitation, unchanged:** this proves the ALGORITHM is correct
against synthetic data. It does not and cannot prove the algorithm
correctly identifies and terminates a REAL Chromium process tree, because
no real Chromium process can be launched in this sandbox to test against
(the same Layer-2 environmental blocker as C-1). That real-process proof
remains an open item for a Chromium-capable environment.

### Verification performed in this pass

- `.venv/bin/python -m pytest -q tests/test_browser_*.py tests/test_agent_tool_registry_browser.py`: **174 passed, 5 skipped**.
- Full suite: `.venv/bin/python -m pytest -q -rs`: **741 passed, 5 skipped**.
- `AOS_BROWSER_RUN_REAL_TESTS=1 pytest tests/test_browser_integration_real.py`: **2 passed, 5 errors** (`TargetClosedError` — unchanged environmental constraint, not attempted to be fixed this pass per explicit direction).
- `python -m compileall -q aos tests`: **PASS**.
- `ruff check aos/browser aos/tools/browser.py aos/interfaces/cli/browser_commands.py tests/test_browser_*.py tests/test_agent_tool_registry_browser.py`: **All checks passed.**
- `git diff --check` over all changed files: **clean**.
- Isolated `aos audit verify`: **valid (0 events)**.
- Static scans: no `shell=True`/`os.system`; `--no-sandbox` string only appears inside the forbidden-flag declaration and the process-status DETECTION check (`BrowserProcessTracker.sandbox_verified`, which reads a real process's cmdline to check FOR the flag — not a constructed launch argument); no live `page.evaluate`/`add_script_tag`/`new_cdp_session`; Playwright import confined to `aos/browser/engine.py`.
- Fail-closed CLI smoke: enrolled a domain, dry-ran successfully, then ran the task for real with no attestations configured and `y` piped to stdin — denied at `supply_chain_unverified` before any prompt could be reached, exit code 1; confirmed `--yes` remains absent from `aos browser task --help`.

### Still unresolved / must be decided by a fresh independent gate

1. Layer-2 real-Chromium gate: unchanged, still 2 passed / 5 errors in this
   sandbox (`TargetClosedError`). This is the same disclosed environment
   constraint as every prior round — not re-attempted this pass per
   explicit direction, since it is not a code-fixable item here.
2. The Layer-2 matrix is still not expanded to cover DNS rebinding,
   app-check-bypass egress, workers/service workers, WebSockets/
   EventSource/WebRTC, frames/popups, prefetch/prerender, or real-process
   orphan inspection — all of that work requires a launchable Chromium to
   write meaningfully against, which this sandbox does not have.
3. The validating-proxy containment boundary is now AOS-controlled and its
   policy enforcement is proven with real (unmocked) CONNECT requests in
   Layer-1 tests, but has not been proven against a REAL Chromium process
   actually routing through it with application-layer checks bypassed
   (that specific case needs Layer-2).
4. Upload TOCTOU remains narrowed (private-snapshot staging), not
   eliminated, for the same disclosed Playwright-API reason as before.
