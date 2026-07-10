from aos.evals.runner import run_fixtures


def test_fixture_file_loads_and_runs():
    outcomes = run_fixtures()
    assert len(outcomes) == 5
    assert all(outcome.passed for outcome in outcomes)
