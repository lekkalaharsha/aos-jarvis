from aos.model.config import ModelConfig, ProviderSettings
from aos.model.router import ModelRouter
from aos.model.types import ModelMessage, ModelProviderKind, ModelRequest, ModelRouteDecision


def _request(provider=ModelProviderKind.LOCAL, allow_cloud=False, sensitivity="normal"):
    return ModelRequest(
        [ModelMessage("user", "hello")],
        "test",
        preferred_provider=provider,
        allow_cloud=allow_cloud,
        sensitivity=sensitivity,
    )


def test_local_route_works():
    result = ModelRouter(ModelConfig()).route(_request())
    assert result.decision == ModelRouteDecision.LOCAL


def test_cloud_route_blocked_when_disabled():
    result = ModelRouter(ModelConfig()).route(_request(ModelProviderKind.CLOUD, allow_cloud=True))
    assert result.decision == ModelRouteDecision.BLOCKED


def test_cloud_route_allowed_only_when_enabled():
    config = ModelConfig(allow_cloud=True, cloud=ProviderSettings(True, "openai_compatible", "m", "https://example.invalid", "OPENAI_API_KEY"))
    result = ModelRouter(config).route(_request(ModelProviderKind.CLOUD, allow_cloud=True))
    assert result.decision == ModelRouteDecision.CLOUD


def test_sensitive_input_blocks_cloud():
    config = ModelConfig(allow_cloud=True, cloud=ProviderSettings(True, "openai_compatible", "m", "https://example.invalid", "OPENAI_API_KEY"))
    result = ModelRouter(config).route(_request(ModelProviderKind.CLOUD, allow_cloud=True, sensitivity="sensitive"))
    assert result.decision == ModelRouteDecision.BLOCKED


def test_fallback_does_not_use_cloud_when_disabled():
    result = ModelRouter(ModelConfig()).fallback_after_error(_request(ModelProviderKind.CLOUD, allow_cloud=False))
    assert result.provider == ModelProviderKind.LOCAL
