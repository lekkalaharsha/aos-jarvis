from __future__ import annotations

from pathlib import Path

from aos.agent.intent import extract_notes_filename, extract_requested_file
from aos.agent.types import Intent, Plan, ToolCall


def build_plan(intent: Intent, user_message: str, *, cwd: str = ".") -> Plan:
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
            summary="Inspect repository working tree status through the safe shell runner.",
            tool_calls=[
                ToolCall("run.preview", {"command": "git status", "cwd": "."}, "T0", False),
                ToolCall("run.apply", {"command": "git status", "cwd": "."}, "T0", False),
            ],
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
    return Plan(
        intent=Intent.UNKNOWN,
        summary="Unsupported request. No tools will be executed.",
        tool_calls=[],
    )

