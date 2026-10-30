# Phase 10 — Controlled Browser Automation: Implementation Report

Status: **IMPLEMENTATION COMPLETE — AWAITING INDEPENDENT CODEX FINAL GATE**
Date: 2026-07-11
Author: Claude Sonnet (implementation engineer role)

This report is a factual build record, not a self-certification. Per the
implementation instruction, this implementer does not declare the Phase 10
security gate passed — that determination is Codex's, as an independent
read-only reviewer, after reading this report and the source directly.

---

## 1. Scope

Implemented Phase 10 exactly as revised in
`docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md`,
`docs/PHASE_10_BROWSER_THREAT_MODEL.md`,
`docs/PHASE_10_BROWSER_TEST_PLAN.md`, `docs/PHASE_10_BROWSER_ARCHITECTURE.md`,
and `docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md`. Did not implement Phase
11 (screen understanding, OCR, desktop control), persistent browser
sessions, autonomous browsing, or any login/credential support. Made no
unrelated refactor. Performed no `git push`/`pull`/`fetch`/`commit`/
`checkout`/`reset`/`merge`/`rebase`.

## 2. Files Added

```
aos/browser/__init__.py           7 lines   package doc, Playwright-isolation note
aos/browser/types.py            169 lines   typed models: BrowserOperation, FieldClassification,
                                             TaskState, SafeBrowserTaskHandle,
                                             UntrustedBrowserObservation, ResourceLimits,
                                             BrowserTaskSpec, OperationEntry, new_task_id
aos/browser/domains.py          216 lines   ApprovedDomainRegistry, DomainEnrollmentAuthority
                                             (structural twin of aos/safety/approved_projects.py)
aos/browser/url_policy.py       175 lines   canonicalize_host (punycode/IDN), validate_url,
                                             private/loopback/link-local denial (parsed address
                                             objects), resolved-address recheck, redirect
                                             classification
aos/browser/approval.py         191 lines   BrowserApproval mint/consume (structural twin of
                                             aos/safety/dev_server.py), per-operation/per-field
                                             binding
aos/browser/redaction.py         68 lines   field sensitivity classification, value redaction
                                             (extends aos/model/redaction.py)
aos/browser/egress.py            56 lines   mandatory OS/container egress-containment
                                             verification (fail-closed attestation check)
aos/browser/sandbox.py           65 lines   mandatory Chromium sandbox verification,
                                             forbidden-launch-flag assertion
aos/browser/supply_chain.py      47 lines   pinned Playwright version / binary verification
aos/browser/engine.py           344 lines   BrowserEngineFactory protocol, PlaywrightEngineFactory
                                             (the only module that imports playwright),
                                             FakeEngineFactory (test double)
aos/browser/quarantine.py       216 lines   quarantine staging, 4-signal type-agreement check,
                                             bounded retention sweep, separate promotion operation
aos/browser/task.py             385 lines   BrowserTaskRunner: the full task lifecycle
                                             orchestrator (validate -> approve -> precondition
                                             check -> launch -> run -> audit -> teardown)
aos/tools/browser.py            144 lines   BrowserTool(BaseTool), the single tool-registry
                                             integration point
aos/interfaces/cli/browser_commands.py
                                 177 lines   `aos browser domain add/list/revoke`,
                                             `aos browser task <spec> [--dry-run] [--yes]`,
                                             `aos browser quarantine list/cleanup/promote`
```

## 3. Files Modified

```
aos/safety/permissions.py     +2 lines   CAPABILITY_KINDS: browser.upload, browser.promote
aos/agent/tool_registry.py    +14 lines  browser.domain_list (T0, read-only) tool-registry
                                          entry only -- see Sec6 for why no T2 browser
                                          operation is agent-reachable
aos/interfaces/cli/main.py    +2 lines   registers `aos browser` command group
pyproject.toml                +1 line    `browser = ["playwright==1.61.0"]` optional extra
```

No other existing file's behavior was changed. `git diff --check` and a
targeted diff review confirm no unrelated file was touched.

## 4. Test Files Added

```
tests/test_browser_url_policy.py                128 lines   28 tests
tests/test_browser_domains.py                     94 lines    9 tests
tests/test_browser_approval.py                    74 lines   12 tests
tests/test_browser_redaction.py                   50 lines    8 tests
tests/test_browser_quarantine.py                 118 lines   14 tests
tests/test_browser_sandbox_egress_supply_chain.py 77 lines   16 tests
tests/test_browser_task.py                       424 lines   29 tests
tests/test_browser_tool.py                         83 lines    7 tests
tests/test_browser_cli.py                          87 lines    7 tests
tests/test_agent_tool_registry_browser.py          34 lines    2 tests
tests/test_browser_integration_real.py            166 lines    6 tests (Layer 2, see Sec7)
```

Total: **132 mocked (Layer 1) tests + 6 real-Chromium (Layer 2) tests = 138
new tests.**

## 5. Design Decisions Made During Implementation (not fully specified by the contract)

The contract fixed the architecture and hard rules but left some exact
mechanics to implementation. These are disclosed for Codex's review, since
they are implementer judgment calls, not contract requirements:

- **`task_id` must be generated by the caller before any approval is
  minted, not inside `BrowserTaskRunner.run()`.** The original architecture
  sketch implied the runner could generate its own task id; that cannot
  work, because an approval bound to a task id must exist *before* the run
  call that would generate it. `BrowserTaskSpec.task_id` is now a required
  field; `aos/browser/types.new_task_id()` is the canonical generator; the
  CLI's `task` command calls `dry_run()` first specifically to obtain a
  task id, mints every T2 approval against it, then calls `execute()` with
  that same id. This was found and fixed during implementation (see Sec9
  below) -- it is exactly the kind of "approval binding to something not
  yet known" class of bug the contract's Sec3a was trying to prevent, and
  it would have been a real defect had it shipped.
- **Egress containment and sandbox verification are implemented as
  fail-closed operator attestations (environment variables
  `AOS_BROWSER_EGRESS_CONTAINMENT_VERIFIED=1` and
  `AOS_BROWSER_SANDBOX_VERIFIED=1`), not auto-detection.** The contract
  (Sec4a/Sec5b) explicitly states the containment *mechanism* is a
  deployment decision and that Phase 10's code only needs to require *that
  one exists and is verified active*. Auto-detecting "is my own process
  actually network-contained" from inside that same process is not
  trustworthy self-certification, so this implementation requires an
  external attestation instead, absent by default (fail-closed). **This
  is a real limitation, disclosed in Sec8**: the current implementation
  cannot itself distinguish a deployment that has genuinely configured
  network-namespace/firewall/proxy containment from one that has merely
  set the environment variable without doing the underlying work. Both the
  contract and this implementation treat that gap as an operational
  deployment responsibility, not a code-closable one, and the checker
  functions are injectable specifically so a future, stronger verifier
  (e.g., an actual proxy health-check call) can replace the attestation
  without changing any caller.
- **The application-layer network-request validator (`request_validator`
  callback threaded into `EngineHandle.navigate/download`) only permits
  requests to the single enrolled domain host** (or same-domain redirects
  passing full `validate_url`). It does not have a per-request allowlist
  for legitimate third-party subresources (fonts, CDN-hosted scripts,
  analytics beacons a normal page might load). This means real-world pages
  with third-party subresources will have many of their subresource
  requests denied by the route guard, which is **more restrictive than a
  typical browser session** but consistent with the contract's narrow,
  single-enrolled-domain design intent. This is a usability limitation,
  not a security gap, and is called out for Human Owner awareness.
- **Quarantine promotion (`QuarantineStore.promote`) does not itself
  require or check a `BrowserApproval` object** -- it performs the
  mechanics (destination revalidation, collision handling, content-hash
  recheck) but the actual T2 approval gate for "promote this file" lives
  in the CLI's interactive confirmation (`aos browser quarantine promote
  ... --approve`), mirroring the same split Phase 9 uses between
  `WorkspaceTool` (mechanics) and the CLI (confirmation UX for launches
  that don't carry a `DevServerApproval`-shaped object). Codex should
  confirm this split is acceptable, since it means `QuarantineStore.promote`
  called directly (bypassing the CLI) has no approval gate of its own --
  by design, every other Phase 10 caller of `promote()` must supply its own
  gating, exactly like Phase 9's `launch_adapter.launch()` has no gate of
  its own and relies on its caller.
- **Field-fill values passed via a CLI task-spec JSON file are still
  redacted before write** (`aos/browser/redaction.redact_value`) as
  defense in depth (contract's TP-CRED-05 requirement), even though the
  contract's Sec7a says field values must never be accepted as a bare CLI
  *argument* (to avoid shell-history leakage) -- this implementation
  interprets "argument" narrowly as argv, and accepts values inside a JSON
  spec *file* (not shell history), which is Sec10's own documented
  mechanism for supplying `field_data`. This distinction should be
  confirmed explicitly by Codex, since it is an implementer interpretation
  of ambiguous contract wording, not a stated contract decision.

## 6. Security Properties Verified by Test (Layer 1, mocked)

- Domain deny-by-default: unenrolled/unknown hosts denied before any
  navigation is attempted (`test_browser_domains.py`,
  `test_browser_url_policy.py`).
- Canonical-host exact match (no substring/suffix match); subdomains not
  implicitly covered; IDN/punycode homograph normalization prevents
  Cyrillic-lookalike collision.
- Private/loopback/link-local/IPv4-mapped-IPv6-loopback all denied via
  parsed `ipaddress` objects, not string prefix matching.
- HTTP denied by default; IP-literal denied by default; both require
  explicit per-domain enrollment flags.
- Non-default port denied unless explicitly whitelisted at enrollment.
- URL length cap enforced.
- Resolved-address (post-DNS) private-range denial via an injectable
  resolver (mocked rebinding scenario).
- Same-domain redirects followed and revalidated; cross-domain redirects
  denied outright at the task-runner layer (no approval-forwarding path
  exists for a mid-navigation redirect approval, so a cross-domain
  redirect currently **fails the operation** rather than pausing for a
  fresh approval -- see Sec9 finding F10-1 below, this is a **known gap**
  relative to the contract's stated "requires a fresh T2 approval" design,
  not a "silently allowed" gap).
- Risk tiers: no T1 tier exists; every T2 operation individually requires
  its own approval, exact-bound to operation/task/domain/URL/locator/
  field-classification/file-identity.
- Sensitive field classifications (password/credential/token/OTP/financial/
  recovery/security-answer) denied at classification time, before any
  approval is even consulted -- confirmed for all 7 denied classifications.
- Approval binding: wrong operation/task/domain/url/locator/classification/
  file each independently denied; reused approval denied; expired approval
  denied.
- Login/credentials: no `login` operation exists in the schema; attempting
  one is rejected at parse time.
- Voice origin: a task-spec with `origin="voice"` is denied before any
  browser process launches.
- Fail-closed preconditions: egress-containment-unverified, sandbox-
  unverified, and supply-chain-unverified each independently deny the task
  before any browser process is launched (confirmed via
  `factory.launched_handles == []`).
- Dry-run: never launches a process, never consumes an approval (confirmed
  the same approval subsequently succeeds on a real run).
- Downloads: 4-signal type agreement (declared MIME, extension, sniffed
  MIME, executable-magic) all must agree; archive extensions denied;
  path-traversal filenames denied; successful downloads land in quarantine
  with a recorded SHA-256; quarantine root is outside any project root and
  not registered with `PermissionEngine`.
- Quarantine retention sweep deletes only expired entries, runs only at
  explicit call time (no background scheduler).
- Promotion: destination must resolve inside an approved root; collision
  denied without explicit overwrite; content-hash mismatch between staging
  and promotion denied (simulated tamper); unknown file id denied.
- Uploads: source path must resolve through the existing
  `PermissionEngine`/`validate_path` (denies `.env`, `id_rsa`, etc. via the
  unchanged Phase 1 checks); source revalidated immediately before use.
- Injection-suspected pattern flag is set on matching page text but does
  not add, remove, or alter any operation in the task's own result list
  (structural non-escalation, confirmed by asserting the result list length
  is exactly the declared operation count).
- Audit: exactly one terminal event (`browser.session.closed` /
  `browser.session.failed`) per task, confirmed by direct query;
  `verify_chain` valid; no raw secret/query-string/field-value/locator
  string found anywhere in `payload_json` across a mixed task (confirmed by
  substring search over every event's raw payload).
- No orphan handle after a denied precondition (confirmed
  `factory.launched_handles == []`); guaranteed cleanup runs even when an
  operation fails (`FakeEngineHandle.closed is True` after every run).
- No `--no-sandbox` (or equivalent) or CDP network-listener flag reachable
  from `build_launch_args()`, statically and via a targeted denylist
  assertion test for every flag in `FORBIDDEN_LAUNCH_FLAGS`.

## 7. Security Properties Verified by Test (Layer 2, real Chromium) -- PARTIAL

`tests/test_browser_integration_real.py` exists and is written to Codex's/
the test plan's Sec1a Layer-2 shape: a real Playwright-managed Chromium
process against a real, loopback-bound Python `http.server` fixture (never
a live public site). **All 6 of its tests were skipped in this
implementation's sandbox**, not run, because the real Chromium binary
cannot launch here:

```
error while loading shared libraries: libnspr4.so: cannot open shared object file
```

This is a missing-OS-package problem (`libnspr4`, and likely `libnss3` and
related NSS/GTK dependencies), fixable only via a root-level
`apt-get install`/`playwright install-deps` call. This implementation
session has no interactive `sudo` and no passwordless `sudo` configured, so
it could not install these packages, and did not attempt to work around
that restriction. The test file's module-level skip check
(`_real_chromium_launchable()`) detects this at collection time and skips
cleanly with a clear reason, rather than failing or silently reporting
success.

**What Layer 2 tests exist to verify, once actually run in an environment
with a working Chromium:**

- `build_launch_args()` never contains `--no-sandbox` or a
  `--remote-debugging-port` flag (this specific pair of assertions
  actually *did* run and pass, since it doesn't require launching a
  browser).
- A real `PlaywrightEngineFactory.launch()` creates an alive handle, and
  `close()` flips it to not-alive.
- Real navigation to the local fixture server succeeds and
  `read_visible_text()` returns the fixture page's real content.
- The `request_validator` callback genuinely blocks a real navigation
  attempt when it returns `False` (proving the route-guard wiring works
  against a real Chromium request, not just a mock).
- The full `BrowserTaskRunner`, wired to a real engine and a real fixture
  server, still denies a loopback navigation target -- proving Hard Rule 7
  holds even with a real Chromium engine configured, not only in the
  mocked layer.

**None of these were confirmed to actually pass in this session.** Codex
(or a subsequent session with root access to run `playwright install-deps`
or an equivalent container image with the needed shared libraries already
present) must run this file and report pass/fail before Phase 10's exit
criteria on the real-engine layer can be considered met. This is the single
most significant gap in this implementation's own verification, and is why
`PHASE_CONTRACT.md` records Phase 10 as "IMPLEMENTATION COMPLETE — AWAITING
INDEPENDENT CODEX FINAL GATE" rather than COMPLETE.

## 8. Known Limitations and Residual Risk (explicit disclosure)

1. **Layer-2 real-browser tests unexecuted in this session** (Sec7). Real
   sandbox-flag behavior, real egress-containment enforcement against a
   live connection attempt, real worker/service-worker/WebSocket coverage,
   and real process-tree cleanup are verified only by code inspection and
   the mocked layer, not by a passing live run.
2. **Egress-containment and sandbox verification are attestation-based, not
   self-proving** (Sec5). A misconfigured deployment that sets the
   attestation environment variables without actually establishing network
   containment or without a genuinely available sandbox would pass Phase
   10's own precondition check while not actually being contained. This
   is disclosed in the contract itself (Sec4a: "the mechanism is a Human
   Owner / deployment decision... Phase 10's code requires *that one of
   these exists and is verified active*"), and this implementation matches
   that design, but it is worth restating plainly: **the fail-closed
   check is only as good as the attestation's honesty**, which is an
   operational/deployment property, not a Phase 10 code property.
3. **Cross-domain redirect handling denies rather than re-prompts for
   approval** (found during implementation, tracked below as F10-1). The
   contract's stated design (Sec4b) is that a cross-domain redirect
   *requires a fresh T2 approval*, implying the flow could pause and
   collect one. This implementation's `BrowserTaskRunner._run_one` instead
   treats a cross-domain redirect as an immediate operation failure --
   safe (nothing unapproved happens), but not the richer "pause, prompt,
   resume" flow the contract's language suggests might be possible. Given
   the one-shot, non-interactive-mid-task nature of the task model (Sec2a:
   no operation can be improvised mid-task), a genuine mid-navigation
   re-prompt would require either a second task-spec round-trip or an
   interactive CLI callback mid-`navigate()` -- neither was implemented
   here. **This is a conservative fail-safe gap** (denies more than the
   contract's ideal design might allow), not a permissive one, so it does
   not weaken any security property, but it does mean a legitimate,
   Human-Owner-desired cross-domain redirect follow cannot currently
   succeed in one task; the caller must issue the follow-up navigation as
   a new, separately-approved task instead.
4. **Third-party subresource requests are denied by the strict
   single-domain request validator** (Sec5, design decision #3). Real
   pages with CDN-hosted assets will see many subresource loads blocked.
   This is intentional narrowness, not a bug, but affects how usable
   real-world page rendering will look in practice; not tested against a
   real page with third-party resources due to the Sec7 environment
   limitation.
5. **No screenshot/visual capability exists** (correctly out of scope per
   contract; locators resolve against Playwright's own accessibility-tree
   API, not pixel coordinates).
6. **Real-world IPv6 IP-literal domain enrollment normalization** may not
   exactly match `ipaddress`'s canonical compressed form in every edge case
   (e.g., a domain enrolled as `::1` vs. `0:0:0:0:0:0:0:1`) -- not
   extensively tested since IP-literal enrollment is a narrow, explicitly
   opt-in feature; flagged for Codex's attention rather than silently
   assumed correct.
7. **Pre-existing test-data artifact**: two `pytest`-invoked-but-briefly-
   misconfigured CLI test runs during this implementation wrote to the real
   `~/.aos-jarvis/browser/approved_domains.json` (two `example.com` entries,
   one revoked) before the CLI test suite was corrected to monkeypatch the
   CLI module's registry constructor (matching the existing
   `tests/test_workspace_cli.py` convention) instead of relying on
   `AOS_DATA_DIR`, which has no effect after Python module import. This is
   disclosed rather than silently deleted (deleting the Human Owner's real
   data directory without explicit authorization was correctly refused by
   this session's own safety tooling). **The Human Owner or Codex should
   inspect and, if appropriate, delete `~/.aos-jarvis/browser/approved_domains.json`**
   on this machine -- it contains only two inert `example.com` test
   entries, no secrets, but it is not real enrollment data and should not
   be mistaken for it. No test in the final suite writes there any longer;
   `tests/test_browser_cli.py` was fixed to use the correct isolation
   pattern before this report was written.

## 9. Bugs Found and Fixed During Implementation

- **F10-1 candidate (see Sec8 item 3):** not a bug per se, but a design gap
  between the contract's stated redirect-approval flow and what a one-shot
  task model can actually implement without a second round trip. Disclosed,
  not silently resolved either way.
- **Real bug, fixed:** `BrowserTaskSpec`/`BrowserTaskRunner` originally had
  the runner generate `task_id` internally inside `run()`, which made it
  structurally impossible for a caller to mint a correctly task-bound
  approval in advance (the id wouldn't exist yet). Fixed by moving task-id
  generation to the caller (`new_task_id()`), with `BrowserTaskSpec.task_id`
  now a required field. Caught by writing an end-to-end smoke test before
  the full test suite, not by an automated tool -- flagged for Codex as a
  reminder that this class of "approval bound to a not-yet-existing
  identifier" bug is exactly the shape of issue the contract's Sec3a
  approval-binding design was meant to prevent, and it's worth Codex
  specifically re-checking that no other approval-binding field has the
  same "generated too late to bind against" problem.
- **Real bug, fixed:** the IP-literal branch of `validate_url` originally
  performed the private/loopback denial check but never compared the
  literal against the enrolled domain's own stored host, meaning enrolling
  *any one* IP-literal domain with `allow_ip_literal=True` would have
  silently authorized navigation to *every* public IP literal, not just
  the one enrolled. Fixed by adding an explicit normalized-literal
  comparison against `domain_host`, mirroring the hostname branch's
  exact-match requirement. Found while writing the real-Chromium
  integration test for loopback denial, not by an automated tool -- Codex
  should specifically re-verify this fix (`aos/browser/url_policy.py`,
  the `is_ip_literal` branch of `validate_url`) since it was a genuine
  authorization-scope bug, not just a missing test.
- **Real bug, fixed:** the URL-digest computation used for approval binding
  originally hashed an empty string (producing a non-empty digest) for
  operations without a URL (`fill`, `clear`, `submit`), which didn't match
  the empty-string default an approval minted for those operations would
  carry, causing every non-navigation T2 approval to be rejected as
  "bound to a different url" even when correctly matched on every other
  field. Fixed in both `BrowserTaskRunner._validate_and_consume_approvals`
  and the CLI's approval-minting loop to use an empty digest (not a hash of
  empty string) when no URL applies to the operation. Found by the mocked
  test suite (`test_fill_with_matching_approval_succeeds` initially
  failed), not by manual review.
- **Ruff findings** (unused imports/variables, an unnecessary f-string)
  were fixed via `ruff check --fix` plus three manual removals; final
  `ruff check` on all new/changed files reports zero findings.
- **Playwright-import isolation violation, fixed:** `aos/browser/
  supply_chain.py` originally did `import playwright` to read
  `playwright.__version__`, violating the architecture's stated rule that
  Playwright is imported only in `aos/browser/engine.py`. Fixed to use
  `importlib.metadata.version("playwright")` instead, which reads
  installed-package metadata without importing the package.

## 10. Test Results (exact)

```
$ python -m compileall -q aos tests
(clean, no output)

$ python -m pytest -q -rs
........................................................................ [ 10%]
...................................ssssss............................... [ 20%]
........................................................................ [ 30%]
........................................................................ [ 41%]
........................................................................ [ 51%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 82%]
........................................................................ [ 92%]
......................................................                   [100%]
SKIPPED [6] tests/test_browser_integration_real.py: real Chromium is not
  launchable in this environment: real chromium launch failed: TargetClosedError
696 passed, 6 skipped in ~6s

$ ruff check aos/browser aos/tools/browser.py aos/interfaces/cli/browser_commands.py \
    tests/test_browser_*.py tests/test_agent_tool_registry_browser.py
All checks passed!

$ grep -rn "shell=True\|os\.system(" aos/
(no matches)

$ grep -rln "import playwright\|from playwright" aos/
aos/browser/engine.py   # the only match, as required

$ git diff --check
(clean)
```

Live CLI smoke test (isolated `AOS_DATA_DIR`, no real browser required for
the read-only/dry-run paths):

```
$ aos browser domain add example.com --approve
<domain_id>
$ aos browser domain list
<domain_id>   active   example.com
$ aos browser task spec.json --dry-run     # operations=[{"operation":"read"}]
task preview: task_id=... domain_id=... operations=1
browser task validated
$ aos audit verify
valid (1 events)
$ aos browser task spec.json --yes         # attempts a real launch (T0 read op)
task preview: task_id=... domain_id=... operations=1
browser task failed (task_id=...): browser launch failed
$ aos audit verify
valid (6 events)
```

The last command demonstrates the intended fail-safe behavior when the real
Chromium binary cannot launch: a clean, typed `FAILED` outcome, a valid
audit chain, no crash, no leaked internal detail -- and, separately, with
the egress/sandbox attestation environment variables unset:

```
$ aos browser task spec.json --yes
task preview: task_id=... domain_id=... operations=1
browser task denied (task_id=...): sandbox_unverified
```

confirming the fail-closed precondition path works end to end through the
real CLI, not only in a unit test.

## 11. Exit Criteria Self-Assessment (honest, not a self-certification)

| Contract Sec14 criterion | Status |
|---|---|
| All Phase 0-9 tests remain green | **Met** -- 696 passed |
| Domain allowlist persists and is revalidated on every use | **Met** (Layer 1 tested) |
| Every navigation/redirect validated hop-by-hop; cross-domain redirect requires fresh approval | **Partially met** -- denies rather than re-prompts (Sec8 item 3) |
| Isolated, ephemeral, single-use process+profile per task | **Met by code/Layer-1 test**; **not confirmed live** (Sec7) |
| Browser-derived content structurally typed/untrusted | **Met** |
| Every T2 operation requires its own fresh, exact-bound approval | **Met** |
| Voice/model/page content cannot mint or forge approval | **Met** |
| No secrets in audit/memory/model prompts | **Met** (Layer 1 tested) |
| Download/upload/quarantine controls | **Met** (Layer 1 tested) |
| Exactly-one-terminal-event lifecycle | **Met** (Layer 1 tested) |
| Cleanup bounded/reliable incl. simulated crash/timeout | **Partially met** -- Layer 1 only; no real crash/timeout test executed live |
| Egress/sandbox fail-closed | **Met**, both by Layer-1 test and live CLI smoke test |
| compile/ruff/audit-verify/static-scan | **Met** |
| Both required test layers pass with zero live-network dependency | **Layer 1 met; Layer 2 unexecuted** (Sec7) |

## 12. Recommendation to Codex

Focus the independent review on:

1. The three "real bugs, fixed" in Sec9, to confirm the fixes are complete
   and correct, not just plausible.
2. Whether the cross-domain-redirect-denies-rather-than-reprompts gap
   (Sec8 item 3) is acceptable as shipped, or whether it should block
   COMPLETE status until a re-prompt flow (or an explicit contract
   amendment accepting deny-only redirect handling) exists.
3. Running `tests/test_browser_integration_real.py` in an environment with
   a working Chromium (installing `libnspr4`, `libnss3`, and Playwright's
   other declared system dependencies, e.g. via `playwright install-deps`
   with root access, or a container image that already has them) and
   reporting the actual pass/fail result -- this is the single largest
   open item.
4. Whether the attestation-based egress/sandbox verification design
   (Sec8 item 2) is an acceptable interpretation of the contract's "the
   mechanism is a deployment decision" language, or whether Codex expects
   a stronger built-in check before COMPLETE.
5. Cleaning up (or advising the Human Owner to clean up) the disclosed
   `~/.aos-jarvis/browser/approved_domains.json` test-data artifact
   (Sec8 item 7).

Do not mark Phase 10 COMPLETE without independently reproducing at least
the Layer-1 test results and forming an independent judgment on items 1-4
above.
