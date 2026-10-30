from aos.model.config import ProviderSettings
from aos.model.local import LocalModelProvider
from aos.model.types import ModelMessage, ModelProviderKind, ModelRequest


def test_local_provider_mock_returns_response():
    def transport(url, payload, headers, timeout):
        return {"message": {"content": "local ok"}}

    provider = LocalModelProvider(ProviderSettings(True, "ollama", "mock", "http://localhost:11434"), transport=transport)
    response = provider.generate(ModelRequest([ModelMessage("user", "hi")], "test"))
    assert response.success
    assert response.provider == ModelProviderKind.LOCAL
    assert response.text == "local ok"


def test_local_provider_error_does_not_crash():
    def transport(url, payload, headers, timeout):
        raise TimeoutError("timeout")

    provider = LocalModelProvider(ProviderSettings(True, "ollama", "mock", "http://localhost:11434"), transport=transport)
    response = provider.generate(ModelRequest([ModelMessage("user", "hi")], "test"))
    assert not response.success
    assert "failed safely" in response.error
