"""Download quarantine and separately-approved promotion (contract Sec8).

The quarantine root is physically outside every approved project root and
is never registered with PermissionEngine/ApprovedProjectRegistry, so it is
structurally unreachable by fs.*, run.command, memory/indexing, the model
layer, the workspace tools, and the dashboard -- none of those capabilities
ever resolve a path here because none of them are ever given this root as
an approved root.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aos.browser.approval import BrowserApproval, consume_browser_approval
from aos.config.loader import DATA_DIR
from aos.safety.approved_projects import ApprovedProjectRegistry
from aos.safety.errors import PermissionBlocked
from aos.safety.paths import validate_path
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import RiskTier

DEFAULT_QUARANTINE_ROOT = DATA_DIR / "browser" / "quarantine"
RETENTION_HOURS = 24
MANIFEST_NAME = ".manifest.json"

# Contract Sec8: declared MIME, extension, sniffed MIME, and executable-magic
# must all agree with the allowlist.
ALLOWED_EXTENSIONS = frozenset({".pdf", ".txt", ".csv", ".png", ".jpg", ".jpeg", ".gif"})
ALLOWED_MIME_TYPES = frozenset({
    "application/pdf", "text/plain", "text/csv",
    "image/png", "image/jpeg", "image/gif",
})
EXECUTABLE_MAGIC = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa", b"#!")
ARCHIVE_EXTENSIONS = frozenset({".zip", ".tar", ".gz", ".7z", ".rar", ".tgz", ".bz2"})


def _sniff_mime(data: bytes, declared: str) -> str:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith((b"\xff\xd8\xff",)):
        return "image/jpeg"
    if data.startswith(b"GIF8"):
        return "image/gif"
    try:
        data.decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return declared or "application/octet-stream"


def check_download_type_agreement(*, filename: str, declared_content_type: str, data: bytes) -> None:
    """Contract Sec8: four signals must all agree with the allowlist.
    A mismatch (e.g. .pdf-named file with ELF magic) is denied."""
    ext = Path(filename).suffix.lower()
    if ext in ARCHIVE_EXTENSIONS:
        raise PermissionBlocked("archive file types are permanently denied")
    if any(data.startswith(magic) for magic in EXECUTABLE_MAGIC):
        raise PermissionBlocked("executable-magic-byte content is permanently denied")
    if ext not in ALLOWED_EXTENSIONS:
        raise PermissionBlocked(f"file extension is not on the download allowlist: {ext!r}")
    if declared_content_type not in ALLOWED_MIME_TYPES:
        raise PermissionBlocked(f"declared content type is not on the download allowlist: {declared_content_type!r}")
    sniffed = _sniff_mime(data, declared_content_type)
    if sniffed not in ALLOWED_MIME_TYPES:
        raise PermissionBlocked(f"sniffed content type is not on the download allowlist: {sniffed!r}")


def _sanitize_filename(name: str) -> str:
    candidate = os.path.basename(name).strip()
    if not candidate or candidate in {".", ".."} or "\x00" in candidate or "/" in candidate or "\\" in candidate:
        raise PermissionBlocked("unsafe download filename")
    return candidate


@dataclass(frozen=True)
class QuarantineFile:
    file_id: str
    filename: str
    sha256: str
    size_bytes: int
    staged_at: str
    content_type: str


class QuarantineStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_QUARANTINE_ROOT

    def _ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, stat.S_IRWXU)  # owner-only, per contract Sec8
        except OSError:
            if os.name == "posix":
                raise PermissionBlocked("quarantine root permissions could not be restricted")

    def _manifest_path(self) -> Path:
        return self.root / MANIFEST_NAME

    def _read_manifest(self) -> dict:
        path = self._manifest_path()
        if not path.exists():
            return {"files": {}}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PermissionBlocked("quarantine manifest is invalid") from exc

    def _write_manifest(self, data: dict) -> None:
        self._ensure_root()
        fd, name = tempfile.mkstemp(dir=self.root, prefix=".manifest-", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self._manifest_path())
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def stage(self, *, filename: str, content_type: str, data: bytes) -> QuarantineFile:
        safe_name = _sanitize_filename(filename)
        check_download_type_agreement(filename=safe_name, declared_content_type=content_type, data=data)
        self._ensure_root()
        file_id = uuid.uuid4().hex
        sha256 = hashlib.sha256(data).hexdigest()
        file_dir = self.root / file_id
        file_dir.mkdir(parents=True, exist_ok=True)
        target = file_dir / safe_name
        target.write_bytes(data)
        try:
            os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            if os.name == "posix":
                raise PermissionBlocked("quarantine file permissions could not be restricted")
        record = QuarantineFile(
            file_id=file_id, filename=safe_name, sha256=sha256, size_bytes=len(data),
            staged_at=datetime.now(timezone.utc).isoformat(), content_type=content_type,
        )
        manifest = self._read_manifest()
        manifest["files"][file_id] = record.__dict__
        self._write_manifest(manifest)
        return record

    def get(self, file_id: str) -> QuarantineFile:
        manifest = self._read_manifest()
        item = manifest["files"].get(file_id)
        if item is None:
            raise PermissionBlocked("quarantined file is unavailable")
        return QuarantineFile(**item)

    def _path_for(self, record: QuarantineFile) -> Path:
        return self.root / record.file_id / record.filename

    @staticmethod
    def promotion_file_identity(
        record: QuarantineFile,
        *,
        project_id: str,
        project_root: Path,
        relative_subpath: str,
        destination_path: Path,
    ) -> str:
        """Exact binding string for a store-bound promotion approval.

        It intentionally includes the quarantined file identity and every
        destination component that could otherwise be substituted after the
        Human Owner approves: enrolled project ID, canonical project root,
        validated relative subpath, and final canonical destination path.
        """
        return "|".join((
            record.file_id,
            record.sha256,
            str(record.size_bytes),
            project_id,
            str(project_root.resolve()),
            relative_subpath,
            str(destination_path.resolve(strict=False)),
        ))

    def sweep_expired(self, *, retention_hours: int = RETENTION_HOURS, now: datetime | None = None) -> list[str]:
        """No background scheduler exists (contract Sec8) -- this runs only
        at explicit task startup or an explicit cleanup command."""
        current = now or datetime.now(timezone.utc)
        manifest = self._read_manifest()
        expired_ids: list[str] = []
        for file_id, item in list(manifest["files"].items()):
            staged_at = datetime.fromisoformat(item["staged_at"])
            if current - staged_at > timedelta(hours=retention_hours):
                record = QuarantineFile(**item)
                path = self._path_for(record)
                if path.exists():
                    path.unlink()
                    try:
                        path.parent.rmdir()
                    except OSError:
                        pass
                del manifest["files"][file_id]
                expired_ids.append(file_id)
        if expired_ids:
            self._write_manifest(manifest)
        return expired_ids

    def promote(
        self,
        file_id: str,
        *,
        project_id: str,
        relative_subpath: str,
        approval: BrowserApproval,
        project_registry: ApprovedProjectRegistry | None = None,
        overwrite: bool = False,
        approvals_consumed_path: Path | None = None,
    ) -> Path:
        """Contract Sec8: separate exact-file T2 operation, requiring its own
        fresh :class:`BrowserApproval` at this store-level call boundary --
        not only enforced by the CLI (remediation Critical #3 last item).

        Remediation (Critical #4): the destination root is resolved from an
        ENROLLED project ID through :class:`ApprovedProjectRegistry`, never
        accepted as an arbitrary caller-supplied path. A caller cannot turn
        promotion into an unauthenticated local file-write primitive by
        naming an arbitrary directory -- only a directory the Human Owner
        has already separately enrolled via ``aos project enroll``-style
        flows can ever be a promotion destination.
        """
        record = self.get(file_id)
        source = self._path_for(record)
        if not source.exists():
            raise PermissionBlocked("quarantined file no longer exists")
        current_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if current_hash != record.sha256:
            raise PermissionBlocked("quarantined file content changed since staging (denied)")
        registry = project_registry or ApprovedProjectRegistry()
        project_root = registry.resolve(project_id)  # raises PermissionBlocked if not an active enrollment
        if any(part in {"..", ""} for part in Path(relative_subpath).parts) or Path(relative_subpath).is_absolute():
            raise PermissionBlocked("promotion subpath must be a relative path with no traversal")
        approved_roots = [project_root]
        dest_resolved = validate_path(project_root / relative_subpath / record.filename, approved_roots)
        PermissionEngine(approved_roots).require_path(dest_resolved, "browser.promote", RiskTier.T2)
        file_identity = self.promotion_file_identity(
            record,
            project_id=project_id,
            project_root=project_root,
            relative_subpath=relative_subpath,
            destination_path=dest_resolved,
        )
        consume_browser_approval(
            approval, operation="promote", task_id=f"promotion-{file_id}", domain_id="",
            file_identity=file_identity, consumed_path=approvals_consumed_path,
        )
        # Re-resolve every security-sensitive input after approval.  Approval
        # consumption is intentionally fail-closed if the project or any
        # destination component changed while the user was deciding.
        current_root = registry.resolve(project_id)
        if current_root != project_root:
            raise PermissionBlocked("promotion project changed after approval")
        dest_resolved = validate_path(current_root / relative_subpath / record.filename, [current_root])
        PermissionEngine([current_root]).require_path(dest_resolved, "browser.promote", RiskTier.T2)
        if self._has_symlinked_parent(current_root, relative_subpath, record.filename):
            raise PermissionBlocked("promotion destination contains a symlinked parent")
        current_identity = self.promotion_file_identity(
            record,
            project_id=project_id,
            project_root=current_root,
            relative_subpath=relative_subpath,
            destination_path=dest_resolved,
        )
        if current_identity != file_identity:
            raise PermissionBlocked("promotion destination changed after approval")
        current_data = source.read_bytes()
        if hashlib.sha256(current_data).hexdigest() != record.sha256:
            raise PermissionBlocked("quarantined file content changed after approval")
        if dest_resolved.exists() and not overwrite:
            raise PermissionBlocked("promotion destination already exists (collision denied)")
        dest_resolved.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if overwrite else os.O_EXCL)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(str(dest_resolved), flags, 0o600)
        except OSError as exc:
            raise PermissionBlocked("promotion destination could not be opened safely") from exc
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(current_data)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise PermissionBlocked("promotion destination could not be written safely") from exc
        source.unlink()
        try:
            source.parent.rmdir()
        except OSError:
            pass
        manifest = self._read_manifest()
        manifest["files"].pop(file_id, None)
        self._write_manifest(manifest)
        return dest_resolved

    @staticmethod
    def _has_symlinked_parent(root: Path, relative_subpath: str, filename: str) -> bool:
        """Reject symlinked destination directories before a promotion write."""
        root = root.resolve()
        lexical_destination = root / relative_subpath / filename
        try:
            relative = lexical_destination.relative_to(root)
        except ValueError:
            return True
        current = root
        for part in relative.parts[:-1]:
            current = current / part
            if current.is_symlink():
                return True
        return False
