"""Tool interface contract. No real tools are active in Phase 0."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel

from aos.safety.risk import RiskTier


class ToolDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    REQUIRE_STRONG_APPROVAL = "REQUIRE_STRONG_APPROVAL"
    DENY = "DENY"


class ToolSchema(BaseModel):
    name: str
    description: str = ""
    args_schema: dict[str, Any] = {}


class ToolDiff(BaseModel):
    resource: str
    before: str = ""
    after: str = ""


class ToolResult(BaseModel):
    ok: bool
    output: str
    decision: ToolDecision


class BaseTool(ABC):
    """Every future tool must implement this contract."""

    @abstractmethod
    def describe(self) -> ToolSchema:
        ...

    @abstractmethod
    def dry_run(self, args: dict[str, Any]) -> ToolResult:
        ...

    @abstractmethod
    def execute(self, args: dict[str, Any]) -> ToolResult:
        ...

    @abstractmethod
    def required_capabilities(self, args: dict[str, Any]) -> list[str]:
        ...

    @abstractmethod
    def risk_tier(self) -> RiskTier:
        ...
