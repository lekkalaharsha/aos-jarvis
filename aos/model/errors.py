from __future__ import annotations


class ModelError(Exception):
    """Base error for safe model support."""


class ModelConfigError(ModelError):
    """Model configuration is invalid or unsafe."""


class ModelProviderError(ModelError):
    """A model provider failed safely."""


class ModelRoutingError(ModelError):
    """A model request cannot be routed safely."""


class ModelValidationError(ModelError):
    """Structured model output failed validation."""


class ModelRedactionError(ModelError):
    """Cloud redaction could not produce a safe request."""
