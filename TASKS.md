# TASKS

Status values: `Todo`, `In Progress`, `Review`, `Blocked`, `Done`.

## Pre-Phase 0 — Project Tracking Setup

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P-000 | Pre-Phase 0 | Create project tracking files | Claude | Done | High | Root docs (PROJECT_SCOPE, ARCHITECTURE, ROADMAP, SECURITY, DEVELOPMENT_WORKFLOW, etc.) |
| P-001 | Pre-Phase 0 | Create phase documents | Claude | Done | High | docs/phases/PHASE_0..12_*.md |
| P-002 | Pre-Phase 0 | Create ADRs | Claude | Done | Medium | docs/adr/0001..0007-*.md |
| P-003 | Pre-Phase 0 | Create shared agent memory files | Claude | Done | High | .agent/*_notes.md, .agent/templates/ |
| P-004 | Pre-Phase 0 | Review documentation consistency | Codex | Todo | Medium | cross-check phase files against ROADMAP/PHASE_CONTRACT |
| P-005 | Pre-Phase 0 | Prepare Phase 0 implementation prompt | Claude | Done | High | Phase 0 was already implemented in a prior session — see below |

## Phase 0 — Foundation + Audit

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P0-001 | Phase 0 | Create repo skeleton | Claude | Done | High | aos/ package with core, tools, safety, memory, models, config, evals, interfaces/cli |
| P0-002 | Phase 0 | Add Typer CLI | Claude | Done | High | aos --help, version, doctor work |
| P0-003 | Phase 0 | Add config loader | Claude | Done | Medium | ~/.aos-jarvis/config.toml created on demand; aos config show works |
| P0-004 | Phase 0 | Add SQLite audit log | Claude | Done | High | actor/event_type/action/resource/risk_tier/status/payload_json/parent_hash/event_hash schema |
| P0-005 | Phase 0 | Add audit hash-chain verification | Claude | Done | High | aos audit verify detects broken parent_hash and modified rows |
| P0-006 | Phase 0 | Add audit tamper detection tests | Claude | Done | High | tests/test_audit.py covers tampering and broken continuity |
| P0-007 | Phase 0 | Add risk tier and capability model | Claude | Done | Medium | Pydantic-based Capability/PermissionDecision, deny-by-default |
| P0-008 | Phase 0 | Add tool interface contract | Claude | Done | Medium | BaseTool/ToolResult/ToolSchema/ToolDiff in aos/tools/base.py |
| P0-009 | Phase 0 | Add eval fixture framework | Claude | Done | Medium | phase0_basic.yaml + runner, aos eval run works |
| P0-010 | Phase 0 | Add Phase 0 docs and ADRs | Claude | Done | Medium | ROADMAP, ARCHITECTURE, SECURITY, docs/*.md, ADRs |
| P0-011 | Phase 0 | Set up shared memory / communication system | Claude | Done | High | HANDOFF/TASKS/BLOCKERS/CHANGELOG templates, .agent/ notes files |
| P0-012 | Phase 0 | Review schema rename and Pydantic conversion | Codex | Done | High | superseded — Codex built directly on this schema for Phase 1 without issue |
| P0-013 | Phase 0 | Run locally on Ubuntu/Kali | OpenCode | Todo | Medium | still pending; folded into P1-008 below |

## Phase 1 — Permission Engine + Safe File Tools

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P1-001 | Phase 1 | Permission engine (allowlist, capability checks, risk tiers) | Codex | Done | High | aos/safety/{permissions,risk,paths,errors}.py |
| P1-002 | Phase 1 | Dangerous path / secret file / traversal / symlink-escape blocking | Codex | Done | High | verified: /etc, ~/.ssh/id_rsa, .env, traversal, outside-root all blocked |
| P1-003 | Phase 1 | Safe file tools (list/read/search/write/edit) | Codex | Done | High | aos/tools/fs_tools.py |
| P1-004 | Phase 1 | Snapshot create/list/get/restore | Codex | Done | High | aos/safety/snapshots.py; restore is T2 and snapshots current state first |
| P1-005 | Phase 1 | CLI: `aos fs *`, `aos snapshot *` | Codex | Done | High | aos/interfaces/cli/{fs_commands,snapshot_commands}.py |
| P1-006 | Phase 1 | Phase 1 tests | Codex | Done | High | 39 passed, 1 skipped (benign Windows symlink limitation) |
| P1-007 | Phase 1 | Phase 1 docs | Codex | Done | Medium | docs/phase_1.md, docs/permissions.md, docs/risk_tiers.md |
| P1-008 | Phase 1 | Independent verification of Codex's Phase 1 work | Claude | Done | High | full test run + manual CLI/audit walkthrough, see PROJECT_STATE.md and HANDOFF.md |
| P1-009 | Phase 1 | Run locally on Ubuntu/Kali | OpenCode | Todo | Medium | verification so far is Windows-only |
| P1-010 | Phase 1 | Persistent directory allowlist (`aos fs allow <path>`) | Unassigned | Todo | Low | currently defaults to CWD; noted as a known limitation, not a blocker |

## Phase 5 — Git and Project Assistant

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P5-001 | Phase 5 | Safe git tools, parsers, summaries, CLI, agent intents, audit, and tests | Claude | Review | High | Implementation present; Codex fixed agent/CLI cwd escape; 194 passed, 2 skipped |
| P5-002 | Phase 5 | Independent security review and final approval | Codex / Human Owner | Review | High | PASS WITH FIXES; see `docs/PHASE_5_IMPLEMENTATION_REPORT.md` |

## Phase 6 — Model Support

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P6-001 | Phase 6 | Model provider interface, types, local/cloud adapters, config, redaction, router, validation, audit events, CLI, agent integration, tests, and docs | Codex | Done | High | Final gate PASS WITH NON-BLOCKING FIXES; 228 passed, 2 skipped; see `docs/PHASE_6_FINAL_GATE_REPORT.md` |
| P6-002 | Phase 6 | Full validation and audit verify in local dev env | Codex | Done | High | Normal project venv verified compile, full pytest, non-empty 21-event audit chain, and CLI audit verify |

## Phase 7 — Read-Only Dashboard

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P7-001 | Phase 7 | Read-only dashboard, loopback CLI, templates, tests, and docs | Claude Code | Done | High | Final gate fixed read-only storage, secret-redaction, port-validation, and bounded-data issues |
| P7-002 | Phase 7 | Independent hostile security final gate | Independent reviewer | Done | High | Independently reconfirmed by Claude Sonnet; 347 passed, 2 skipped; all four fixes verified; COMPLETE |

## Phase 8 — Voice Interface

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P8-001 | Phase 8 | Voice types, config, normalization, safety, session, service | Claude Sonnet | Done | High | `aos/voice/` module; all optional deps lazy; yes=False invariant enforced |
| P8-002 | Phase 8 | STT/TTS provider interfaces and mock/local implementations | Claude Sonnet | Done | High | `aos/voice/providers/`; FasterWhisperSTT, PiperTTS, MockSTT, MockTTS |
| P8-003 | Phase 8 | `aos voice doctor/devices/listen/speak` CLI commands | Claude Sonnet | Done | High | `aos/interfaces/cli/voice_commands.py`; no mic at import time |
| P8-004 | Phase 8 | Voice tests (types/normalization, safety, session, service, CLI) | Claude Sonnet | Done | High | 98 new tests; 445 passed, 2 skipped total |
| P8-005 | Phase 8 | `docs/phase_8.md` and `docs/PHASE_8_IMPLEMENTATION_REPORT.md` | Claude Sonnet | Done | Medium | Architecture diagram, safety invariants, module table, security verification checklist |
| P8-006 | Phase 8 | Codex final gate review | Codex | Done | High | FAIL verdict stands; F8-1–F8-3 fixed during gate; F8-4 fixed by Claude Sonnet remediation pass |
| P8-007 | Phase 8 | F8-4 remediation: session lifecycle audit events | Claude Sonnet | Done | High | VoiceSessionLifecycle + 5 lifecycle methods; 476 passed, 2 skipped; report at docs/PHASE_8_F8_4_REMEDIATION_REPORT.md |
| P8-008 | Phase 8 | Independent re-gate: confirm all F8-1–F8-4 fixed | Claude Sonnet | Done | High | Reviewer-assisted PASS (see HANDOFF.md disclosure); 476 passed, 2 skipped; all four findings verified fixed |
| P8-009 | Phase 8 | Human Owner approval to open Phase 9 | Human Owner | Done | High | Approved 2026-07-11; recorded in PHASE_CONTRACT.md |
| P8-010 | Phase 8 | Live timeout traceability remediation | Codex | Done | High | Typed recording/transcription/synthesis outcomes; supplemental verification PASS; 137 focused voice tests and 484 total tests passed (2 skipped) |

## Phase 9 — Workspace and App Control

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P9-001 | Phase 9 | Implement approved workspace and app control scope | Codex/OpenCode | Done | High | Typed folder opening, confirmed single-use server approval, foreground Ctrl+C lifecycle, contextual audit, and specific path exceptions; 560 tests passed. |
| P9-002 | Phase 9 | Independent re-review + F-1/F-2/N-1 follow-up fixes | Claude Sonnet | Done | High | Clean PASS, no outstanding findings; 564 passed; see `docs/PHASE_9_INDEPENDENT_RECONFIRMATION.md` |
| P9-003 | Phase 9 | Human Owner sign-off | Human Owner | Done | High | Recorded in `PHASE_CONTRACT.md` 2026-07-11; Phase 9 COMPLETE; B007 CLOSED |

## Phase 10 — Controlled Browser Automation

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P10-001 | Phase 10 | Draft contract, threat model, test plan, architecture, and DRAFT `PHASE_CONTRACT.md` section | Claude Sonnet | Done | High | No code written; see `docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md`, `docs/PHASE_10_BROWSER_THREAT_MODEL.md`, `docs/PHASE_10_BROWSER_TEST_PLAN.md`, `docs/PHASE_10_BROWSER_ARCHITECTURE.md` |
| P10-002 | Phase 10 | Human Owner review of scope expansion vs. original placeholder | Human Owner | Done | High | Approved as part of the 2026-07-11 Phase 10 implementation instruction |
| P10-003 | Phase 10 | Human Owner activation decision | Human Owner | Done | High | Approved 2026-07-11; recorded in `PHASE_CONTRACT.md` |
| P10-004 | Phase 10 | Independent contract review | Codex | Done | High | Verdict `READY WITH REQUIRED CONTRACT FIXES`; no code written |
| P10-005 | Phase 10 | Contract remediation: resolve all required findings from P10-004 | Claude Sonnet | Done | High | Task-based execution model, mandatory egress containment, corrected risk tiers, deferred login, strengthened quarantine/promotion/audit, normative limits, two-layer test plan; see `docs/PHASE_10_CONTRACT_REMEDIATION_REPORT.md`. No code written. |
| P10-006 | Phase 10 | Human Owner review of remediated contract | Human Owner | Done | High | Approved as part of the 2026-07-11 Phase 10 implementation instruction |
| P10-007 | Phase 10 | Implement `aos/browser/*`, `aos/tools/browser.py`, `aos/interfaces/cli/browser_commands.py`, tool-registry/permissions extensions | Claude Sonnet | Done | High | 3,597 lines added across 13 new production files + 11 new test files; 696 passed, 6 skipped; see `docs/PHASE_10_IMPLEMENTATION_REPORT.md` |
| P10-008 | Phase 10 | Independent Codex final-gate review | Codex | Done | High | **FAIL**; Critical and Important gaps recorded in `docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`; Phase 11 blocked |
| P10-009 | Phase 10 | Remediate Codex final-gate findings and complete both test layers | Claude Sonnet | Done | High | Every Critical/Important finding fixed same-day: real egress/sandbox checks, engine-derived locators/classification, immediate per-op approval (`--yes` removed), enrolled-project-bound promotion, TOCTOU-narrowed upload, enforced resource limits, corrected audit lifecycle, DNS-free Layer-1 tests. 718 passed, 5 skipped. Layer-2 still incomplete/unexecutable in this sandbox — disclosed. See `docs/PHASE_10_REMEDIATION_REPORT.md`. Not self-certified. |
| P10-010 | Phase 10 | Fresh independent Codex final-gate review of the remediation | Codex | Done | High | **FAIL**; regression evidence improved (focused browser 152 passed; full suite 718 passed, 5 skipped; compileall/Ruff/diff/audit/CLI/static scans passed), but Layer-2 remains skipped/incomplete and additional contract gaps remain. See `docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`; Phase 11 remains blocked. |
| P10-011 | Phase 10 | Remediate fresh Codex final-gate findings and complete required Layer-2 gate | Claude Sonnet (builder round) / Codex (gate) | Done (builder round) | High | Follow-up Codex gate **FAIL**: focused remediation subset 106 passed; default full suite 725 passed / 8 skipped; compileall/Ruff/diff/audit passed; opt-in Layer-2 fails closed in this environment (2 passed / 5 errors, Chromium TargetClosedError). Blocking gaps remain: full Layer-2 matrix incomplete/unpassed, validating-proxy containment unproven, post-launch sandbox/process verification unproven by real Chromium, T2 action audit terminal semantics not exact, and resource/cleanup guarantees partial. See `docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`; Phase 11 remains blocked. |
| P10-012 | Phase 10 | Second follow-up remediation: fix C-2/I-2/I-1(partial)/I-3(partial) from the Follow-up Remediation Gate | Claude Sonnet | Done | High | AOS-controlled validating proxy (`aos/browser/validating_proxy.py`) replaces the declared-proxy-URL egress check, verified via real unmocked CONNECT requests; fixed the duplicate `browser.action.denied` audit bug (3 new tests); made `BrowserProcessTracker` injectable with 9 new deterministic unit tests. C-1 (Layer-2 Chromium launch) deliberately not re-attempted per explicit direction -- environment constraint, not code-fixable here. 741 passed, 5 skipped; Layer-2 opt-in unchanged (2 passed, 5 errors). See `docs/PHASE_10_REMEDIATION_REPORT.md` second follow-up section. Not self-certified. |
| P10-013 | Phase 10 | Fresh independent Codex final-gate review of the second remediation | Codex | In Progress | High | Review started. Human Owner decision also needed on how to resolve the Layer-2 environmental blocker (Chromium-capable/root-access environment vs. explicit contract amendment) since repeated remediation rounds cannot fix it. |
| P10-014 | Phase 10 | Recovery planning: Chromium-capable environment, real egress enforcement, Layer-2 completion matrix, design-gap classification, Human Owner decisions, phased execution plan | Codex (plan author) / Claude Sonnet (review + coordination update) | Done | High | Phase 10 recovery planning complete; no implementation started; Phase 11 remains blocked. See `docs/PHASE_10_GATE_RECOVERY_PLAN.md`. Recommends rootless Podman + pinned Playwright/Chromium image; next phase is P10-R1 (environment image), not yet started; 5 Human Owner decisions still open. |
| P10-015 | Phase 10 | P10-R1: reproducible rootless-Podman Chromium verification environment (Human Owner approved 2026-07-12, P10-R1 only) | Claude Sonnet/Codex | Review | High | Strict seccomp-source validation and exact Chromium role/state validation remediated the two High fresh-review gaps. Real rootless verifier passed; focused **129 passed, 8 skipped**; full **795 passed, 8 skipped**. **P10-R1 VALIDATION GAPS REMEDIATED — AWAITING FRESH INDEPENDENT VERIFICATION.** No P10-R2/R3/R4 or Phase 11 work was added. |
| P10-016 | Phase 10 | Research autonomous browser-agent architectures and map reusable patterns to AOS boundaries | Codex | Done | Medium | Reviewed the supplied shortlist and Browser Harness. Recommended taking planner/verification/evaluation patterns only; no persistent browser sessions, login automation, unrestricted CDP, or autonomous runtime behavior. |
| P10-017 | Phase 10 | Define a phase-safe AOS goal-based browser-agent boundary | Codex / Human Owner | Todo | High | Produce a review proposal for planner, policy gate, approval, executor, verifier, and audit stages. Requires Human Owner approval before implementation or phase-contract changes. |
| P10-018 | Phase 10 | Define deterministic browser-agent evaluation matrix | Codex | Todo | High | Cover navigation, redirects, approvals, egress, sandbox, quarantine, cleanup, prompt injection, and failure recovery using the existing Layer-1/Layer-2 contract. |
| P10-019 | Phase 10 | Implement only the approved Phase 10 browser gate fixes | Claude Sonnet / Codex | Todo | High | No autonomous planner or persistent agent. Start only after P10-013 and the remaining Human Owner/environment decisions are resolved. |
| P10-020 | Phase 10 | Restore complete cross-platform test baseline | Codex | Done | High | Stabilized optional voice dependency tests; full suite **765 passed, 38 skipped**. Real-Chromium Layer-2 skips remain governed by B010. |
| P10-021 | Phase 10 | Independent static/security checkpoint after test-baseline repair | Codex | In Progress | High | Compileall passed; changed-file Ruff passed; focused browser security suite **132 passed**. Podman is unavailable on this host, so real Chromium Layer-2 verification remains blocked. Repository-wide Ruff still reports 52 baseline findings outside this checkpoint. |
| P10-022 | Phase 10 | Clean production static-analysis baseline | Codex | Done | Medium | Removed unused imports and restored `MemoryStatus`; `ruff check aos` passes with zero findings. Test execution remains delegated to the other verification system. |

## Phase 11 — Screen Understanding Plugin

| ID | Phase | Task | Owner | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| P11-001 | Phase 11 | Activate bounded Phase 11 contract | Human Owner / Codex | Done | High | Activated 2026-10-30 in `PHASE_CONTRACT.md`; Phase 10 remains implementation-frozen and independently unverified. |
| P11-002 | Phase 11 | Implement explicit screenshot capture tool | Codex | Todo | High | Terminal-triggered only; bounded capture; T2 approval; no background or continuous capture. |
| P11-003 | Phase 11 | Implement bounded OCR and untrusted observation boundary | Codex | Todo | High | OCR text is data, never authority; apply redaction, size limits, and audit controls. |
| P11-004 | Phase 11 | Implement terminal-error detection and screen summary | Codex | Todo | Medium | Read-only analysis over an explicit capture; no automatic action. |
| P11-005 | Phase 11 | Implement approval-gated suggested-fix proposals | Codex | Todo | High | Suggestions route through existing model validation, permission, risk, approval, and audit paths. |
| P11-006 | Phase 11 | Add Phase 11 security regression tests | Codex / external verifier | Todo | High | Prompt-injection resistance, secret redaction, capture boundary, approval enforcement, bounded output, and audit integrity. |
