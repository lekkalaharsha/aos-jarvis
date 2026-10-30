# AOS-Jarvis Dashboard

## Overview

The AOS-Jarvis dashboard is a local, read-only web UI for inspecting system state.
It is implemented as a FastAPI application served by uvicorn and is accessible only
on the loopback interface (127.0.0.1).

## Starting the dashboard

```bash
aos dashboard               # starts on http://127.0.0.1:8501
aos dashboard --port 9000   # custom port
```

Open a browser and navigate to the printed URL.  The dashboard is read-only;
no system state can be changed through it.

## Available views

### Overview (`/`)

- AOS-Jarvis version
- Data directory path
- Audit chain validity and event count
- Current configuration

### Audit Timeline (`/audit`)

Full audit log in reverse-chronological order.  Fields: ID, timestamp, actor,
event type, action, resource, risk tier, status.  Payload values with
sensitive-sounding field names are shown as `[REDACTED]`.  Default: 50 rows,
max: 200.

### Permission Decisions (`/permissions`)

Events with status `ALLOW`, `DENY`, or `BLOCK`.  Useful for reviewing what the
permission engine has allowed or blocked.

### Project & Memory Activity (`/activity`)

Memory store statistics (indexed event count, entity count, timeline count) and the
most recent timeline entries from the memory subsystem.

### Snapshot Metadata (`/snapshots`)

Lists all snapshots with original path, timestamp, SHA-256 hash, and size.
Snapshot restore is **not available** through this dashboard.

### Model Provider Status (`/model`)

Shows the configured default provider, whether cloud is allowed in config, and
whether cloud is currently operational.  API keys are never displayed.

### Security Events (`/security`)

Events with `DENY`/`BLOCK` status or T3 risk tier.  Useful for a quick security
posture view.

## Security boundaries

- Loopback-only binding (`127.0.0.1`).  The `--host` flag is intentionally absent.
- All write HTTP methods (POST, PUT, PATCH, DELETE) return `405 Method Not Allowed`.
- Jinja2 autoescape prevents XSS from event data containing HTML/JS characters.
- Audit payload fields matching sensitive name patterns are redacted before display.
- OpenAPI schema and interactive docs endpoints (`/docs`, `/redoc`, `/openapi.json`)
  are disabled.
- The dashboard never invokes `restore_snapshot`, writes files, executes shell
  commands, or calls model providers.

## Installing dashboard dependencies

The dashboard dependencies are optional:

```bash
pip install 'aos-jarvis[dashboard]'
# installs: fastapi, uvicorn, jinja2
```

All three packages are likely already available if you are running in the standard
development virtual environment.
