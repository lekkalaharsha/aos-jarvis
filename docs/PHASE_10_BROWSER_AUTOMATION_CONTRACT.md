# Phase 10 — Controlled Browser Automation: Contract

Status: **DRAFT — NOT ACTIVE UNTIL HUMAN OWNER APPROVAL**
Date: 2026-07-11 (original draft) — Revised 2026-07-11 (contract remediation
pass, Claude Sonnet, following Codex's independent contract review verdict
`READY WITH REQUIRED CONTRACT FIXES`)
Author: Claude Sonnet (security architect role — planning only, no code
changes in either pass)

This document supersedes and narrows the placeholder scope in
`docs/phases/PHASE_10_BROWSER_TOOLS.md` (open/search/extract only). That
placeholder under-specified session isolation, T2 interaction (forms, login,
uploads, downloads), and audit lifecycle. This contract is the authoritative
Phase 10 design until the Human Owner approves or amends it. See
`docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` for exactly what changed in
this revision and why, and §16 of that report for the exact discrepancy this
expansion needs sign-off on.

No code, dependency, CLI command, or test in this repository was changed to
produce this document, in either drafting pass. This is a planning artifact
only. Every design decision below is a **proposal requiring Human Owner
sign-off**, not an active authorization.

---

## 0. What Changed in This Revision (summary)

Codex's independent review returned `READY WITH REQUIRED CONTRACT FIXES`.
This revision resolves all required findings:

1. Replaced the unusable multi-command session model (`open` → `read` →
   `fill` → `submit` → `close` across separate CLI invocations, which cannot
   work because nothing survives CLI process exit) with a single bounded
   **task** model: one foreground process performs a validated, bounded
   sequence of approved actions and exits. See §2, §5, §10.
2. Replaced "Playwright interception proves the destination" with a
   requirement for real network containment: OS/container egress filtering
   or a locally controlled validating proxy, enforced before any Chromium
   socket can reach the network, fail-closed if unavailable. See §4a.
3. Corrected the risk-tier table: initial navigation, every field fill, and
   every external side effect are T2, not T0/T1. See §3.
4. Deferred all login/credential automation to a future phase. See §7.
5. Made every field fill (not just submission) a fresh T2 action. See §3, §7a.
6. Corrected redirect policy: every cross-domain redirect requires fresh T2
   approval, even to an enrolled domain. See §4b.
7. Strengthened download quarantine and defined download promotion as its
   own T2 operation. See §8.
8. Strengthened upload approval binding. See §8a.
9. Made audit privacy stricter (opaque domain IDs, no raw paths) and defined
   a normative lifecycle state machine. See §9.
10. Defined a concrete typed untrusted-content envelope. See §6.
11. Made all resource limits normative constants and required two test
    layers (mocked + real-browser isolated integration). See §5a, §12.
12. Added browser supply-chain controls. See §5b.

---

## 1. Goal

Give AOS-Jarvis a narrow, permission-governed capability to interact with an
explicitly Human-Owner-approved set of websites: open allowed pages, read
rendered content, extract bounded visible text, and — only with fresh T2
approval for every single field/action — fill non-sensitive form fields or
take an external-effect action (submit, upload, download). Every task runs
in an isolated, ephemeral, network-contained browser process that cannot
outlive the CLI invocation that created it, and is audited exactly like
every other AOS-Jarvis capability.

**Browser automation in Phase 10 is not unrestricted web access, not
autonomous internet access, not a general-purpose scraping or RPA engine,
and not a login/credential-automation tool.** It is a bounded, one-task-at-a-
time tool that can act only inside domains the Human Owner has explicitly
enrolled, with every field write and every external effect gated by its own
fresh approval, following the same enrollment pattern Phase 9 established
for local project directories.

## 2. Required Authority Flow

### 2a. Task model (replaces multi-command sessions)

The original draft proposed `aos browser open` / `read` / `fill` / `submit`
/ `close` as separate CLI invocations sharing a `session-id`. **This cannot
work as specified**: nothing in this codebase persists a live browser
process, its Playwright context, or any in-memory handle across separate CLI
process exits (Phase 9 established this same constraint for the dev server
and enforced it structurally — no cross-invocation registry, no PID
reattachment). A `session-id` accepted by a second, later CLI invocation
would either be meaningless or would require introducing exactly the
cross-invocation daemon/registry that Phase 9's hard rule forbids.

The supported model is a single **bounded task**:

```text
aos browser task <structured-approved-task-spec>
→ validate (schema, domain allowlist, per-field/per-action risk tier)
→ mint/collect required T2 approvals (fresh, non-voice, exact-bound)
→ create isolated browser process + fresh temporary profile
→ verify egress containment and sandbox preconditions (fail closed if absent)
→ perform the bounded, pre-declared sequence of approved actions
→ return a structured, safe, untrusted-labeled result
→ tear down browser process + profile (guaranteed, bounded)
```

A task-spec is a bounded, ahead-of-time-declared sequence of operations
(e.g. "navigate to enrolled domain D at path P; read visible text; fill
field F with value V; do not submit" or "navigate to D; fill field F with V;
submit"). The task-spec itself is validated and risk-classified per
operation (§3) before anything executes; a task cannot escalate itself mid-
run by improvising new operations from page content (§6).

Hard properties of the task model:

- No browser context, process, or handle survives CLI exit, ever.
- No session/task identifier is valid in a later, separate CLI invocation.
- No background or daemon browser process exists at any point.
- No remote-debugging listener exists at any point, on any interface.
- No raw process handle or PID is exposed to a caller, model, or CLI output.
- A task that needs a follow-up action (e.g. "now read what the confirmation
  page says") is a **new task**, re-validated and re-approved from scratch;
  it is not a continuation of a prior process.

This intentionally removes the "keep a browser open across several
sequential CLI/agent calls" idea floated in the original draft's §5 — that
idea is exactly the unusable design Codex flagged, and it is not carried
forward.

### 2b. Full flow

```text
User request
→ structured browser task-spec (typed, bounded operation sequence)
→ domain and URL validation (canonical host, scheme, allowlist membership)
→ per-operation/per-field risk classification (T0 / T2 / permanently denied — see §3)
→ Human Owner approval for every T2 item, individually (non-voice, fresh, exact-bound)
→ isolated, ephemeral, network-contained browser process (one per task, no default profile)
→ bounded browser actions (fixed action set, no arbitrary JS/CDP)
→ safe observation/result (redacted, size-capped, untrusted-labeled)
→ sanitized audit events (hash-chained, no secrets/cookies/page source/raw paths)
→ structured response to caller
→ guaranteed teardown (process + profile + containment resources)
```

Forbidden authority flow (must be structurally impossible, not just
policy-forbidden):

```text
Webpage content / webpage prompt / model output
→ browser command, additional task operation, or permission escalation
```

Every webpage, DOM text, downloaded document, URL parameter, redirect
target, cookie, browser error, and tool output is untrusted input under
`SECURITY_BOUNDARIES.md` Trust Rule 3 ("Webpage content is untrusted") and
Trust Rule 6 ("Model output is untrusted until validated"). Phase 10 adds no
exception to either rule.

## 3. Risk Tiers (revised — corrects the original T0/T1 misclassification)

Codex's review correctly identified that the original T0/T1 assignments
under-classified risk: initial navigation discloses network metadata (IP,
TLS SNI, timing) to the destination and can trigger server-side state
(analytics, session creation, rate-limit counters) even before any visible
interaction; a field fill can trigger an `onchange`/`oninput` XHR that
transmits data immediately, before any "submit" click. The revised table:

| Tier | Browser action |
|---|---|
| **T0** | Validate a URL/domain locally against the registry (no network call); inspect local task-spec metadata before execution; read an already-loaded, already-fetched bounded safe observation held in the current task's own memory (no new network fetch); close/tear down the current task. |
| **T1** | **Removed.** No browser action in Phase 10 qualifies: every action either causes no network/disclosure effect (and is T0) or does (and is T2). No non-network, non-disclosing local browser action was identified during this revision that isn't already covered by T0. If a future revision identifies one, it must be named explicitly with its own approval requirements, not assumed by omission. |
| **T2** | Initial navigation to any URL; every navigation after the first within a task; opening a new tab; every individual field fill or field clear; every popup/consent-dialog interaction; every cross-domain redirect (see §4b), even to an already-enrolled domain; form submission; file upload; file download; sending any message/comment/post; and any other action with an external side effect. |
| **T3 / permanently denied** | Financial, payment, banking, trading, cryptocurrency fields or actions; account-recovery, security-answer, or security-question fields; credential/password/token/one-time-code fields (see §7 — login is deferred entirely, not merely gated); CAPTCHA interaction; arbitrary JavaScript or CDP access; browser extension installation; cookie manipulation; proxy/VPN configuration; remote control; navigation to a private-network target. |

Why initial navigation is T2, not T0/T1: loading a URL is itself an
external, observable network action — the destination server sees the
request (IP address behind any egress proxy, TLS SNI, User-Agent, timing),
may set cookies, may log the visit, and may trigger server-side analytics or
rate-limiting state changes, all before a single byte of the response is
read by AOS-Jarvis. This is not a local, reversible action; it is
indistinguishable in effect from a "GET request to a URL a script chose,"
which is exactly the class of action Phase 2's command-policy model already
treats as requiring approval for anything beyond a fixed, reviewed
read-only set. No narrower "safe initial navigation" carve-out was found
that doesn't reduce to "trust the destination," so none is proposed; the
Human Owner may choose to grant a *pre-approved navigation allowlist* at
domain-enrollment time in a future revision, but that is an explicit,
separately-approved relaxation, not the Phase 10 default.

### 3a. Approval binding (every T2 approval)

Every T2 approval, once minted, binds to all of the following before it can
be consumed, mirroring and extending Phase 9's `DevServerApproval` pattern
(`aos/safety/dev_server.py`):

- `operation` (exact enum value — e.g. `navigate`, `fill`, `submit`,
  `download`, `upload`)
- `task_id` (opaque, single task, minted fresh per task)
- `domain_id` (opaque registry ID — never a raw host string)
- `sanitized_url_identity` (canonical scheme+host+path digest — never the
  raw query/fragment, per §9)
- current allowlist state at approval time (re-validated at consumption
  time — an approval minted before a domain revocation is denied at use)
- `locator_identity` (for field operations — the bounded, resolved locator
  the approval was shown for, not a re-resolved one at execution time)
- `field_classification` (for field operations — e.g. `non_sensitive_text`;
  an approval minted for one classification cannot be reused if the field
  resolves to a different, more sensitive classification at execution time)
- `file_identity` (content hash + size, for upload/download — see §8)
- `origin` (`"terminal"` only — see §11)
- `expiry` (short-lived; unused approvals expire)
- a one-use nonce/digest, consumed exactly once, atomically, before the
  side-effecting action runs

Approval consumption is atomic and precedes the side effect. If the action
subsequently fails, the approval **remains consumed** (mirrors Phase 9's
"failed launch still consumes approval" rule) — a failed attempt requires a
fresh approval to retry, never a silent re-use.

## 4. Domain, URL, and Network Authorization

Everything in the original draft's §4 (persistent domain allowlist,
canonical/punycode host validation, HTTPS-only default, IP-literal handling,
private/local network blocking, port restrictions, subdomain policy, URL
length limits, fragment/query redaction, deny-by-default) remains, with two
corrections below.

### 4a. Real network containment is mandatory (corrects the original claim)

The original draft implied that Playwright's own request/response
interception is sufficient to prove and control the actual network
destination Chromium's socket layer connects to. **This is not true and
must not be relied upon as the sole control.** Playwright's interception
operates inside (or alongside) the browser process at the protocol layer it
instruments; it does not itself prove what a compromised or buggy renderer,
a raw socket opened by a plugin/extension (denied by policy, but the
*absence* of that policy control is exactly what this section protects
against), or an unhandled protocol (WebSocket upgrade, QUIC, a worker's
independent fetch) actually reaches at the OS network layer. Application-
layer URL/request interception is **defense in depth, not sufficient SSRF /
DNS-rebinding containment** on its own.

Phase 10 therefore requires, as a hard precondition to launching any browser
process:

- **Independent OS/container egress filtering**, or a **locally controlled
  validating proxy** that all browser traffic is forced through (e.g. no
  direct route to the internet except via the proxy; OS firewall/network-
  namespace rules deny direct egress from the browser's process/user/cgroup
  to anything but the proxy or an explicitly allowed range). The mechanism
  is a Human Owner / deployment decision (container network policy, network
  namespace + nftables/iptables rules, a mandatory local proxy with its own
  allowlist enforcement) — Phase 10's code requires *that one of these
  exists and is verified active*, not a specific implementation.
- **Fail-closed launch.** If egress containment (or, per §5b, Chromium
  sandbox verification) cannot be confirmed active at task start, the
  browser task fails immediately with a clear, safe error. Phase 10 must
  never silently fall back to "run without containment."
- **Coverage for every network-capable surface**, not only the initial
  navigation: top-level frames, iframes, dedicated/shared workers, service
  workers (denied per below — but the *denial* itself must be enforced, not
  assumed), `fetch`/`XHR`, WebSocket, `EventSource` (server-sent events),
  popups/new windows, downloads, client-side (script-initiated) redirects,
  form `action` targets, prefetch/prerender hints, and any URL scheme the
  engine might otherwise handle.
- **Service workers, WebRTC, speculative prefetch, and prerender are
  disabled** at browser-launch configuration time unless a future revision
  defines how each is safely contained under the same egress policy and the
  Human Owner explicitly re-enables it. None are enabled by default in
  Phase 10.
- **One browser process and one fresh profile per task** (§2a, §5b) — this
  bounds the blast radius of any containment gap to a single, short-lived,
  already-isolated task.
- **Low-privilege runtime identity or container** for the browser process:
  it must not run as the same OS user/privilege level that owns
  `~/.aos-jarvis`, SSH keys, or other project roots where this can be
  arranged by the deployment; where it cannot be arranged (e.g. a bare host
  with no container runtime), Phase 10 must fail closed rather than launch
  unconfined (see §5b).
- **Read-only filesystem for the browser process** except a narrowly
  mounted task-output/download-quarantine location (§8). No access to the
  Human Owner's home directory, personal browser profile/data, SSH keys or
  other credential/config files, any AOS-Jarvis project root, the audit
  database, or process environment secrets.
- **Guaranteed process-tree cleanup** on timeout, cancellation, crash, or a
  cleanup-step failure itself (§5, §9) — a hung or partially-cleaned-up
  containment boundary (e.g. a leaked network namespace or an orphaned proxy
  child process) is treated as a cleanup failure and audited as such, not
  silently ignored.

This section states plainly: **application-layer URL/host checks (§4 base,
canonical-host validation, redirect revalidation) are defense in depth. They
are not, by themselves, sufficient SSRF or DNS-rebinding containment.**
Sufficient containment requires the OS/container/proxy layer above. See
`docs/PHASE_10_BROWSER_THREAT_MODEL.md` TM-03/TM-04 for the updated
residual-risk framing.

### 4b. Redirect policy (corrects an internal inconsistency)

The original draft's §3 said cross-domain redirects require fresh T2
approval, but its §4 described redirect handling only as "revalidate against
the allowlist," without stating the approval requirement in the same place,
and its §10 CLI/schema sketch implied redirects could be silently followed
once a domain was enrolled. This revision states one unambiguous rule,
replacing all prior redirect language in this document and in
`docs/PHASE_10_BROWSER_TEST_PLAN.md`:

- **Same-domain redirect** (post-normalization host identical to the
  current task's already-approved domain): revalidated against the full
  §4 base URL/network rule set (scheme, port, private/loopback denial,
  resolved-address recheck) and permitted only if every check passes. No
  additional approval beyond the task's existing navigation approval, since
  the domain identity hasn't changed.
- **Cross-domain redirect** (post-normalization host differs from the
  current task's approved domain), **even to a domain that is separately
  enrolled and currently active in the registry**: requires a **fresh** T2
  approval before the browser is permitted to follow it. Enrollment
  establishes eligibility, not standing consent to arrive there via
  redirect from somewhere else — a redirect chain can be used to obscure
  which site is actually being interacted with, so each hop that changes
  the destination domain gets its own fresh confirmation naming both the
  originating and the target domain.
- **Redirect depth and loop controls**: a hard depth cap (normative
  constant, §5a) on the number of hops per navigation; exceeding it fails
  the navigation closed, not partially.
- **Validation at every hop**, not only the first and last.
- **Client-side redirects are in scope**: `<meta http-equiv="refresh">`,
  `beforeunload`/`onload`-triggered `location` changes, iframe/popup
  navigations, form `action` submissions that redirect, and any
  script-initiated navigation are all subject to the identical same-domain/
  cross-domain rule above — there is no exemption for "the page's own
  script did it" versus "the server's HTTP redirect did it." Both are
  untrusted-origin navigation attempts under Trust Rule 3.

## 5. Browser Process, Isolation, and Resource Bounds

### 5a. Normative resource limits

The original draft listed session limits as "proposed" values with no
stated consequence for treating them as anything but binding. This revision
makes them **normative constants** — implementation-time defaults that
require their own Human Owner sign-off to change, not aspirational
suggestions:

| Limit | Value | Consequence when exceeded |
|---|---|---|
| Task timeout (absolute) | 10 minutes | Task force-terminated, `browser.task.timed_out` audited |
| Task timeout (idle, no action in window) | 2 minutes | Task force-terminated |
| Concurrent browser processes | 1 (Phase 10 does not support concurrent tasks) | A second task request is denied/queued, never silently parallel |
| Concurrent tasks | 1 | Same as above |
| Tabs/pages per task | 3 | New-tab request denied once reached |
| Navigation depth per task | 10 | Task fails closed once reached |
| Redirect depth per navigation | 5 | Navigation fails closed once reached |
| Responses buffered per task | 100 | Task fails closed once reached |
| Response body size (single response) | 25 MB | Response aborted, navigation fails |
| Total task bandwidth | 100 MB | Task force-terminated |
| Download size | 50 MB | Download aborted, partial bytes discarded |
| URL length | 2048 bytes | Denied before navigation |
| Host length | 253 bytes | Denied before navigation |
| Path length (recorded/audited) | 512 bytes | Denied before navigation; longer paths hashed, not stored raw, per §9 |
| Field/locator identity length | 256 bytes | Denied at task-spec validation |
| Page title length (as read, before redaction/truncation) | 512 bytes | Truncated at extraction |
| Audit payload field length (any single field) | 1024 bytes | Truncated before write |
| Browser process CPU budget | operator-configured cgroup/container limit; Phase 10 code assumes containment enforces this, does not itself schedule CPU | Process killed by containment layer; Phase 10 treats this as a crash (§5, `browser.session.failed`) |
| Browser process memory budget | operator-configured cgroup/container limit | Same as above |
| Browser process file-descriptor budget | operator-configured cgroup/container limit | Same as above |

These are defaults for the initial implementation proposal; the Human Owner
may adjust them before or at activation, but Phase 10 must not launch with
*no* limit in any row above.

### 5b. Process and sandbox model (revises the original "context, not
process, per session" design)

The original draft's §5 proposed one long-lived Playwright `Browser`
process hosting many isolated `BrowserContext`s across the session's
lifetime, explicitly framed as spanning "several sequential CLI/agent calls
within one logical task." That framing depended on the multi-command
session model this revision removes (§2a) and is not carried forward.

Revised model:

- **One browser process and one fresh temporary profile per task.** Every
  `aos browser task` invocation launches a new Chromium process against a
  freshly created, empty temporary user-data directory, and both are torn
  down when the task ends. There is no process reuse across tasks.
- **Chromium sandbox is mandatory.** `--no-sandbox` (and any equivalent
  flag that disables the renderer/GPU process sandbox) is **permanently
  forbidden** in Phase 10, with no configuration override. Launch fails
  closed if sandbox verification (the same category of precondition check
  as egress-containment verification, §4a) cannot be confirmed — e.g. an
  environment where the sandbox's required kernel features (user
  namespaces, seccomp-bpf) are unavailable and no alternative containment
  (a container runtime providing equivalent isolation) is present.
- **P10-R1 zygote clarification (Human Owner, 2026-07-12).**
  `--no-sandbox` remains forbidden on every process. `--no-zygote-sandbox`
  is accepted only for a full-Chromium `--type=zygote` process whose parent is
  in the verified browser tree. Every renderer, GPU, network-service, and
  utility process must independently show zero effective capabilities,
  `NoNewPrivs=1`, seccomp filtering, and namespace evidence in `/proc`; any
  other placement or missing evidence fails closed. The rootless P10-R1
  runtime may add only namespaced `CAP_SYS_CHROOT` for Chromium's `chroot`.
  No other capability, privileged mode, host namespace, host mount, runtime
  socket, or host network is authorized.
- **No browser daemon, ever.** No component of Phase 10 starts a
  long-running browser process independent of a specific, in-flight,
  audited task.
- **No raw PID authority.** Mirrors Phase 9's `SafeProcessHandle`
  (deliberately no PID field): a Phase 10 handle exposes only an opaque
  task ID, state, and safe metadata (domain ID, started-at, action count) —
  never a Playwright object, PID, or CDP endpoint, to any caller including
  the model.
- **No cross-invocation session or process management.** No `status`,
  `list`, `attach`, or `stop <id>` command targets a browser process from a
  different CLI invocation than the one that created it, mirroring Phase
  9's C-2 hard rule for the dev server exactly.
- **No remote-debugging listener on any interface**, loopback included —
  the original draft only forbade a *non-loopback* CDP listener; this
  revision forbids any CDP network listener at all, since Playwright does
  not require one bound to a TCP port for its own operation (it can drive
  the browser over a local pipe), and a loopback listener is still a local
  attack surface Phase 9's dashboard/dev-server precedent already treats as
  meaningful.
- **No personal browser profile, ever.** Unchanged from the original draft:
  never `~/.config/google-chrome`, never any existing profile path, no
  imported cookies/history/extensions/password store.
- **Guaranteed teardown.** Task completion, failure, timeout, or
  cancellation always: closes all pages, closes the browser process (kill
  after a bounded grace period if it does not exit cleanly, mirroring Phase
  9's `stop_timeout_seconds` → `TimeoutExpired` → kill pattern), deletes the
  temporary profile directory, releases any containment/proxy resources
  allocated for the task, and emits exactly one terminal audit event.
  Cleanup runs in a guaranteed-execution path (`finally`-equivalent) so it
  executes even when the triggering action failed. A cleanup-step failure
  itself is visible (`browser.session.cleanup_failed`), never silently
  swallowed or reported as success.

### 5c. Browser supply-chain controls (new — required fix 12)

- **Browser binary source**: the Playwright-managed Chromium build (via
  `playwright install`), not a system-package or user-supplied binary — this
  keeps the binary's provenance tied to a single, auditable install path.
- **Version pinning**: the Playwright Python package version is pinned
  exactly (not a floating range) in `pyproject.toml` when Phase 10 is
  implemented; the Chromium build it installs is implicitly pinned by that
  package version.
- **Integrity verification**: rely on Playwright's own install-time
  download integrity checks; Phase 10 does not invent a parallel checksum
  mechanism, but launch must fail closed (not proceed with a best-effort
  browser) if the expected managed browser binary is absent or the
  installed version does not match the pinned expectation.
- **Update process**: browser/Playwright version bumps are a normal
  dependency-update PR, reviewed like any other `pyproject.toml` change —
  no auto-update mechanism inside Phase 10 itself.
- **Minimum supported version**: whatever Playwright version is pinned at
  implementation time; documented in the implementation report when Phase
  10 is built.
- **Browser version as safe session metadata**: the installed Chromium/
  Playwright version is safe to record in audit metadata (it is not a
  secret) and should be, to aid future incident triage.
- **Launch failure on unmet prerequisites**: browser binary missing/
  mismatched, sandbox unverifiable (§5b), or egress containment unverifiable
  (§4a) are each independently fail-closed conditions — any one being true
  is sufficient to refuse to launch, with a clear, safe, non-leaking error
  message.

## 6. Prompt-Injection Defense and the Untrusted-Content Envelope

Trust-origin handling (extends `SECURITY_BOUNDARIES.md` Trust Rules 1–7,
adds no new trusted source) is unchanged from the original draft's table.
This revision adds a concrete typed structure, replacing the original
draft's more abstract "labeled envelope" language:

```text
UntrustedBrowserObservation:
  source_domain_id: str          # opaque registry ID, never a raw host
  source_url_digest: str         # canonical scheme+host+path hash, never raw query/fragment
  content_type: enum             # e.g. VISIBLE_TEXT, STRUCTURE_OUTLINE, ERROR_BODY
  bounded_text: str              # size-capped (per §5a), redaction-swept (Phase 6 module extended)
  truncated: bool
  injection_suspected: bool      # conservative pattern match, informational only
  provenance: Literal["browser"] # fixed; never reassignable by any caller
```

Hard rules governing this structure, all structural (enforced by AOS-Jarvis's
own code, never by asking the model nicely):

- It is **never** interpolated into a system or developer instruction
  channel — it stays in a data slot, structurally separate from instruction
  content the same way Phase 6 keeps `ModelRequest` system content separate
  from redacted user/tool content.
- It **cannot** be converted directly into a tool request. A
  `UntrustedBrowserObservation` is not, and cannot be coerced into, a
  `ToolCall`. Producing a new browser task operation always requires a fresh
  pass through validation → risk classification → approval (§2), regardless
  of what an observation contains.
- Browser-derived content **cannot select** domains, URLs, locators, fields,
  upload paths, or approval parameters for any subsequent operation — those
  are always supplied by the caller's own structured request, validated
  independently of anything read from a page.
- Model output derived from a `UntrustedBrowserObservation` **cannot
  initiate another browser action** without a fresh, explicit Human Owner
  instruction — a model summarizing page content and then "deciding" to
  fill a field is not a valid trigger; only a new, separately-issued user/
  agent request re-validated from scratch is.
- Page text or fabricated JSON inside `bounded_text` **cannot reconstruct a
  tool call** — the schema layer never accepts a "tool call" shaped value
  read out of page content as equivalent to a real `ToolCall`.
- `provenance` **survives** model summarization and memory processing: any
  derived record stored in Phase 4's memory system that traces back to a
  `UntrustedBrowserObservation` retains a marker that its origin was
  browser-derived, untrusted data — it is never silently promoted to
  trusted status by passing through a summary step.
- `injection_suspected` (from the conservative pattern match described
  below) **cannot reduce risk or suppress provenance** — it is a visibility/
  logging signal only, never a basis for skipping a check or granting more
  trust to the content it flags. A false negative on this flag does not
  weaken any structural control above, because none of those controls
  depend on the flag being correct.

Everything else in the original draft's §6 (injection pattern detection
producing `browser.injection_suspected` as informational logging, no
auto-submit from `<meta refresh>`/auto-submitting forms/`beforeunload`/
`onload`, every T2 action requiring an explicit user-supplied approval)
remains, restated in terms of the task model (§2a) rather than the removed
session model.

## 7. Credentials and Login (deferred, not merely gated)

The original draft contained an internal contradiction: §3 listed "login
(submitting credentials of any kind)" as T2-approvable, while also
describing credential handling as effectively out of scope. Codex's review
correctly flagged this as contradictory language that would allow plaintext
automated login under the right approval sequence. This revision removes
the contradiction by **deferring all login and credential automation
entirely** — Phase 10 does not implement it, not even behind approval.

Phase 10 must prohibit, structurally (schema-level rejection, not
runtime-only policy):

- Password fields (any field with `type="password"` or an equivalent
  semantic role).
- Credential fields of any kind.
- API keys.
- Tokens (session tokens, bearer tokens, API tokens).
- One-time codes / two-factor codes.
- Recovery values (recovery codes, recovery email/phone entry in a
  recovery-flow context).
- Security-question / security-answer fields.
- Financial/payment fields (account numbers, card numbers, routing numbers,
  CVV, expiry — already permanently denied per §3, restated here for
  completeness).
- Browser password-store access (already denied per §3, restated here).
- Automatic credential filling of any kind.
- Credential input arriving through **any** channel Phase 10 touches: CLI
  arguments, JSON task-spec fields, config files, environment variables read
  by the browser tool, audit records, memory records, model prompts/
  responses, shell history, or a voice transcript.

If the Human Owner directly interacts with the page themselves (i.e. Phase
10 is not automating the credential-entry step at all — the Human Owner is
looking at their own separately-controlled interactive session), that is
outside Phase 10's automation boundary entirely and not something this
contract needs to gate, because AOS-Jarvis is not the actor performing it.

**Credential-manager-assisted or direct Human Owner credential entry through
AOS-Jarvis itself is deferred to a future, separately approved phase.** That
future phase would need its own contract, threat model, and test plan
addressing credential-reference handling (never plaintext through the tool's
own request schema), and is explicitly out of scope here.

## 7a. Non-Sensitive Field Fill (every fill is its own fresh T2 action)

Field fill is not a bulk or session-scoped grant — every individual field
fill and every individual field clear requires its own fresh T2 approval,
consumed before that specific write occurs:

- **Exact field/locator identity** is part of the approval binding (§3a) —
  an approval minted for one locator cannot be reused for a different one,
  even on the same page.
- **Field-type and label classification** (e.g. `non_sensitive_text`,
  `search_query`, `comment_draft`) is determined by AOS-Jarvis's own code
  from the resolved accessibility-tree node, not trusted from a caller-
  supplied label string.
- **Disclosure preview without unnecessary logging**: the approval-request
  preview shown to the Human Owner displays the value about to be written
  (so they can confirm it's correct) but that value is never logged,
  displayed again, or persisted anywhere beyond the interactive confirmation
  prompt itself — not in CLI history-visible arguments, not in audit, not in
  a model prompt, not in an error message.
- **Exact destination domain and current page/task context** are shown in
  the same preview.
- **Fresh, non-voice Human Owner approval for each fill**, and a **separate
  fresh approval for any subsequent submission** — filling three fields and
  submitting a form is four separate T2 approvals, not one.
- **No value in CLI arguments** (a value passed as a bare CLI arg would leak
  into shell history and process listings — the interactive confirmation
  flow must collect the value itself, not accept it as an argv token), audit,
  memory, model prompt, shell history, or error text.
- **Denied fields**: any field that resolves to password, credential, token,
  financial, recovery, or security-answer classification (§7) is denied at
  the classification step, before any approval prompt is even offered —
  there is no approval path that can override this classification.
- **Disclosure-behavior tests are explicit requirements** (not assumed
  safe): autosave-on-blur, XHR-on-input-change, and similar "the page
  transmits data before you click submit" behaviors must have dedicated
  test coverage (see `docs/PHASE_10_BROWSER_TEST_PLAN.md` TP-FORM-06..08),
  since they mean a field write can itself be the external-effect action,
  not just a local draft.

## 8. Downloads, Quarantine, and Promotion

### 8. Downloads

All of the original draft's base download rules remain (T2 approval naming
exact source URL and destination; both initiating and final post-redirect
domain must be allowlist-approved; filename sanitized against traversal
using Phase 1's `paths.py` approach; MIME/type allowlist excluding
executables/archives; hard size cap per §5a; content hash recorded, content
never embedded in audit payload; no automatic open/execute ever), with the
quarantine and promotion model strengthened as follows.

**Quarantine location**, precisely defined:

- Physically **outside every approved project root** — not a subdirectory
  of any `ApprovedProjectRegistry` entry, so it cannot be reached by
  path-prefix logic that trusts project roots.
- **Inaccessible by default to every existing tool capability**: the
  filesystem tools (`fs.read`/`fs.write`/`fs.edit`/`fs.search`/`fs.list`),
  the shell runner, the model layer, the memory/indexing system, the agent
  loop, the workspace tools, and the dashboard must have no path that
  resolves into the quarantine directory — this is enforced the same way
  Phase 1 already denies secret paths: by never granting the quarantine
  root as part of any approved root set.
- **Created with restrictive permissions** (owner-only read/write; no
  group/world access) at task-start time if it does not already exist.
- **Never scanned, parsed, summarized, indexed, or executed automatically**
  by any AOS-Jarvis component — a quarantined file is inert data until a
  distinct, explicit promotion action (below) moves it somewhere else.

**Download promotion**, defined as its own operation, separate from the
download itself:

- A **separate, exact-file T2 operation** (`browser.download.promote` or
  equivalent) — downloading a file and later using it are two different
  approved actions, never one approval covering both.
- Approval binds to: file identity (path within quarantine), content hash,
  size, safe filename metadata (sanitized, traversal-checked), destination
  path (must resolve inside an approved project root via the existing
  `PermissionEngine`), origin (`"terminal"` only), and expiry.
- **Destination path is revalidated immediately before promotion executes**
  — not only at approval-mint time — closing the same class of TOCTOU gap
  Phase 9's F-2 fix addressed for dev-server approvals.
- **Collision policy defined**: promotion to an existing destination path
  fails closed (denied, requires an explicit different destination or
  explicit overwrite confirmation as its own distinct approval) rather than
  silently overwriting.
- **Audit lifecycle defined**: `browser.download.promotion.requested` /
  `.completed` / `.denied` / `.failed`, following the same exactly-one-
  terminal-event rule as everything else (§9).
- **No background retention scheduler.** Quarantine cleanup (deleting
  unpromoted files past the retention window) happens only at bounded task
  startup (a new task checks and sweeps expired quarantine entries before
  proceeding) or via an explicit, separate cleanup command — never via a
  persistent timer/daemon process, consistent with §5b's "no daemon, ever."
- **Type checking uses four signals that must all agree with the
  allowlist**: declared `Content-Type` header, file extension, sniffed MIME
  (magic-byte detection independent of the declared header), and an
  executable-magic-bytes check (ELF/PE/Mach-O and script shebangs). A
  mismatch among these (e.g. a `.pdf`-named file with an executable magic
  header) is denied, not resolved by trusting any single signal.
- **Oversized downloads abort mid-stream** without retaining the partial
  file — the streaming write is capped at the size limit (§5a) and any
  partial bytes already written are deleted, not left as a truncated file
  in quarantine.

### 8a. Uploads

All of the original draft's base upload rules remain (T2 approval naming
exact local path and destination; path resolved through `PermissionEngine`/
`validate_path`, which already denies secret/dangerous paths; content hash
recorded; no directory upload; no automatic retry after failure), with
approval binding made explicit and complete:

- Approval binds to: project ID (of the approved root the file lives in),
  canonical source path, file identity (inode or platform-equivalent
  stable identity, in addition to path), size, cryptographic hash,
  destination domain ID, target/form/action identity on the destination
  page, origin (`"terminal"` only), and expiry.
- **Revalidated immediately before consumption** — path, hash, and size are
  rechecked right before the upload executes, not only at approval time.
- **The same safely opened file object that was validated is what gets
  uploaded** — the file is opened once, validated (path/hash/size), and
  that same open file handle/descriptor is what's read for the upload; it
  is never re-opened by path between validation and use, which would allow
  a symlink swap or content replacement in between.
- **Any symlink or content/path replacement detected between preview and
  use is denied and consumes the approval** — a detected TOCTOU attempt is
  treated as a failed, consumed attempt requiring a fresh approval to retry,
  not silently re-validated and retried automatically.
- No directory upload, no automatic retry, and no upload of any file
  matching the existing `SECRET_FILE_PATTERNS`/`check_secret_path`/
  `check_dangerous_path` checks (already enforced via `validate_path`,
  restated here for completeness).

## 9. Auditing

### 9a. Audit privacy (strengthened — required fix 9)

The original draft's fragment/query redaction rule is retained but
tightened: **raw URL path segments are not audited by default at all**, not
merely the query/fragment.

Audit payloads record **only**:

- Opaque `domain_id` (never a raw host string).
- Scheme category (`https` / `http` — enrolled-only category, not a raw
  scheme string that could carry unexpected values).
- Port classification (`default` / `enrolled_nondefault`), not a raw port
  number beyond what's needed to distinguish those two cases.
- A `path_present` boolean.
- A bounded path **hash** (not the raw path), or, where a human-readable
  audit trail is genuinely needed for a specific domain, a sanitized route
  *template* the domain's enrollment record explicitly opts into recording
  (e.g. `/search` as a template, never `/search?q=<raw text>`) — this is an
  explicit, narrow, per-domain allowlist decision, never the default.
- Typed `operation`, `outcome`, `risk_tier`, and `origin` fields.
- Opaque `task_id`.

Audit payloads **never** record: raw paths, raw query strings, raw
fragments, page titles, locator labels, filenames (beyond what §8's
sanitized-safe-filename-metadata explicitly allows for download/upload
events), headers, cookies, page source/HTML, form field values, prompt
text, downloaded file bytes, tokens, credentials, PII, process IDs, process
objects, or raw exception text/tracebacks (mirrors Phase 8's F8-1 lesson —
`"error": "provider_error"`-style typed sentinels, not raw error strings).

### 9b. Normative lifecycle state machine (new — required fix 9)

Every browser task, and every T2 action within a task, follows this exact
state machine:

```text
REQUESTED
  → VALIDATED
  → APPROVAL_REQUIRED
  → APPROVED
  → STARTING
  → RUNNING
  → COMPLETED | DENIED | FAILED | TIMED_OUT | CANCELLED   (terminal)
  → CLEANUP
```

Requirements, mirroring Phase 9's independently-verified F-1 fix pattern
exactly:

- At most **one** `REQUESTED`-equivalent marker per task/action — no
  duplicate initial audit rows.
- **Exactly one** terminal event (`COMPLETED`, `DENIED`, `FAILED`,
  `TIMED_OUT`, or `CANCELLED`) per task and per individual T2 action. A
  rejection path must `return` a safe result directly, never `raise` an
  exception that a caller then separately catches and re-audits — this was
  exactly Phase 9's F-1 bug and is a named test requirement here (see
  `docs/PHASE_10_BROWSER_TEST_PLAN.md` TP-AUDIT-01/02).
- `CLEANUP` events (`browser.session.cleanup_completed` /
  `.cleanup_failed`) are **not** additional terminal outcomes — they follow
  a terminal event and describe teardown, not the task's own result.
- **Cleanup failure remains visible**: a `.cleanup_failed` event is emitted
  and is itself audited distinctly, never silently absorbed into a
  `.cleanup_completed` for optics.
- **Mixed-outcome audit-chain tests are required**: a test sequence
  containing successful, denied, timed-out, and cancelled actions within
  one mixed activity run must still produce a valid hash chain end to end
  (`docs/PHASE_10_BROWSER_TEST_PLAN.md` TP-AUDIT-06), extending Phase 9's
  audit-chain-integrity test pattern.

Proposed safe browser audit event types (namespaced `browser.*`, following
the `workspace.*` naming precedent from Phase 9) are otherwise unchanged
from the original draft's list, with `browser.download.promotion.*` and
`browser.url.rebinding_denied` added per §8 and §4a.

## 10. CLI and Agent Interface (proposed names — not implemented)

Replaces the original draft's multi-command session sketch (§2a explains
why).

```text
aos browser domain add <host> --approve
aos browser domain list
aos browser domain revoke <domain-id>
aos browser task <task-spec-file-or-inline>   # the only execution entrypoint
aos browser quarantine list
aos browser quarantine promote <file-id> --dest <project-id> --approve
aos browser quarantine cleanup
```

There is no `open`, `read`, `fill`, `submit`, or `close` as independent,
separately-invokable CLI subcommands operating on a `session-id` — those
operations exist only as **entries inside a single task-spec** passed to
`aos browser task`, which runs them all within one process's lifetime and
exits.

Structured task-spec schema (proposed shape, mirrors Phase 9's
`WorkspaceRequest`):

- `domain_id`: opaque registry ID (never a raw host/path — mirrors Phase 9's
  `workspace project_id must be an opaque registry ID` rule, enforced the
  same way in `ToolRegistry.validate`)
- `operations`: an ordered, bounded list of typed operation entries
  (`navigate`, `read`, `fill`, `clear`, `back`, `submit`, `download`,
  `upload`), each independently risk-classified (§3) and, for every T2
  entry, carrying its own approval reference (§3a) — not one approval for
  the whole task
- `canonical_url`: only present for a `navigate` entry; validated
  server-side regardless of caller-supplied value
- `element_locator`: a bounded, declarative locator (unchanged from the
  original draft) — never a raw CSS/XPath string sourced from model or page
  content without validation
- `field_data`: bounded key/value map for `fill`, size-capped,
  redaction-swept before audit, and — per §7a — never accepted as a bare CLI
  argument
- `approvals`: a list of opaque approval-object references, one per T2
  operation entry in `operations`, each structurally identical in spirit to
  Phase 9's `DevServerApproval` — unforgeable outside the minting module,
  mintable only from a non-voice terminal-origin, human-confirmed flow,
  single-use, durably consumed before its specific action
- `origin`: `"terminal"` | `"agent"` | `"voice"` (voice can never appear on
  a request carrying any T2 operation — see §11)

**Element locator policy** is unchanged from the original draft: a
constrained locator vocabulary resolved by AOS-Jarvis's own code against a
bounded accessibility-tree snapshot, never a raw CSS selector, XPath
expression, or arbitrary DOM query taken verbatim from model or page-content
output.

Models must never provide, and the schema must reject: arbitrary
JavaScript, raw browser command strings, executable paths, raw CDP
commands, unbounded/raw selectors, credentials (§7), or unrestricted
(non-enrolled) URLs. This mirrors exactly how Phase 9's `ToolRegistry.
_workspace_spec` restricts agent-supplied args to `{"project_id"}` only and
structurally cannot carry a live approval object through JSON-serializable
`ToolCall.args`.

## 11. Voice and Model Boundaries

Unchanged in substance from the original draft, restated against the task
model:

- Voice-originated browser requests always retain `yes=False` — unchanged
  Phase 8 Hard Rule 2, extended verbatim to Phase 10.
- Voice can never approve any T2 operation entry within a task-spec.
- Model output alone can never approve a browser action — mirrors ADR-0005;
  a model may *propose* a structured task-spec, but every T2 entry's
  approval minting requires the same non-voice, terminal-origin,
  human-confirmed flow Phase 9 established for dev-server approvals.
- Browser page content can never approve a browser action (§6).
- Any T2 operation requires fresh Human Owner confirmation through a
  non-voice interface (terminal; the Phase 7 dashboard remains read-only
  and is not extended by Phase 10).
- Dry-run never creates a real browser process, real navigation, or any
  external effect, and never consumes an approval — mirrors Phase 9's
  `dry_run()` never calling `consume_dev_server_approval` or
  `launch_adapter.launch`.
- Dry-run must not persist any browser/domain/quarantine state.

## 12. Required Test Plan

See `docs/PHASE_10_BROWSER_TEST_PLAN.md` for the full test plan, now split
into two required layers per the contract remediation:

1. **Deterministic mocked unit tests**, no external network, no live
   browser — the original draft's baseline requirement, unchanged in
   spirit.
2. **Real-browser integration tests** using isolated local fixture
   infrastructure (a local test HTTP server bound to loopback, serving
   fixed fixture content) with **no external-network dependency**, required
   specifically to verify properties that cannot be proven by mocking the
   engine boundary: real sandbox launch configuration, real egress
   containment behavior, real process-tree cleanup, real worker/service-
   worker/WebSocket behavior, and the absence of orphan processes.

Summary requirement (unchanged): no test may depend on a live public
website, a real credential, a real payment, a real upload target, or a
browser process that outlives its test.

## 13. Hard Rules

1. A webpage is untrusted input, never authority.
2. A browser action may not bypass permission, risk, approval, validation,
   or audit boundaries that already exist for every other AOS-Jarvis
   capability.
3. No T2 browser action may occur without fresh, non-voice Human Owner
   approval, unforgeable by voice, model, or page content, bound to the
   exact operation/field/file per §3a.
4. Browser processes and profiles are isolated and ephemeral by
   construction: one process, one fresh temporary profile, per task; no
   shared profile, cookies, history, or extensions; nothing survives past
   task teardown.
5. No raw credentials, cookies, tokens, sensitive form values, page source,
   or downloaded file bytes may appear in audit records, memory, or model
   prompts.
6. No unrestricted browser automation, arbitrary JavaScript execution, CDP
   command access, or browser extension installation, ever, in Phase 10.
7. No private-network, loopback, link-local, unique-local, metadata,
   multicast, unspecified, reserved, or otherwise non-global-unicast
   navigation target, ever, in Phase 10, with no per-domain override.
8. No payment, financial, account-recovery, CAPTCHA-solving, or any login/
   credential-automation activity, ever, in Phase 10 (§7 — deferred, not
   merely gated).
9. Every redirect — server-side or script-initiated — requires the same
   URL/network validation as the initial navigation target, hop by hop,
   with a hard depth cap; every cross-domain redirect additionally requires
   a fresh T2 approval (§4b), even to an already-enrolled domain.
10. Browser process and profile cleanup is mandatory, bounded, and produces
    exactly one terminal audit event per task/action; no orphan browser
    process may remain after a request completes, fails, times out, or is
    cancelled.
11. Independent OS/container egress containment or a locally controlled
    validating proxy, and Chromium sandbox verification, are mandatory
    preconditions to launching any browser process; launch fails closed if
    either cannot be confirmed active (§4a, §5b).
12. No browser session or process may be reused, reattached, or referenced
    across separate CLI invocations; every task is self-contained from
    launch to teardown within a single foreground process (§2a, §5b).

## 14. Exit Criteria (measurable)

- All Phase 0–9 tests remain green (no regression) — reproducible via the
  same `pytest -q` full-suite command used for every prior phase gate.
- The browser domain allowlist persists across process restarts and is
  revalidated (host, port, scheme, resolved-address-vs-private-range) on
  every use, not only at enrollment time.
- Every navigation target and every redirect hop (server-side and
  script-initiated) is validated against the domain allowlist and the
  private/loopback denylist before the browser engine is permitted to load
  it, and every cross-domain redirect additionally requires a fresh T2
  approval.
- The browser runs only inside an isolated, ephemeral, single-use process
  and temporary profile per task, verified sandboxed and egress-contained
  before launch, with no default profile/cookie/history/extension
  inheritance and no reuse across tasks.
- Browser-derived content is structurally represented as a typed
  `UntrustedBrowserObservation` (§6) at every boundary it crosses — verified
  by dedicated prompt-injection tests, not just by documentation.
- Every T2 operation (navigation, field fill/clear, submit, login-adjacent
  actions — none of which exist, per §7 — upload, download, download
  promotion) requires its own fresh, non-voice, exact-bound Human Owner
  approval, consumed durably before the action executes and remaining
  consumed on failure.
- Voice, model, and page content cannot mint, forge, or otherwise supply a
  valid T2 approval, under test.
- No credentials, cookies, tokens, or other secrets leak into audit
  records, memory, or model prompts, under test.
- Download and upload controls (MIME/type-signal agreement, size caps,
  path-traversal denial, secret-file denial, quarantine isolation from
  every other capability, promotion as a separate approved operation) pass
  deterministic tests.
- Every browser task and every T2 action lifecycle has exactly one terminal
  audit event, under test, including in mixed-outcome sequences.
- Session/process cleanup is bounded and reliable under test, including
  simulated crash and timeout conditions, verified in both the mocked unit
  layer and the real-browser integration layer; no browser process remains
  after failure or cancellation.
- Egress containment and sandbox-verification fail-closed behavior is
  covered by test: a simulated "containment unavailable" or "sandbox
  unverifiable" condition prevents launch, with a safe, non-leaking error.
- `python -m compileall -q aos tests`, `ruff check` on all new/changed
  files, any configured type checker (none currently configured, per Phase
  9 precedent), CLI smoke checks (`--help` on every new command group),
  audit hash-chain verification, and a static bypass scan (no `shell=True`,
  no raw CDP exposure, no arbitrary-JS-eval path, no `--no-sandbox`) all
  pass.
- All Phase 10 tests in `docs/PHASE_10_BROWSER_TEST_PLAN.md` pass — the
  mocked layer with zero live-network dependency, the real-browser
  integration layer against isolated local fixtures only, never a live
  public website.

## 15. Relationship to the Existing Reserved Phase 10 Doc

`docs/phases/PHASE_10_BROWSER_TOOLS.md` (written during initial project
scaffolding) scoped Phase 10 narrowly to open/search/extract with explicit
"out of scope: form-filling, login flows, purchases." This contract expands
that scope to include field interaction (now T2, every fill individually
approved, per §3/§7a) and T2 form submission/upload/download, while
**narrowing** the original expanded-scope draft by deferring login/
credential automation entirely (§7) rather than gating it. This remains a
**material scope expansion** over the original reserved placeholder for
field interaction and is called out explicitly as an open design decision
requiring Human Owner sign-off — not silently assumed. See
`docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md` §15 for the exact list of
Human Owner decisions still required.

## 16. Design Points Still Requiring Explicit Human Owner Sign-Off

Restated from the remediation brief's "Approved Design Direction for
Revision" — these are the proposed final design, not active authorization
until the Human Owner signs off in `PHASE_CONTRACT.md`:

1. Browser lifecycle: foreground, one bounded task per invocation (§2a).
2. No browser session ID is usable across separate CLI invocations (§2a,
   §5b).
3. Mandatory independent OS/container egress containment or a validating
   proxy (§4a).
4. Browser launch fails closed if egress containment or Chromium sandbox
   verification is unavailable (§4a, §5b, §5c).
5. Private, loopback, link-local, unique-local, metadata, multicast,
   unspecified, reserved, and non-global-unicast destinations remain
   permanently denied (§4 base, §13 Hard Rule 7).
6. Login, credential-field automation, password fields, token fields,
   recovery fields, security-answer fields, and financial fields are
   deferred or permanently denied in Phase 10 (§7).
7. Non-sensitive field fill remains possible only as a fresh T2 action per
   field, because field events can immediately transmit data (§7a).
8. Every cross-domain redirect requires fresh T2 approval, even if the
   destination domain is enrolled (§4b).
9. Download quarantine is outside all ordinary approved project roots and
   unavailable to filesystem, memory, model, shell, workspace, agent,
   indexing, and auto-open paths (§8).
10. Download promotion is a separate, exact-file T2 operation (§8).
11. One browser process and one fresh temporary profile per task (§5b).
12. Chromium sandbox is mandatory; `--no-sandbox` is permanently forbidden
    (§5b).
13. No browser daemon, no raw PID authority, no cross-invocation session/
    process management, no remote debugging listener, no personal profile
    (§5b).

None of these become active authorization until the Human Owner replaces
the status line at the top of this document's `PHASE_CONTRACT.md` Phase 10
section with an explicit approval statement.
