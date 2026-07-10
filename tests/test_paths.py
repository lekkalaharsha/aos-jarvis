import os
from pathlib import Path

import pytest

from aos.safety.errors import (
    DangerousPathBlocked,
    PathOutsideApprovedRoot,
    SecretPathBlocked,
    SymlinkEscapeBlocked,
)
import aos.safety.paths as path_safety
from aos.safety.paths import check_dangerous_path, validate_path


def test_path_traversal_outside_approved_root_is_blocked(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(Exception):
        validate_path("../outside.txt", approved_roots=[tmp_path])


def test_dangerous_system_path_is_blocked():
    with pytest.raises(DangerousPathBlocked):
        validate_path("/etc/passwd", approved_roots=[Path.cwd()])


def test_secret_file_pattern_is_blocked(tmp_path):
    with pytest.raises(SecretPathBlocked):
        validate_path(tmp_path / ".env", approved_roots=[tmp_path])


def test_pem_file_pattern_is_blocked(tmp_path):
    with pytest.raises(SecretPathBlocked):
        validate_path(tmp_path / "cert.pem", approved_roots=[tmp_path])


def test_gcloud_credential_path_is_blocked_without_literal_tilde(tmp_path):
    gcloud_dir = tmp_path / ".config" / "gcloud"
    gcloud_dir.mkdir(parents=True)
    cred = gcloud_dir / "legacy_credentials.json"
    cred.write_text("secret", encoding="utf-8")

    with pytest.raises(DangerousPathBlocked):
        validate_path(cred, approved_roots=[tmp_path])


def test_resolved_escape_outside_approved_root_is_blocked(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.txt"

    monkeypatch.setattr(path_safety, "resolve_path", lambda path, base_dir=None: outside)

    with pytest.raises(PathOutsideApprovedRoot):
        validate_path(root / "link.txt", approved_roots=[root])


def test_real_symlink_escape_raises_symlink_specific_error(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "note.txt"
    secret.write_text("outside", encoding="utf-8")
    link = root / "escape.txt"
    try:
        os.symlink(secret, link)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(SymlinkEscapeBlocked):
        validate_path(link, approved_roots=[root])


def test_windows_system32_is_blocked_via_dangerous_path_check(monkeypatch):
    monkeypatch.setenv("WINDIR", "C:\\Windows")
    with pytest.raises(DangerousPathBlocked):
        check_dangerous_path("C:\\Windows\\System32\\config\\SAM")


def test_windows_programdata_is_blocked_via_dangerous_path_check(monkeypatch):
    monkeypatch.setenv("PROGRAMDATA", "C:\\ProgramData")
    with pytest.raises(DangerousPathBlocked):
        check_dangerous_path("C:\\ProgramData\\secrets.db")


def test_windows_appdata_roaming_gcloud_credential_path_is_blocked():
    with pytest.raises(DangerousPathBlocked):
        check_dangerous_path("C:\\Users\\tester\\AppData\\Roaming\\gcloud\\legacy_credentials\\adc.json")


def test_windows_appdata_local_chrome_profile_path_is_blocked():
    with pytest.raises(DangerousPathBlocked):
        check_dangerous_path("C:\\Users\\tester\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cookies")


def test_windows_appdata_temp_dir_is_not_blocked():
    """AppData/Local/Temp must stay usable -- it's where Windows (and pytest's
    tmp_path fixture) put ordinary temporary files."""
    check_dangerous_path("C:\\Users\\tester\\AppData\\Local\\Temp\\pytest-of-tester\\pytest-1\\project\\a.txt")


def test_unix_etc_passwd_still_blocked_via_dangerous_path_check():
    with pytest.raises(DangerousPathBlocked):
        check_dangerous_path("/etc/passwd")
