import pytest

from aos.model.config import ModelConfig, ModelConfigError, model_config_from_dict
from aos.model.types import ModelProviderKind


def test_default_model_config_has_cloud_disabled():
    config = model_config_from_dict({})
    assert config.default_provider == ModelProviderKind.LOCAL
    assert config.allow_cloud is False
    assert config.cloud.enabled is False


def test_api_key_env_var_name_allowed():
    config = model_config_from_dict({"model": {"cloud": {"api_key_env": "OPENAI_API_KEY"}}})
    assert config.cloud.api_key_env == "OPENAI_API_KEY"


def test_raw_api_key_in_config_rejected():
    with pytest.raises(ModelConfigError):
        model_config_from_dict({"model": {"cloud": {"api_key": "sk-abc12345678901234567890"}}})


def test_invalid_provider_rejected():
    with pytest.raises(ModelConfigError):
        model_config_from_dict({"model": {"local": {"provider": "auto_discover"}}})


def test_cloud_fallback_rejected_when_cloud_disabled():
    with pytest.raises(ModelConfigError):
        model_config_from_dict({"model": {"fallback_provider": "cloud", "allow_cloud": False}})
