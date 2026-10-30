from __future__ import annotations

from dataclasses import dataclass

from aos.model.config import ModelConfig, load_model_config
from aos.model.types import ModelProviderKind, ModelRequest, ModelRouteDecision
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event


@dataclass(frozen=True)
class RouteResult:
    decision: ModelRouteDecision
    provider: ModelProviderKind | None
    reason: str


class ModelRouter:
    def __init__(self, config: ModelConfig | None = None) -> None:
        self.config = config or load_model_config()

    def route(self, request: ModelRequest) -> RouteResult:
        preferred = request.preferred_provider or self.config.default_provider
        sensitive = request.sensitivity.lower() in {"sensitive", "private", "secret"}
        if preferred == ModelProviderKind.CLOUD:
            if sensitive:
                return self._audit(request, RouteResult(ModelRouteDecision.BLOCKED, None, "sensitive input cannot route to cloud"))
            if not (self.config.allow_cloud and self.config.cloud.enabled and request.allow_cloud):
                return self._audit(request, RouteResult(ModelRouteDecision.BLOCKED, None, "cloud disabled"))
            return self._audit(request, RouteResult(ModelRouteDecision.CLOUD, ModelProviderKind.CLOUD, "cloud route allowed"))
        if preferred == ModelProviderKind.LOCAL:
            if not self.config.local.enabled:
                return self._audit(request, RouteResult(ModelRouteDecision.BLOCKED, None, "local disabled"))
            return self._audit(request, RouteResult(ModelRouteDecision.LOCAL, ModelProviderKind.LOCAL, "local route allowed"))
        return self._audit(request, RouteResult(ModelRouteDecision.BLOCKED, None, "no model provider configured"))

    def fallback_after_error(self, request: ModelRequest) -> RouteResult:
        if self.config.fallback_provider == ModelProviderKind.LOCAL and self.config.local.enabled:
            return self._audit(request, RouteResult(ModelRouteDecision.FALLBACK_LOCAL, ModelProviderKind.LOCAL, "fallback to local"))
        if self.config.fallback_provider == ModelProviderKind.CLOUD:
            if self.config.allow_cloud and self.config.cloud.enabled and request.allow_cloud:
                return self._audit(request, RouteResult(ModelRouteDecision.CLOUD, ModelProviderKind.CLOUD, "fallback to cloud"))
            return self._audit(request, RouteResult(ModelRouteDecision.BLOCKED, None, "cloud fallback disabled"))
        return self._audit(request, RouteResult(ModelRouteDecision.ERROR, None, "no safe fallback"))

    def _audit(self, request: ModelRequest, result: RouteResult) -> RouteResult:
        append_event(
            DEFAULT_AUDIT_PATH,
            actor="model",
            event_type="model.route",
            action="model route",
            resource=request.task_type,
            risk_tier="T0",
            status="ALLOW" if result.provider else "DENY",
            payload={
                "decision": result.decision.value,
                "provider": result.provider.value if result.provider else None,
                "cloud": result.provider == ModelProviderKind.CLOUD,
                "reason": result.reason,
                "prompt_length": len(request.prompt_text),
            },
        )
        return result
