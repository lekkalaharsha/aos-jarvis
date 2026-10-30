"""Tests for the `aos dashboard` CLI command."""

from __future__ import annotations

import builtins
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from aos.interfaces.cli.main import app


runner = CliRunner()


def test_dashboard_help_exits_zero():
    result = runner.invoke(app, ["dashboard", "--help"])
    assert result.exit_code == 0
    assert "127.0.0.1" in result.output or "loopback" in result.output or "dashboard" in result.output.lower()


def test_dashboard_launches_on_loopback(tmp_path, monkeypatch):
    monkeypatch.setenv("AOS_DATA_DIR", str(tmp_path))
    # Initialize audit DB so DashboardService can start
    from aos.safety.audit import init_audit_db
    init_audit_db(tmp_path / "audit" / "audit.db")

    captured = {}

    def mock_uvicorn_run(app_instance, host, port, **kwargs):
        captured["host"] = host
        captured["port"] = port

    with patch("uvicorn.run", side_effect=mock_uvicorn_run):
        result = runner.invoke(app, ["dashboard", "--port", "9999"])

    assert captured.get("host") == "127.0.0.1", (
        f"Dashboard must bind to loopback only, got: {captured.get('host')}"
    )
    assert captured.get("port") == 9999


def test_dashboard_default_port_is_loopback(tmp_path, monkeypatch):
    monkeypatch.setenv("AOS_DATA_DIR", str(tmp_path))
    from aos.safety.audit import init_audit_db
    init_audit_db(tmp_path / "audit" / "audit.db")

    captured = {}

    def mock_uvicorn_run(app_instance, host, port, **kwargs):
        captured["host"] = host
        captured["port"] = port

    with patch("uvicorn.run", side_effect=mock_uvicorn_run):
        result = runner.invoke(app, ["dashboard"])

    assert captured.get("host") == "127.0.0.1"
    assert captured.get("port") == 8501


def test_dashboard_no_host_flag_in_help():
    result = runner.invoke(app, ["dashboard", "--help"])
    assert result.exit_code == 0
    # Confirm there is no --host option exposed to callers
    assert "--host" not in result.output


@pytest.mark.parametrize("port", ["1", "8000", "65535"])
def test_dashboard_accepts_valid_port_range(port: str):
    with patch("uvicorn.run") as run:
        result = runner.invoke(app, ["dashboard", "--port", port])
    assert result.exit_code == 0
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert run.call_args.kwargs["port"] == int(port)


def test_dashboard_environment_cannot_override_loopback(monkeypatch):
    monkeypatch.setenv("AOS_DASHBOARD_HOST", "0.0.0.0")
    with patch("uvicorn.run") as run:
        result = runner.invoke(app, ["dashboard", "--port", "8000"])
    assert result.exit_code == 0
    assert run.call_args.kwargs["host"] == "127.0.0.1"


@pytest.mark.parametrize("port", ["0", "-1", "65536"])
def test_dashboard_rejects_invalid_port_without_starting_server(port: str):
    with patch("uvicorn.run") as run:
        result = runner.invoke(app, ["dashboard", "--port", port])
    assert result.exit_code == 2
    assert "Invalid port" in result.output
    run.assert_not_called()


def test_dashboard_rejects_non_numeric_port_without_starting_server():
    with patch("uvicorn.run") as run:
        result = runner.invoke(app, ["dashboard", "--port", "not-a-port"])
    assert result.exit_code != 0
    run.assert_not_called()


def test_dashboard_missing_optional_dependency_has_clear_error(monkeypatch):
    original_import = builtins.__import__

    def fail_uvicorn(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("simulated missing dashboard dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_uvicorn)
    result = runner.invoke(app, ["dashboard"])
    assert result.exit_code == 1
    assert "uvicorn not installed" in result.output
