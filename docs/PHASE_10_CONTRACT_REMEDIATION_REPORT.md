# Phase 10 — Controlled Browser Automation: Contract Remediation Report

Status: **DRAFT — NOT ACTIVE UNTIL HUMAN OWNER APPROVAL**
Date: 2026-07-11
Author: Claude Sonnet (security architect role — planning only)
Trigger: Codex's independent Phase 10 Contract Review verdict —
`READY WITH REQUIRED CONTRACT FIXES`.

This report records what changed in the Phase 10 planning documents to
resolve every required finding from that review, and exactly what remains
for the Human Owner to decide. **No browser code, dependency, CLI command,
or test was implemented or modified to produce this report.** No file under
`aos/` or `tests/` was touched. `PHASE_CONTRACT.md`'s Active Phase line still
names Phase 9 (COMPLETE); Phase 10 remains inactive.

---

## 1. Verdict

**READY FOR HUMAN OWNER APPROVAL** (of the *revised planning documents* —
this is a verdict on the documentation, not an activation; Phase 10 code
still does not exist and still requires the separate activation decision
described in §17).

All twelve required contract fixes from the remediation brief are resolved
in the revised documents. No Critical or Important gap in Codex's review
was left open. Several items previously framed as "open design decisions"
(notably the OS/container egress-containment requirement) are now resolved
as **mandatory, fail-closed requirements** rather than left unresolved.

## 2. Documents Updated

- `docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md` — substantially revised:
  task-based execution model (§2a), corrected risk tiers (§3), mandatory
  network containment (§4a), corrected redirect policy (§4b), normative
  resource limits and process/sandbox model (§5a–§5c), untrusted-content
  envelope (§6), deferred login/credentials (§7), per-field T2 fill (§7a),
  strengthened downloads/quarantine/promotion (§8), strengthened uploads
  (§8a), audit privacy and lifecycle state machine (§9a–§9b), revised CLI/
  schema (§10), revised hard rules (§13), revised exit criteria (§14), and a
  new §16 listing every open Human Owner decision.
- `docs/PHASE_10_BROWSER_THREAT_MODEL.md` — new §2a control-layer separation
  table; TM-03, TM-04, TM-10, TM-14 ratings and mitigations corrected;
  summary risk table annotated with the mandatory-precondition caveats.
- `docs/PHASE_10_BROWSER_TEST_PLAN.md` — new §1a two-layer test structure
  (mocked + real-browser integration); TP-FORM-*, TP-CRED-*, TP-REDIR-*
  rewritten for per-field T2 and deferred login; new TP-SSRF-INT-*,
  TP-REBIND-INT-*, TP-SANDBOX-*, TP-LIMIT-*, TP-QUAR-*, TP-NET-INT-*,
  TP-CLEAN-INT-* groups; revised threat-to-test coverage table.
- `docs/PHASE_10_BROWSER_ARCHITECTURE.md` — task-based module layout
  (`task.py` replaces the long-lived `session.py`); new `egress.py`,
  `sandbox.py`, `supply_chain.py`, `quarantine.py` modules; revised data
  flow showing precondition verification before launch and guaranteed
  teardown.
- `PHASE_CONTRACT.md` — Phase 10 DRAFT section revised to match the above;
  Active Phase line unchanged (still Phase 9).
- `PROJECT_STATE.md`, `TASKS.md`, `TASK_BOARD.md`, `HANDOFF.md`,
  `BLOCKERS.md`, `CHANGELOG.md` — updated to record this remediation pass
  without changing phase/activation status.
- `docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` — this document, new.

## 3. Resolution of C10-1 — Session Lifecycle

**Problem:** The original draft's CLI sketch (`aos browser open` → `read` →
`fill` → `submit` → `close`, sharing a `session-id` across separate
invocations) cannot work: nothing in this codebase persists a live browser
process or its in-memory handle across separate CLI process exits, and
building that persistence would require exactly the cross-invocation daemon/
registry Phase 9 established as forbidden for the dev server.

**Resolution:** Replaced with a single bounded **task** model (contract
§2a): `aos browser task <spec>` validates, approves, launches one isolated
process, executes a pre-declared bounded operation sequence, returns a
result, and tears down — all within one foreground CLI invocation. No
task/session identifier is valid in a later invocation. A logical follow-up
("now read the confirmation page") is a **new task**, independently
validated and approved, never a continuation. This is reflected in the
architecture's `task.py` (`BrowserTaskRunner`, replacing the removed
long-lived `session.py`/`BrowserSessionManager`) and in the CLI proposal
(§10), which has no independent `open`/`read`/`fill`/`submit`/`close`
subcommands.

## 4. Resolution of C10-2 — Egress/SSRF Containment

**Problem:** The original draft implied Playwright's request/response
interception alone proves what the underlying Chromium socket actually
connects to, and treated an OS-level egress control as an "open design
decision" rather than a requirement (see the original TM-04 residual-risk
note).

**Resolution:** Contract §4a now states plainly that application-layer URL/
host checks are defense in depth, not sufficient SSRF/DNS-rebinding
containment, and makes independent OS/container egress filtering or a
locally controlled validating proxy a **mandatory, fail-closed precondition**
to launching any browser process — covering frames/iframes/workers/service
workers/fetch/XHR/WebSocket/EventSource/popups/downloads/client-side
redirects/form actions/prefetch/prerender, with service workers, WebRTC,
speculative prefetch/prerender disabled by default. Threat model TM-03 and
TM-04 are rewritten with the new §2a control-layer-separation framework,
explicitly stating each mitigating layer (application / browser / OS-
container) and marking post-mitigation risk as Low **only conditioned on**
the OS/container layer being verified active — not unconditionally Low as
the original draft implied.

## 5. Resolution of C10-3 — Field-Fill Risk

**Problem:** The original draft classified draft field fill as T1
("reversible local interaction"), on the theory that a value "never
submitted, never leaves the local session." Codex correctly identified that
this ignores `onchange`/`oninput`-driven XHR/WebSocket transmission, which
can send a filled value before any explicit submit action.

**Resolution:** Contract §3 removes the T1 tier entirely (no Phase 10
action was found that is genuinely non-network and non-disclosing beyond
what's already T0) and reclassifies every field fill and clear as its own
individually-approved T2 action (§7a), with its own approval binding to
exact locator identity and field classification (§3a). Threat model TM-10
is generalized from "form submission abuse" to "form/field-fill abuse" and
explicitly covers the autosave/XHR-on-input-change scenario. Test plan adds
TP-FORM-06/07 (autosave and WebSocket-on-input-change fixtures) as named,
required test cases, not an assumed-safe gap.

## 6. Resolution of I10-1 through I10-8

The remediation brief's twelve numbered "Required Contract Fixes" map onto
Codex's finding IDs as follows (I10-1..I10-8 correspond to fixes 4 through
11 in that numbering; C10-1..C10-3 correspond to fixes 1 through 3 above):

- **I10-1 (credentials/login contradiction):** Resolved — §7 defers login
  and all credential automation entirely; the schema has no `login`
  operation; sensitive-field classification denies before any approval
  prompt is even offered.
- **I10-2 (redirect policy inconsistency):** Resolved — §4b states one
  unambiguous rule: same-domain redirects revalidated, cross-domain
  redirects (even to enrolled domains) require a fresh T2 approval, at
  every hop, for both server-side and script-initiated navigation.
- **I10-3 (download quarantine/promotion under-specified):** Resolved —
  §8 defines quarantine as physically outside every approved root and
  unreachable by every other tool capability, and promotion as its own
  exact-file T2 operation with destination revalidation and collision
  handling.
- **I10-4 (upload approval binding incomplete):** Resolved — §8a lists the
  full binding set (project ID, path, file identity, size, hash,
  destination domain/target, origin, expiry), revalidation immediately
  before use, and same-object-reuse to prevent a symlink/content swap.
- **I10-5 (audit privacy — raw paths/values):** Resolved — §9a restricts
  audit payloads to opaque domain IDs, scheme/port categories, a
  `path_present` boolean, and a bounded path hash/template — no raw path,
  query, fragment, title, locator label, filename beyond safe metadata,
  header, cookie, page source, form value, prompt text, token, credential,
  PII, PID, process object, or raw exception text.
- **I10-6 (no normative lifecycle state machine):** Resolved — §9b defines
  the exact state machine (`REQUESTED → VALIDATED → APPROVAL_REQUIRED →
  APPROVED → STARTING → RUNNING → {COMPLETED|DENIED|FAILED|TIMED_OUT|
  CANCELLED} → CLEANUP`) with exactly-one-terminal-event and cleanup-
  failure-visibility requirements, mirroring Phase 9's F-1 lesson.
- **I10-7 (untrusted-content envelope was abstract, not concrete):**
  Resolved — §6 defines the typed `UntrustedBrowserObservation` structure
  and states the six hard rules governing it (never interpolated into
  instructions, never convertible to a tool request, cannot select
  parameters for future operations, cannot initiate further actions without
  fresh instruction, cannot be reconstructed into a tool call, provenance
  survives summarization, `injection_suspected` cannot reduce risk).
- **I10-8 (resource limits were "proposed," not normative; single mocked
  test layer only):** Resolved — §5a makes every limit a normative constant
  with a stated consequence; §12/test plan §1a require two test layers
  (mocked unit + real-browser isolated integration) and the architecture
  and threat-model documents cross-reference which layer proves what.

## 7. Revised Risk-Tier Table

See contract §3, reproduced here for convenience:

| Tier | Browser action |
|---|---|
| T0 | Local URL/domain validation, local task-spec metadata inspection, reading an already-fetched observation held in task memory, task close/teardown. |
| T1 | Removed — no qualifying action found. |
| T2 | Every navigation (including the first), new tab, every field fill/clear, every popup/consent interaction, every cross-domain redirect (even to an enrolled domain), form submission, upload, download, download promotion, any other external-side-effect action. |
| T3 / permanently denied | Financial/payment/account-recovery/security-answer/credential/password/token/one-time-code fields or actions; CAPTCHA; arbitrary JS/CDP; extensions; cookie manipulation; proxy/VPN config; remote control; private-network targets. |

## 8. Revised Browser Hard Rules

See contract §13 (12 rules, up from the original draft's 10) — the two new
rules added in this revision are: mandatory OS/container egress containment
and Chromium sandbox verification as fail-closed launch preconditions (new
Rule 11), and the prohibition on any browser session/process being reused
or referenced across separate CLI invocations (new Rule 12, making the
task-model constraint an explicit hard rule rather than only a design
narrative).

## 9. Revised Session/Isolation Model

Replaced "one long-lived browser process hosting many isolated contexts
across a session that may span several sequential CLI calls" with "one
browser process and one fresh temporary profile per task, launched and torn
down entirely within a single foreground CLI invocation." See contract §5b
and architecture §2/§3. No PID exposure, no daemon, no cross-invocation
registry, no CDP listener on any interface (loopback included, tightened
from the original draft's "non-loopback only" restriction).

## 10. Revised Domain/Network Model

Base domain/URL rules (persistent allowlist, canonical/punycode host
validation, HTTPS-only default, IP-literal handling, private/local network
blocking, port restrictions, subdomain policy, URL length limits, fragment/
query redaction) are retained from the original draft. Added: mandatory
OS/container egress containment as a launch precondition (§4a) and an
unambiguous, single redirect policy requiring fresh T2 approval for every
cross-domain hop (§4b), replacing the original draft's internally
inconsistent redirect language.

## 11. Revised Upload/Download/Quarantine Model

Quarantine is now precisely defined as physically outside every approved
project root, created with restrictive permissions, and structurally
unreachable by the filesystem, shell, model, memory/indexing, agent,
workspace, and dashboard capabilities (§8). Download promotion is a
separate, exact-file T2 operation with its own approval binding and
immediate destination revalidation (§8). Upload approval binding is now
complete and revalidated immediately before consumption, using the same
already-validated open file object rather than a re-opened path (§8a). Type
checking for downloads now requires four independent signals (declared
MIME, extension, sniffed MIME, executable magic) to agree with the
allowlist (§8).

## 12. Revised Audit Lifecycle

§9a restricts payload content to opaque/typed/boolean/hash fields, never raw
paths or values beyond narrowly-scoped, per-domain-opted-in safe route
templates. §9b defines the normative state machine and the exactly-one-
terminal-event requirement, with cleanup failures visible and distinct from
terminal outcomes, and requires a mixed-outcome audit-chain integrity test
(TP-AUDIT-06).

## 13. Revised Test Strategy

Test plan §1a now requires two layers: deterministic mocked unit tests (as
originally scoped) plus real-browser integration tests against isolated
local fixtures with zero external-network dependency, specifically to prove
properties mocking cannot (real sandbox launch flags, real egress
containment, real process-tree cleanup, real worker/service-worker/
WebSocket behavior). A Layer-2 skip is explicitly stated as not equivalent
to a Layer-2 pass for final-gate purposes (TP-REGR-08).

## 14. Threat-Model Changes

New §2a separates application, browser, and OS/container control layers and
requires every network-facing `TM-*` entry to state its mitigation using
that structure. TM-03 (SSRF) and TM-04 (DNS rebinding) are corrected to
state that post-mitigation risk is Low *only* when the OS/container egress
layer is verified active, and reverts to High/unmitigated otherwise — this
is why launch must fail closed rather than degrade silently. TM-10 is
generalized from submission-only to cover every field fill. TM-14 (browser-
process/sandbox escape) explicitly remains a **Medium accepted residual
risk**, not reduced to Low — mandatory sandbox verification lowers
likelihood of launching unsandboxed, and OS/container controls bound
impact, but neither closes a genuine renderer 0-day. The summary risk table
and per-threat sections make no claim that a `BrowserContext` alone is a
security sandbox.

## 15. Human Owner Decisions Still Required

Beyond the general Phase 10 activation decision, the Human Owner must
separately confirm (or amend) each of the following, restated from contract
§16:

1. Browser lifecycle: foreground, one bounded task per invocation.
2. No browser session ID usable across separate CLI invocations.
3. Mandatory independent OS/container egress containment or a validating
   proxy — and which mechanism the deployment will actually use (container
   network policy, network namespace + firewall rules, or a mandatory local
   proxy) is itself an operational decision outside this document's scope.
4. Fail-closed launch if egress containment or sandbox verification is
   unavailable.
5. Permanent denial of private/loopback/link-local/unique-local/metadata/
   multicast/unspecified/reserved/non-global-unicast destinations.
6. Login, credential-field automation, and financial fields deferred/denied
   in Phase 10 entirely (a future phase would need its own contract).
7. Non-sensitive field fill as a fresh, per-field T2 action.
8. Fresh T2 approval for every cross-domain redirect, even to an enrolled
   domain.
9. Quarantine location outside every approved root and unreachable by every
   other capability.
10. Download promotion as a separate exact-file T2 operation.
11. One browser process and one fresh temporary profile per task.
12. Mandatory Chromium sandbox; permanent `--no-sandbox` prohibition.
13. No daemon, no raw PID authority, no cross-invocation session/process
    management, no remote-debugging listener on any interface, no personal
    profile.

Also unresolved from the original draft and still requiring sign-off,
carried forward unchanged: the scope-expansion question versus the original
placeholder `docs/phases/PHASE_10_BROWSER_TOOLS.md` (contract §15), and the
general decision of whether to activate Phase 10 at all right now (`BLOCKERS.md`
B008).

## 16. Confirmation: No Production Code, Dependency, CLI Command, or Existing Test Changed

Verified before and after this remediation pass:

- `git status` / `git diff` shows changes only in `docs/PHASE_10_*.md`,
  `PHASE_CONTRACT.md`, `PROJECT_STATE.md`, `TASKS.md`, `TASK_BOARD.md`,
  `HANDOFF.md`, `BLOCKERS.md`, `CHANGELOG.md`, and this new report.
- No file under `aos/` was created, modified, or deleted.
- No file under `tests/` was created, modified, or deleted.
- `pyproject.toml` was not modified; no dependency (Playwright or otherwise)
  was added.
- No CLI command was registered; `aos/interfaces/cli/main.py` was not
  touched.
- `PHASE_CONTRACT.md`'s "Active Phase" line still names **Phase 9**.
- Phase 10's status line still reads **DRAFT — NOT ACTIVE UNTIL HUMAN OWNER
  APPROVAL** everywhere it appears.

## 17. Exact Phase 10 Activation Statement for the Human Owner

Unchanged in mechanism from the original draft, updated to name this
revision's documents. To activate Phase 10, the Human Owner replaces the
Phase 10 section's status line in `PHASE_CONTRACT.md` with:

> APPROVED — Phase 10 — Controlled Browser Automation is active as of
> `<date>`. `docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md`,
> `docs/PHASE_10_BROWSER_THREAT_MODEL.md`,
> `docs/PHASE_10_BROWSER_TEST_PLAN.md`, `docs/PHASE_10_BROWSER_ARCHITECTURE.md`,
> and `docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` (revised 2026-07-11) are
> the authoritative Phase 10 design, superseding both the narrower
> placeholder scope in `docs/phases/PHASE_10_BROWSER_TOOLS.md` and the
> original 2026-07-11 Phase 10 draft that Codex's contract review required
> fixes to.

and updates "Active Phase" at the top of `PHASE_CONTRACT.md` to name Phase
10. Until that exact replacement happens, Phase 10 is not active, no browser
code may be written, and no agent may implement it. The Human Owner may
instead request further changes (returning this to another remediation
pass) or decline Phase 10 entirely.
