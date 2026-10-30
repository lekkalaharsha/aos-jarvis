from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

from aos.model.config import ProviderSettings
from aos.model.errors import ModelProviderError
from aos.model.provider import ModelProvider
from aos.model.types import ModelProviderKind, ModelRequest, ModelResponse, ModelUsage

Transport = Callable[[str, bytes, dict[str, str], int], dict]


def _http_json_post(url: str, payload: bytes, headers: dict[str, str], timeout: int) -> dict:
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured endpoint, no shell/tools
        return json.loads(response.read().decode("utf-8"))


class LocalModelProvider(ModelProvider):
    def __init__(self, settings: ProviderSettings, *, transport: Transport | None = None) -> None:
        self.settings = settings
        self._transport = transport or _http_json_post

    def generate(self, request: ModelRequest) -> ModelResponse:
        prompt = request.prompt_text[: request.max_output_chars * 4]
        payload = {
            "model": request.preferred_model or self.settings.model,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
            "stream": False,
        }
        try:
            if self.settings.provider == "ollama":
                url = self.settings.base_url.rstrip("/") + "/api/chat"
                data = self._transport(url, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"}, request.timeout_seconds)
                text = str(data.get("message", {}).get("content", data.get("response", "")))
            elif self.settings.provider in {"openai_compatible", "mock"}:
                url = self.settings.base_url.rstrip("/") + "/chat/completions"
                data = self._transport(url, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"}, request.timeout_seconds)
                text = str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
            else:
                raise ModelProviderError(f"unsupported local provider: {self.settings.provider}")
            text = text[: request.max_output_chars]
            return ModelResponse(
                text=text,
                provider=ModelProviderKind.LOCAL,
                model=request.preferred_model or self.settings.model,
                success=True,
                usage=ModelUsage(prompt_chars=len(prompt), response_chars=len(text)),
                audit_summary={"provider": "local", "model": request.preferred_model or self.settings.model},
            )
        except (TimeoutError, urllib.error.URLError, OSError, KeyError, IndexError, json.JSONDecodeError, ModelProviderError) as exc:
            return ModelResponse(
                text="",
                provider=ModelProviderKind.LOCAL,
                model=request.preferred_model or self.settings.model,
                success=False,
                error=f"local provider failed safely: {exc}",
                usage=ModelUsage(prompt_chars=len(prompt), response_chars=0),
            )
