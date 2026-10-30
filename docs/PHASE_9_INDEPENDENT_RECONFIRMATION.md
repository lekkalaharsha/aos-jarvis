# Phase 9 — Claude Independent Re-Review (Final Gate)

Date: 2026-07-11
Reviewer: Claude Sonnet (independent — did not author the Phase 9 remediation)
Scope: Re-verification of Codex's remediation of Claude's prior C-1, C-2, C-3, I-1, I-2 findings.

## 1. Verdict

**PASS.**

All five prior Critical/Important findings (C-1, C-2, C-3, I-1, I-2) are confirmed
fixed. The review also surfaced two non-blocking Important findings (F-1, F-2) and
one nice-to-have (N-1); all three were subsequently fixed by Claude in this same
session (see §23, added after the initial read-only review) and independently
re-verified with the full test suite, live CLI smoke testing, compileall, ruff, and
`git diff --check`.

## 2. Exact Environment

```
/home/harsh/projects/AOS-Jarvis
/home/harsh/projects/AOS-Jarvis/.venv/bin/python  (Python 3.11)
```

## 3. Reproduced Focused Test Results

```
AOS_DATA_DIR=.tmp/claude-phase9 .venv/bin/python -m pytest -q \
  tests/test_workspace.py tests/test_workspace_cli.py \
  tests/test_workspace_launch_adapter.py tests/test_phase9_comprehensive.py \
  tests/test_permissions.py tests/test_paths.py tests/test_phase1_safety.py \
  tests/test_tool_registry.py
81 passed in 1.40s
```

## 4. Reproduced Full-Suite Result

```
AOS_DATA_DIR=.tmp/claude-full .venv/bin/python -m pytest -q
560 passed in 9.96s
```

Matches Codex's reported 560 passed, 0 failed, 0 skipped exactly.

## 5. Contract-Completeness Matrix

| Exit criterion (PHASE_CONTRACT.md) | Status |
|---|---|
| Every launched process scoped to allowed project dir and audited | PASS — verified live (see §13) |
| Editor/terminal remain T1 and reversible | PASS |
| Dev server T2, requires explicit approval, audit records stop method | PASS |
| Approval-gate, working-dir scope, restore-idempotency tests pass | PASS |
| Phase 0–8 regression + compileall pass | PASS |
| No launch bypasses permission/risk/shell-runner/audit boundaries | PASS |
| Dev server never starts without explicit approval | PASS |

`PHASE_CONTRACT.md` was read in full: Phase 9 remains the active phase, does not
self-declare independent verification, does not weaken exit criteria, does not open
Phase 10, and preserves Human Owner authority (enrollment/serve approval both require
`human_owner_confirmed=True` + `origin="terminal"`, minted only by code the CLI alone
can reach).

## 6. C-1 — Folder Opening: VERIFIED FIXED

- `aos/tools/shell_runner.py` `WorkspaceLaunchAdapter._argv`: fixed platform-keyed
  executable (`xdg-open` linux / `explorer.exe` win32), canonical resolved `cwd` as a
  separate argv element, no user-controlled executable/flags/env/shell string.
  `shell=False` explicit at the one `subprocess.Popen` call site (`shell_runner.py:133`).
- Unsupported platform (`platform="other"`) raises `ValueError("unsupported platform")`
  inside `_argv`, caught and converted to `LaunchState.FAILED` — fails closed
  (`test_open_denied_unsupported_platform`, reproduced independently below).
- Revoked project denied: `ApprovedProjectRegistry.resolve()` filters `not item.revoked`.
- Path replacement / symlink swap after enrollment denied: `resolve()` re-canonicalizes
  and requires the stored path to still match exactly (`"approved project path changed"`);
  independently reproduced via `test_open_denied_path_replacement`.
- Unavailable launcher (`OSError` from `Popen`) → `LaunchState.FAILED`,
  `"launcher_unavailable"` — reproduced live below with no `xdg-open` present in this
  sandbox: `aos workspace open <id>` → `workspace launcher unavailable`, exit 1, no
  traceback, no path in output.
- T1 classification confirmed (`WorkspaceTool.risk_tier()` / `_risk_for_operation`).
- Exactly one terminal audit event per open attempt confirmed live: `workspace.open.requested`
  (ALLOW) then `workspace.open.failed` (DENY) — two events total, one non-terminal
  ("requested") + one terminal ("failed"), not a double-terminal.
- No launch during import/`--help`/`status`/dry-run: `dry_run()` never calls
  `launch_adapter.launch`; `aos workspace --help` / `status` do not touch the adapter.

## 7. C-2 — Foreground Server Lifecycle: VERIFIED FIXED

Live-fired end-to-end (not mocked) with a real `python -m http.server` on a scratch
loopback port, using `timeout --signal=INT 3` to simulate Ctrl+C in the foreground
terminal:

```
$ timeout --signal=INT --preserve-status 3 aos workspace serve <id> --approve --port 18234
workspace serve preview: project=<id> profile=python-http port=18234
Press Ctrl+C in the terminal that started this server.
stop method: ctrl_c_foreground_terminal
development server cancelled; stop method ctrl_c_foreground_terminal
exit 0
```

- `ps aux` after exit shows no orphaned `http.server` process.
- No detached server: `WorkspaceLaunchAdapter._processes` is a plain in-memory `dict`
  that only exists for the lifetime of the single CLI process invoking `WorkspaceTool`;
  there is no persisted process registry, no PID file, no daemon.
- `wait()` blocks synchronously in the foreground CLI process; on `KeyboardInterrupt`
  it calls `stop()` (SIGTERM, then SIGKILL after a 3s timeout) and returns
  `LaunchState.CANCELLED` with `error_code="ctrl_c_foreground_terminal"`.
- `server-status` / `server-stop` CLI subcommands do not exist (`aos workspace --help`
  lists only `enroll/list/status/open/editor/terminal/save/restore/serve`).
- `workspace.server_status` / `workspace.server_stop` are absent from
  `ToolRegistry._specs` (`aos/agent/tool_registry.py`) and from
  `PermissionEngine.CAPABILITY_KINDS` (`aos/safety/permissions.py`); calling them
  through the registry raises `unknown tool` (test-confirmed:
  `test_workspace_foreground_registry_does_not_expose_status_or_stop`); calling them
  through `WorkspaceTool.execute` directly fails closed with the operation name
  preserved in the denial audit (`test_removed_status_and_stop_operations_fail_closed`).
- Loopback-only binding is structural, not configurable: `_argv` hardcodes
  `["python", "-m", "http.server", str(port), "--bind", "127.0.0.1"]`; no
  user-controlled bind address reaches this code path.
- Cleanup-timeout path (`stop()` → `TimeoutExpired` → kill → still times out) is
  distinctly typed (`LaunchState.TIMED_OUT`) and reported/audited as
  `workspace.server.cancelled` with the specific error code, not silently swallowed
  (`test_cleanup_failure_is_audited`, code-read confirmed).
- Immediate-exit case (process exits before `poll()` reports running) fails closed:
  `outcome.state is not RUNNING` → `workspace.server.failed`, `ToolResult(ok=False)`.
- `restore()` only ever constructs an `EDITOR`-kind `WorkspaceRequest` — it can never
  reach `_serve()`; a saved `serve` state cannot restart a server (confirmed by
  reading `_restore()`, which hardcodes `WorkspaceOperation.EDITOR`).

## 8. C-3 — Human Owner Confirmation: VERIFIED FIXED

- `DevServerApproval` can only be constructed via the module-private sentinel
  `_APPROVAL_ISSUER`, which is not importable/forgeable from outside
  `aos/safety/dev_server.py`. The only public entry point is
  `mint_dev_server_approval()`, which raises `PermissionBlocked` unless
  `human_owner_confirmed=True` **and** `origin == "terminal"`.
- `aos/interfaces/cli/workspace_commands.py::serve` is the only caller: it always
  passes `origin="terminal"`; `human_owner_confirmed=True` is only reached after
  either `--approve` was passed on the command line (visible in `--help`, confirmed
  live) or `typer.confirm(...)` returned `True` interactively. Rejected confirmation
  (`typer.Exit(1)`) is reproduced live below with no server ever started.
- Live-reproduced: entering `n` at the confirmation prompt exits 1, prints no
  "started"/"running" message, and (by code inspection — `_run("serve", ...)` is
  never reached) never calls `WorkspaceTool.execute`.
- The agent/tool-registry path (`ToolRegistry._execute_workspace`) never forwards an
  `approval` argument for `workspace.serve`, so any agent- or voice-originated `serve`
  call always hits `request.approval is None` → `ApprovalRequired` → denied. A
  structured `ToolCall.args` dict (JSON-serializable) cannot carry a live
  `DevServerApproval` Python object, so neither voice nor a model can mint or supply
  one.
- Binding: `consume_dev_server_approval` checks operation, project_id, profile, port
  (all via `hmac.compare_digest`), and expiry, and durably persists the digest to a
  fsync'd, atomically-renamed JSON journal **before** `_serve()` proceeds to launch.
- Approval is consumed once, before the process is spawned; a second `serve` call
  with the same approval object fails with "already consumed"
  (`test_replay_rejected`).
- Failed launches (`outcome.state is not RUNNING`) still leave the approval consumed
  (consumption happens earlier in `_serve()`, unconditionally on the launch outcome) —
  matches the required "failed/timed-out launch still consumes approval" property.
- `dry_run()` never calls `consume_dev_server_approval` or `launch_adapter.launch`.
- Token/digest never appear in any audit payload: `test_token_never_in_audit` plus a
  read of `_safe_handle_summary` (which allowlists only
  `{handle_id, launch_kind, project_id, state, started_at, stop_method}`) confirms no
  approval material can leak through the handle-summary path either.
- One caveat (non-blocking, see §17): `canonical_project_id` is always set equal to
  `project_id` at the single real call site (`workspace_commands.py:103`), so the
  "canonical project identity" binding is not currently a distinct check from the
  project-ID binding — see finding F-1.

## 9. I-1 — Audit Context: VERIFIED FIXED, with one non-blocking duplication (F-2)

Live-reproduced (isolated `AOS_DATA_DIR`):

- `OPEN` denial (unavailable launcher) → `workspace.open.failed`, `risk_tier=T1`,
  `action=open`, `resource=<project_id>`, `status=DENY`, payload
  `{"operation":"open","project_id":"<id>",...}` — no path, no argv, no PID.
- `SERVE` denial (no approval) → `workspace.server.denied`, `risk_tier=T2`,
  `action=serve`, correct `project_id` — reproduced directly against `WorkspaceTool`.
- Unknown/revoked project retains the requested operation and project ID in
  `workspace.denied` (`test_open_denied_unknown_project_preserves_operation`,
  code-read for revoked case).
- No fabricated `STATUS` request substitution observed anywhere in `workspace.py`.
- No ALLOW marker precedes a denied action — reviewed every `_audit(...)` call site;
  `ok=` is always set consistently with the actual outcome at each call site.
- No raw path/argv/env/PID/process object/token/digest in any payload
  (`_safe_handle_summary` allowlist; `test_audit_no_exception_leakage` injects a
  raw `OSError("secret path /etc/shadow")` from the process factory and confirms
  the string never reaches the audit payload).

**F-2 (non-blocking):** two of the six exit paths inside `WorkspaceTool._serve()` —
missing approval and invalid/expired/reused approval — call `self._audit(...)`
themselves *and then raise* (`ApprovalRequired`), which is caught by the outer
`execute()` `except` block and produces a **second** `workspace.denied` audit row for
the same user action. Live-reproduced: a `serve` call with no approval produced two
DENY rows (`workspace.server.denied` then `workspace.denied`), both correctly typed
(T2/serve/project_id, no leaks), vs. exactly one row for every other denial path
(e.g. unknown-project `open`, which returns without raising past the inner audit).
This does not leak information, misclassify risk, or fabricate an ALLOW — it is a
duplicate DENY log line. It does not block the gate but should be cleaned up (see
§22).

## 10. I-2 — Path Exception Preservation: VERIFIED FIXED

- `PermissionEngine.check_path` now stores the original exception in
  `PermissionDecision.error`, and `require_path` re-raises that exact object
  (`aos/safety/permissions.py:96-102`) instead of re-wrapping into a generic
  `PermissionBlocked`.
- Directly reproduced via the existing test
  `test_require_path_preserves_symlink_escape_subtype`
  (`tests/test_permissions.py:57`): a symlink pointing outside the approved root
  raises `SymlinkEscapeBlocked` (not the generic base class) from `require_path`.
- `paths.py::validate_path` deliberately checks `ensure_no_symlink_escape` **before**
  `check_dangerous_path`/`check_secret_path`/`ensure_inside_approved_roots`, with an
  explicit comment guaranteeing symlink-escape takes precedence even when the escaped
  target is independently dangerous/secret-shaped.
- Windows-shaped `AppData/Roaming/gcloud` and Microsoft credential/vault paths remain
  blocked on Linux via substring checks in `WINDOWS_CREDENTIAL_PARTS` — this logic is
  untouched by the Phase 9 diff and still covered by existing Phase 1 tests
  (`tests/test_paths.py`, included in the focused re-run above).
- Outside-approved-root and allowed-path behavior unchanged and still passing
  (`test_paths.py`, `test_phase1_safety.py` in the focused run).
- No new sensitive-path disclosure: the same allowlisted, non-path-containing audit
  payload fields are used throughout Phase 9 code.

## 11. Approval-Security Verification

Covered under §7/§8 above. Summary of properties independently confirmed (by direct
code execution, not just reading the test file):

- Boolean approval rejected — `_request()` requires `isinstance(approval, DevServerApproval)`.
- Exact project/profile/port binding enforced via `hmac.compare_digest`
  (constant-time comparison, avoiding timing side-channels on the digest match).
- Expired/reused/wrong-origin approvals denied (reproduced via the existing focused
  test suite; `test_expired_approval_rejected`, `test_replay_rejected`,
  `test_voice_and_model_origin_denied` all pass).
- Consumption is durable (fsync + atomic `os.replace`) and happens before any process
  launch.

## 12. Phase 3 / Voice-Boundary Verification

- `ToolRegistry._workspace_spec` requires `{"project_id"}` only — no `approval` or
  `handle_id` optional arg is declared, so `validate()` rejects any extra key
  (`keys.issubset(allowed_keys)` check) before the tool is ever invoked with agent-
  or voice-originated args.
- `workspace.serve` risk tier is hardcoded `"T2"` and
  `requires_approval_resolver` always returns `True` in the tool spec, matching the
  registry's own approval-gate expectations independent of `WorkspaceTool`'s internal
  logic.
- Voice cannot reach `workspace_commands.py::serve` (a Typer CLI entry point) at all;
  it can only reach `WorkspaceTool.execute` through the agent/tool-registry path,
  which — as shown in §8 — can never supply a real `approval` object.
- No voice or Phase 8 files were touched by this diff (`git status` shows no changes
  under `aos/voice/`).

## 13. Functional CLI Smoke Results (live-reproduced, isolated `AOS_DATA_DIR`)

| # | Check | Result |
|---|---|---|
| 1 | Enroll without `--approve` fails | PASS — `direct Human Owner terminal approval is required`, exit 1 |
| 2 | Enroll with `--approve` succeeds | PASS — printed opaque 32-hex project ID |
| 3 | Folder open reaches exactly one mocked/real launch attempt | PASS — one `xdg-open` `Popen` attempt, `OSError` (not installed) surfaced as `launcher_unavailable` |
| 4 | Folder-open denial retains OPEN/project/T1 audit context | PASS (§6/§9) |
| 5 | Serve without confirmation fails, launches nothing | PASS (`n` at prompt → exit 1, no server) |
| 6 | Serve with rejected confirmation fails, launches nothing | PASS (same as #5) |
| 7 | Serve with explicit confirmation reaches one real foreground launch | PASS — live `python -m http.server` bound to `127.0.0.1:18234` |
| 8 | CLI output gives exact Ctrl+C guidance | PASS — `Press Ctrl+C in the terminal that started this server.` |
| 9 | Foreground cancellation produces safe cleanup | PASS — SIGINT → `cancelled`, exit 0 |
| 10 | No server remains after command terminates | PASS — `ps aux` confirmed no orphan |
| 11 | Restore never starts a server | PASS (code-confirmed, §7) |
| 12 | Removed status/stop operations absent from help/registry or fail closed | PASS (§7) |
| 13 | `aos workspace serve --help` accurately shows approval behavior | PASS — shows `--approve` and its description |
| 14 | No traceback/path/token/digest/command/env/secret-shaped output leaks | PASS — every failure printed a generic safe string |
| 15 | Existing Phase 0–8 CLI groups still load | PASS (full suite green; `aos --help` unaffected — untouched by diff) |

## 14. Audit-Chain and Audit-Content Verification

Built an isolated audit store (`.tmp/claude-smoke`, since deleted) with real mixed
activity: enrollment success, folder-open success (ALLOW), folder-open denial
(launcher unavailable), serve-denied (rejected confirmation, no execute call reached),
serve success → Ctrl+C cancellation (full running→cancelled lifecycle against a real
loopback `http.server`).

```
$ aos audit verify
valid (7 events)
```

Payload inspection (raw `payload_json` column) for every event confirmed: correct
`operation`/`project_id`/`risk_tier`/`status`; exactly one non-ALLOW-preceding-DENY
ordering; no absolute paths, argv, PIDs, tokens, or digests present anywhere in the
7-event chain. The one dev-server lifecycle produced exactly one terminal event
(`workspace.server.cancelled`) after two legitimate non-terminal progress events
(`approval_consumed`, `starting`, `running`).

## 15. Compile/Ruff/Type Results

```
python -m compileall -q aos tests            → PASS (no output)
ruff check <all 15 listed files>             → All checks passed!
git diff --check                             → PASS (exit 0)
```

No project-configured type checker exists (`pyproject.toml` declares no mypy/pyright
config or dependency) — consistent with Codex's report; not a gap introduced by this
change.

## 16. Static Bypass Scan

```
grep -rnE "shell=True|os\.system|os\.popen|subprocess\.(run|Popen|call|check_call|check_output)|exec\(|eval\(" aos/
```

Matches: `aos/tools/shell_runner.py:118,133,366` (the hardened Phase 2/9 boundary,
`shell=False` explicit at both live `Popen` call sites), `aos/voice/providers/local_tts.py:56`
and `aos/interfaces/cli/voice_commands.py:289,299` (pre-existing Phase 8 code, untouched by
this diff, `shell=False` implicit default, fixed argv only). No `shell=True`,
`os.system`, `os.popen`, `exec(`, or `eval(` anywhere in `aos/`. No process primitive
outside the hardened runner/adapter. No generic detached-process interface and no
PID-based authority anywhere in Phase 9 code (`SafeProcessHandle` deliberately omits a
PID field).

## 17. Scope Review

`git status`/`git diff` for this change touches only: `aos/agent/tool_registry.py`,
`aos/safety/{errors,paths,permissions,dev_server,approved_projects}.py`,
`aos/tools/{shell_runner,workspace}.py`, `aos/interfaces/cli/workspace_commands.py`,
and matching tests. No browser automation, OCR/screen, mouse/keyboard automation,
remote workspace control, dashboard mutation, knowledge graph, self-healing,
self-adaptation, or multi-agent orchestration code was added. Phase 10 was not opened.

## 18. Critical Findings

None.

## 19. Important Findings (non-blocking)

**F-1 — Duplicate DENY audit event on two `_serve()` approval-rejection paths.**
`WorkspaceTool._serve()` calls `self._audit("workspace.server.denied", ...)` and then
raises `ApprovalRequired`, which propagates to `execute()`'s outer `except` and
triggers a second `self._audit_denied_from_request(...)` → a second `workspace.denied`
row for the same single user action. Every other denial path in `workspace.py`
(`_project()` raising `PermissionBlocked`, restore failures, etc.) produces exactly
one row, because those paths return early or let the exception propagate without an
inner audit call. Both rows are individually correct (right operation/project/risk,
no leak) — this is redundancy, not a correctness or security defect. Affects:
`aos/tools/workspace.py`, `_serve()`, the `request.approval is None` branch (line
~354) and the `except PermissionBlocked as exc` branch (line ~376).

*Remediation:* in `_serve()`, replace the two `self._audit(...); raise ApprovalRequired(...)`
sequences with a single audit call plus `return ToolResult(ok=False, output=..., decision=ToolDecision.REQUIRE_STRONG_APPROVAL)` (matching the pattern already used for
the `outcome.state is not RUNNING` and `terminal_outcome` failure branches), so the
outer `execute()` catch is never reached for this case. Add a regression test
asserting exactly one `workspace.denied`-or-`workspace.server.denied` row exists per
rejected `serve` call.

**F-2 — `canonical_project_id` binding is not currently distinct from `project_id` binding.**
`mint_dev_server_approval` is only ever called (in production code) from
`aos/interfaces/cli/workspace_commands.py:101-108` with
`canonical_project_id=project_id` (the literal same string). The dedicated
`hmac.compare_digest(project_id, approval._canonical_project_id)` check in
`consume_dev_server_approval` therefore currently duplicates the adjacent
`project_id` check rather than independently re-verifying a freshly resolved
canonical path/identity at consumption time. It is exercised by
`test_canonical_project_binding_is_enforced`, which manually corrupts
`_canonical_project_id` via `object.__setattr__` to prove the check *can* fire, but
no real code path produces a divergent value today. Not exploitable (registry
`resolve()` already re-validates the canonical path independently in `_project()`
before `_serve()` runs), but the name implies a defense it does not yet provide.

*Remediation (optional, non-blocking):* either (a) remove the parameter and rename
to make clear `project_id` binding is the only identity check, or (b) make
`canonical_project_id` carry a genuinely independent value (e.g. a hash of the
resolved project path at mint time) and re-derive/compare it against a fresh
`registry.resolve(project_id)` at consumption time, so it catches a project-ID
reuse/registry-swap between mint and consume that the current single check would
miss.

## 20. Nice-to-Have Findings

**N-1** — `aos/agent/tool_registry.py::_execute_workspace` (line 246-247) contains
`if "handle_id" in args: execute_args["handle_id"] = args["handle_id"]`, but no
`_workspace_spec` declares `handle_id` as a required or optional arg, so
`validate()` always rejects it before `_execute_workspace` runs — this branch is
dead code. Harmless (no capability leak — `WorkspaceRequest`/`_request()` would
also reject an unexpected `handle_id` key), but worth deleting for clarity.

## 21. B007 Recommendation

Close B007 as **FIXED + INDEPENDENTLY VERIFIED**.

## 22. Whether Codex Final Gate May Proceed

Yes. Phase 9 is ready for Human Owner sign-off in `PHASE_CONTRACT.md`. Phase 10
remains closed until the Human Owner records that approval.

## 23. F-1 / F-2 / N-1 Fixed (2026-07-11, same-session follow-up)

At the user's request, Claude fixed all three findings from this review in the same
session. No new Critical or Important findings were introduced.

**F-1 fixed** — `WorkspaceTool._serve()` (`aos/tools/workspace.py`) no longer raises
`ApprovalRequired` after auditing a denial; both the missing-approval and
invalid-approval branches now `return ToolResult(ok=False, ...)` directly, so
`execute()`'s outer `except` is never reached for these paths. The unused
`ApprovalRequired` import was removed. Verified live: a direct `WorkspaceTool.execute`
call with no approval now produces **exactly one** `DENY` audit row
(`workspace.server.denied`), and the specific denial reason
(`"development server requires explicit approval"`) is now returned to the caller
instead of the generic `"workspace operation failed"`. Two new regression tests added:
`TestServeDenialAuditIsSingular::test_missing_approval_produces_exactly_one_denial_event`
and `::test_invalid_approval_produces_exactly_one_denial_event`.

**F-2 fixed** — Added `canonical_project_digest(path: Path) -> str`
(`aos/safety/dev_server.py`), a SHA-256 digest of the resolved project path.
`consume_dev_server_approval` gained an optional `canonical_project_id: str | None`
keyword (falls back to the old `project_id`-based comparison when omitted, for
backward compatibility); when a real caller supplies it, the check is now
independent of the `project_id` string comparison. The one real production caller,
`WorkspaceTool._serve()`, now passes `canonical_project_id=canonical_project_digest(project)`
using the already freshly-resolved project `Path` — binding the approval to the
exact resolved directory, not just the opaque project-ID string. The CLI
(`aos/interfaces/cli/workspace_commands.py::serve`) now mints the approval with
`canonical_project_id=canonical_project_digest(resolved_project)` using the path
returned by `registry.resolve(project_id)`, instead of duplicating `project_id`.
Two new regression tests added:
`test_canonical_project_binding_catches_path_change_with_same_project_id` (proves a
path change between mint and consume is now rejected even when `project_id` is
unchanged) and `test_canonical_project_binding_accepts_matching_resolved_path`
(proves the legitimate matching-path case still succeeds).

**N-1 fixed** — Removed the dead `handle_id` branch from
`aos/agent/tool_registry.py::_execute_workspace` (no `_workspace_spec` ever declares
`handle_id` as an allowed arg, so it could never be reached).

**Re-verification after fixes:**

```
AOS_DATA_DIR=... .venv/bin/python -m pytest -q      → 564 passed (was 560; +4 new tests)
.venv/bin/python -m compileall -q aos tests          → PASS
.venv/bin/ruff check <all 15 listed files>            → All checks passed!
git diff --check                                      → PASS (exit 0)
```

Live-reproduced once more end to end: enroll → `serve` rejected at confirmation
prompt (no execute call, no audit rows) → `serve --approve` real foreground
`python -m http.server` launch → real SIGINT → clean `cancelled` outcome, exit 0, no
orphan process, approval consumed exactly once with the new path-bound canonical
digest matching correctly between mint (CLI) and consume (`_serve()`).

No production code review scope was exceeded: only
`aos/tools/workspace.py`, `aos/safety/dev_server.py`,
`aos/interfaces/cli/workspace_commands.py`, `aos/agent/tool_registry.py`, and
`tests/test_phase9_comprehensive.py` were touched by this follow-up.
