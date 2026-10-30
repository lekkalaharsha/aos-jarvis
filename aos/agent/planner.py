from __future__ import annotations

from pathlib import Path

from aos.agent.intent import extract_notes_filename, extract_project_id, extract_requested_file
from aos.agent.types import Intent, Plan, ToolCall


def build_plan(intent: Intent, user_message: str, *, cwd: str = ".") -> Plan:
    workspace_operations = {
        Intent.WORKSPACE_OPEN: ("workspace.open", "T1"),
        Intent.WORKSPACE_EDITOR: ("workspace.editor", "T1"),
        Intent.WORKSPACE_TERMINAL: ("workspace.terminal", "T1"),
        Intent.WORKSPACE_SERVE: ("workspace.serve", "T2"),
    }
    if intent in workspace_operations:
        tool, risk = workspace_operations[intent]
        project_id = extract_project_id(user_message)
        if project_id is None:
            return Plan(intent=intent, summary="An enrolled project ID is required; paths cannot be used here.", tool_calls=[])
        return Plan(intent=intent, summary="Launch only the explicitly enrolled workspace project.", tool_calls=[ToolCall(tool, {"project_id": project_id}, risk, True)])
    if intent == Intent.PROJECT_SUMMARY:
        return Plan(
            intent=intent,
            summary="Inspect top-level project files for a concise summary.",
            tool_calls=[
                ToolCall("fs.list", {"path": "."}, "T0", False),
                ToolCall("fs.read", {"path": "README.md"}, "T0", False),
                ToolCall("fs.read", {"path": "pyproject.toml"}, "T0", False),
                ToolCall("fs.read", {"path": "package.json"}, "T0", False),
            ],
        )
    if intent == Intent.FIND_TODOS:
        return Plan(
            intent=intent,
            summary="Search the approved project for TODO-style markers.",
            tool_calls=[
                ToolCall("fs.search", {"query": "TODO", "root": "."}, "T0", False),
                ToolCall("fs.search", {"query": "FIXME", "root": "."}, "T0", False),
                ToolCall("fs.search", {"query": "HACK", "root": "."}, "T0", False),
            ],
        )
    if intent == Intent.RUN_TESTS:
        return Plan(
            intent=intent,
            summary="Preview and, with approval, run the default test command.",
            tool_calls=[
                ToolCall("run.preview", {"command": "pytest", "cwd": "."}, "T1", False),
                ToolCall("run.apply", {"command": "pytest", "cwd": "."}, "T1", True),
            ],
        )
    if intent == Intent.GIT_STATUS:
        return Plan(
            intent=intent,
            summary="Inspect repository working tree status through the safe git assistant.",
            tool_calls=[
                ToolCall("git.status", {"cwd": "."}, "T0", False),
            ],
        )
    if intent == Intent.PROJECT_CHANGES:
        return Plan(
            intent=intent,
            summary="Summarize repository changes through the safe project assistant.",
            tool_calls=[ToolCall("project.summarize_changes", {"cwd": "."}, "T0", False)],
        )
    if intent == Intent.DRAFT_COMMIT:
        return Plan(
            intent=intent,
            summary="Draft a commit message without modifying the repository.",
            tool_calls=[ToolCall("project.draft_commit", {"cwd": "."}, "T0", False)],
        )
    if intent == Intent.CURRENT_BRANCH:
        return Plan(
            intent=intent,
            summary="Read the current git branch through the safe git assistant.",
            tool_calls=[ToolCall("git.branch", {"cwd": "."}, "T0", False)],
        )
    if intent == Intent.RECENT_COMMITS:
        return Plan(
            intent=intent,
            summary="Read recent commits through the safe git assistant.",
            tool_calls=[ToolCall("git.log", {"cwd": ".", "limit": 5}, "T0", False)],
        )
    if intent == Intent.READ_FILE:
        path = extract_requested_file(user_message) or "README.md"
        return Plan(
            intent=intent,
            summary=f"Read the requested file through the safe filesystem tool: {path}.",
            tool_calls=[ToolCall("fs.read", {"path": path}, "T0", False)],
        )
    if intent == Intent.CREATE_NOTES:
        path = extract_notes_filename(user_message)
        content = (
            f"# Project Notes\n\n"
            f"- Created by AOS-Jarvis Phase 3 agent loop.\n"
            f"- Project directory: {Path(cwd).name or '.'}\n"
        )
        return Plan(
            intent=intent,
            summary=f"Create or overwrite {path} through the safe filesystem tool.",
            tool_calls=[ToolCall("fs.write", {"path": path, "content": content}, "T1", True)],
        )
    if intent == Intent.RECALL_MEMORY:
        return Plan(
            intent=intent,
            summary="Recall recent system or project activity from audit-derived memory.",
            tool_calls=[ToolCall("memory.recall", {"query": user_message, "limit": 10}, "T0", False)],
        )
    return Plan(
        intent=Intent.UNKNOWN,
        summary="Unsupported request. No tools will be executed.",
        tool_calls=[],
    )
