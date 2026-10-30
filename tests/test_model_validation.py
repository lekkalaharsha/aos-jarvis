import pytest

from aos.model.errors import ModelValidationError
from aos.model.validation import parse_structured_output, validate_structured_output


def test_valid_tool_proposal_accepted_if_registered_and_safe():
    output = parse_structured_output('{"intent":"PROJECT_CHANGES","tool":"project.summarize_changes","risk":"T0","args":{"cwd":"."}}')
    assert output is not None
    assert validate_structured_output(output).tool_proposals[0].tool == "project.summarize_changes"


def test_unknown_tool_blocked():
    output = parse_structured_output('{"intent":"X","tool":"new.tool","risk":"T0","args":{}}')
    with pytest.raises(ModelValidationError):
        validate_structured_output(output)


def test_shell_run_git_push_proposal_blocked():
    output = parse_structured_output('{"intent":"X","tool":"shell.run","risk":"T0","args":{"command":"git push"}}')
    with pytest.raises(ModelValidationError):
        validate_structured_output(output)


def test_model_cannot_override_risk_tier():
    output = parse_structured_output('{"intent":"X","tool":"fs.write","risk":"T0","args":{"path":"x","content":"y"}}')
    with pytest.raises(ModelValidationError):
        validate_structured_output(output)


def test_invalid_json_treated_as_plain_text():
    assert parse_structured_output("not json") is None
