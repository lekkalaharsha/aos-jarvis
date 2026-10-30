from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from aos.config.loader import CONFIG_PATH, ensure_config, load_config
from aos.model.errors import ModelConfigError
from aos.model.types import ModelProviderKind
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event


@dataclass(frozen=True)
class ProviderSettings:
    enabled: bool
    provider: str
    model: str
    base_url: str
    api_key_env: str | None = None


@dataclass(frozen=True)
class ModelConfig:
    default_provider: ModelProviderKind = ModelProviderKind.LOCAL
    allow_cloud: bool = False
    fallback_provider: ModelProviderKind = ModelProviderKind.LOCAL
    max_prompt_chars: int = 12000
    max_response_chars: int = 6000
    timeout_seconds: int = 30
    local: ProviderSettings = ProviderSettings(True, "ollama", "qwen2.5-coder:7b", "http://localhost:11434")
    cloud: ProviderSettings = ProviderSettings(False, "openai_compatible", "gpt-4.1-mini", "https://api.openai.com/v1", "OPENAI_API_KEY")


def _provider_kind(value: str) -> ModelProviderKind:
    try:
        kind = ModelProviderKind(value)
    except ValueError as exc:
        raise ModelConfigError(f"invalid model provider: {value}") from exc
    if kind not in {ModelProviderKind.NONE, ModelProviderKind.LOCAL, ModelProviderKind.CLOUD}:
        raise ModelConfigError(f"invalid model provider: {value}")
    return kind


def _reject_raw_keys(section: dict[str, Any], *, name: str) -> None:
    for key, value in section.items():
        lowered = key.lower()
        if lowered in {"api_key", "token", "secret", "password"}:
            raise ModelConfigError(f"raw secret field not allowed in model.{name}: {key}")
        if isinstance(value, str) and (value.startswith("sk-") or value.startswith("ghp_")):
            raise ModelConfigError(f"raw secret value not allowed in model.{name}")


def _validate_endpoint(url: str, *, cloud: bool) -> str:
    """Validate provider endpoints before any request can use them."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ModelConfigError("model endpoint must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ModelConfigError("model endpoint must not contain credentials, query, or fragment data")
    if cloud and parsed.scheme != "https":
        raise ModelConfigError("cloud model endpoint must use HTTPS")
    return url.rstrip("/")


def model_config_from_dict(config: dict[str, Any]) -> ModelConfig:
    model = dict(config.get("model", {}))
    local_section = dict(model.get("local", {}))
    cloud_section = dict(model.get("cloud", {}))
    _reject_raw_keys(model, name="root")
    _reject_raw_keys(local_section, name="local")
    _reject_raw_keys(cloud_section, name="cloud")

    default_provider = _provider_kind(str(model.get("default_provider", "local")))
    fallback_provider = _provider_kind(str(model.get("fallback_provider", "local")))
    allow_cloud = bool(model.get("allow_cloud", False))
    cloud_enabled = bool(cloud_section.get("enabled", False))
    if default_provider == ModelProviderKind.CLOUD and not (allow_cloud and cloud_enabled):
        raise ModelConfigError("cloud default requires model.allow_cloud=true and model.cloud.enabled=true")
    if fallback_provider == ModelProviderKind.CLOUD and not (allow_cloud and cloud_enabled):
        raise ModelConfigError("cloud fallback requires model.allow_cloud=true and model.cloud.enabled=true")

    local = ProviderSettings(
        enabled=bool(local_section.get("enabled", True)),
        provider=str(local_section.get("provider", "ollama")),
        model=str(local_section.get("model", "qwen2.5-coder:7b")),
        base_url=str(local_section.get("base_url", "http://localhost:11434")),
    )
    cloud = ProviderSettings(
        enabled=cloud_enabled,
        provider=str(cloud_section.get("provider", "openai_compatible")),
        model=str(cloud_section.get("model", "gpt-4.1-mini")),
        base_url=str(cloud_section.get("base_url", "https://api.openai.com/v1")),
        api_key_env=str(cloud_section.get("api_key_env", "OPENAI_API_KEY")),
    )
    if cloud.api_key_env and any(part in cloud.api_key_env for part in ("=", " ", "\n", "\r")):
        raise ModelConfigError("api_key_env must be an environment variable name, not a value")
    local = ProviderSettings(local.enabled, local.provider, local.model, _validate_endpoint(local.base_url, cloud=False))
    cloud = ProviderSettings(cloud.enabled, cloud.provider, cloud.model, _validate_endpoint(cloud.base_url, cloud=True), cloud.api_key_env)
    if not local.provider:
        raise ModelConfigError("local provider is required")
    if cloud.provider not in {"openai_compatible"}:
        raise ModelConfigError(f"invalid cloud provider: {cloud.provider}")
    if local.provider not in {"ollama", "openai_compatible", "mock"}:
        raise ModelConfigError(f"invalid local provider: {local.provider}")
    return ModelConfig(
        default_provider=default_provider,
        allow_cloud=allow_cloud,
        fallback_provider=fallback_provider,
        max_prompt_chars=int(model.get("max_prompt_chars", 12000)),
        max_response_chars=int(model.get("max_response_chars", 6000)),
        timeout_seconds=int(model.get("timeout_seconds", 30)),
        local=local,
        cloud=cloud,
    )


def load_model_config(config_path: Path = CONFIG_PATH) -> ModelConfig:
    return model_config_from_dict(load_config(config_path))


def _render_bool(value: bool) -> str:
    return "true" if value else "false"


def save_model_config(config: ModelConfig, config_path: Path = CONFIG_PATH, *, audit: bool = True) -> None:
    ensure_config(config_path)
    text = f"""[project]
phase = "phase6"

[audit]
enabled = true

[model]
default_provider = "{config.default_provider.value}"
allow_cloud = {_render_bool(config.allow_cloud)}
fallback_provider = "{config.fallback_provider.value}"
max_prompt_chars = {config.max_prompt_chars}
max_response_chars = {config.max_response_chars}
timeout_seconds = {config.timeout_seconds}

[model.local]
enabled = {_render_bool(config.local.enabled)}
provider = "{config.local.provider}"
model = "{config.local.model}"
base_url = "{config.local.base_url}"

[model.cloud]
enabled = {_render_bool(config.cloud.enabled)}
provider = "{config.cloud.provider}"
model = "{config.cloud.model}"
base_url = "{config.cloud.base_url}"
api_key_env = "{config.cloud.api_key_env or 'OPENAI_API_KEY'}"
"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(text, encoding="utf-8")
    if audit:
        append_event(
            DEFAULT_AUDIT_PATH,
            actor="cli",
            event_type="model.config_update",
            action="model config update",
            resource=str(config_path),
            risk_tier="T0",
            status="ALLOW",
            payload={
                "default_provider": config.default_provider.value,
                "allow_cloud": config.allow_cloud,
                "cloud_enabled": config.cloud.enabled,
                "local_provider": config.local.provider,
                "cloud_provider": config.cloud.provider,
                "api_key_env_present": bool(config.cloud.api_key_env),
            },
        )


def cloud_api_key_present(config: ModelConfig) -> bool:
    return bool(config.cloud.api_key_env and os.environ.get(config.cloud.api_key_env))
