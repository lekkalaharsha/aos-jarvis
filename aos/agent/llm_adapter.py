from __future__ import annotations

from abc import ABC, abstractmethod

from aos.agent.intent import classify_intent
from aos.agent.planner import build_plan
from aos.agent.types import Plan


class BaseLLMAdapter(ABC):
    @abstractmethod
    def plan_request(self, user_message: str, *, cwd: str = ".") -> Plan:
        ...


class RuleBasedAdapter(BaseLLMAdapter):
    def plan_request(self, user_message: str, *, cwd: str = ".") -> Plan:
        intent = classify_intent(user_message)
        return build_plan(intent, user_message, cwd=cwd)


class NullLLMAdapter(RuleBasedAdapter):
    pass

