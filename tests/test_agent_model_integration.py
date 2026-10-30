from aos.agent.loop import ask
from aos.model.provider import ModelProvider
from aos.model.service import ModelService
from aos.model.types import ModelProviderKind, ModelResponse, ModelUsage


class FakeProvider(ModelProvider):
    def __init__(self, text: str, success: bool = True):
        self.text = text
        self.success = success

    def generate(self, request):
        return ModelResponse(
            self.text,
            request.preferred_provider or ModelProviderKind.LOCAL,
            "fake",
            self.success,
            usage=ModelUsage(prompt_chars=len(request.prompt_text), response_chars=len(self.text)),
        )


def test_agent_model_answer_does_not_bypass_tools():
    service = ModelService(local_provider=FakeProvider("model summary"))
    result = ask("summarize this project", dry_run=True, model="local", model_service=service)
    assert result.success
    assert result.final_answer == "Dry run only. No tools were executed."


def test_model_generated_unsafe_command_is_blocked():
    service = ModelService(local_provider=FakeProvider('{"intent":"X","tool":"shell.run","risk":"T0","args":{"command":"git push"}}'))
    result = ask("summarize this project", dry_run=True, model="local", model_service=service)
    assert result.success
    assert result.final_answer == "Dry run only. No tools were executed."
