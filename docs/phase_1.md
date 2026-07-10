# Phase 1: Permission Engine and Safe File Tools

Phase 1 adds safe local file access for approved project folders. File actions are routed through path checks, capability decisions, risk tiers, audit events, and snapshots when writes can modify existing data.

## What Phase 1 Does

- Lists approved directories.
- Reads approved non-secret UTF-8 text files.
- Searches approved project files while skipping blocked, secret, binary, and unreadable files.
- Writes and edits approved files after explicit approval.
- Creates snapshots before modifying existing files.
- Restores snapshots to their original approved paths with T2 approval.
- Audits allowed and blocked file actions.

## What Phase 1 Does Not Do

Phase 1 does not implement an AI agent loop, shell runner, voice, dashboard, browser automation, screen understanding, memory system, model routing, or multi-agent behavior. It also does not provide unrestricted filesystem access.

## CLI Examples

```powershell
aos fs list .
aos fs read README.md
aos fs search audit --root .
aos fs write notes.txt --content "hello" --yes
aos fs edit notes.txt --old "hello" --new "hello phase 1" --yes
aos snapshot list
aos snapshot restore <snapshot_id> --yes
```

`--yes` is the non-interactive approval flag used for tests and scripted local checks. Without it, write and edit commands prompt once for confirmation; restore (T2) prompts twice -- a high-risk warning confirmation, then a typed `RESTORE` confirmation -- see `docs/risk_tiers.md`.

## Known Limitations

- Approved roots currently default to the CLI working directory unless a caller provides explicit roots to the Python API.
- File reads and edits are limited to UTF-8 text files up to the safe display size.
- Delete is intentionally not implemented in the Phase 1 CLI.
- Search is simple literal matching, not regex or indexed search.
- Symlink tests are skipped on systems that do not permit symlink creation (e.g. Windows without Developer Mode or admin rights); a platform-independent pre-resolution-path test covers the same logic without needing a real symlink.
- Windows dangerous-path coverage blocks `%WINDIR%`/`%PROGRAMDATA%` wholesale and specific known credential subfolders under `%APPDATA%`/`%LOCALAPPDATA%`, but does not block those AppData trees wholesale (see `docs/permissions.md`). Other Windows-specific credential stores not yet enumerated could still be missed.
