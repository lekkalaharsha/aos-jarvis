from __future__ import annotations

import pytest

from aos.browser.approval import consume_browser_approval, mint_browser_approval
from aos.safety.errors import PermissionBlocked


def test_mint_requires_human_owner_confirmation():
    with pytest.raises(PermissionBlocked):
        mint_browser_approval(operation="navigate", task_id="t1", domain_id="d1", human_owner_confirmed=False, origin="terminal")


def test_mint_requires_terminal_origin():
    with pytest.raises(PermissionBlocked):
        mint_browser_approval(operation="navigate", task_id="t1", domain_id="d1", human_owner_confirmed=True, origin="voice")
    with pytest.raises(PermissionBlocked):
        mint_browser_approval(operation="navigate", task_id="t1", domain_id="d1", human_owner_confirmed=True, origin="model")
    with pytest.raises(PermissionBlocked):
        mint_browser_approval(operation="navigate", task_id="t1", domain_id="d1", human_owner_confirmed=True, origin="agent")


def test_successful_consume(tmp_path):
    approval = mint_browser_approval(operation="navigate", task_id="t1", domain_id="d1", url_digest="u1", human_owner_confirmed=True, origin="terminal")
    consume_browser_approval(approval, operation="navigate", task_id="t1", domain_id="d1", url_digest="u1", consumed_path=tmp_path / "consumed.json")


def test_reused_approval_denied(tmp_path):
    approval = mint_browser_approval(operation="navigate", task_id="t1", domain_id="d1", url_digest="u1", human_owner_confirmed=True, origin="terminal")
    path = tmp_path / "consumed.json"
    consume_browser_approval(approval, operation="navigate", task_id="t1", domain_id="d1", url_digest="u1", consumed_path=path)
    with pytest.raises(PermissionBlocked):
        consume_browser_approval(approval, operation="navigate", task_id="t1", domain_id="d1", url_digest="u1", consumed_path=path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation", "submit"),
        ("task_id", "t2"),
        ("domain_id", "d2"),
        ("url_digest", "different"),
        ("locator_identity", "different"),
        ("field_classification", "different"),
        ("file_identity", "different"),
    ],
)
def test_wrong_binding_denied(tmp_path, field, value):
    kwargs = dict(operation="navigate", task_id="t1", domain_id="d1", url_digest="u1", locator_identity="loc1", field_classification="", file_identity="")
    approval = mint_browser_approval(human_owner_confirmed=True, origin="terminal", **kwargs)
    consume_kwargs = dict(kwargs)
    consume_kwargs[field] = value
    with pytest.raises(PermissionBlocked):
        consume_browser_approval(approval, consumed_path=tmp_path / "consumed.json", **consume_kwargs)


def test_expired_approval_denied(tmp_path, monkeypatch):
    import aos.browser.approval as approval_module

    monkeypatch.setattr(approval_module, "APPROVAL_TTL_SECONDS", -1)
    # Re-mint with the patched TTL to get an already-expired approval.
    expired = mint_browser_approval(operation="navigate", task_id="t1", domain_id="d1", human_owner_confirmed=True, origin="terminal")
    with pytest.raises(PermissionBlocked):
        consume_browser_approval(expired, operation="navigate", task_id="t1", domain_id="d1", consumed_path=tmp_path / "consumed.json")


def test_approval_for_one_field_cannot_fill_a_different_field(tmp_path):
    approval = mint_browser_approval(operation="fill", task_id="t1", domain_id="d1", locator_identity="#field-a", human_owner_confirmed=True, origin="terminal")
    with pytest.raises(PermissionBlocked):
        consume_browser_approval(approval, operation="fill", task_id="t1", domain_id="d1", locator_identity="#field-b", consumed_path=tmp_path / "consumed.json")


def test_invalid_approval_object_denied(tmp_path):
    with pytest.raises(PermissionBlocked):
        consume_browser_approval("not-an-approval", operation="navigate", task_id="t1", domain_id="d1", consumed_path=tmp_path / "consumed.json")
