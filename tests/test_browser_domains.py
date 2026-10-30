from __future__ import annotations

import pytest

from aos.browser.domains import ApprovedDomainRegistry, DomainEnrollmentAuthority
from aos.safety.errors import PermissionBlocked


def _registry(tmp_path):
    return ApprovedDomainRegistry(tmp_path / "domains.json")


def test_enrollment_requires_human_owner_confirmation(tmp_path):
    authority = DomainEnrollmentAuthority()
    with pytest.raises(PermissionBlocked):
        authority.approve_one("example.com", human_owner_confirmed=False, origin="terminal")


def test_enrollment_requires_terminal_origin(tmp_path):
    authority = DomainEnrollmentAuthority()
    with pytest.raises(PermissionBlocked):
        authority.approve_one("example.com", human_owner_confirmed=True, origin="voice")
    with pytest.raises(PermissionBlocked):
        authority.approve_one("example.com", human_owner_confirmed=True, origin="agent")


def test_successful_enrollment(tmp_path):
    registry = _registry(tmp_path)
    authority = DomainEnrollmentAuthority()
    approval = authority.approve_one("example.com", human_owner_confirmed=True, origin="terminal")
    domain = registry.enroll("example.com", approval=approval)
    assert domain.host == "example.com"
    assert not domain.revoked
    resolved = registry.resolve(domain.domain_id)
    assert resolved.domain_id == domain.domain_id


def test_unknown_domain_denied_before_any_connection(tmp_path):
    registry = _registry(tmp_path)
    with pytest.raises(PermissionBlocked):
        registry.resolve_by_host("example.com")


def test_enrollment_approval_is_single_use(tmp_path):
    registry = _registry(tmp_path)
    authority = DomainEnrollmentAuthority()
    approval = authority.approve_one("example.com", human_owner_confirmed=True, origin="terminal")
    registry.enroll("example.com", approval=approval)
    with pytest.raises(PermissionBlocked):
        registry.enroll("example.com", approval=approval)


def test_enrollment_approval_bound_to_exact_host(tmp_path):
    registry = _registry(tmp_path)
    authority = DomainEnrollmentAuthority()
    approval = authority.approve_one("example.com", human_owner_confirmed=True, origin="terminal")
    with pytest.raises(PermissionBlocked):
        registry.enroll("other.example.com", approval=approval)


def test_revoked_domain_denied_on_next_use(tmp_path):
    registry = _registry(tmp_path)
    authority = DomainEnrollmentAuthority()
    approval = authority.approve_one("example.com", human_owner_confirmed=True, origin="terminal")
    domain = registry.enroll("example.com", approval=approval)
    registry.revoke(domain.domain_id)
    with pytest.raises(PermissionBlocked):
        registry.resolve(domain.domain_id)
    with pytest.raises(PermissionBlocked):
        registry.resolve_by_host("example.com")


def test_homograph_domain_does_not_collide_with_enrolled(tmp_path):
    registry = _registry(tmp_path)
    authority = DomainEnrollmentAuthority()
    approval = authority.approve_one("example.com", human_owner_confirmed=True, origin="terminal")
    registry.enroll("example.com", approval=approval)
    with pytest.raises(PermissionBlocked):
        registry.resolve_by_host("еxample.com")  # Cyrillic 'e'


def test_registry_membership_alone_grants_nothing_extra(tmp_path):
    # Sec4/Phase9-style rule: listing the registry must not itself be an
    # authorization path -- resolve() is the only lookup that matters and it
    # re-checks revocation every time.
    registry = _registry(tmp_path)
    authority = DomainEnrollmentAuthority()
    approval = authority.approve_one("example.com", human_owner_confirmed=True, origin="terminal")
    domain = registry.enroll("example.com", approval=approval)
    listed = registry.list()
    assert any(d.domain_id == domain.domain_id for d in listed)
    registry.revoke(domain.domain_id)
    listed_after = registry.list()
    assert any(d.domain_id == domain.domain_id and d.revoked for d in listed_after)
