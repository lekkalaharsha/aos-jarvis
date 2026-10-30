from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelProviderKind(str, Enum):
    NONE = "none"
    LOCAL = "local"
    CLOUD = "cloud"


class ModelCapability(str, Enum):
    INTENT_CLASSIFICATION = "intent_classification"
    SUMMARY = "summary"
    EXPLANATION = "explanation"
    STRUCTURED_PROPOSAL = "structured_proposal"
    FINAL_ANSWER = "final_answer"


class ModelRouteDecision(str, Enum):
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    BLOCKED = "BLOCKED"
    FALLBACK_LOCAL = "FALLBACK_LOCAL"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ModelUsage:
    prompt_chars: int = 0
    response_chars: int = 0
    prompt_tokens: int | None = None
    response_tokens: int | None = None


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redacted: bool
    counts_by_category: dict[str, int] = field(default_factory=dict)
    blocked: bool = False
    reason: str | None = None

    @property
    def total_count(self) -> int:
        return sum(self.counts_by_category.values())


@dataclass(frozen=True)
class ToolProposal:
    intent: str
    tool: str
    risk: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuredModelOutput:
    intent: str | None = None
    tool_proposals: list[ToolProposal] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelRequest:
    messages: list[ModelMessage]
    task_type: str
    preferred_provider: ModelProviderKind | None = None
    preferred_model: str | None = None
    allow_cloud: bool = False
    sensitivity: str = "normal"
    max_output_chars: int = 6000
    timeout_seconds: int = 30
    audit_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def prompt_text(self) -> str:
        return "\n".join(f"{message.role}: {message.content}" for message in self.messages)


@dataclass(frozen=True)
class ModelResponse:
    text: str
    provider: ModelProviderKind
    model: str
    success: bool
    structured_output: StructuredModelOutput | None = None
    error: str | None = None
    usage: ModelUsage = field(default_factory=ModelUsage)
    redaction: RedactionResult | None = None
    audit_summary: dict[str, Any] = field(default_factory=dict)
