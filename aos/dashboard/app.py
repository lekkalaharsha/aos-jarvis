"""FastAPI read-only dashboard application factory.

Security guarantees:
- No write endpoints; POST/PUT/PATCH/DELETE return 405 by default.
- Jinja2 autoescape enabled for all .html templates (XSS protection).
- Pagination capped at MAX_ROWS server-side regardless of query param.
- OpenAPI docs and schema endpoints disabled.
- Host binding enforced to 127.0.0.1 by the CLI launcher.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from aos.dashboard.service import DashboardService, MAX_ROWS

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(service: DashboardService | None = None) -> FastAPI:
    """Return a configured read-only FastAPI dashboard application."""
    _svc = service or DashboardService()

    app = FastAPI(
        title="AOS-Jarvis Dashboard",
        docs_url=None,      # no Swagger UI
        redoc_url=None,     # no ReDoc
        openapi_url=None,   # no OpenAPI schema endpoint
    )

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    templates.env.autoescape = True

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def overview(request: Request) -> Response:
        data = _svc.get_overview()
        return templates.TemplateResponse(request, "overview.html", {"data": data})

    # ------------------------------------------------------------------
    # Audit timeline
    # ------------------------------------------------------------------

    @app.get("/audit", response_class=HTMLResponse)
    async def audit(request: Request, limit: int = 50) -> Response:
        limit = max(1, min(limit, MAX_ROWS))
        rows = _svc.get_audit_events(limit=limit)
        return templates.TemplateResponse(request, "audit.html", {"rows": rows, "limit": limit})

    # ------------------------------------------------------------------
    # Permission decisions
    # ------------------------------------------------------------------

    @app.get("/permissions", response_class=HTMLResponse)
    async def permissions(request: Request, limit: int = 50) -> Response:
        limit = max(1, min(limit, MAX_ROWS))
        rows = _svc.get_permission_events(limit=limit)
        return templates.TemplateResponse(request, "permissions.html", {"rows": rows, "limit": limit})

    # ------------------------------------------------------------------
    # Project / memory activity
    # ------------------------------------------------------------------

    @app.get("/activity", response_class=HTMLResponse)
    async def activity(request: Request, limit: int = 50) -> Response:
        limit = max(1, min(limit, MAX_ROWS))
        act = _svc.get_activity(limit=limit)
        return templates.TemplateResponse(request, "activity.html", {"act": act})

    # ------------------------------------------------------------------
    # Snapshot metadata
    # ------------------------------------------------------------------

    @app.get("/snapshots", response_class=HTMLResponse)
    async def snapshots(request: Request, limit: int = 50) -> Response:
        limit = max(1, min(limit, MAX_ROWS))
        rows = _svc.get_snapshots(limit=limit)
        return templates.TemplateResponse(request, "snapshots.html", {"rows": rows})

    # ------------------------------------------------------------------
    # Model-provider status
    # ------------------------------------------------------------------

    @app.get("/model", response_class=HTMLResponse)
    async def model_status(request: Request) -> Response:
        data = _svc.get_model_status()
        return templates.TemplateResponse(request, "model.html", {"data": data})

    # ------------------------------------------------------------------
    # Security events
    # ------------------------------------------------------------------

    @app.get("/security", response_class=HTMLResponse)
    async def security_events(request: Request, limit: int = 50) -> Response:
        limit = max(1, min(limit, MAX_ROWS))
        rows = _svc.get_security_events(limit=limit)
        return templates.TemplateResponse(request, "security.html", {"rows": rows, "limit": limit})

    return app
