import json

from aos.model.cloud import CloudModelProvider
from aos.model.config import ModelConfig, ProviderSettings
from aos.model.provider import ModelProvider
from aos.model.service import ModelService
from aos.model.types import ModelMessage, ModelProviderKind, ModelRequest


def _enabled_config():
    return ModelConfig(
        allow_cloud=True,
        cloud=ProviderSettings(True, "openai_compatible", "mock-cloud", "https://example.invalid/v1", "OPENAI_API_KEY"),
    )


def test_cloud_provider_mock_returns_response_and_gets_redacted_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-env-secret")
    seen = {}

    def transport(url, payload, headers, timeout):
        seen["payload"] = json.loads(payload.decode("utf-8"))
        seen["headers"] = headers
        return {"choices": [{"message": {"content": "cloud ok"}}]}

    provider = CloudModelProvider(_enabled_config(), transport=transport)
    response = provider.generate(
        ModelRequest(
            [ModelMessage("user", "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz")],
            "test",
            preferred_provider=ModelProviderKind.CLOUD,
            allow_cloud=True,
        )
    )
    assert response.success
    assert response.text == "cloud ok"
    sent_text = seen["payload"]["messages"][0]["content"]
    assert "ghp_" not in sent_text
    assert "[REDACTED_SECRET]" in sent_text
    assert seen["headers"]["Authorization"] == "Bearer sk-real-env-secret"


def test_cloud_provider_blocked_by_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-env-secret")
    provider = CloudModelProvider(ModelConfig())
    response = provider.generate(ModelRequest([ModelMessage("user", "hi")], "test", preferred_provider=ModelProviderKind.CLOUD, allow_cloud=True))
    assert not response.success
    assert response.error == "cloud model disabled"


def test_cloud_provider_blocked_redaction_result_returns_error(monkeypatch):
    """blocked=True on RedactionResult must prevent the cloud request from being sent."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-env-secret")
    transport_called = []

    def transport(url, payload, headers, timeout):
        transport_called.append(True)
        return {"choices": [{"message": {"content": "should not reach here"}}]}

    from aos.model.types import RedactionResult

    provider = CloudModelProvider(_enabled_config(), transport=transport)
    original_redact = provider.__class__.generate

    import unittest.mock

    with unittest.mock.patch("aos.model.cloud.redact_text") as mock_redact:
        mock_redact.return_value = RedactionResult(text="[REDACTED]", redacted=True, blocked=True, reason="content too sensitive to send")
        provider._transport = transport
        response = provider.generate(
            ModelRequest([ModelMessage("user", "ultra-sensitive content")], "test", preferred_provider=ModelProviderKind.CLOUD, allow_cloud=True)
        )
    assert not response.success
    assert "too sensitive" in (response.error or "")
    assert not transport_called, "transport should not be called when redaction is blocked"


def test_model_service_redacts_before_cloud_provider_receives_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-env-secret")
    seen = {}

    class FakeCloud(ModelProvider):
        def generate(self, request):
            seen["prompt"] = request.prompt_text
            from aos.model.types import ModelResponse, ModelUsage

            return ModelResponse("ok", ModelProviderKind.CLOUD, "fake", True, usage=ModelUsage(prompt_chars=len(request.prompt_text), response_chars=2))

    response = ModelService(_enabled_config(), cloud_provider=FakeCloud()).generate(
        ModelRequest(
            [ModelMessage("user", "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz")],
            "test",
            preferred_provider=ModelProviderKind.CLOUD,
            allow_cloud=True,
        )
    )
    assert response.success
    assert "sk-" not in seen["prompt"]
    assert "[REDACTED_SECRET]" in seen["prompt"]
