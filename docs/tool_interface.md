# Tool Interface

Defined in `aos/tools/base.py`. Every future tool implements `BaseTool`:

- `describe() -> ToolSchema`
- `dry_run(args) -> ToolResult`
- `execute(args) -> ToolResult`
- `required_capabilities(args) -> list[str]`
- `risk_tier() -> RiskTier`

No concrete tool exists in Phase 0 — only the contract. See `TOOL_CAPABILITIES.md` for risk tier examples.
