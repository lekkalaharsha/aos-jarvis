from __future__ import annotations

from aos.model.cloud import CloudModelProvider
from aos.model.config import ModelConfig, load_model_config
from aos.model.local import LocalModelProvider
from aos.model.provider import ModelProvider
from aos.model.redaction import redact_metadata, redact_text
from aos.model.router import ModelRouter
from aos.model.types import ModelMessage, ModelProviderKind, ModelRequest, ModelResponse
from aos.model.validation import parse_structured_output, validate_structured_output
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event


class ModelService:
    def __init__(
        self,
        config: ModelConfig | None = None,
        *,
        local_provider: ModelProvider | None = None,
        cloud_provider: ModelProvider | None = None,
    ) -> None:
        self.config = config or load_model_config()
        self.local_provider = local_provider or LocalModelProvider(self.config.local)
        self.cloud_provider = cloud_provider or CloudModelProvider(self.config)
        self.router = ModelRouter(self.config)

    def generate(self, request: ModelRequest, *, validate_structured: bool = False, cwd: str = ".") -> ModelResponse:
        route = self.router.route(request)
        if route.provider is None:
            response = ModelResponse("", request.preferred_provider or ModelProviderKind.NONE, request.preferred_model or "", False, error=route.reason)
            self._audit_response(request, response)
            return response
        provider = self.local_provider if route.provider == ModelProviderKind.LOCAL else self.cloud_provider
        provider_request = request
        pre_redaction = None
        if route.provider == ModelProviderKind.CLOUD:
            pre_redaction = redact_text(request.prompt_text)
            provider_request = ModelRequest(
                messages=[ModelMessage("user", pre_redaction.text)],
                task_type=request.task_type,
                preferred_provider=request.preferred_provider,
                preferred_model=request.preferred_model,
                allow_cloud=request.allow_cloud,
                sensitivity=request.sensitivity,
                max_output_chars=request.max_output_chars,
                timeout_seconds=request.timeout_seconds,
                audit_metadata=request.audit_metadata,
            )
        self._audit_request(provider_request, route.provider)
        response = provider.generate(provider_request)
        if pre_redaction is not None and response.redaction is None:
            response = ModelResponse(
                text=response.text,
                provider=response.provider,
                model=response.model,
                success=response.success,
                structured_output=response.structured_output,
                error=response.error,
                usage=response.usage,
                redaction=pre_redaction,
                audit_summary=response.audit_summary,
            )
        structured = parse_structured_output(response.text)
        if structured is not None and validate_structured:
            try:
                structured = validate_structured_output(structured, cwd=cwd)
                response = ModelResponse(
                    text=response.text,
                    provider=response.provider,
                    model=response.model,
                    success=response.success,
                    structured_output=structured,
                    error=response.error,
                    usage=response.usage,
                    redaction=response.redaction,
                    audit_summary=response.audit_summary,
                )
            except Exception as exc:
                response = ModelResponse(
                    text="",
                    provider=response.provider,
                    model=response.model,
                    success=False,
                    error=f"structured output blocked: {exc}",
                    usage=response.usage,
                    redaction=response.redaction,
                    audit_summary=response.audit_summary,
                )
        self._audit_response(request, response)
        if not response.success:
            fallback = self.router.fallback_after_error(request)
            if fallback.provider == ModelProviderKind.LOCAL and route.provider != ModelProviderKind.LOCAL:
                fallback_request = ModelRequest(
                    messages=request.messages,
                    task_type=request.task_type,
                    preferred_provider=ModelProviderKind.LOCAL,
                    preferred_model=self.config.local.model,
                    allow_cloud=False,
                    sensitivity=request.sensitivity,
                    max_output_chars=request.max_output_chars,
                    timeout_seconds=request.timeout_seconds,
                    audit_metadata=request.audit_metadata,
                )
                self._audit_request(fallback_request, ModelProviderKind.LOCAL)
                response = self.local_provider.generate(fallback_request)
                self._audit_response(fallback_request, response)
        return response

    def _audit_request(self, request: ModelRequest, provider: ModelProviderKind) -> None:
        append_event(
            DEFAULT_AUDIT_PATH,
            actor="model",
            event_type="model.request",
            action="model request",
            resource=request.task_type,
            risk_tier="T0",
            status="ALLOW",
            payload={
                "provider": provider.value,
                "cloud": provider == ModelProviderKind.CLOUD,
                "prompt_length": len(request.prompt_text),
                "task_type": request.task_type,
                "sensitivity": request.sensitivity,
                "metadata": redact_metadata(request.audit_metadata),
            },
        )

    def _audit_response(self, request: ModelRequest, response: ModelResponse) -> None:
        event_type = "model.response" if response.success else "model.error"
        redaction = response.redaction
        if redaction is not None:
            append_event(
                DEFAULT_AUDIT_PATH,
                actor="model",
                event_type="model.redaction",
                action="model redaction",
                resource=request.task_type,
                risk_tier="T0",
                status="ALLOW" if not redaction.blocked else "DENY",
                payload={
                    "redacted": redaction.redacted,
                    "secret_categories": sorted(redaction.counts_by_category),
                    "secret_count": redaction.total_count,
                    "blocked": redaction.blocked,
                    "reason": redaction.reason,
                },
            )
        append_event(
            DEFAULT_AUDIT_PATH,
            actor="model",
            event_type=event_type,
            action=event_type,
            resource=request.task_type,
            risk_tier="T0",
            status="ALLOW" if response.success else "DENY",
            payload={
                "provider": response.provider.value,
                "model": response.model,
                "cloud": response.provider == ModelProviderKind.CLOUD,
                "success": response.success,
                "error": response.error,
                "prompt_length": response.usage.prompt_chars,
                "response_length": response.usage.response_chars,
                "redacted": bool(redaction and redaction.redacted),
                "secret_categories": sorted(redaction.counts_by_category) if redaction else [],
                "secret_count": redaction.total_count if redaction else 0,
            },
        )
