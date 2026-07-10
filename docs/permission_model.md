# Permission Model

Phase 0 only defines placeholders in `aos/safety/permissions.py`: `Capability` and `PermissionDecision`, both deny-by-default. The real directory allowlist, secret denylist, and enforcement engine are Phase 1 work — see `ROADMAP.md`.

Risk tiers (`aos/safety/risk.py`) already map to decisions and are active now:

| Tier | Decision |
|------|----------|
| T0 | ALLOW |
| T1 | REQUIRE_APPROVAL |
| T2 | REQUIRE_STRONG_APPROVAL |
| T3 | DENY |
