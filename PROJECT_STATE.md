# Project State

Current phase: Phase 11 — Screen Understanding Plugin, **ACTIVE WITH BOUNDED READ-ONLY SCOPE**. Phase 10 implementation is frozen pending independent real-Chromium verification; Phase 10 is not declared complete. Phases 0–9 are COMPLETE + REVIEWED + HARDENED. Phase 11 is limited to explicit terminal screenshot capture, bounded OCR, terminal-error detection, screen summaries, and approval-gated fix proposals. Continuous/background capture, desktop control, remote workspace control, credential handling, and automatic screen-derived actions remain forbidden.

**Phase 10 recovery planning remains recorded; Phase 11 is active with bounded read-only scope.** `docs/PHASE_10_GATE_RECOVERY_PLAN.md` (read-only planning artifact) designs the Chromium-capable verification environment (rootless Podman + pinned Playwright/Chromium image), a real OS/container egress-enforcement architecture layered on the existing validating proxy, a complete Layer-2 test matrix, an honest classification of remaining design gaps, 5 explicit Human Owner decisions, and a phased P10-R1..R4 execution plan. No Phase 10 completion or P10-R2 authorization is implied by the Phase 11 activation.

## Completed

- Repo skeleton (`aos/` package: core, tools, safety, memory, models, config, evals, interfaces/cli)
- Typer CLI: `aos --help`, `version`, `doctor`, `config show`, `audit list`, `audit verify`, `eval run`
- Config system (`~/.aos-jarvis/config.toml`, default-created if missing)
- SQLite audit log with hash-chain verification and tamper detection
- Risk tier model (T0-T3) and decision mapping
- Capability/permission placeholders (deny-by-default, Pydantic models)
- Tool interface contract (`BaseTool`, `ToolResult`, `ToolSchema`, `ToolDiff`)
- Placeholder modules for core/intent/router/loop, memory/events/timeline, models/base (explicitly marked as later phases)
- Eval fixture framework (`phase0_basic.yaml` + runner)
- Coordination docs: README, PHASE_CONTRACT, AGENTS, TASK_BOARD, DECISIONS, RISK_REGISTER, EVAL_SPEC, TOOL_CAPABILITIES, SECURITY_BOUNDARIES, CODING_RULES, ROADMAP, ARCHITECTURE, SECURITY, ADRs
- Shared memory files: PROJECT_STATE.md, TASKS.md, HANDOFF.md, BLOCKERS.md, `.agent/`
- Full project-tracking/doc system: PROJECT_SCOPE.md, DEVELOPMENT_WORKFLOW.md, MODEL_PROVIDER.md, TOOL_INTERFACE.md, PERMISSION_MODEL.md, AUDIT_LOG.md, EVALS.md, TESTING_STRATEGY.md, RELEASE_CHECKLIST.md
- Per-phase docs (`docs/phases/PHASE_0..12_*.md`), extended ADR set (`docs/adr/0001..0007-*.md`), reserved `docs/security/`, `docs/models/`, `docs/tools/`, `docs/workflows/`
- Per-agent notes and templates (`.agent/{claude,codex,opencode,antigravity}_notes.md`, `.agent/templates/`)
- **Phase 1 — Permission engine** (`aos/safety/{permissions,risk,paths,errors}.py`): directory allowlist, capability checks, T0-T3 classification, dangerous-path/secret-file/traversal/symlink-escape blocking, deny-by-default.
- **Phase 1 — Safe file tools** (`aos/tools/fs_tools.py`): `list_dir`, `read_file`, `search_files`, `write_file`, `edit_file`, each audited and risk-gated; `delete_file` intentionally unimplemented.
- **Phase 1 — Snapshot/restore system** (`aos/safety/snapshots.py`): snapshot before every write/edit of an existing file, `list_snapshots`/`get_snapshot`/`restore_snapshot` (restore is T2, snapshots the current state first).
- **Phase 1 — CLI** (`aos/interfaces/cli/{fs_commands,snapshot_commands}.py`): `aos fs list/read/search/write/edit`, `aos snapshot list/restore`, wired into `main.py`.
- **Phase 1 — Docs**: `docs/phase_1.md`, `docs/permissions.md`, `docs/risk_tiers.md`.
- **Phase 1 — Independently verified** (2026-07-10, Claude Code): full `pytest -q -rs` run (39 passed, 1 skipped — the skip is a benign Windows-can't-create-unprivileged-symlinks limitation, covered instead by a resolved-path-escape test); manual CLI walkthrough in a throwaway project directory confirmed blocked paths (`/etc`, `~/.ssh/id_rsa`, `.env`, traversal, outside-approved-root), correct `list/read/search/write/edit`, snapshot-before-edit, and a real restore that correctly reverted file content; `audit list`/`audit verify` confirmed every allowed and blocked action was logged and the hash chain stayed valid; Phase 0 commands (`version`, `doctor`, `eval run`) confirmed unaffected.

- **Phase 2 — Command policy** (`aos/safety/command_policy.py`, `aos/safety/commands.py`): command classification (ALLOW_READONLY / ALLOW_PROJECT_TEST / ALLOW_WITH_APPROVAL / DENY / UNKNOWN), deny-by-default for unknown commands.
- **Phase 2 — Safe shell runner** (`aos/tools/shell_runner.py`, `aos/safety/sandbox.py`): no `shell=True`, cwd restricted to approved roots, sanitized env, timeout and output caps, audited execution.
- **Phase 2 — CLI** (`aos/interfaces/cli/run_commands.py`): `aos run`, wired into `main.py`.
- **Phase 2 — Docs**: `docs/phase_2.md`, `docs/command_runner.md`, updated `docs/risk_tiers.md`.
- **Phase 2 — Verified** (2026-07-10): full suite green — 133 passed, 2 skipped (benign platform skips); declared COMPLETE + HARDENED by Human Owner.

- **Phase 3 — Minimal agent loop**: deterministic intent classifier, structured plan/tool-call dataclasses, allowlisted tool registry, dry-run mode, approval stop, safe delegation to Phase 1 file tools and Phase 2 shell runner, audit events for agent actions. No real LLM required. Allowed intents: PROJECT_SUMMARY, FIND_TODOS, RUN_TESTS, GIT_STATUS, READ_FILE, CREATE_NOTES, UNKNOWN.

- **Phase 4 — Memory system**: local SQLite memory store derived from the append-only audit log. Full rebuild/index with idempotent event processing. Timeline queries, entity tracking, and deterministic rule-based recall. CLI commands: `aos memory status/rebuild/recent/timeline/files/commands/blocked/failures` and `aos recall "<query>"`. Agent integration through RECALL_MEMORY intent (T0 read-only). All memory operations audited. 157 tests pass, 2 skipped (benign platform skips). Independently reviewed 2026-07-10.
- **Phase 5 — Git and Project Assistant**: safe read-only git tools, deterministic parsers and summaries, CLI `aos git` commands, agent intents/tools, deny-by-default git policy, audit events, and deterministic commit-message drafting. Full suite: 194 passed, 2 benign Windows symlink skips. Independently reviewed 2026-07-11. Human Owner approval to begin Phase 6 recorded in the 2026-07-11 Phase 6 implementation instruction.
- **Phase 6 — Model Support**: safe model request/response types, provider interface, local HTTP adapter, cloud OpenAI-compatible adapter disabled by default, model config, secret redaction, deterministic router, structured output validation, optional controlled agent integration, model audit events, and `aos model` CLI commands. Final gate: **PASS WITH NON-BLOCKING FIXES** — 228 passed, 2 benign skips; 21-event Phase 6 audit chain valid. See `docs/PHASE_6_FINAL_GATE_REPORT.md`.
- **Phase 7 — Read-Only Dashboard**: FastAPI + Jinja2 + uvicorn local dashboard, loopback-only. Seven read-only views. `aos dashboard` CLI command. Four Important fixes applied by Codex final gate (F7-1 through F7-4: no storage init on GET, recursive secret redaction, port validation, bounded loading). Independently reconfirmed by Claude Sonnet: 347 passed, 2 benign skips; all four fixes verified; no Critical/Important findings. COMPLETE. See `docs/PHASE_7_INDEPENDENT_RECONFIRMATION.md`.
- **Phase 8 — Voice Interface**: local-only push-to-talk voice interface with a permanent `yes=False` approval boundary. All F8-1 through F8-4 findings, typed timeout outcomes, exact-once lifecycle events, microphone boundary, audit privacy, and redaction were independently verified through supplemental review. **484 passed, 2 skipped**; focused voice suite: **137 passed**. COMPLETE by Human Owner approval. See `docs/PHASE_8_OPENCODE_TIMEOUT_VERIFICATION.md`.
- **Phase 9 — Workspace and App Control**: typed, allowlisted folder/editor/terminal
  opening; a foreground, loopback-only dev server whose only stop method is Ctrl+C in
  the invoking terminal (no cross-invocation status/stop commands or registry
  capabilities); explicit Human Owner confirmation required and durably consumed,
  bound independently to both the opaque project ID and a SHA-256 digest of the
  resolved project path (`canonical_project_digest`), before any server launch;
  contextual denial audit (exactly one DENY row per rejected `serve` call); and
  preserved Phase 1 path exception subtypes (`SymlinkEscapeBlocked` propagates
  through `PermissionEngine.require_path`). Independently re-reviewed by Claude
  Sonnet: initial pass was PASS WITH NON-BLOCKING FINDINGS (560 passed); the two
  Important findings and one nice-to-have were then fixed and re-verified in the
  same session, live end to end (real foreground `python -m http.server` launch
  cancelled by a real SIGINT, no orphan process). Full suite: **564 passed, 0
  failed, 0 skipped**. **COMPLETE** by Human Owner sign-off (2026-07-11). B007 is
  CLOSED, no outstanding findings of any severity. See
  `docs/PHASE_9_INDEPENDENT_RECONFIRMATION.md`.

## In Progress

- **Phase 10 — Controlled Browser Automation**: SECOND REMEDIATION APPLIED
  — AWAITING FRESH INDEPENDENT CODEX FINAL GATE. Built `aos/browser/{types,
  domains,url_policy,approval,redaction,egress,sandbox,supply_chain,engine,
  quarantine,task,validating_proxy}.py`, `aos/tools/browser.py`,
  `aos/interfaces/cli/browser_commands.py`, and extended
  `aos/safety/permissions.py` and `aos/agent/tool_registry.py`. Task-based
  `aos browser task <spec>` execution model; per-operation, IMMEDIATE (not
  bulk) T2 approval via a terminal-only callback, with `--yes` removed
  entirely; real, AOS-spawned, policy-enforcing validating CONNECT proxy
  per task (verified via actual unmocked CONNECT requests proving genuine
  `403` enforcement, not mere reachability) plus real kernel-capability
  sandbox precondition checks; engine-derived accessibility-tree field
  locators and runtime field classification (no caller-controlled selector
  or classification); enrolled-project-ID-bound quarantine promotion
  requiring its own fresh destination-bound approval at the store boundary;
  upload private-snapshot staging bound by project ID + inode + size + hash;
  enforced redirect-depth/tab/bandwidth/task-timeout/idle-timeout limits
  with bounded forced-timeout cleanup visible on the result; exactly-one-
  terminal-event-per-T2-action audit lifecycle (duplicate-denial bug fixed);
  DNS-free Layer-1 tests; injectable, unit-tested `/proc` process-tracking
  and forced-kill logic. Full suite: **741 passed, 5 skipped**; ruff,
  compileall, diff check, isolated audit verify, CLI smoke, and static
  checks all passed. Opt-in Layer-2 remains unchanged at **2 passed, 5
  errors** (`TargetClosedError`) — a missing-shared-library/no-root-access
  environment constraint deliberately NOT re-attempted this round, since no
  application-code change can fix it in this sandbox; a Chromium-capable
  environment or root access is required to close this specific blocker.
  See `docs/PHASE_10_REMEDIATION_REPORT.md` (second follow-up section) and
  `docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md`. Not self-certified. Phase 11
  remains blocked.

  **2026-07-12 — P10-R1 remediation attempted by Codex; failed closed.**
  Remediated the two verified P10-R1 defects in code shape: full Chromium
  channel launch with sandbox enabled and exact `/proc` executable/flag
  validation; no headless-shell fallback; `--no-sandbox` and
  `--no-zygote-sandbox` rejected anywhere; Playwright sync API ownership kept
  on one owner thread with close exceptions/timeouts surfaced and forced
  process-tree cleanup. The required real rootless-Podman verifier was run
  and failed closed because Chromium's namespace sandbox needs
  `chroot("/proc/self/fdinfo/")`, which is denied (`EPERM`) under the approved
  `--cap-drop=ALL` container profile. No extra capability or sandbox
  disabling flag was added. Full suite **774 passed, 7 skipped** outside the
  managed sandbox; focused suite **108 passed, 7 skipped**. Phase 10 is not
  COMPLETE. P10-R2/P10-R3/P10-R4 and Phase 11 remain not started.

## Planned (not active)

(none currently — Phase 10 remains In Progress above pending remediation of Codex's
independent final gate; see `PHASE_CONTRACT.md` for the exact activation
record)

## Not Started

- Directory allowlist persistence beyond the CLI's current-working-directory default (`aos fs allow <path>` not yet implemented)
- `delete_file` (intentionally deferred, per Phase 1 scope)

## Do Not Build Yet

- Always-on microphone / wake-word detection (Phase 8 is push-to-talk only)
- Voice-only approval for risky actions (permanently forbidden)
- Login/credential automation in the browser tool (deferred entirely per Phase 10 contract Sec7, not implemented)
- Persistent browser sessions, autonomous browsing (Phase 10 hard rules)
- Screen understanding
- Multi-agent planner
- Embeddings/vector database
- Autonomous coding agent
- Dashboard mutation buttons, remote access, login systems
