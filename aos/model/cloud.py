from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable

from aos.model.config import ModelConfig
from aos.model.errors import ModelProviderError
from aos.model.provider import ModelProvider
from aos.model.redaction import redact_text
from aos.model.types import ModelMessage, ModelProviderKind, ModelRequest, ModelResponse, ModelUsage

Transport = Callable[[str, bytes, dict[str, str], int], dict]


def _http_json_post(url: str, payload: bytes, headers: dict[str, str], timeout: int) -> dict:
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - explicit configured cloud endpoint
        return json.loads(response.read().decode("utf-8"))


class CloudModelProvider(ModelProvider):
    def __init__(self, config: ModelConfig, *, transport: Transport | None = None) -> None:
        self.config = config
        self.settings = config.cloud
        self._transport = transport or _http_json_post

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not (self.config.allow_cloud and self.settings.enabled and request.allow_cloud):
            return ModelResponse("", ModelProviderKind.CLOUD, self.settings.model, False, error="cloud model disabled")
        api_key = os.environ.get(self.settings.api_key_env or "")
        if not api_key:
            return ModelResponse("", ModelProviderKind.CLOUD, self.settings.model, False, error="cloud API key env var not set")

        redaction = redact_text(request.prompt_text)
        if redaction.blocked:
            return ModelResponse("", ModelProviderKind.CLOUD, self.settings.model, False, error=redaction.reason, redaction=redaction)
        redacted_messages = [ModelMessage("user", redaction.text)]
        payload = {
            "model": request.preferred_model or self.settings.model,
            "messages": [{"role": message.role, "content": message.content} for message in redacted_messages],
        }
        real_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        try:
            if self.settings.provider != "openai_compatible":
                raise ModelProviderError(f"unsupported cloud provider: {self.settings.provider}")
            url = self.settings.base_url.rstrip("/") + "/chat/completions"
            data = self._transport(url, json.dumps(payload).encode("utf-8"), real_headers, request.timeout_seconds)
            text = str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))[: request.max_output_chars]
            return ModelResponse(
                text=text,
                provider=ModelProviderKind.CLOUD,
                model=request.preferred_model or self.settings.model,
                success=True,
                usage=ModelUsage(prompt_chars=len(redaction.text), response_chars=len(text)),
                redaction=redaction,
                audit_summary={
                    "provider": "cloud",
                    "model": request.preferred_model or self.settings.model,
                    "redacted": redaction.redacted,
                    "secret_categories": sorted(redaction.counts_by_category),
                    "secret_count": redaction.total_count,
                },
            )
        except (TimeoutError, urllib.error.URLError, OSError, KeyError, IndexError, json.JSONDecodeError, ModelProviderError) as exc:
            return ModelResponse(
                text="",
                provider=ModelProviderKind.CLOUD,
                model=request.preferred_model or self.settings.model,
                success=False,
                error=f"cloud provider failed safely: {exc}",
                usage=ModelUsage(prompt_chars=len(redaction.text), response_chars=0),
                redaction=redaction,
            )
