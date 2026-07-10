# Claude Notes

## Current assumptions
- Python 3.11+, Typer CLI, Pydantic v2 models, Rich CLI output, SQLite audit log, YAML eval fixtures.
- No file tools, no shell execution, no model calls in Phase 0.

## Implementation notes
- Audit store is in `aos/safety/audit.py` (event schema: actor/event_type/action/resource/risk_tier/status/payload_json/parent_hash/event_hash).
- CLI entrypoint is `aos/interfaces/cli/main.py`.
- Config loader is `aos/config/loader.py` (`~/.aos-jarvis/config.toml`, default-created if missing).
- Capability/tool contract models are Pydantic (`aos/safety/permissions.py`, `aos/tools/base.py`).
