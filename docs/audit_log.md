# Audit Log

Implemented in `aos/safety/audit.py`, backed by SQLite at `~/.aos-jarvis/audit/audit.db`.

Each event stores: `id`, `timestamp`, `actor`, `event_type`, `action`, `resource`, `risk_tier`, `status`, `payload_json`, `parent_hash`, `event_hash`.

Hashing rule: `event_hash = sha256(canonical_json(event_without_event_hash) + parent_hash)`, with canonical JSON meaning `json.dumps(..., sort_keys=True)`. Each event's `parent_hash` is the previous event's `event_hash`; the first event chains from a genesis hash of all zeros.

`aos audit verify` walks the chain and reports the first row where either the stored hash doesn't match a recomputed hash, or `parent_hash` doesn't match the previous row's `event_hash` — both are tested in `tests/test_audit.py`.
