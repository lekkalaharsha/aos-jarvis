"""Phase 0 config loader. Deny-by-default: an unreadable/missing config
never blocks the CLI, it falls back to a safe, minimal default.
"""

from __future__ import annotations

import tomllib
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("AOS_DATA_DIR", Path.home() / ".aos-jarvis")).expanduser()
CONFIG_PATH = DATA_DIR / "config.toml"
LOGS_DIR = DATA_DIR / "logs"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"

DEFAULT_CONFIG_TOML = """\
[project]
phase = "phase0"

[audit]
enabled = true
"""


def ensure_config(config_path: Path = CONFIG_PATH) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
    return config_path


def load_config(config_path: Path = CONFIG_PATH) -> dict:
    ensure_config(config_path)
    with config_path.open("rb") as f:
        return tomllib.load(f)
