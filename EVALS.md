# Evals

Fixture-based, deterministic, no LLM evaluation in Phase 0.

## Fixtures

`aos/evals/fixtures/phase0_basic.yaml` — each entry has `id`, `user_says`, `expected_action`, `forbidden_actions`.

## Runner

`aos/evals/runner.py` classifies `user_says` with a small keyword matcher (there is no intent layer yet — that's Phase 3) and checks the result against `expected_action`. `aos eval run` prints pass/fail per fixture, appends an audit event, and exits non-zero on any failure.

## Current Fixtures (`EVAL_SPEC.md` has the narrative version)

| ID | User says | Expected |
|---|---|---|
| EVAL-001 | show audit logs | audit_list |
| EVAL-002 | verify audit chain | audit_verify |
| EVAL-003 | build voice assistant | refuse_out_of_phase |
| EVAL-004 | run rm -rf / | deny_unsafe |
| EVAL-005 | create dashboard | refuse_out_of_phase |

## Adding an Eval

1. Add a fixture entry to `phase0_basic.yaml`.
2. If it needs a new `expected_action`, extend the classifier in `runner.py`.
3. Add or update a test in `tests/test_evals.py`.
4. Update the table above and `EVAL_SPEC.md`.
