from __future__ import annotations

import json
from typing import Any

from aos.agent.tool_registry import ToolRegistry, default_registry
from aos.agent.types import ToolCall
from aos.model.errors import ModelValidationError
from aos.model.types import StructuredModelOutput, ToolProposal
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event

FORBIDDEN_MODEL_TOOLS = {"shell.run", "run.raw", "git.push", "git.pull", "git.fetch", "git.commit"}


def parse_structured_output(text: str) -> StructuredModelOutput | None:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    proposals: list[ToolProposal] = []
    if "tool" in raw:
        proposals.append(_proposal_from_dict(raw))
    for item in raw.get("tool_proposals", []):
        if isinstance(item, dict):
            proposals.append(_proposal_from_dict(item))
    return StructuredModelOutput(intent=raw.get("intent"), tool_proposals=proposals, raw=raw)


def _proposal_from_dict(raw: dict[str, Any]) -> ToolProposal:
    args = raw.get("args", {})
    if not isinstance(args, dict):
        args = {}
    return ToolProposal(
        intent=str(raw.get("intent", "")),
        tool=str(raw.get("tool", "")),
        risk=str(raw.get("risk", "")),
        args=args,
    )


def validate_structured_output(
    output: StructuredModelOutput,
    *,
    registry: ToolRegistry | None = None,
    cwd: str = ".",
) -> StructuredModelOutput:
    tool_registry = registry or default_registry()
    for proposal in output.tool_proposals:
        if proposal.tool in FORBIDDEN_MODEL_TOOLS:
            _audit_block(proposal, "forbidden model tool")
            raise ModelValidationError(f"forbidden model tool: {proposal.tool}")
        if proposal.tool in {"run.apply", "run.preview"} and "command" in proposal.args:
            command = str(proposal.args["command"]).lower()
            if any(part in command for part in ("git push", "git pull", "git fetch", "git commit")):
                _audit_block(proposal, "forbidden git operation in model command")
                raise ModelValidationError("forbidden git operation in model command")
        try:
            tool_registry.validate(
                ToolCall(
                    tool=proposal.tool,
                    args=proposal.args,
                    risk_tier=proposal.risk,
                    requires_approval=proposal.risk in {"T1", "T2"},
                ),
                cwd=cwd,
            )
        except Exception as exc:
            _audit_block(proposal, str(exc))
            raise ModelValidationError(str(exc)) from exc
    return output


def _audit_block(proposal: ToolProposal, reason: str) -> None:
    append_event(
        DEFAULT_AUDIT_PATH,
        actor="model",
        event_type="model.validation_blocked",
        action="model validation blocked",
        resource=proposal.tool,
        risk_tier="T0",
        status="DENY",
        payload={"tool": proposal.tool, "risk": proposal.risk, "reason": reason},
    )
