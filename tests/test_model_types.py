from aos.model.types import ModelMessage, ModelProviderKind, ModelRequest, ModelResponse, ModelUsage, ToolProposal


def test_model_request_prompt_text_is_structured():
    request = ModelRequest(
        [ModelMessage("system", "safe"), ModelMessage("user", "hello")],
        "summary",
        preferred_provider=ModelProviderKind.LOCAL,
    )
    assert request.prompt_text == "system: safe\nuser: hello"


def test_model_response_usage_defaults_are_safe():
    response = ModelResponse("ok", ModelProviderKind.LOCAL, "mock", True)
    assert response.usage == ModelUsage()
    assert response.audit_summary == {}


def test_tool_proposal_carries_no_execution_capability():
    proposal = ToolProposal("PROJECT_CHANGES", "project.summarize_changes", "T0", {"cwd": "."})
    assert proposal.tool == "project.summarize_changes"
    assert not hasattr(proposal, "execute")
