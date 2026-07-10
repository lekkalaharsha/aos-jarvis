# Evals

Fixture-based, no LLM evaluation in Phase 0. Fixtures live in `aos/evals/fixtures/phase0_basic.yaml`; each entry has `id`, `user_says`, `expected_action`, and `forbidden_actions`.

`aos/evals/runner.py` classifies `user_says` with a small deterministic keyword matcher (there is no intent layer yet — that's Phase 3) and checks the result against `expected_action`. `aos eval run` prints pass/fail per fixture and exits non-zero on any failure.
