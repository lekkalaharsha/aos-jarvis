# Phase 7 — Read-Only Dashboard

## Goal

Provide a local, read-only web dashboard for inspecting AOS-Jarvis system state.
No system state is modified by the dashboard.  No secrets or API keys are displayed.
All views are read-only; no write, mutation, or restore endpoints exist.

## Technology

FastAPI + Jinja2 (HTML templates) + uvicorn.  Listed in `ARCHITECTURE.md` as the
planned dashboard stack.  Installed as an optional extra (`pip install
'aos-jarvis[dashboard]'`).  The `TestClient` from Starlette allows all routes to be
tested without starting a real server.

## CLI command

```
aos dashboard [--port PORT]
```

Binds to `127.0.0.1` only.  Default port: 8501.  No `--host` flag is exposed.

## Views

| Path | Description |
|---|---|
| `/` | Overview: version, data-dir, audit chain validity |
| `/audit` | Full audit timeline (most-recent first, paginated) |
| `/permissions` | Permission decisions (ALLOW/DENY/BLOCK events) |
| `/activity` | Memory store status and timeline entries |
| `/snapshots` | Snapshot metadata (no restore button) |
| `/model` | Model-provider status (no API key values shown) |
| `/security` | Security events (DENY/BLOCK/T3 risk events) |

## Security properties

- Binds to `127.0.0.1` only; host is hardcoded in the launcher.
- POST/PUT/PATCH/DELETE on all routes return 405.
- Jinja2 autoescape enabled; `<script>` tags in event data are HTML-escaped.
- Pagination capped at `MAX_ROWS = 200` server-side regardless of query param.
- Fields with sensitive-sounding names (`api_key`, `token`, `secret`, …) in audit
  payloads are replaced with `[REDACTED]` before rendering.
- OpenAPI schema, Swagger docs, and ReDoc endpoints are all disabled.
- No snapshot restore.  No file write.  No shell execution.  No model invocation.

## Module layout

```
aos/dashboard/
    __init__.py
    service.py          read-only data service (talks to audit, memory, snapshot stores)
    app.py              FastAPI application factory
    templates/
        base.html
        overview.html
        audit.html
        permissions.html
        activity.html
        snapshots.html
        model.html
        security.html
aos/interfaces/cli/dashboard_commands.py   Typer `aos dashboard` command
```

## Tests

89 new tests across four files:
- `tests/test_dashboard_service.py` — service-layer unit tests
- `tests/test_dashboard_app.py` — HTTP integration tests (TestClient, no real server)
- `tests/test_dashboard_security.py` — XSS, secret exposure, write-method blocking,
  pagination overflow, introspection endpoints
- `tests/test_dashboard_cli.py` — CLI command, loopback-only binding verification
