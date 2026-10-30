from __future__ import annotations

from abc import ABC, abstractmethod

from aos.model.types import ModelRequest, ModelResponse


class ModelProvider(ABC):
    """Safe model provider interface.

    Providers only accept ModelRequest and return ModelResponse. They do not
    receive tool registries, permission engines, shell runners, audit internals,
    or filesystem helpers.
    """

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        ...
