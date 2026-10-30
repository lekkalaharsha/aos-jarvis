from __future__ import annotations

import typer
from rich.console import Console

from aos.agent.loop import ask

console = Console()


def ask_cli(
    request: str = typer.Argument(..., help="Natural-language request for the minimal agent loop."),
    cwd: str = typer.Option(".", "--cwd"),
    model: str | None = typer.Option(None, "--model", help="Optional model provider: local or cloud."),
    yes: bool = typer.Option(False, "--yes", help="Approve approval-gated tool calls."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the structured plan without executing tools."),
) -> None:
    result = ask(request, cwd=cwd, yes=yes, dry_run=dry_run, model=model)
    console.print(f"intent: {result.intent.value}")
    if result.tool_calls:
        for tool_call in result.tool_calls:
            console.print(
                f"tool: {tool_call.tool} risk={tool_call.risk_tier} approval={'yes' if tool_call.requires_approval else 'no'} args={tool_call.args}"
            )
    else:
        console.print("tool: none")
    console.print(result.final_answer)
    if result.blocked:
        raise typer.Exit(code=1)
