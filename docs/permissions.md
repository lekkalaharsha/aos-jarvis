# Permissions

Phase 1 denies by default. A file action is allowed only when all of these checks pass:

- Any symlink in the path, checked before resolution, does not resolve outside the approved roots.
- The resolved real path is inside an approved project root.
- The path is not a known dangerous system or credential location.
- The filename does not match secret deny patterns.
- The requested capability is a known one and maps to the action being performed.
- The risk tier has a valid decision.

## Directory Allowlist

The CLI uses the current working directory as the approved project root. The Python API accepts `approved_roots` for tests and future configuration-driven callers.

## Capabilities

Current Phase 1 capabilities and the access kind each one grants (`aos/safety/permissions.py::CAPABILITY_KINDS`):

| Capability | Kind |
|---|---|
| `fs.list` | `file.read` |
| `fs.read` | `file.read` |
| `fs.search` | `file.read` |
| `fs.write` | `file.write` |
| `fs.edit` | `file.write` |
| `snapshot.restore` | `file.restore` |

A capability name not in this table is denied by `PermissionEngine.check_path` with reason `unknown capability: <name>`, even if the path itself is otherwise safe.

## Symlink Escape Behavior

Symlink checking walks the path **before** it is resolved: `validate_path` computes both the pre-resolution absolute path and the fully-resolved real path, then checks each component of the pre-resolution path for a symlink whose target resolves outside the approved roots. A real symlink escape raises `SymlinkEscapeBlocked`. As defense in depth, the resolved-path containment check (`ensure_inside_approved_roots`) still runs afterward and would independently catch anything that slipped past the symlink walk, raising `PathOutsideApprovedRoot` in that case. A symlink whose target cannot be resolved (broken/dangling) is treated as an escape and blocked, rather than silently skipped.

## Blocked Paths

The path engine blocks Linux system and credential paths including `/etc`, `/root`, `/boot`, `/dev`, `/proc`, `/sys`, `~/.ssh`, `~/.aws`, `~/.config/gcloud`, and `~/.gnupg`. Browser cookie and profile credential locations are also blocked.

On Windows, the path engine also blocks `%WINDIR%` (or `%SystemRoot%`, default `C:\Windows`, which covers `System32` as a subpath) and `%PROGRAMDATA%` (default `C:\ProgramData`) as full-tree prefixes, read from environment variables rather than a hardcoded username. `%APPDATA%`/`%LOCALAPPDATA%` are **not** blocked wholesale -- those trees also hold ordinary temporary and application data (Windows' own TEMP directory lives under `%LOCALAPPDATA%\Temp`), so blanket-blocking them would break normal project and test usage. Instead, specific known Windows credential subfolders are blocked wherever they occur, the same way browser profile paths are: `AppData\Roaming\gcloud`, `AppData\Roaming\Microsoft\Credentials`, `AppData\Local\Microsoft\Credentials`, and `AppData\Roaming\Microsoft\Vault`.

## Secret Blocking

Secret file patterns are blocked even inside approved roots:

- `.env`
- `.env.*`
- `*.pem`
- `*.key`
- `id_rsa`
- `id_ed25519`
- `credentials.json`
- `token.json`
- `secrets.*`
- private-key and password-store paths

Blocked actions raise explicit exceptions and write `fs.blocked` audit events. They are not silently ignored.
