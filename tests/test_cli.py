from typer.testing import CliRunner

import aos.safety.snapshots as snapshots_module
from aos.interfaces.cli import main as cli_main
from aos.interfaces.cli import snapshot_commands

runner = CliRunner()


def _make_snapshot(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    file_path = root / "a.txt"
    file_path.write_text("before", encoding="utf-8")

    monkeypatch.setattr(snapshots_module, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(snapshots_module, "DEFAULT_AUDIT_PATH", tmp_path / "audit.db")
    monkeypatch.chdir(root)

    snapshot = snapshots_module.create_snapshot(
        file_path, reason="test", created_by_action="test", approved_roots=[root]
    )
    file_path.write_text("after", encoding="utf-8")
    return file_path, snapshot


def test_cli_doctor_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_main, "DEFAULT_AUDIT_PATH", tmp_path / "audit.db")
    monkeypatch.setattr(cli_main, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(cli_main, "CONFIG_PATH", tmp_path / "config" / "config.toml")

    result = runner.invoke(cli_main.app, ["doctor"])
    assert result.exit_code == 0


def test_cli_audit_verify_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_main, "DEFAULT_AUDIT_PATH", tmp_path / "audit.db")

    result = runner.invoke(cli_main.app, ["audit", "verify"])
    assert result.exit_code == 0
    assert "valid" in result.output


def test_cli_snapshot_restore_declining_first_t2_prompt_does_not_restore(tmp_path, monkeypatch):
    file_path, snapshot = _make_snapshot(tmp_path, monkeypatch)

    result = runner.invoke(snapshot_commands.app, ["restore", snapshot.snapshot_id], input="n\n")

    assert result.exit_code != 0
    assert file_path.read_text(encoding="utf-8") == "after"


def test_cli_snapshot_restore_wrong_typed_confirmation_does_not_restore(tmp_path, monkeypatch):
    file_path, snapshot = _make_snapshot(tmp_path, monkeypatch)

    result = runner.invoke(snapshot_commands.app, ["restore", snapshot.snapshot_id], input="y\nNOPE\n")

    assert result.exit_code != 0
    assert file_path.read_text(encoding="utf-8") == "after"


def test_cli_snapshot_restore_full_t2_confirmation_restores(tmp_path, monkeypatch):
    file_path, snapshot = _make_snapshot(tmp_path, monkeypatch)

    result = runner.invoke(snapshot_commands.app, ["restore", snapshot.snapshot_id], input="y\nRESTORE\n")

    assert result.exit_code == 0
    assert file_path.read_text(encoding="utf-8") == "before"


def test_cli_snapshot_restore_yes_flag_skips_both_t2_prompts(tmp_path, monkeypatch):
    file_path, snapshot = _make_snapshot(tmp_path, monkeypatch)

    result = runner.invoke(snapshot_commands.app, ["restore", snapshot.snapshot_id, "--yes"])

    assert result.exit_code == 0
    assert file_path.read_text(encoding="utf-8") == "before"
