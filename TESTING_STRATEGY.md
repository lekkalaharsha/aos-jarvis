# Testing Strategy

## Tooling

`pytest`. No other test framework. Tests live under `tests/` (Phase 0 is flat; `tests/unit/`, `tests/integration/`, `tests/security/` subfolders are reserved for later phases when there's enough surface area to warrant the split).

## Required Coverage (Phase 0)

- Audit append/list works.
- Audit verify passes for a valid chain.
- Audit verify fails after tampering with a row.
- Audit verify fails on broken `parent_hash` continuity.
- Risk tier -> decision mapping is correct for all four tiers.
- `BaseTool` contract exists and is truly abstract (cannot instantiate without implementing every method).
- Capability model round-trips through serialization.
- Config loader creates a safe default and loads it back.
- Eval fixtures load and every Phase 0 fixture passes.
- `PHASE_CONTRACT.md` contains Active Phase, Forbidden Work, and Exit Criteria sections.
- CLI `doctor` and `audit verify` run cleanly end to end.
- Required shared-memory root files and `.agent/` files exist.

## Rules

- Every new security-relevant behavior ships with at least one test in the same change.
- Never mark a failing test as skipped without a documented reason.
- Never weaken a test just to make it pass — fix the code or the test's premise, not its assertions.
- Tests must not touch the real `~/.aos-jarvis` directory — use `tmp_path` and monkeypatch module-level path constants (see `tests/test_cli.py` for the pattern).

## Running

```bash
pip install -e .
pytest -q
```

All tests must pass before a phase is considered frozen — see `RELEASE_CHECKLIST.md`.
