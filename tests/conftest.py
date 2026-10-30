from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _phase6_audit_tmp_path(tmp_path, monkeypatch):
    """Keep Phase 6 model audit events inside pytest temp storage."""
    audit_path = tmp_path / "audit.db"
    for module_name in (
        "aos.model.router",
        "aos.model.service",
        "aos.model.validation",
        "aos.model.config",
    ):
        try:
            module = __import__(module_name, fromlist=["DEFAULT_AUDIT_PATH"])
        except Exception:
            continue
        if hasattr(module, "DEFAULT_AUDIT_PATH"):
            monkeypatch.setattr(module, "DEFAULT_AUDIT_PATH", audit_path)
