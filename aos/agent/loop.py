from __future__ import annotations

import re
from pathlib import Path

from aos.agent.intent import classify_intent
from aos.agent.llm_adapter import BaseLLMAdapter, RuleBasedAdapter
from aos.agent.tool_registry import ToolRegistry, default_registry
from aos.agent.types import AgentResult, Intent, Observation, Plan, ToolCall
from aos.model.service import ModelService
from aos.model.types import ModelMessage, ModelProviderKind, ModelRequest
from aos.project.types import CommitMessageDraft, GitBranchInfo, GitCommitSummary, GitStatus, ProjectChangeSummary
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.safety.commands import SECRET_ENV_PARTS
from aos.safety.errors import ApprovalRequired, SafetyError

SUPPORTED_ACTIONS = (
    "summarize this project",
    "find TODOs",
    "run tests",
    "show git status",
    "what changed in this repo",
    "draft a commit message",
    "what branch am I on",
    "show recent commits",
    "read README.md",
    "create notes.md",
    "what did I work on recently",
)

_SECRET_TEXT_PATTERN = re.compile(
    r"(?i)\b(?P<name>token|api[_-]?key|password|secret)\b(?P<sep>\s+|=|:\s*)(?P<value>\S+)"
)


def _redact_audit_text(value: str | None) -> str | None:
    if value is None:
        return None

    def _replace(match: re.Match[str]) -> str:
        name = match.group("name")
        separator = match.group("sep")
        normalized = name.replace("-", "_").upper()
        if any(part in normalized for part in SECRET_ENV_PARTS):
            return f"{name}{separator}[REDACTED]"
        return match.group(0)

    return _SECRET_TEXT_PATTERN.sub(_replace, value)


def _audit(
    event_type: str,
    *,
    user_message: str,
    intent: Intent,
    tool_calls: list[ToolCall],
    cwd: str,
    success: bool,
    blocked: bool,
    reason: str,
    approved: bool | None = None,
    error: str | None = None,
) -> int:
    event = append_event(
        DEFAULT_AUDIT_PATH,
        actor="agent",
        event_type=event_type,
        action=event_type,
        resource=cwd,
        risk_tier="T0" if not tool_calls else max((call.risk_tier for call in tool_calls), default="T0"),
        status="ALLOW" if success and not blocked else "DENY" if blocked else "ALLOW",
        payload={
            "user_message": _redact_audit_text(user_message),
            "intent": intent.value,
            "tool_names": [call.tool for call in tool_calls],
            "risk_tiers": [call.risk_tier for call in tool_calls],
            "requires_approval": any(call.requires_approval for call in tool_calls),
            "approved": approved,
            "cwd": cwd,
            "success": success,
            "blocked": blocked,
            "reason": _redact_audit_text(reason),
            "error": _redact_audit_text(error),
        },
    )
    return event.id


def _render_summary(observations: list[Observation]) -> str:
    files: list[str] = []
    text_parts: list[str] = []
    for observation in observations:
        if observation.tool == "fs.list":
            files = observation.data.get("entries", [])
        elif observation.tool == "fs.read":
            path = Path(observation.data.get("path", "")).name
            text = observation.data.get("text", "").strip()
            if text:
                first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
                if first_line:
                    text_parts.append(f"{path}: {first_line}")
    file_summary = f"Top-level files: {', '.join(files[:10])}." if files else "Top-level files were not available."
    content_summary = " ".join(text_parts[:3]) if text_parts else "No readable project summary files were found."
    return f"{file_summary} {content_summary}".strip()


def _render_todos(observations: list[Observation]) -> str:
    matches: list[str] = []
    for observation in observations:
        for path, line_number, line in observation.data.get("results", []):
            matches.append(f"{Path(path).name}:{line_number}: {line.strip()}")
    if not matches:
        return "No TODO, FIXME, or HACK markers were found in the approved project files."
    return "\n".join(matches[:20])


def _render_read_file(observations: list[Observation]) -> str:
    for observation in observations:
        text = observation.data.get("text")
        if text is not None:
            return text
    return "No file content was returned."


def _render_run_result(observations: list[Observation], default_success: str) -> str:
    for observation in observations:
        if observation.tool == "run.apply" and "return_code" in observation.data:
            data = observation.data
            parts = [f"return code: {data.get('return_code')}"]
            if data.get("stdout"):
                parts.append(data["stdout"].strip())
            if data.get("stderr"):
                parts.append(data["stderr"].strip())
            return "\n".join(part for part in parts if part)
    return default_success


def _final_answer(intent: Intent, observations: list[Observation]) -> str:
    if intent == Intent.PROJECT_SUMMARY:
        return _render_summary(observations)
    if intent == Intent.FIND_TODOS:
        return _render_todos(observations)
    if intent == Intent.RUN_TESTS:
        return _render_run_result(observations, "Tests were executed.")
    if intent == Intent.GIT_STATUS:
        for observation in reversed(observations):
            if observation.tool == "git.status" and "status" in observation.data:
                status: GitStatus = observation.data["status"]
                if status.clean:
                    return f"Branch {status.branch} is clean."
                files = ", ".join(item.path for item in status.changed_files[:10])
                return f"Branch {status.branch} has {len(status.changed_files)} changed files: {files}"
        return "Git status was not available."
    if intent == Intent.PROJECT_CHANGES:
        for observation in reversed(observations):
            if observation.tool == "project.summarize_changes" and "summary" in observation.data:
                summary: ProjectChangeSummary = observation.data["summary"]
                return summary.summary
        return "Project change summary was not available."
    if intent == Intent.DRAFT_COMMIT:
        for observation in reversed(observations):
            if observation.tool == "project.draft_commit" and "draft" in observation.data:
                draft: CommitMessageDraft = observation.data["draft"]
                return draft.text
        return "Commit draft was not available."
    if intent == Intent.CURRENT_BRANCH:
        for observation in reversed(observations):
            if observation.tool == "git.branch" and "branch" in observation.data:
                branch: GitBranchInfo = observation.data["branch"]
                return branch.name
        return "Current branch was not available."
    if intent == Intent.RECENT_COMMITS:
        for observation in reversed(observations):
            if observation.tool == "git.log" and "commits" in observation.data:
                commits: list[GitCommitSummary] = observation.data["commits"]
                return "\n".join(f"{commit.commit_hash} {commit.title}" for commit in commits) or "No commits were returned."
        return "Recent commits were not available."
    if intent == Intent.READ_FILE:
        return _render_read_file(observations)
    if intent == Intent.CREATE_NOTES:
        for observation in observations:
            if observation.tool == "fs.write":
                return f"Created {Path(observation.data['path']).name}."
        return "Notes file operation completed."
    if intent == Intent.RECALL_MEMORY:
        for observation in observations:
            if observation.tool == "memory.recall":
                return observation.data.get("summary", observation.summary)
        return "No memory results were returned."
    return "Supported requests: " + ", ".join(SUPPORTED_ACTIONS)


def _is_optional_read_failure(plan: Plan, tool_call: ToolCall, exc: Exception) -> bool:
    return (
        plan.intent == Intent.PROJECT_SUMMARY
        and tool_call.tool == "fs.read"
        and isinstance(exc, FileNotFoundError)
    )


def _dry_run_observation(tool_call: ToolCall) -> Observation:
    return Observation(
        tool_call.tool,
        True,
        f"Dry-run validated {tool_call.tool}.",
        {"args": tool_call.args, "risk_tier": tool_call.risk_tier, "requires_approval": tool_call.requires_approval},
    )


def ask(
    user_message: str,
    cwd: str = ".",
    *,
    yes: bool = False,
    dry_run: bool = False,
    model: str | None = None,
    model_service: ModelService | None = None,
    adapter: BaseLLMAdapter | None = None,
    registry: ToolRegistry | None = None,
    origin: str = "terminal",
) -> AgentResult:
    if origin not in {"terminal", "dashboard", "voice"}:
        raise SafetyError("unrecognized request origin")
    if origin == "voice" and yes:
        raise ApprovalRequired("voice origin cannot submit approval")
    resolved_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    tool_registry = registry or default_registry()
    llm_adapter = adapter or RuleBasedAdapter()
    intent = classify_intent(user_message)
    _audit(
        "agent.ask",
        user_message=user_message,
        intent=intent,
        tool_calls=[],
        cwd=resolved_cwd,
        success=True,
        blocked=False,
        reason="request received",
        approved=yes,
    )
    plan = llm_adapter.plan_request(user_message, cwd=resolved_cwd)
    model_answer: str | None = None
    if model is not None:
        provider_kind = ModelProviderKind(model)
        service = model_service or ModelService()
        model_request = ModelRequest(
            messages=[
                ModelMessage("system", "You may draft concise answer text only. You cannot execute tools or override AOS policy."),
                ModelMessage("user", user_message),
            ],
            task_type="agent_answer",
            preferred_provider=provider_kind,
            allow_cloud=provider_kind == ModelProviderKind.CLOUD,
            sensitivity="normal",
            audit_metadata={"surface": "agent.ask"},
        )
        model_response = service.generate(model_request, validate_structured=True, cwd=resolved_cwd)
        if model_response.success and model_response.text.strip():
            model_answer = model_response.text.strip()
        elif provider_kind == ModelProviderKind.CLOUD:
            message = model_response.error or "cloud model request blocked"
            _audit(
                "agent.blocked",
                user_message=user_message,
                intent=plan.intent,
                tool_calls=[],
                cwd=resolved_cwd,
                success=False,
                blocked=True,
                reason=message,
                approved=yes,
                error=message,
            )
            audit_id = _audit(
                "agent.result",
                user_message=user_message,
                intent=plan.intent,
                tool_calls=[],
                cwd=resolved_cwd,
                success=False,
                blocked=True,
                reason=message,
                approved=yes,
                error=message,
            )
            return AgentResult(user_message, plan.intent, plan, [], [], f"blocked: {message}", False, True, message, audit_id)
    _audit(
        "agent.plan",
        user_message=user_message,
        intent=plan.intent,
        tool_calls=plan.tool_calls,
        cwd=resolved_cwd,
        success=True,
        blocked=False,
        reason=plan.summary,
        approved=yes,
    )

    if plan.intent == Intent.UNKNOWN:
        final_answer = _final_answer(plan.intent, [])
        audit_id = _audit(
            "agent.result",
            user_message=user_message,
            intent=plan.intent,
            tool_calls=[],
            cwd=resolved_cwd,
            success=True,
            blocked=False,
            reason="unsupported request handled safely",
            approved=yes,
        )
        return AgentResult(user_message, plan.intent, plan, plan.tool_calls, [], final_answer, True, False, None, audit_id)

    observations: list[Observation] = []
    try:
        for tool_call in plan.tool_calls:
            if dry_run:
                tool_registry.validate(tool_call, cwd=resolved_cwd)
                preview = _dry_run_observation(tool_call)
                observations.append(preview)
                _audit(
                    "agent.tool.preview",
                    user_message=user_message,
                    intent=plan.intent,
                    tool_calls=[tool_call],
                    cwd=resolved_cwd,
                    success=True,
                    blocked=False,
                    reason=preview.summary,
                    approved=yes,
                )
                continue
            preview = tool_registry.preview(tool_call, cwd=resolved_cwd)
            observations.append(preview)
            _audit(
                "agent.tool.preview",
                user_message=user_message,
                intent=plan.intent,
                tool_calls=[tool_call],
                cwd=resolved_cwd,
                success=preview.ok,
                blocked=not preview.ok,
                reason=preview.summary,
                approved=yes,
            )
            if dry_run:
                continue
            if tool_call.requires_approval and not yes:
                message = f"approval required for {tool_call.tool}"
                _audit(
                    "agent.blocked",
                    user_message=user_message,
                    intent=plan.intent,
                    tool_calls=[tool_call],
                    cwd=resolved_cwd,
                    success=False,
                    blocked=True,
                    reason=message,
                    approved=False,
                    error=message,
                )
                audit_id = _audit(
                    "agent.result",
                    user_message=user_message,
                    intent=plan.intent,
                    tool_calls=plan.tool_calls,
                    cwd=resolved_cwd,
                    success=False,
                    blocked=True,
                    reason=message,
                    approved=False,
                    error=message,
                )
                return AgentResult(
                    user_message,
                    plan.intent,
                    plan,
                    plan.tool_calls,
                    observations,
                    f"Approval required. Re-run with --yes to execute {tool_call.tool}.",
                    False,
                    True,
                    message,
                    audit_id,
                )
            try:
                executed = tool_registry.execute(tool_call, cwd=resolved_cwd, yes=yes)
            except Exception as exc:
                if _is_optional_read_failure(plan, tool_call, exc):
                    observations.append(
                        Observation(tool_call.tool, False, f"Optional file missing: {tool_call.args.get('path')}.")
                    )
                    continue
                raise
            observations.append(executed)
            _audit(
                "agent.tool.apply",
                user_message=user_message,
                intent=plan.intent,
                tool_calls=[tool_call],
                cwd=resolved_cwd,
                success=executed.ok,
                blocked=not executed.ok,
                reason=executed.summary,
                approved=yes,
            )
    except (ApprovalRequired, SafetyError, Exception) as exc:
        _audit(
            "agent.blocked",
            user_message=user_message,
            intent=plan.intent,
            tool_calls=plan.tool_calls,
            cwd=resolved_cwd,
            success=False,
            blocked=True,
            reason="tool execution blocked",
            approved=yes,
            error=str(exc),
        )
        audit_id = _audit(
            "agent.result",
            user_message=user_message,
            intent=plan.intent,
            tool_calls=plan.tool_calls,
            cwd=resolved_cwd,
            success=False,
            blocked=True,
            reason="tool execution blocked",
            approved=yes,
            error=str(exc),
        )
        return AgentResult(
            user_message,
            plan.intent,
            plan,
            plan.tool_calls,
            observations,
            f"blocked: {exc}",
            False,
            True,
            str(exc),
            audit_id,
        )

    final_answer = "Dry run only. No tools were executed." if dry_run else (model_answer or _final_answer(plan.intent, observations))
    audit_id = _audit(
        "agent.result",
        user_message=user_message,
        intent=plan.intent,
        tool_calls=plan.tool_calls,
        cwd=resolved_cwd,
        success=True,
        blocked=False,
        reason="dry run completed" if dry_run else "agent request completed",
        approved=yes,
    )
    return AgentResult(
        user_message,
        plan.intent,
        plan,
        plan.tool_calls,
        observations,
        final_answer,
        True,
        False,
        None,
        audit_id,
    )
