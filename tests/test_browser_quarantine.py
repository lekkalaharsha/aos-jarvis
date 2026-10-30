from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from aos.browser.approval import mint_browser_approval
from aos.browser.quarantine import QuarantineStore, check_download_type_agreement
from aos.safety.approved_projects import ApprovedProjectRegistry, HumanOwnerEnrollmentAuthority
from aos.safety.errors import PermissionBlocked


def _store(tmp_path):
    return QuarantineStore(tmp_path / "quarantine")


def _project(tmp_path, name="project"):
    root = tmp_path / name
    root.mkdir()
    registry = ApprovedProjectRegistry(tmp_path / "projects.json")
    approval = HumanOwnerEnrollmentAuthority().approve_one(root, human_owner_confirmed=True, origin="terminal")
    project = registry.enroll(root, approval=approval)
    return registry, project, root


def _promote_approval(store: QuarantineStore, record, project, project_root, relative_subpath: str = "."):
    dest = (project_root / relative_subpath / record.filename).resolve(strict=False)
    file_identity = store.promotion_file_identity(
        record,
        project_id=project.project_id,
        project_root=project_root,
        relative_subpath=relative_subpath,
        destination_path=dest,
    )
    return mint_browser_approval(
        operation="promote", task_id=f"promotion-{record.file_id}", domain_id="",
        file_identity=file_identity, human_owner_confirmed=True, origin="terminal",
    )


def _old_hash_only_approval(file_id: str, sha256: str):
    return mint_browser_approval(operation="promote", task_id=f"promotion-{file_id}", domain_id="", file_identity=sha256, human_owner_confirmed=True, origin="terminal")


def test_quarantine_root_outside_any_project_root(tmp_path):
    _, project, project_root = _project(tmp_path)
    store = _store(tmp_path)
    store.stage(filename="doc.pdf", content_type="application/pdf", data=b"%PDF-1.4 fake")
    assert not str(store.root).startswith(str(project_root))


def test_executable_magic_bytes_denied(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(PermissionBlocked):
        store.stage(filename="doc.pdf", content_type="application/pdf", data=b"MZ\x90\x00fake-exe")


def test_archive_extension_denied(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(PermissionBlocked):
        store.stage(filename="bundle.zip", content_type="application/zip", data=b"PK\x03\x04")


def test_mime_extension_mismatch_denied(tmp_path):
    with pytest.raises(PermissionBlocked):
        check_download_type_agreement(filename="report.pdf", declared_content_type="application/pdf", data=b"MZ\x90\x00")


def test_path_traversal_filename_denied(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(PermissionBlocked):
        store.stage(filename="../../etc/passwd", content_type="text/plain", data=b"hi")


def test_successful_stage_and_hash(tmp_path):
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    assert record.sha256 == hashlib.sha256(b"hello").hexdigest()


def test_retention_sweep_deletes_expired(tmp_path):
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    future = datetime.now(timezone.utc) + timedelta(hours=25)
    expired = store.sweep_expired(now=future)
    assert record.file_id in expired
    with pytest.raises(PermissionBlocked):
        store.get(record.file_id)


def test_retention_sweep_keeps_fresh_files(tmp_path):
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    expired = store.sweep_expired(now=datetime.now(timezone.utc))
    assert record.file_id not in expired
    assert store.get(record.file_id).file_id == record.file_id


def test_promotion_requires_an_enrolled_project_id(tmp_path):
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    approval = _old_hash_only_approval(record.file_id, record.sha256)
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id="not-a-real-project", relative_subpath=".", approval=approval, project_registry=ApprovedProjectRegistry(tmp_path / "projects.json"), approvals_consumed_path=tmp_path / "consumed.json")


def test_promotion_rejects_caller_controlled_root_string(tmp_path):
    # A caller can no longer smuggle an arbitrary destination by naming a
    # path directly -- only an enrolled project_id resolves a root at all
    # (remediation Critical #4). There is no "destination_dir" parameter
    # left on the public API to even accept an arbitrary path.
    assert "destination_dir" not in QuarantineStore.promote.__code__.co_varnames


def test_promotion_requires_a_fresh_approval(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id=project.project_id, relative_subpath=".", approval="not-a-real-approval", project_registry=project_registry, approvals_consumed_path=tmp_path / "consumed.json")  # type: ignore[arg-type]


def test_successful_promotion_moves_file_and_removes_from_quarantine(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    approval = _promote_approval(store, record, project, project_root)
    dest = store.promote(record.file_id, project_id=project.project_id, relative_subpath=".", approval=approval, project_registry=project_registry, approvals_consumed_path=tmp_path / "consumed.json")
    assert dest.exists()
    assert dest.read_bytes() == b"hello"
    assert str(dest).startswith(str(project_root))
    with pytest.raises(PermissionBlocked):
        store.get(record.file_id)


def test_promotion_subpath_traversal_denied(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    approval = _promote_approval(store, record, project, project_root)
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id=project.project_id, relative_subpath="../outside", approval=approval, project_registry=project_registry, approvals_consumed_path=tmp_path / "consumed.json")


def test_promotion_collision_denied_without_overwrite(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    (project_root / "notes.txt").write_bytes(b"existing")
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    approval = _promote_approval(store, record, project, project_root)
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id=project.project_id, relative_subpath=".", approval=approval, project_registry=project_registry, approvals_consumed_path=tmp_path / "consumed.json")


def test_promotion_of_unknown_file_id_denied(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    store = _store(tmp_path)
    approval = _old_hash_only_approval("unknown", "0" * 64)
    with pytest.raises(PermissionBlocked):
        store.promote("unknown", project_id=project.project_id, relative_subpath=".", approval=approval, project_registry=project_registry, approvals_consumed_path=tmp_path / "consumed.json")


def test_content_change_between_stage_and_promotion_denied(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    tampered_path = store.root / record.file_id / record.filename
    tampered_path.write_bytes(b"tampered")
    approval = _promote_approval(store, record, project, project_root)
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id=project.project_id, relative_subpath=".", approval=approval, project_registry=project_registry, approvals_consumed_path=tmp_path / "consumed.json")


def test_hash_only_promotion_approval_denied_at_store_boundary(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    approval = _old_hash_only_approval(record.file_id, record.sha256)
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id=project.project_id, relative_subpath=".", approval=approval, project_registry=project_registry, approvals_consumed_path=tmp_path / "consumed.json")


def test_destination_substitution_approval_denied_at_store_boundary(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    (project_root / "approved").mkdir()
    (project_root / "substituted").mkdir()
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    approval = _promote_approval(store, record, project, project_root, relative_subpath="approved")
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id=project.project_id, relative_subpath="substituted", approval=approval, project_registry=project_registry, approvals_consumed_path=tmp_path / "consumed.json")


def test_promotion_approval_replay_denied_at_store_boundary(tmp_path):
    project_registry, project, project_root = _project(tmp_path)
    (project_root / "notes.txt").write_bytes(b"existing")
    store = _store(tmp_path)
    record = store.stage(filename="notes.txt", content_type="text/plain", data=b"hello")
    approval = _promote_approval(store, record, project, project_root)
    consumed = tmp_path / "consumed.json"
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id=project.project_id, relative_subpath=".", approval=approval, project_registry=project_registry, approvals_consumed_path=consumed)
    (project_root / "notes.txt").unlink()
    with pytest.raises(PermissionBlocked):
        store.promote(record.file_id, project_id=project.project_id, relative_subpath=".", approval=approval, project_registry=project_registry, approvals_consumed_path=consumed)
