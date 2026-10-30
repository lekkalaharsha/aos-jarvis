"""Path normalization and deny-list checks for Phase 1 file tools."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from aos.safety.errors import (
    DangerousPathBlocked,
    PathOutsideApprovedRoot,
    SecretPathBlocked,
    SymlinkEscapeBlocked,
)

DANGEROUS_PREFIXES = (
    "/etc",
    "/root",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
    "~/.ssh",
    "~/.aws",
    "~/.config/gcloud",
    "~/.gnupg",
)

DANGEROUS_PARTS = (".ssh", ".aws", ".gnupg")

BROWSER_CREDENTIAL_PARTS = (
    "cookies",
    "login data",
    "key4.db",
    "firefox/profiles",
    "mozilla/firefox",
    "google/chrome",
    "chromium",
    "microsoft/edge",
)

# Windows credential stores that live inside AppData. Matched as substrings of
# the resolved path (like BROWSER_CREDENTIAL_PARTS above), NOT as a blanket
# prefix on %APPDATA%/%LOCALAPPDATA% -- those trees also hold ordinary user
# and temp-directory data (e.g. Windows TEMP is under AppData\Local\Temp).
WINDOWS_CREDENTIAL_PARTS = (
    "appdata/roaming/gcloud",
    "appdata/roaming/microsoft/credentials",
    "appdata/local/microsoft/credentials",
    "appdata/roaming/microsoft/vault",
)

SECRET_FILE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "token.json",
    "secrets.*",
)


def _windows_dangerous_prefixes() -> tuple[str, ...]:
    """Windows system roots, read from env vars (not a hardcoded username).
    AppData is deliberately NOT blocked wholesale here -- see WINDOWS_CREDENTIAL_PARTS."""
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "C:\\Windows"
    programdata = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
    return (windir, programdata)


def _normalize_for_rules(path: str | Path) -> str:
    return str(path).replace("\\", "/").lower().rstrip("/")


def _path_parts_lower(path: Path) -> tuple[str, ...]:
    return tuple(part.lower() for part in path.parts)


def _absolute_unresolved(path: str | Path, base_dir: Path | None = None) -> Path:
    """Expand and make absolute WITHOUT following symlinks, so callers can walk
    the original path components before resolution collapses them away."""
    requested = Path(path).expanduser()
    if not requested.is_absolute():
        requested = (base_dir or Path.cwd()) / requested
    return requested


def resolve_path(path: str | Path, base_dir: Path | None = None) -> Path:
    return _absolute_unresolved(path, base_dir).resolve(strict=False)


def resolve_roots(approved_roots: list[str | Path] | None = None) -> list[Path]:
    # ``None`` preserves legacy local-tool behaviour; an explicit empty list is
    # a deny-all set and must never become an implicit cwd approval.
    roots = [Path.cwd()] if approved_roots is None else approved_roots
    return [Path(root).expanduser().resolve(strict=False) for root in roots]


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def is_inside_any_root(path: Path, roots: list[Path]) -> bool:
    return any(is_relative_to(path, root) for root in roots)


def check_dangerous_path(path: str | Path, resolved: Path | None = None) -> None:
    candidate = resolved or Path(path).expanduser()
    raw = _normalize_for_rules(path)
    expanded = _normalize_for_rules(Path(path).expanduser())
    resolved_norm = _normalize_for_rules(candidate)

    all_prefixes = DANGEROUS_PREFIXES + _windows_dangerous_prefixes()
    for prefix in all_prefixes:
        prefix_norm = _normalize_for_rules(prefix)
        for candidate_str in (raw, expanded, resolved_norm):
            if candidate_str == prefix_norm or candidate_str.startswith(prefix_norm + "/"):
                raise DangerousPathBlocked(f"blocked dangerous path: {path}")
    parts = _path_parts_lower(candidate)
    if any(part in DANGEROUS_PARTS for part in parts):
        raise DangerousPathBlocked(f"blocked credential directory: {path}")

    # Use normalized text as well as pathlib parts: on POSIX a Windows-shaped
    # path is one Path component, but it must still hit Windows credential rules.
    joined = "/".join(parts) + "/" + _normalize_for_rules(candidate)
    if any(marker in joined for marker in BROWSER_CREDENTIAL_PARTS):
        raise DangerousPathBlocked(f"blocked browser credential path: {path}")
    if any(marker in joined for marker in WINDOWS_CREDENTIAL_PARTS):
        raise DangerousPathBlocked(f"blocked windows credential path: {path}")
    if ".config/gcloud" in joined:
        raise DangerousPathBlocked(f"blocked gcloud credential path: {path}")


def check_secret_path(path: str | Path, resolved: Path | None = None) -> None:
    candidate = resolved or Path(path)
    name = candidate.name.lower()
    for pattern in SECRET_FILE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            raise SecretPathBlocked(f"blocked secret file pattern: {candidate.name}")

    joined = "/".join(_path_parts_lower(candidate))
    if "private" in joined and "key" in joined:
        raise SecretPathBlocked(f"blocked private key path: {path}")
    if "password" in joined and ("store" in joined or "vault" in joined):
        raise SecretPathBlocked(f"blocked password store path: {path}")


def ensure_inside_approved_roots(path: Path, roots: list[Path]) -> None:
    if not is_inside_any_root(path, roots):
        raise PathOutsideApprovedRoot(f"path is outside approved roots: {path}")


def ensure_no_symlink_escape(path: Path, roots: list[Path]) -> None:
    """Walk `path` BEFORE symlink resolution and block any symlink component
    whose target resolves outside the approved roots. Callers must pass the
    pre-resolution path (see `_absolute_unresolved`) -- an already-resolved
    path can never report `is_symlink() == True` on any of its components."""
    current = path if path.exists() else path.parent
    for candidate in [current, *current.parents]:
        if not candidate.is_symlink():
            continue
        try:
            target = candidate.resolve(strict=True)
        except OSError as exc:
            raise SymlinkEscapeBlocked(f"symlink target could not be resolved: {candidate}") from exc
        if not is_inside_any_root(target, roots):
            raise SymlinkEscapeBlocked(f"symlink escapes approved roots: {candidate}")


def validate_path(path: str | Path, approved_roots: list[str | Path] | None = None) -> Path:
    roots = resolve_roots(approved_roots)
    pre_resolved = _absolute_unresolved(path)
    resolved = resolve_path(path)
    # Preserve the specific escape diagnostic even if an escaped target would
    # independently be dangerous or secret-shaped.
    ensure_no_symlink_escape(pre_resolved, roots)
    check_dangerous_path(path, resolved)
    check_secret_path(path, resolved)
    ensure_inside_approved_roots(resolved, roots)
    return resolved
