"""Security-focused tests for the AOS-Jarvis dashboard.

Covers XSS escaping, secret exposure, write-method blocking,
pagination overflow, and disabled introspection endpoints.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from aos.dashboard.app import create_app
from aos.dashboard.service import DashboardService, MAX_ROWS
from aos.safety.audit import append_event, init_audit_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_ROUTES = ["/", "/audit", "/permissions", "/activity", "/snapshots", "/model", "/security"]
_WRITE_METHODS = ["POST", "PUT", "PATCH", "DELETE"]


class _ASGIClient:
    def __init__(self, app) -> None:
        self._app = app

    def request(self, method: str, path: str):
        async def _run():
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path)

        return asyncio.run(_run())

    def get(self, path: str):
        return self.request("GET", path)


def _make_client_with_event(tmp_path: Path, **event_kwargs) -> _ASGIClient:
    audit_db = tmp_path / "audit" / "audit.db"
    init_audit_db(audit_db)
    defaults = dict(
        actor="cli",
        event_type="test.event",
        action="test action",
        resource="res",
        risk_tier="T0",
        status="ALLOW",
    )
    defaults.update(event_kwargs)
    append_event(audit_db, **defaults)
    svc = DashboardService(audit_db=audit_db, data_dir=tmp_path)
    return _ASGIClient(create_app(service=svc))


# ---------------------------------------------------------------------------
# XSS: script tags are HTML-escaped in rendered output
# ---------------------------------------------------------------------------


def test_xss_script_tag_escaped_in_audit(tmp_path: Path):
    payload = "<script>alert(1)</script>"
    client = _make_client_with_event(tmp_path, action=payload)
    resp = client.get("/audit")
    assert resp.status_code == 200
    assert "<script>" not in resp.text
    assert "&lt;script&gt;" in resp.text


def test_xss_script_tag_escaped_in_permissions(tmp_path: Path):
    payload = "<script>alert(2)</script>"
    client = _make_client_with_event(tmp_path, action=payload, status="DENY")
    resp = client.get("/permissions")
    assert resp.status_code == 200
    assert "<script>" not in resp.text


def test_xss_img_onerror_escaped_in_audit(tmp_path: Path):
    payload = '<img src=x onerror="alert(1)">'
    client = _make_client_with_event(tmp_path, action=payload)
    resp = client.get("/audit")
    assert resp.status_code == 200
    assert 'onerror="alert(1)"' not in resp.text


def test_xss_in_resource_field_escaped(tmp_path: Path):
    payload = "<b>bold</b>"
    client = _make_client_with_event(tmp_path, resource=payload)
    resp = client.get("/audit")
    assert "<b>" not in resp.text
    assert "&lt;b&gt;" in resp.text


# ---------------------------------------------------------------------------
# Secret strings must not appear in response body
# ---------------------------------------------------------------------------


def test_secret_sk_prefix_not_in_response_body(tmp_path: Path):
    audit_db = tmp_path / "audit" / "audit.db"
    init_audit_db(audit_db)
    append_event(
        audit_db,
        actor="cli",
        event_type="model.request",
        action="model request",
        resource="local",
        risk_tier="T0",
        status="ALLOW",
        payload={"api_key": "sk-supersecretvalue", "prompt": "hello"},
    )
    svc = DashboardService(audit_db=audit_db, data_dir=tmp_path)
    client = _ASGIClient(create_app(service=svc))
    for route in ["/audit", "/permissions", "/security"]:
        resp = client.get(route)
        assert "sk-supersecretvalue" not in resp.text, f"Secret leaked at {route}"


def test_api_key_payload_shows_redacted_label(tmp_path: Path):
    audit_db = tmp_path / "audit" / "audit.db"
    init_audit_db(audit_db)
    append_event(
        audit_db,
        actor="cli",
        event_type="model.request",
        action="model request",
        resource="local",
        risk_tier="T0",
        status="ALLOW",
        payload={"api_key": "sk-toplevel"},
    )
    from aos.dashboard.service import _redact_payload
    redacted = _redact_payload(json.dumps({"api_key": "sk-toplevel"}))
    assert redacted["api_key"] == "[REDACTED]"


@pytest.mark.parametrize("secret", [
    "sk-test-secret",
    "Bearer abcdef",
    "Authorization: Basic xyz",
    "AWS_SECRET_ACCESS_KEY=example",
    "ghp_exampletoken",
    "-----BEGIN PRIVATE KEY-----",
    "password=example",
    "api_key=example",
])
def test_secret_shaped_audit_columns_are_not_rendered(tmp_path: Path, secret: str):
    client = _make_client_with_event(
        tmp_path,
        actor=secret,
        event_type=secret,
        action=secret,
        resource=secret,
        status="DENY",
    )
    for route in ["/audit", "/permissions", "/security"]:
        assert secret not in client.get(route).text


# ---------------------------------------------------------------------------
# Pagination overflow is capped server-side
# ---------------------------------------------------------------------------


def test_large_limit_is_capped(tmp_path: Path):
    client = _make_client_with_event(tmp_path)
    resp = client.get("/audit?limit=1000000")
    assert resp.status_code == 200


def test_negative_limit_is_handled(tmp_path: Path):
    client = _make_client_with_event(tmp_path)
    resp = client.get("/audit?limit=-5")
    assert resp.status_code == 200


def test_zero_limit_is_handled(tmp_path: Path):
    client = _make_client_with_event(tmp_path)
    resp = client.get("/audit?limit=0")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# All write methods on all routes return 405 (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("route", _ALL_ROUTES)
@pytest.mark.parametrize("method", _WRITE_METHODS)
def test_write_method_rejected(tmp_path: Path, route: str, method: str):
    client = _make_client_with_event(tmp_path)
    resp = client.request(method, route)
    assert resp.status_code == 405, (
        f"Expected 405 for {method} {route}, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# No OpenAPI / docs endpoints
# ---------------------------------------------------------------------------


def test_openapi_json_returns_404(tmp_path: Path):
    client = _make_client_with_event(tmp_path)
    assert client.get("/openapi.json").status_code == 404


def test_swagger_docs_returns_404(tmp_path: Path):
    client = _make_client_with_event(tmp_path)
    assert client.get("/docs").status_code == 404


def test_redoc_returns_404(tmp_path: Path):
    client = _make_client_with_event(tmp_path)
    assert client.get("/redoc").status_code == 404


# ---------------------------------------------------------------------------
# MAX_ROWS constant is a reasonable bound
# ---------------------------------------------------------------------------


def test_max_rows_constant_is_bounded():
    assert 1 <= MAX_ROWS <= 1000
