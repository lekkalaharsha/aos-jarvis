# Phase 10 — Controlled Browser Automation: Architecture

Status: **DRAFT — NOT ACTIVE UNTIL HUMAN OWNER APPROVAL**
Date: 2026-07-11 (original) — Revised 2026-07-11 (contract remediation pass,
Claude Sonnet, following Codex's `READY WITH REQUIRED CONTRACT FIXES`
verdict).
Companion to `docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md`. This document is
planning only — no module listed below exists yet.

## 0. What Changed in This Revision

- Removed the long-lived `BrowserSessionManager` process hosting many
  contexts across sequential CLI calls; replaced with a one-process-per-task
  model (contract §2a, §5b).
- Added `egress.py` as the module responsible for verifying and, where
  Phase 10 itself manages it (e.g. a locally controlled validating proxy
  option), enforcing the mandatory OS/container/proxy egress containment
  precondition (contract §4a).
- Added `quarantine.py`, split out from the original `downloads.py`, to
  represent the quarantine/promotion split as its own component (contract
  §8).
- Added `supply_chain.py` for browser binary/version verification (contract
  §5c).
- Renamed the data-flow entrypoint from a multi-call session API to a single
  `BrowserTool.execute(task_spec)` call per contract §2a/§10.

## 1. Engine Choice and Rationale

**Recommendation: Playwright, Chromium channel, Python sync or async API.**

This matches the existing `ARCHITECTURE.md` "Reuse Strategy" note, which
already names Playwright as the intended Phase 10 browser engine — Phase 10
does not introduce a new dependency decision, it fulfills a previously
recorded one.

Rationale:

- **Isolated contexts without per-session process launch.** Playwright's
  `Browser.new_context()` gives a fully isolated cookie/storage/cache jar
  (equivalent to a private window) without launching a new OS process per
  session — this maps directly onto the contract's "one isolated
  context/session per approved task" requirement (§5) while keeping resource
  usage bounded (one browser process can host many contexts).
- **Built-in request/response interception.** Playwright exposes
  `page.on("response")` / route interception hooks, which is exactly the
  mechanism needed to implement redirect-by-redirect revalidation (§4) and
  response-size bounding (§5) without needing a custom network stack.
- **Accessibility-tree-based locators.** Playwright's locator API
  (`get_by_role`, `get_by_label`, `get_by_text`) operates against the
  accessibility tree rather than raw CSS/XPath, which is what makes the
  contract's bounded declarative locator policy (§10) implementable without
  inventing new page-parsing code.
- **No default extensions, no default profile.** A fresh Playwright launch
  has zero extensions and no imported profile by default — the "isolated by
  default" requirement is the *natural* state, not something to fight against.
- **Mature timeout/cancellation primitives**, matching the bounded-timeout
  philosophy already used in Phase 2 (`DEFAULT_TIMEOUT_SECONDS`) and Phase 9
  (`stop_timeout_seconds`).
- **CDP is used internally by Playwright but is never exposed** to callers by
  default — the contract's "no CDP exposure to model/page content" hard rule
  is enforceable by simply never threading a CDP endpoint through any public
  AOS-Jarvis API, not by fighting the library's own design.

Chromium (not Firefox/WebKit) is the recommended channel for the widest
compatibility with real-world sites and the most mature sandboxing story.

## 2. Proposed Module Layout (not implemented)

```
aos/
  browser/
    __init__.py
    types.py            # enums, dataclasses: BrowserOperation, RiskTier reuse,
                         # SafeBrowserTaskHandle, TaskOutcome-equivalent,
                         # UntrustedBrowserObservation (contract §6)
    domains.py           # ApprovedDomainRegistry, DomainEnrollmentAuthority
                         # (structural twins of Phase 9's
                         #  ApprovedProjectRegistry / HumanOwnerEnrollmentAuthority)
    url_policy.py        # canonical host validation, punycode normalization,
                         # private/loopback/rebinding checks, redirect validation
                         # (per-hop, same-domain vs cross-domain per contract §4b)
    task.py              # BrowserTaskRunner: owns exactly one task's lifecycle
                         # end to end (validate -> approve -> launch -> run ->
                         # teardown); no state survives past a single
                         # BrowserTaskRunner.run() call; no cross-task registry
    engine.py             # BrowserEngineFactory protocol + PlaywrightEngineFactory
                         # implementation; the one place Playwright is imported
    egress.py             # verifies OS/container egress containment or a
                         # locally controlled validating proxy is active before
                         # launch (contract §4a); fail-closed if unverifiable;
                         # the one place that knows how to check/enforce this
                         # precondition, separate from url_policy.py's
                         # application-layer checks
    sandbox.py             # verifies Chromium sandbox preconditions before
                         # launch (contract §5b); fail-closed if unverifiable;
                         # constructs launch args and asserts `--no-sandbox`
                         # is never present
    supply_chain.py        # pinned browser/Playwright version check, binary
                         # presence/version verification at launch time
                         # (contract §5c)
    locators.py           # bounded declarative locator resolution against the
                         # accessibility-tree snapshot
    downloads.py          # MIME/type allowlist (4-signal agreement), size
                         # caps, streaming-abort-on-oversize, path-traversal-safe
                         # filename handling (reuses aos/safety/paths.py)
    quarantine.py          # quarantine location management (outside every
                         # approved root), bounded-retention sweep at task
                         # startup, and the separate promotion operation with
                         # its own T2 approval and destination revalidation
                         # (contract §8)
    approval.py            # BrowserApproval (T2 mint/consume), structural twin
                         # of aos/safety/dev_server.py; per-operation/per-field
                         # binding (contract §3a)
    redaction.py          # extends aos/model/redaction.py (Phase 6) with
                         # browser-specific field/pattern coverage; field
                         # sensitivity classification (contract §7/§7a)
  tools/
    browser.py            # BrowserTool(BaseTool) — the single integration
                         # point registered with the agent tool registry,
                         # mirrors aos/tools/workspace.py's shape; one method,
                         # execute(task_spec), no session-scoped sub-methods
  interfaces/cli/
    browser_commands.py   # aos browser domain add/list/revoke, aos browser
                         # task <spec>, aos browser quarantine list/promote/
                         # cleanup — mirrors
                         # aos/interfaces/cli/workspace_commands.py's shape;
                         # no open/read/fill/submit/close as independent
                         # subcommands (contract §2a/§10)
  agent/
    tool_registry.py      # add workspace.*-style _browser_spec entries,
                         # T0 auto, T2 requires_approval_resolver=True per
                         # operation entry, never forwards a live approval
                         # object (existing file, extended — not a new file)
  safety/
    permissions.py        # add browser.* CAPABILITY_KINDS entries, including
                         # browser.download/browser.upload/browser.promote
                         # (existing file, extended — not a new file)
```

This layout deliberately mirrors Phase 9's `aos/tools/workspace.py` +
`aos/safety/dev_server.py` + `aos/safety/approved_projects.py` +
`aos/interfaces/cli/workspace_commands.py` split, because Phase 9's
reviewed, independently-verified pattern (opaque registry IDs, module-private
approval-minting sentinel, injectable process/engine factory, allowlisted
audit-payload fields) is the template Phase 10 should replicate rather than
reinvent. `egress.py` and `sandbox.py` have no Phase 9 analog — they exist
because Phase 10 introduces a genuinely new precondition class (OS/container-
level containment and sandbox verification) that no prior phase needed,
since no prior phase spawns a network-capable renderer process.

## 3. Data Flow (target, once implemented)

```
CLI (aos browser task <spec>) or Agent (ToolRegistry.execute)
  -> BrowserTool.execute(task_spec)
       -> _request(task_spec)                  # schema validation, reuses
                                               # WorkspaceRequest-style dataclass;
                                               # rejects arbitrary JS/CDP/raw
                                               # selectors/credentials at this step
       -> domains.ApprovedDomainRegistry.resolve(domain_id)
       -> url_policy.validate(url, registry_entry)   # canonical host, scheme,
                                               # port, private/loopback denial,
                                               # per operation entry and per
                                               # redirect hop (contract §4b)
       -> per-operation risk classification (T0/T2 -- no T1, contract §3;
                                               # reuses RiskTier from
                                               # aos/safety/risk.py)
       -> [every T2 entry] approval.consume_browser_approval(...)   # durable,
                                               # single-use, per-operation,
                                               # before that specific action
                                               # (contract §3a)
       -> supply_chain.verify()                # pinned version/binary check;
                                               # fail closed if unmet
       -> sandbox.verify()                     # fail closed if unmet
       -> egress.verify()                      # OS/container containment or
                                               # validating proxy active; fail
                                               # closed if unmet (contract §4a)
       -> task.BrowserTaskRunner.run(task_spec)   # ONE process, ONE fresh
                                               # profile, launched fresh for
                                               # this call only
            -> engine.BrowserEngineFactory (Playwright in prod,
                                             fake in tests / real-but-local
                                             fixture server in integration tests)
            -> for each operation: navigate/read/fill/submit/download/upload,
               each already risk-classified and (for T2) already approved above
            -> quarantine.stage(download)      # downloads land outside every
                                               # approved root; never auto-opened
       -> redaction.sweep(result)              # before returning to caller
                                               # and before audit; produces
                                               # UntrustedBrowserObservation
                                               # (contract §6) for any content
       -> append_event(...)                    # existing aos/safety/audit.py,
                                               # unchanged schema, new
                                               # event_type values only,
                                               # opaque-ID-only payloads
                                               # (contract §9a)
       -> guaranteed teardown                  # process kill + profile delete
                                               # + egress resource release,
                                               # runs even on failure/timeout/
                                               # cancellation (contract §5b)
  <- ToolResult(ok, output, decision)
```

A later "promote this downloaded file" action is a **separate**
`BrowserTool.execute()` call with its own task-spec (a `promote` operation
against `quarantine.py`), not a continuation of the task that downloaded the
file — consistent with contract §2a's "no session survives past task
teardown" rule applying even to a task's own follow-up actions.

## 4. Integration Points with Existing Phases (reused unchanged)

| Existing component | Reused for |
|---|---|
| `aos/safety/audit.py` (`append_event`, `verify_chain`) | All `browser.*` events — no schema change |
| `aos/safety/risk.py` (`RiskTier`, `decision_for_risk`) | T0/T1/T2 classification, identical enum |
| `aos/safety/permissions.py` (`PermissionEngine`, `CAPABILITY_KINDS`) | Download-destination and upload-source path validation — add `browser.download`/`browser.upload` capability kinds, same enforcement code path |
| `aos/safety/paths.py` (`validate_path`, `check_secret_path`, `check_dangerous_path`) | Upload source-path safety (denies `.env`, `id_rsa`, etc. automatically) and download destination-path traversal safety |
| `aos/tools/base.py` (`BaseTool`, `ToolResult`, `ToolDecision`) | `BrowserTool`'s public contract, identical shape to every existing tool |
| `aos/agent/tool_registry.py` (`ToolRegistry`, `ToolSpec`) | Agent-facing `browser.*` operations, opaque-ID arg validation, T2 approval-object-cannot-be-forwarded structural guarantee |
| `aos/model/redaction.py` (Phase 6) | Base pattern set extended with browser-specific sensitive-field detection |
| Phase 9's `DevServerApproval` design (`aos/safety/dev_server.py`) | Direct structural template for `BrowserApproval`: module-private issuer sentinel, `mint_*` requiring `human_owner_confirmed=True` + `origin=="terminal"`, `consume_*` with `hmac.compare_digest` exact-bound checks, durable single-use consumption before the action, and (per the Phase 9 F-2 fix) an independent path/identity-derived canonical binding alongside the opaque ID binding — extended in Phase 10 to bind per-operation/per-field (contract §3a), not once per session |
| Phase 9's `WorkspaceLaunchAdapter` design (`aos/tools/shell_runner.py`) | Direct structural template for `task.BrowserTaskRunner`: injectable engine factory for tests, in-memory-only tracking scoped to a single `run()` call (no PID file, no cross-invocation registry, no long-lived manager instance — stricter than Phase 9's dev-server, which is itself foreground-only but Phase 10 additionally forbids the "spans several sequential CLI calls" framing the original Phase 10 draft proposed), bounded stop/cleanup with `TimeoutExpired`-style fallback, `SafeBrowserTaskHandle`-style opaque handle with no raw engine object or PID exposed |
| Phase 9's `ApprovedProjectRegistry` / enrollment pattern (`aos/safety/approved_projects.py`) | Direct structural template for `ApprovedDomainRegistry` / `DomainEnrollmentAuthority`: fresh, terminal-origin, human-confirmed, one-use, expiring approval bound to the exact canonical host before any registry write |
| Phase 1's `validate_path` / `check_secret_path` / `check_dangerous_path` (`aos/safety/paths.py`) | Upload source-path safety and download destination/promotion-path traversal safety, unchanged, reused as-is; also the template for `quarantine.py`'s own path handling (quarantine root itself is never a member of any approved-root set, so these same checks structurally cannot resolve into it) |

No existing file's *behavior* changes — Phase 10 only adds new capability
kinds, new tool-registry entries, and new audit event types, following
exactly the same extension pattern Phase 9 used when it added
`workspace.*` entries alongside Phase 1–8's existing ones.

## 5. Why Not Alternatives

- **Selenium**: heavier, weaker native support for isolated ephemeral
  contexts (profile-per-session is the natural unit, not context-per-session),
  weaker built-in network interception story.
- **Raw CDP client (no Playwright)**: would require reimplementing
  navigation/locator/interception machinery Playwright already provides
  safely, increasing the amount of custom security-relevant code — directly
  against `CODING_RULES.md`'s "prefer simple Python over clever
  abstractions" and "avoid unnecessary dependencies" (Playwright already
  wraps CDP safely; a hand-rolled CDP client would be *more* surface area,
  not less).
- **A hosted/remote browser API**: rejected outright — Phase 10 is local-first
  per the project's core identity, and a remote browser service is a data
  exfiltration surface and a new trust boundary this contract explicitly
  does not want.

## 6. Non-Goals for This Document

This document does not specify exact function signatures, exact test
fixtures, or exact CLI flag parsing — those are implementation-phase
decisions for whoever builds Phase 10 after Human Owner activation. This
document fixes the module boundaries, the reused-unchanged integration
points, and the engine choice, so that implementation has a single
agreed-upon shape to build against and a re-reviewer has a fixed
architecture to check the implementation against.
