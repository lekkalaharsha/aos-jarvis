from aos.agent.intent import classify_intent
from aos.agent.planner import build_plan
from aos.agent.types import Intent


def test_project_summary_plan_uses_safe_file_tools():
    plan = build_plan(Intent.PROJECT_SUMMARY, "summarize this project")
    assert all(call.tool in {"fs.list", "fs.read", "fs.search"} for call in plan.tool_calls)


def test_find_todos_plan_uses_search():
    plan = build_plan(Intent.FIND_TODOS, "find TODOs")
    assert [call.tool for call in plan.tool_calls] == ["fs.search", "fs.search", "fs.search"]


def test_run_tests_plan_uses_preview_and_apply():
    plan = build_plan(Intent.RUN_TESTS, "run tests")
    assert [call.tool for call in plan.tool_calls] == ["run.preview", "run.apply"]


def test_git_status_plan_uses_git_status_tool():
    plan = build_plan(Intent.GIT_STATUS, "show git status")
    assert [call.tool for call in plan.tool_calls] == ["git.status"]


def test_project_changes_plan_uses_project_summary_tool():
    plan = build_plan(Intent.PROJECT_CHANGES, "what changed in this repo")
    assert [call.tool for call in plan.tool_calls] == ["project.summarize_changes"]


def test_draft_commit_plan_uses_draft_tool_only():
    plan = build_plan(Intent.DRAFT_COMMIT, "draft a commit message")
    assert [call.tool for call in plan.tool_calls] == ["project.draft_commit"]


def test_current_branch_plan_uses_branch_tool():
    plan = build_plan(Intent.CURRENT_BRANCH, "what branch am I on")
    assert [call.tool for call in plan.tool_calls] == ["git.branch"]


def test_recent_commits_plan_uses_git_log():
    plan = build_plan(Intent.RECENT_COMMITS, "show recent commits")
    assert [call.tool for call in plan.tool_calls] == ["git.log"]


def test_read_file_plan_uses_fs_read():
    plan = build_plan(Intent.READ_FILE, "read README.md")
    assert len(plan.tool_calls) == 1
    assert plan.tool_calls[0].tool == "fs.read"


def test_create_notes_plan_uses_fs_write_and_approval():
    plan = build_plan(Intent.CREATE_NOTES, "create notes.md")
    assert len(plan.tool_calls) == 1
    assert plan.tool_calls[0].tool == "fs.write"
    assert plan.tool_calls[0].requires_approval


def test_recall_memory_plan_uses_memory_recall_only():
    plan = build_plan(Intent.RECALL_MEMORY, "what did I work on recently")
    assert len(plan.tool_calls) == 1
    assert plan.tool_calls[0].tool == "memory.recall"
    assert plan.tool_calls[0].risk_tier == "T0"


def test_unknown_plan_has_no_tool_calls():
    plan = build_plan(Intent.UNKNOWN, "unsupported request")
    assert plan.tool_calls == []


def test_workspace_plan_requires_opaque_project_id_not_path():
    plan = build_plan(Intent.WORKSPACE_OPEN, "open workspace /tmp/project")
    assert plan.tool_calls == []
    project_id = "a" * 32
    plan = build_plan(Intent.WORKSPACE_OPEN, f"open workspace {project_id}")
    assert plan.tool_calls[0].tool == "workspace.open"
    assert plan.tool_calls[0].args == {"project_id": project_id}
