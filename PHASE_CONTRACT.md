# Phase Contract

## Active Phase: Phase 11 — Screen Understanding Plugin

Phase 10 implementation is frozen for coding while its independent real-
Chromium verification remains delegated to the external verification system.
Phase 10 is not declared complete by this activation. Phase 11 coding is
authorized only within the bounded scope below.

Human Owner approval to begin implementing Phase 10 was recorded in the
2026-07-11 Phase 10 implementation instruction, against the remediated
design in `docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md`,
`docs/PHASE_10_BROWSER_THREAT_MODEL.md`, `docs/PHASE_10_BROWSER_TEST_PLAN.md`,
`docs/PHASE_10_BROWSER_ARCHITECTURE.md`, and
`docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` (all dated/revised 2026-07-11),
which are now the authoritative Phase 10 design, superseding both the
narrower placeholder scope in `docs/phases/PHASE_10_BROWSER_TOOLS.md` and
the original pre-remediation Phase 10 draft.

Phase 10 status: **IMPLEMENTATION FROZEN — AWAITING FRESH INDEPENDENT
CODEX FINAL GATE.** Codex's fresh 2026-07-11 "Follow-up Remediation Gate"
review returned **FAIL** on: (C-1) the required Layer-2 real-Chromium gate
not passing and the matrix remaining incomplete — an environmental
constraint (real Chromium cannot launch in this sandbox; not code-fixable
here, and per Human Owner direction not re-attempted this round); (C-2) the
validating-proxy egress shape not proven as an AOS-controlled containment
boundary; (I-1) post-launch sandbox verification unproven by Layer 2; (I-2)
T2 action audit lifecycle lacking exact terminal semantics; (I-3) resource/
cleanup guarantees remaining partial. Claude Sonnet fixed every code-level
finding same-day: `aos/browser/validating_proxy.py` now implements a real,
AOS-spawned, policy-enforcing HTTP CONNECT proxy scoped per task, verified
via actual (unmocked) CONNECT requests proving real `403` enforcement, not
mere reachability; the duplicate `browser.action.denied` audit bug is fixed
(exactly one terminal-shaped event per denied T2 action, with new tests);
`BrowserProcessTracker`'s `/proc`-scanning and kill-loop logic is now
injectable and has 9 new deterministic unit tests proving the algorithm
correct against synthetic process trees (real-Chromium proof remains
blocked by the same Layer-2 environment constraint). Full suite: **741
passed, 5 skipped**. The Layer-2 real-Chromium gate is UNCHANGED (2 passed,
5 errors, `TargetClosedError`) — genuinely not fixable without a Chromium-
capable environment or root access, and this remains the single largest
open blocker. See `docs/PHASE_10_REMEDIATION_REPORT.md` (second follow-up
section) and `docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md` for the full
finding record. Not self-certified. Phase 10 is not COMPLETE; its remaining
verification blocker does not authorize changes to the Phase 10 browser
security boundary during Phase 11.

**P10-R1 targeted Human Owner clarification (2026-07-12):** `--no-sandbox`
remains permanently forbidden on every Chromium process. The sole permitted
exception is `--no-zygote-sandbox` on an expected full-Chromium zygote whose
parent is in the verified browser tree, while every renderer, GPU, network
service, and utility process independently proves zero effective capabilities,
`NoNewPrivs=1`, seccomp filtering, and namespace evidence through `/proc`.
The rootless P10-R1 verifier uses no added container capability: it replaces
only Podman's conditional `chroot` seccomp entries with one unconditional
`chroot` allow, so Chromium receives that capability only inside its nested
user namespace. It may not use privileged mode, `SYS_ADMIN`, host
namespaces/mounts/network, runtime sockets, or any other capability. This does
not authorize P10-R2 or Phase 10 completion. Phase 11 is activated below with
an independent, read-only screen-understanding scope; fresh Phase 10
environment verification remains required separately.

Phase 9: **COMPLETE** (2026-07-11, Human Owner sign-off following Claude Sonnet
independent re-review — clean PASS, no outstanding findings). Typed, allowlisted
folder/editor/terminal launching; a foreground, loopback-only dev server whose only
stop method is Ctrl+C in the invoking terminal; explicit Human Owner confirmation
required and durably consumed, with an independent path-bound canonical check,
before any server launch; contextual denial audit; and preserved Phase 1 path
exception subtypes. Cross-invocation server status/stop capabilities do not exist.
Full suite: **564 passed, 0 failed, 0 skipped**. B007 is CLOSED. See
`docs/PHASE_9_INDEPENDENT_RECONFIRMATION.md` for full verification evidence.

Phase 7 is COMPLETE + INDEPENDENTLY RECONFIRMED (2026-07-11, Claude Sonnet).  347 passed, 2 skipped.
All four Important fixes (F7-1 through F7-4) verified.  See `docs/PHASE_7_INDEPENDENT_RECONFIRMATION.md`.

Phase 8: COMPLETE. Timeout remediation and supplemental verification passed:
**137 focused voice tests passed; 484 tests passed, 2 skipped**. All F8-1 through
F8-4 findings are verified fixed. See
`docs/PHASE_8_OPENCODE_TIMEOUT_VERIFICATION.md`.

## Phase 9 Goal

Let AOS-Jarvis open and arrange the user's local development environment:
approved project folders, editor, terminal, and explicitly approved dev servers.

## Phase 9 Allowed Work

- Implement `aos/tools/workspace.py` as a `BaseTool`.
- Open an approved project folder, VS Code, or a terminal in an approved project.
- Restore the last workspace.
- Start a development server only through the existing audited Phase 2 shell runner
  and only with explicit T2 approval.
- Add deterministic tests and update documentation and coordination records.

## Phase 9 Forbidden Work

- Browser tools or browser automation (Phase 10).
- Screen understanding, OCR, remote workspace control, or actions outside approved
  project directories.
- Any process launch that bypasses the Phase 2 shell runner, permission checks, or audit log.
- Starting a dev server without explicit approval.
- Git push, pull, fetch, commit, checkout, reset, merge, or rebase.

## Phase 9 Exit Criteria

- Every launched process is scoped to an allowed project directory and audited.
- Opening editor and terminal actions remain T1 and reversible.
- A dev server is classified T2, requires explicit approval, and its audit event
  records how to stop it.
- Approval-gate, working-directory scope, and workspace-restore idempotency tests pass.
- Phase 0–8 regression tests and `python -m compileall -q aos tests` pass.

## Phase 9 Hard Rule

**No workspace or application launch may bypass the existing permission, risk,
Phase 2 shell-runner, or audit boundaries.** A dev server must never start without
explicit approval.

## Phase Goal (Phase 6 — kept for reference)

Implement safe configurable model support. Local and explicitly enabled cloud providers may help classify intents, draft summaries, explain safe outputs, or produce structured proposals. Models never directly execute tools.

Required flow:

`User request -> intent/planner -> model adapter if needed -> structured output -> validator -> tool registry -> permission/risk gate -> safe tools -> audit -> final answer`

Forbidden flow:

`User request -> model directly runs shell/files/git/tools`

## Allowed Work

- Add model request/response types, provider interface, local adapter, cloud adapter, deterministic router, config, redaction, structured output validation, model audit events, and CLI model commands.
- Keep cloud disabled by default and require API keys via environment variables only.
- Integrate optional model-assisted answer generation through the existing controlled agent path.
- Add deterministic mocked tests with no real LLM, no network dependency, and no real API calls.
- Update Phase 6 docs and coordination files.

## Forbidden Work

The following remain forbidden in Phase 6:

- voice
- dashboard
- browser automation
- screen understanding
- multi-agent system
- embeddings or vector databases
- autonomous coding agent
- remote workspace control
- cloud sync
- unrestricted model tool execution
- model marketplace
- automatic provider discovery
- real API calls in tests
- git push, pull, fetch, commit, checkout, reset, merge, rebase, or other repository-mutating operations
- raw unrestricted filesystem or shell access
- model access to permission internals, audit database internals, shell runner internals, memory tools, or raw project paths beyond approved/redacted request data

## Exit Criteria

- Existing Phase 0-5 tests still pass.
- Phase 6 model config, redaction, router, provider, validation, CLI, agent integration, and safety tests pass.
- `aos model list`, `aos model show`, and `aos model doctor` work.
- `aos ask --model local "..."` works with mocked/local model support.
- `aos ask --model cloud "..."` is blocked by default unless cloud is explicitly enabled.
- Local adapter is mockable and does not require Ollama in tests.
- Cloud adapter exists, is disabled by default, requires explicit config enablement, and requires API key via env var only.
- Redaction happens before cloud provider receives prompt text.
- Raw API keys are rejected from config and not printed/audited.
- Structured model tool proposals are validated through the tool registry.
- Unsafe model proposals are blocked and audited.
- Model usage events are audited safely without secrets or full unredacted prompts.
- Audit verification passes.
- Docs are updated.

## Phase 7 Goal

Provide a local, read-only web dashboard for inspecting AOS-Jarvis system state.
The dashboard must not mutate any system state.

## Phase 7 Allowed Work

- FastAPI + Jinja2 + uvicorn dashboard, loopback-only.
- Seven read-only views: overview, audit, permissions, activity, snapshots, model, security.
- `aos dashboard` CLI command (no --host flag).
- Dashboard optional extra in `pyproject.toml`.
- Tests with TestClient (no real server required).
- Documentation: `docs/phase_7.md`, `docs/dashboard.md`, `docs/PHASE_7_IMPLEMENTATION_REPORT.md`.
- Update coordination files.

## Phase 7 Forbidden Work

- Any write/mutation endpoint.
- snapshot restore from dashboard.
- Exposing API keys, raw secrets, or unredacted prompts.
- Non-loopback binding.
- Remote dashboard access, login systems, authentication.
- Voice, browser, screen, multi-agent, embeddings, model invocation.
- Git operations.

## Phase 7 Exit Criteria

- All Phase 0–6 tests still pass.
- 7 required dashboard views all return 200.
- POST/PUT/PATCH/DELETE on all routes return 405.
- XSS: `<script>` in event data is HTML-escaped in response.
- No `sk-` prefix or API key values appear in any response.
- Loopback binding verified by test.
- No `/openapi.json`, `/docs`, `/redoc` endpoints.
- `aos dashboard --help` exits 0, no `--host` in output.
- 20+ new dashboard tests pass.
- `python -m compileall -q aos tests` passes.

## Agent Rule

Before doing work, every agent must read:

1. `PHASE_CONTRACT.md`
2. `TASK_BOARD.md`
3. `SECURITY_BOUNDARIES.md`
4. `TOOL_CAPABILITIES.md`
5. `CODING_RULES.md`

No agent may implement work outside the active phase unless the Human Owner updates `PHASE_CONTRACT.md`.

---

## Phase 10 — Controlled Browser Automation

### APPROVED — Phase 10 — Controlled Browser Automation is active as of 2026-07-11.

`docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md`, `docs/PHASE_10_BROWSER_THREAT_MODEL.md`,
`docs/PHASE_10_BROWSER_TEST_PLAN.md`, `docs/PHASE_10_BROWSER_ARCHITECTURE.md`, and
`docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` (revised 2026-07-11) are the
authoritative Phase 10 design, superseding both the narrower placeholder
scope in `docs/phases/PHASE_10_BROWSER_TOOLS.md` and the original
pre-remediation Phase 10 draft that Codex's contract review required fixes
to.

**Final-gate status (2026-07-11, Codex): FAIL — REMEDIATION REQUIRED.** See
`docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md` for the independent findings.

**Follow-up remediation gate status (2026-07-11, Codex): FAIL —
REMEDIATION STILL REQUIRED.** Claude Sonnet addressed several original findings in
`docs/PHASE_10_REMEDIATION_REPORT.md`, and Codex verified meaningful
improvements: focused browser suite 152 passed outside the sandbox with
isolated `AOS_DATA_DIR`; full suite 718 passed, 5 skipped; compileall,
Ruff, `git diff --check`, audit verify, CLI smoke, and static scans passed.
The skipped tests are still required Layer-2 real-Chromium tests and remain
blocking. The Layer-2 matrix is also incomplete, and additional contract
gaps remain for enforced egress containment, exact destination-bound
promotion approval, post-launch Chromium sandbox verification, exact audit
terminal semantics, process-tree cleanup/resource enforcement, live-DNS
Layer-1 tests, and residual upload TOCTOU. See
`docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`. Phase 10 cannot be declared
COMPLETE.

**Follow-up final gate status (2026-07-11, Codex): FAIL — REMEDIATION STILL
REQUIRED.** Follow-up remediation improved egress shape, promotion binding,
post-launch sandbox hooks, task terminal audit coverage, process-tree cleanup
hooks, DNS-free Layer 1, and upload snapshot staging. Codex reproduced:
focused subset 106 passed; full suite 725 passed, 8 skipped; compileall,
changed Phase 10 Ruff, `git diff --check`, and isolated audit verify passed.
The opt-in Layer-2 gate produced 2 passed, 5 errors because Chromium cannot
launch. Remaining blockers are listed in
`docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`: incomplete/unpassed Layer 2,
unproven validating-proxy containment, unproven real post-launch sandbox/
process verification, non-exact T2 action terminal audit semantics, and
partial resource/cleanup guarantees.

**Revision note (2026-07-11, contract remediation pass, prior to
implementation):** Codex's independent contract review returned `READY
WITH REQUIRED CONTRACT FIXES`. Claude Sonnet revised all four Phase 10
planning documents to resolve every required finding before implementation
began. See `docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` for the full
remediation record.

Full detail lives in:

- `docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md` — goal, revised risk-tier
  work breakdown (no T1; T2 for navigation/every field fill/every external
  effect), task-based (not multi-command session) execution model, mandatory
  OS/container egress containment, deferred login/credentials, quarantine
  and download-promotion model, normative audit lifecycle and resource
  limits, CLI/schema proposal, voice/model boundaries, hard rules, exit
  criteria.
- `docs/PHASE_10_BROWSER_THREAT_MODEL.md` — assets, trust boundaries,
  attacker capabilities, control-layer separation (application vs. browser
  vs. OS/container vs. residual), 20 ranked threat scenarios with revised
  mitigations and residual risk (TM-03/TM-04/TM-10/TM-14 corrected).
- `docs/PHASE_10_BROWSER_TEST_PLAN.md` — two required test layers
  (deterministic mocked unit tests, and real-browser integration tests
  against isolated local fixtures with zero external-network dependency).
- `docs/PHASE_10_BROWSER_ARCHITECTURE.md` — Playwright engine choice and
  rationale, revised module layout (task-based execution, egress/sandbox/
  supply-chain verification modules), integration points reused unchanged
  from Phases 1/2/3/6/9.
- `docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` — record of every required
  fix, its resolution, and the Human Owner decisions still required.

### Phase 10 Goal (proposed, revised)

A narrow, permission-governed browser capability: open explicitly
Human-Owner-enrolled websites, read rendered content, extract bounded
visible text, and — only with a fresh, per-field/per-action T2 Human Owner
approval — fill a non-sensitive form field, submit a form, upload a file, or
download a file to a quarantine location pending a separate promotion
approval. Every capability runs as a single bounded **task**: one isolated,
network-contained, sandboxed browser process per invocation, with nothing
surviving past that invocation's exit. Not unrestricted web access. Not
autonomous internet access. **Not a login or credential-automation tool —
that is deferred to a future, separately approved phase.**

### Phase 10 Allowed Work (proposed, once activated, revised)

- Implement `aos/browser/*` and `aos/tools/browser.py` as a `BaseTool`,
  following the module layout in `docs/PHASE_10_BROWSER_ARCHITECTURE.md`,
  including the `egress.py`, `sandbox.py`, `supply_chain.py`, and
  `quarantine.py` modules the revision added.
- T0 read-only, auto-allowed: local URL/domain validation, local task-spec
  metadata inspection, reading an already-fetched bounded observation held
  in the current task's own memory, closing/tearing down the current task.
- T2 with fresh, non-voice, exact-bound, per-operation Human Owner approval:
  every navigation (including the first), every field fill/clear, every
  popup/consent interaction, every cross-domain redirect (even to an
  enrolled domain), form submission, upload, download, and download
  promotion. There is no T1 tier in Phase 10 — see the revised risk table
  in `docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md` §3 for why.
- Mandatory preconditions to any browser launch: OS/container egress
  containment or a locally controlled validating proxy verified active, and
  Chromium sandbox verified active — launch fails closed if either cannot
  be confirmed.
- Add tests per both required layers in
  `docs/PHASE_10_BROWSER_TEST_PLAN.md` (deterministic mocked unit tests, and
  real-browser integration tests against isolated local fixtures) and
  update documentation and coordination records.

### Phase 10 Forbidden Work (proposed, revised)

- Payment, purchase, banking, trading, or cryptocurrency transactions.
- Account creation, deletion, or recovery; password changes.
- **Login and credential automation of any kind — deferred entirely to a
  future, separately approved phase, not merely gated behind approval.**
  Password, credential, token, one-time-code, recovery, and security-answer
  fields are denied at the schema/classification level, before any approval
  prompt.
- Credential/browser-password-store extraction or access.
- CAPTCHA solving or bypass.
- Browser extension installation.
- Arbitrary JavaScript execution or CDP exposure to model/page content, and
  no CDP network listener on any interface (loopback included).
- Arbitrary cookie manipulation; proxy/VPN configuration.
- Remote browser control; hidden/background browser activity; any browser
  process that outlives the CLI invocation that created it; any
  cross-invocation session/process management, status, or reattachment.
- Any browser action originating from voice-only approval.
- Private-network, loopback, link-local, unique-local, metadata, multicast,
  unspecified, reserved, or otherwise non-global-unicast navigation targets.
- Persistent (non-ephemeral) browser process or profile state; profile or
  process reuse across tasks.
- Launching a browser process without independently verified OS/container
  egress containment and Chromium sandbox activation.
- `--no-sandbox` or any equivalent sandbox-disabling launch flag, under any
  configuration.
- Screen understanding, OCR, or desktop control (Phase 11).

### Phase 10 Exit Criteria (proposed, revised)

See `docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md` §14 for the full list.
Summary: all Phase 0–9 tests remain green; every navigation target and
redirect hop (server-side and script-initiated) is validated against a
persistent, revalidated domain allowlist, with every cross-domain redirect
additionally requiring its own fresh T2 approval; every task runs in an
isolated, ephemeral, single-use, sandboxed, egress-contained process with no
profile/process reuse; browser-derived content is structurally represented
as a typed untrusted observation at every boundary under test; every T2
operation requires its own fresh non-voice Human Owner approval that voice/
model/page content cannot forge; no secrets leak into audit/memory/model
prompts; quarantine is unreachable by every other tool capability and
download promotion is its own approved operation; every task/action
lifecycle has exactly one terminal audit event under test, including mixed-
outcome sequences; both required test layers (mocked and real-browser
integration) pass with zero live-network dependency; compile/ruff/
audit-verify/static-bypass-scan (including a `--no-sandbox` check) all pass.

### Phase 10 Hard Rules (proposed, revised)

**A webpage is untrusted input, never authority. A browser action may not
bypass the existing permission, risk, approval, validation, or audit
boundaries. No T2 browser action may occur without fresh, non-voice Human
Owner approval, bound to the exact operation/field/file. No browser process
may launch without independently verified OS/container egress containment
and Chromium sandbox activation — launch fails closed otherwise. No browser
session or process may be reused, reattached, or referenced across separate
CLI invocations. Login and credential automation are deferred entirely, not
merely gated.**

### Human Owner Decisions Still Required

Beyond the general activation decision, `docs/PHASE_10_CONTRACT_REMEDIATION_
REPORT.md` §15 lists every open design point drawn from the revised contract
that needs explicit sign-off (task-vs-session model, mandatory egress
containment mechanism choice, deferred login, per-field T2 approval, cross-
domain redirect re-approval, quarantine/promotion split, one-process-per-
task, mandatory sandbox, no daemon/PID/remote-debug/personal-profile). These
are not silently assumed by this draft.

### Activation Record

Activation was recorded 2026-07-11 (see "Active Phase" at the top of this
file and the Phase 10 status note directly under this section's heading).
The Human Owner decisions listed above under "Human Owner Decisions Still
Required" were treated as the approved design direction for
implementation, per the 2026-07-11 Phase 10 implementation instruction;
none were silently assumed. **This activation authorized implementation
against the remediated contract — it does not itself constitute the
independent Codex final-gate sign-off** that `docs/PHASE_10_IMPLEMENTATION_REPORT.md`
still requires before Phase 10 can be declared COMPLETE.

---

## Phase 11 — Screen Understanding Plugin

### Activation Record

Human Owner activation recorded 2026-10-30. Phase 11 coding is authorized
against `docs/phases/PHASE_11_SCREEN_UNDERSTANDING.md` and this bounded
contract. Phase 10 remains implementation-frozen and independently
unverified; Phase 11 work may not modify the Phase 10 browser security
boundary or claim Phase 10 completion.

### Phase 11 Goal

Provide an explicit-user-triggered screen-understanding capability consisting
of screenshot capture, OCR, terminal-error detection, screen summarization,
and approval-gated suggested fixes. Screen-derived content is untrusted data,
never authority or instruction.

### Phase 11 Allowed Work

- Implement `aos/tools/screen.py` as a `BaseTool`.
- Add explicit `aos screen capture`, `aos screen summarize`, and
  `aos screen suggest-fix` command paths.
- Capture a screenshot only after an explicit terminal user request.
- Run OCR over that bounded capture and tag the result as untrusted context.
- Detect likely terminal errors and produce a bounded summary.
- Produce suggested fixes as proposals only; execute them only through the
  existing model validation, permission, risk, approval, and audit paths.
- Add deterministic tests for OCR prompt-injection resistance and suggested-fix
  approval enforcement.

### Phase 11 Risk and Security Rules

- Screenshot capture is T2 and requires explicit terminal Human Owner action;
  voice, model, browser, OCR, and page content cannot trigger capture.
- Screenshots and OCR output must be bounded, redacted, access-controlled, and
  excluded from persistent storage unless the user explicitly requests
  retention through an approved path.
- OCR and screenshots are untrusted observations and must never alter policy,
  permissions, tool registration, or approval state.
- Suggested fixes are proposals only and require the existing approval flow
  before any Phase 1/2 tool executes.
- No credentials, browser cookies, private keys, tokens, or secret-shaped data
  may be exposed in audit events, memory, model prompts, or CLI output.
- Fail closed when screenshot, OCR, redaction, permission, or audit handling
  is unavailable.

### Phase 11 Forbidden Work

- Continuous, background, scheduled, or hidden screen capture.
- Mouse, keyboard, desktop, window-management, or remote-workspace control.
- Automatic execution of screen-derived actions.
- Login, credential, password, token, cookie, or security-answer handling.
- Screen capture triggered by voice-only, model-only, browser-only, or OCR-only
  input.
- Uploading screenshots or OCR content to a cloud provider by default.
- New daemon, remote API, messaging gateway, multi-agent, or Phase 12 workflow
  behavior.

### Phase 11 Exit Criteria

- Explicit terminal capture boundary is enforced and tested.
- OCR output is structurally tagged as untrusted at every model/tool boundary.
- Prompt-injection text in screenshots cannot cause tool execution or approval.
- Suggested fixes cannot execute without exact existing approval binding.
- Secret redaction and bounded output tests pass.
- All Phase 0–10 regression tests remain green in the external verification
  environment, subject to the separately tracked Phase 10 Layer-2 blocker.
- `compileall`, focused Ruff, audit verification, and static bypass scans pass.
- Phase 11 receives an independent review before Phase 12 is considered.
