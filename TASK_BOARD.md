# Task Board

Phase 9 is COMPLETE. Human Owner sign-off recorded in PHASE_CONTRACT.md on
2026-07-11 following Claude Sonnet's independent re-review (clean PASS, all
findings fixed and re-verified). B007 is CLOSED.

Phase 11 — Screen Understanding Plugin — is **ACTIVE WITH BOUNDED READ-ONLY
SCOPE**. Phase 10 implementation is frozen and remains pending fresh
independent environment verification. The
conditional-`chroot` seccomp defect was remediated without any added container
capability; the verified zygote-only `--no-zygote-sandbox` exception remains.
Codex remediated only the verified
P10-R1 defects: full Chromium `channel="chromium"` launch with
`chromium_sandbox=True`, exact supply-chain `/proc` binary binding,
headless-shell rejection, `--no-sandbox`/`--no-zygote-sandbox` rejection
anywhere, and one-owner-thread Playwright close with surfaced
exceptions/timeouts. The required real `./ops/phase10/verify_p10r1.sh` run
now passes in the approved rootless, zero-container-capability container:
the full binary launches with no `--no-sandbox`, the approved zygote exception
is correctly parented, all required long-lived processes have zero effective
capabilities, local navigation and owner-thread close succeed, and cleanup is
clean. Phase 10 remains blocked pending fresh independent verification; Phase
11 screen scope is active; Phase 10 is not declared complete.

**Phase 10 recovery planning remains recorded; Phase 11 is now active with
bounded read-only scope.** See `docs/PHASE_10_GATE_RECOVERY_PLAN.md` for the
Chromium-capable verification environment design, egress-enforcement
architecture, full Layer-2 test matrix, design-gap classification, Human
Owner decisions, and phased P10-R1..R4 execution plan. This is a planning
artifact only.

## Todo

- Codex/independent verifier: fresh P10-R1 environment verification of the zero-capability seccomp transformation
- Human Owner: decide the remaining open items in `docs/PHASE_10_GATE_RECOVERY_PLAN.md` §5 not covered by the 2026-07-12 P10-R1 approval (egress-enforcement topology for P10-R2, download-cap residual, upload-TOCTOU residual, cross-platform scope)
- Builder: P10-R2 (OS/container egress enforcement) — not started; requires independent P10-R1 environment verification first
- Codex: fresh independent final-gate review of the second remediation pass
- Human Owner: decide how to resolve the Layer-2 environmental blocker — provide a Chromium-capable/root-access environment, or explicitly amend the Phase 10 exit criteria for this constraint (repeated remediation cycles cannot fix an environment limitation)
- Builder/reviewer (once a Chromium-capable environment exists): complete the remaining Layer-2 matrix gaps (DNS rebinding, independent egress blocking with application checks bypassed, workers/service-workers/WebSockets/EventSource/WebRTC/frames/popups/prefetch/prerender, timeout/crash orphan inspection, real-process proof of the post-launch sandbox check and process-tree cleanup), then run the full layer in that environment
- Builder/reviewer: add cross-capability quarantine-isolation tests if required by the fresh gate
- Human Owner or Codex: inspect/clean up the disclosed test-data artifact at `~/.aos-jarvis/browser/approved_domains.json`

## In Progress

- Phase 10 fresh independent Codex final-gate review of the second remediation pass (not yet started)
- P10-R1 fresh independent environment verification

## Done

- Initial project structure after generation
- Add CODING_RULES.md and link it from coordination docs
- Phase 0 foundation CLI, config, audit, risk, tool contract, and eval scaffolding
- Phase 1 permission engine and safe file tools
- Phase 1 snapshot create/list/restore
- Phase 1 CLI commands for `aos fs` and `aos snapshot`
- Phase 1 safety tests and documentation
- Phase 2 command policy, safe shell runner, CLI `aos run`, and audit coverage
- Phase 3 deterministic minimal agent loop and CLI `aos ask`
- Phase 4 audit-derived memory store, timeline, recall, CLI, and agent integration
- Phase 5 safe git and project assistant, CLI `aos git`, and agent git/project intents
- Phase 6 safe configurable model support, `aos model` CLI, and optional agent integration
- Phase 7 read-only dashboard, loopback-only CLI, 7 views, gate findings fixed and independently reconfirmed
- Phase 8 local-only push-to-talk voice interface, `aos voice` CLI, yes=False invariant, timeout remediation, and supplemental verification (484 passed, 2 skipped)
- Phase 9 remediation: typed folder opening, explicit server confirmation, foreground Ctrl+C lifecycle, contextual denial audit, and preserved path exception types (560 passed)
- Phase 9 independent re-review (Claude Sonnet): PASS, live CLI/audit smoke testing
- Phase 9 F-1/F-2/N-1 follow-up fixes (Claude Sonnet): duplicate-audit-row fix, independent path-bound canonical approval check, dead-code cleanup; 564 passed
- Phase 9 Human Owner sign-off recorded in PHASE_CONTRACT.md; Phase 9 COMPLETE
- Phase 10 planning: contract, threat model, test plan, architecture drafted (Claude Sonnet); Phase 10 NOT activated
- Phase 10 contract remediation: Codex independent review (`READY WITH REQUIRED CONTRACT FIXES`) followed by Claude Sonnet resolving every required finding same-day; Phase 10 still NOT activated
- Phase 10 activated by Human Owner; Claude Sonnet implemented `aos/browser/*` and integration points same-day; 696 passed, 6 skipped; IMPLEMENTATION COMPLETE, awaiting Codex final gate
- Phase 10 independent Codex final gate completed: **FAIL**; B010 opened and Phase 11 remains blocked
- Phase 10 fresh independent Codex final gate of remediation completed: **FAIL**; 718 passed, 5 skipped regression evidence, but Layer-2 and remaining contract findings block completion
- Phase 10 follow-up remediation applied after fresh Codex FAIL: default full suite 725 passed / 8 skipped; opt-in Layer-2 fails closed with 2 passed / 5 errors in this environment; awaiting fresh independent Codex gate
- Phase 10 follow-up independent Codex final gate completed: **FAIL**; focused remediation subset 106 passed and full suite 725 passed / 8 skipped, but opt-in Layer-2 still errors in this environment and the full matrix/containment/audit/resource findings remain blocking
- Phase 10 second follow-up remediation (Claude Sonnet): AOS-controlled validating proxy replaces declared-proxy-URL egress check; duplicate action-denial audit fixed; process-tracker logic made testable with 9 new unit tests; 741 passed, 5 skipped; Layer-2 environmental blocker unchanged and not re-attempted per explicit direction; awaiting fresh independent Codex gate
- P10-R1 implemented then remediated (Claude Sonnet/Codex): environment built; defects fixed for full Chromium/headless-shell rejection and owner-thread close; real verifier ran and failed closed at Chromium namespace-sandbox `chroot` under `--cap-drop=ALL`. No P10-R2/R3/R4 started.

## Blocked

- Phase 10 completion remains blocked by B010 pending a fresh independent PASS and completion of the required Layer-2 real-Chromium gate in a capable contained environment. Phase 11 activation is complete, but its implementation must remain within the bounded contract scope.

## Out of Scope

- Always-on microphone / wake-word detection (Phase 8 is push-to-talk only)
- Voice-only approval for risky actions (permanently forbidden)
- Desktop control, OCR-triggered actions, continuous screen capture, and remote workspace control remain out of scope for Phase 11
- Multi-agent planner
- Dashboard mutation buttons, remote access, login systems
- Cloud memory
- Git write operations
- Browser login/credential automation (deferred entirely per Phase 10 contract Sec7)
- Persistent browser sessions, autonomous browsing (Phase 10 hard rules)
