"""Integration tests for the FastAPI dashboard app via ASGI transport."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from aos.dashboard.app import create_app
from aos.dashboard.service import DashboardService
from aos.safety.audit import append_event, init_audit_db


def _request(app, method: str, path: str, **kwargs):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


@pytest.fixture()
def app(tmp_path: Path):
    audit_db = tmp_path / "audit" / "audit.db"
    init_audit_db(audit_db)
    append_event(
        audit_db,
        actor="cli",
        event_type="fs.read",
        action="read file",
        resource="/project/foo.txt",
        risk_tier="T0",
        status="ALLOW",
    )
    append_event(
        audit_db,
        actor="cli",
        event_type="fs.write",
        action="write file",
        resource="/project/bar.txt",
        risk_tier="T1",
        status="DENY",
    )
    svc = DashboardService(audit_db=audit_db, data_dir=tmp_path)
    return create_app(service=svc)


def test_overview_returns_200(app):
    resp = _request(app, "GET", "/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_audit_returns_200(app):
    resp = _request(app, "GET", "/audit")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_permissions_returns_200(app):
    resp = _request(app, "GET", "/permissions")
    assert resp.status_code == 200


def test_activity_returns_200(app):
    resp = _request(app, "GET", "/activity")
    assert resp.status_code == 200


def test_snapshots_returns_200(app):
    resp = _request(app, "GET", "/snapshots")
    assert resp.status_code == 200


def test_model_status_returns_200(app):
    resp = _request(app, "GET", "/model")
    assert resp.status_code == 200


def test_security_events_returns_200(app):
    resp = _request(app, "GET", "/security")
    assert resp.status_code == 200


def test_audit_limit_capped_at_max_rows(app):
    resp = _request(app, "GET", "/audit?limit=99999")
    assert resp.status_code == 200


def test_permissions_limit_capped(app):
    resp = _request(app, "GET", "/permissions?limit=99999")
    assert resp.status_code == 200


def test_security_limit_capped(app):
    resp = _request(app, "GET", "/security?limit=99999")
    assert resp.status_code == 200


def test_post_overview_returns_405(app):
    resp = _request(app, "POST", "/")
    assert resp.status_code == 405


def test_put_overview_returns_405(app):
    resp = _request(app, "PUT", "/")
    assert resp.status_code == 405


def test_delete_overview_returns_405(app):
    resp = _request(app, "DELETE", "/")
    assert resp.status_code == 405


def test_patch_overview_returns_405(app):
    resp = _request(app, "PATCH", "/")
    assert resp.status_code == 405


def test_post_audit_returns_405(app):
    resp = _request(app, "POST", "/audit")
    assert resp.status_code == 405


def test_delete_snapshots_returns_405(app):
    resp = _request(app, "DELETE", "/snapshots")
    assert resp.status_code == 405


def test_patch_model_returns_405(app):
    resp = _request(app, "PATCH", "/model")
    assert resp.status_code == 405


def test_put_permissions_returns_405(app):
    resp = _request(app, "PUT", "/permissions")
    assert resp.status_code == 405


def test_openapi_schema_not_exposed(app):
    resp = _request(app, "GET", "/openapi.json")
    assert resp.status_code == 404


def test_docs_not_exposed(app):
    resp = _request(app, "GET", "/docs")
    assert resp.status_code == 404


def test_redoc_not_exposed(app):
    resp = _request(app, "GET", "/redoc")
    assert resp.status_code == 404


def test_overview_contains_version(app):
    resp = _request(app, "GET", "/")
    assert resp.status_code == 200
    from aos import __version__
    assert __version__ in resp.text


def test_audit_page_contains_event_data(app):
    resp = _request(app, "GET", "/audit")
    assert resp.status_code == 200
    body = resp.text
    assert "read file" in body or "write file" in body
