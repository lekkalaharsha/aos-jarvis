"""Dashboard CLI command — starts the read-only local dashboard.

Binds to 127.0.0.1 only; no --host flag is exposed to callers.
"""

from __future__ import annotations

import typer

app = typer.Typer(help="Read-only local dashboard (loopback-only, no state mutation).")


@app.callback(invoke_without_command=True)
def launch(
    port: int = typer.Option(8501, "--port", "-p", help="Port to listen on (default: 8501)."),
) -> None:
    """Start the AOS-Jarvis read-only dashboard at http://127.0.0.1:<port>."""
    if not 1 <= port <= 65535:
        typer.echo("Invalid port: choose an integer from 1 through 65535.", err=True)
        raise typer.Exit(2)
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        typer.echo(
            "uvicorn not installed. Run: pip install 'aos-jarvis[dashboard]'", err=True
        )
        raise typer.Exit(1)

    try:
        from aos.dashboard.app import create_app
    except ImportError as exc:
        typer.echo(f"Dashboard import failed: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Dashboard starting at http://127.0.0.1:{port}  (Ctrl-C to stop)")
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
