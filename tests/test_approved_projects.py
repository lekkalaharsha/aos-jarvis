"""Security matrix for the Phase 9 enrollment boundary."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from aos.safety.approved_projects import ApprovedProjectRegistry, HumanOwnerEnrollmentAuthority
from aos.safety.errors import PermissionBlocked
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import RiskTier


def _approval(path):
    return HumanOwnerEnrollmentAuthority().approve_one(path, human_owner_confirmed=True, origin="terminal")


def test_first_project_enrollment_requires_no_prior_registry_membership(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    added = registry.enroll(project, approval=_approval(project))
    assert registry.resolve(added.project_id) == project.resolve()


def test_enrollment_without_approval_and_self_approval_are_denied(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    with pytest.raises(TypeError):
        registry.enroll(project)  # type: ignore[call-arg]
    with pytest.raises(PermissionBlocked):
        registry.enroll(project, approval=project)  # type: ignore[arg-type]


def test_enrollment_approval_is_operation_bound(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    approval = _approval(project)
    # Tamper with the operation field via object.__setattr__ (bypasses sealed guard)
    object.__setattr__(approval, "_operation", "different.operation")
    with pytest.raises(PermissionBlocked):
        registry.enroll(project, approval=approval)


def test_cwd_and_registry_reads_never_grant_authorization(tmp_path, monkeypatch):
    project = tmp_path / "project"; project.mkdir()
    monkeypatch.chdir(project)
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    assert registry.list() == []
    assert not PermissionEngine([]).check_path(project, "workspace.open", RiskTier.T1).allowed
    with pytest.raises(PermissionBlocked):
        _approval(project)


def test_approval_is_exact_path_bound_and_single_use(tmp_path):
    one = tmp_path / "one"; one.mkdir()
    two = tmp_path / "two"; two.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    approval = _approval(one)
    with pytest.raises(PermissionBlocked):
        registry.enroll(two, approval=approval)
    added = registry.enroll(one, approval=approval)
    with pytest.raises(PermissionBlocked):
        registry.enroll(one, approval=approval)
    assert registry.resolve(added.project_id) == one.resolve()


def test_replay_is_rejected_after_new_registry_and_simulated_restart(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    path = tmp_path / "projects.json"
    approval = _approval(project)
    ApprovedProjectRegistry(path).enroll(project, approval=approval)
    with pytest.raises(PermissionBlocked):
        ApprovedProjectRegistry(path).enroll(project, approval=approval)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert len(persisted["consumed_approval_digests"]) == 1
    assert approval._token not in path.read_text(encoding="utf-8")


def test_consumption_survives_registry_rollback_and_digest_is_not_approval(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    before = registry._empty()
    approval = _approval(project)
    registry.enroll(project, approval=approval)
    registry._write(before)  # simulate restoration of only the registry snapshot
    with pytest.raises(PermissionBlocked):
        ApprovedProjectRegistry(registry.path).enroll(project, approval=approval)
    digest = json.loads(registry._consumed_path.read_text(encoding="utf-8"))[0]
    with pytest.raises(PermissionBlocked):
        ApprovedProjectRegistry(registry.path).enroll(project, approval=digest)  # type: ignore[arg-type]


def test_crash_after_consumption_fails_closed_and_never_persists_token(tmp_path, monkeypatch):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    approval = _approval(project)
    original_write = registry._write
    writes = 0

    def crash_after_consume(data):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("simulated crash")
        original_write(data)

    monkeypatch.setattr(registry, "_write", crash_after_consume)
    with pytest.raises(OSError):
        registry.enroll(project, approval=approval)
    restarted = ApprovedProjectRegistry(registry.path)
    assert restarted.list() == []
    with pytest.raises(PermissionBlocked):
        restarted.enroll(project, approval=approval)
    assert approval._token not in registry.path.read_text(encoding="utf-8")


def test_concurrent_enrollment_consumes_one_approval_once(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    approval = _approval(project)
    results: list[object] = []

    def enroll() -> None:
        try:
            results.append(registry.enroll(project, approval=approval))
        except PermissionBlocked as exc:
            results.append(exc)

    first = threading.Thread(target=enroll); second = threading.Thread(target=enroll)
    first.start(); second.start(); first.join(); second.join()
    assert sum(isinstance(item, PermissionBlocked) for item in results) == 1
    assert len(registry.list()) == 1


def test_expired_voice_and_model_approvals_are_denied(tmp_path, monkeypatch):
    project = tmp_path / "project"; project.mkdir()
    monkeypatch.setattr("aos.safety.approved_projects.APPROVAL_TTL_SECONDS", 0)
    expired = _approval(project)
    with pytest.raises(PermissionBlocked):
        ApprovedProjectRegistry(tmp_path / "projects.json").enroll(project, approval=expired)
    authority = HumanOwnerEnrollmentAuthority()
    with pytest.raises(PermissionBlocked):
        authority.approve_one(project, human_owner_confirmed=True, origin="voice")
    with pytest.raises(PermissionBlocked):
        authority.approve_one(project, human_owner_confirmed=True, origin="model")


def test_valid_unexpired_voice_and_model_origin_approvals_are_denied(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    authority = HumanOwnerEnrollmentAuthority()
    with pytest.raises(PermissionBlocked):
        authority.approve_one(project, human_owner_confirmed=True, origin="voice")
    with pytest.raises(PermissionBlocked):
        authority.approve_one(project, human_owner_confirmed=True, origin="model")


def test_symlink_change_between_approval_and_persistence_is_denied(tmp_path):
    target_one = tmp_path / "one"; target_one.mkdir()
    target_two = tmp_path / "two"; target_two.mkdir()
    link = tmp_path / "project-link"
    try:
        link.symlink_to(target_one, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")
    approval = _approval(link)
    link.unlink(); link.symlink_to(target_two, target_is_directory=True)
    with pytest.raises(PermissionBlocked):
        ApprovedProjectRegistry(tmp_path / "projects.json").enroll(link, approval=approval)


@pytest.mark.parametrize("path_name", [".ssh", ".env", "private-key"])
def test_dangerous_secret_and_non_directory_roots_are_rejected(tmp_path, path_name):
    path = tmp_path / path_name
    path.mkdir()
    with pytest.raises(PermissionBlocked):
        _approval(path)
    file_path = tmp_path / "not-a-project"; file_path.write_text("x")
    with pytest.raises(PermissionBlocked):
        _approval(file_path)


def test_filesystem_and_home_roots_are_overly_broad(tmp_path):
    with pytest.raises(PermissionBlocked):
        _approval(Path("/"))
    with pytest.raises(PermissionBlocked):
        _approval(Path.home())


def test_duplicate_and_revoked_projects_require_fresh_reenrollment(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    first = registry.enroll(project, approval=_approval(project))
    with pytest.raises(PermissionBlocked):
        registry.enroll(project, approval=_approval(project))
    registry.revoke(first.project_id)
    with pytest.raises(PermissionBlocked):
        registry.resolve(first.project_id)
    second = registry.enroll(project, approval=_approval(project))
    assert second.project_id != first.project_id
    assert registry.resolve(second.project_id) == project.resolve()


def test_token_never_appears_in_exception_text_or_registry(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    approval = _approval(project)
    token = approval._token
    # Successful enrollment — token must not be in registry file
    enrolled = registry.enroll(project, approval=approval)
    assert token not in registry.path.read_text(encoding="utf-8")
    # project_id is a uuid, not the token
    assert token not in enrolled.project_id
    # Re-enrollment must fail and exception text must not contain the token
    with pytest.raises(PermissionBlocked) as exc_info:
        registry.enroll(project, approval=_approval(project))
    assert token not in str(exc_info.value)
    # Expired approval exception text must not contain the token
    import time
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr("aos.safety.approved_projects.APPROVAL_TTL_SECONDS", 0)
        expired = _approval(project)
        with pytest.raises(PermissionBlocked) as exc_info:
            registry.enroll(project, approval=expired)
        assert token not in str(exc_info.value)
    finally:
        monkeypatch.undo()
    # CLI enroll output must not contain the token (enrolled.project_id is the only user-visible value)
    assert token not in enrolled.project_id
    assert token not in enrolled.path


def test_corrupt_registry_fails_closed_and_cannot_bypass_enrollment(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    registry.path.write_text(json.dumps({"schema_version": 1, "projects": [{"path": str(project)}]}), encoding="utf-8")
    with pytest.raises(PermissionBlocked):
        registry.list()
    with pytest.raises(PermissionBlocked):
        registry.enroll(project, approval=_approval(project))
