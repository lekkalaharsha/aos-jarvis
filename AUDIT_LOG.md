# Audit Log

Implemented in `aos/safety/audit.py`, backed by SQLite at `~/.aos-jarvis/audit/audit.db`.

## Schema

Each event: `id`, `timestamp`, `actor`, `event_type`, `action`, `resource`, `risk_tier`, `status`, `payload_json`, `parent_hash`, `event_hash`.

## Hashing Rule

```text
event_hash = sha256(canonical_json(event_without_event_hash) + parent_hash)
```

Canonical JSON means `json.dumps(..., sort_keys=True)` — deterministic field ordering is required or the chain can't be re-verified. Each event's `parent_hash` is the previous event's `event_hash`; the first event chains from a genesis hash of all zeros.

## Verification

`aos audit verify` (backed by `verify_chain()`) walks the chain and reports the first row where either:

- the stored `event_hash` doesn't match a recomputed hash (data was tampered with), or
- `parent_hash` doesn't match the previous row's `event_hash` (a row was deleted/inserted/reordered).

Both cases are covered in `tests/test_audit.py`.

## What Must Be Audited

Every future risky action, without exception. In Phase 0, `aos eval run` already appends an audit event for each run. As Phase 1+ tools come online, every `execute()` call must append an event before returning.
