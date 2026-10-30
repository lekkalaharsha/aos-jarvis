from aos.model.config import ModelConfig
from aos.model.types import ModelProviderKind


def test_phase6_cloud_disabled_by_default():
    config = ModelConfig()
    assert config.allow_cloud is False
    assert config.cloud.enabled is False
    assert config.default_provider != ModelProviderKind.CLOUD
