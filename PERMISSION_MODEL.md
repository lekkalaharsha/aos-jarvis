# Permission Model

## Default Rule

Deny by default. Allow only scoped, explainable, auditable actions. If a risk tier is unknown, treat it as `T3` (deny) — see `CODING_RULES.md` error-handling rules.

## Risk Tiers

| Tier | Meaning | Decision |
|---|---|---|
| T0 | read-only inside approved scope | ALLOW (auto) |
| T1 | reversible write with snapshot | REQUIRE_APPROVAL (show diff) |
| T2 | hard-to-reverse action | REQUIRE_STRONG_APPROVAL (show exact command/diff) |
| T3 | denied | DENY (never execute) |

Implemented now in `aos/safety/risk.py` (`RiskTier`, `Decision`, `decision_for_risk`).

## Capability Model

`aos/safety/permissions.py` defines `Capability` (name + description) and `PermissionDecision` (capability + decision + reason), both Pydantic models, both deny-by-default. The real directory allowlist and secret denylist enforcement is Phase 1 work.

## Approval Prompt Rule

Never show only a model's summary as the approval basis. For file changes: show file, risk tier, snapshot id, and diff. For shell commands: show command, working directory, risk tier, and sandbox status.

## Phase 0 Status

Risk tiers and capability placeholders exist and are tested. There is no enforcement engine, directory allowlist, or secret denylist wired to real actions yet — see `docs/phases/PHASE_1_SAFE_FILE_TOOLS.md`.
