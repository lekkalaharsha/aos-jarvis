# Tool Interface

Every future tool must implement the contract defined in `aos/tools/base.py`:

- `describe() -> ToolSchema`
- `dry_run(args) -> ToolResult`
- `execute(args) -> ToolResult`
- `required_capabilities(args) -> list[str]`
- `risk_tier() -> RiskTier`

## Supporting Models

- `ToolSchema` — name, description, args schema.
- `ToolDiff` — resource, before, after (used to render approval previews).
- `ToolResult` — ok, output, decision.
- `RiskTier` — T0-T3 (see `PERMISSION_MODEL.md` / `SECURITY.md`).

## Rule

`dry_run` must never mutate state — it only previews what `execute` would do. `execute` must always go through the permission engine's decision for the tool's `risk_tier()` before doing anything (Phase 1+; in Phase 0 no tool executes).

## Phase 0 Status

Only the contract exists (`aos/tools/base.py`), with no concrete tool implementations. Real file tools land in Phase 1, shell tools in Phase 2. See `docs/tools/` for tool-specific design notes as they're added.
