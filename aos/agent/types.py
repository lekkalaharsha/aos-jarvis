from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Intent(str, Enum):
    PROJECT_SUMMARY = "PROJECT_SUMMARY"
    FIND_TODOS = "FIND_TODOS"
    RUN_TESTS = "RUN_TESTS"
    GIT_STATUS = "GIT_STATUS"
    READ_FILE = "READ_FILE"
    CREATE_NOTES = "CREATE_NOTES"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: dict[str, Any]
    risk_tier: str
    requires_approval: bool


@dataclass(frozen=True)
class Plan:
    intent: Intent
    summary: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class Observation:
    tool: str
    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    user_message: str
    intent: Intent
    plan: Plan
    tool_calls: list[ToolCall]
    observations: list[Observation]
    final_answer: str
    success: bool
    blocked: bool
    error: str | None
    audit_event_id: int | None

