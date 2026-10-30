import aos.agent.loop as agent_loop
import aos.project.git_tools as git_tools
import aos.project.project_summary as project_summary
import aos.tools.fs_tools as fs_tools
import aos.tools.shell_runner as shell_runner
import pytest

from aos.agent.loop import ask
from aos.agent.tool_registry import ToolRegistry
from aos.agent.types import ToolCall
from aos.safety.errors import PermissionBlocked
from aos.project.types import CommitMessageDraft, GitBranchInfo, GitCommitSummary, GitChangedFile, GitStatus, ProjectChangeSummary


@pytest.fixture()
def agent_env(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    audit_path = tmp_path / "audit.db"
    monkeypatch.setattr(agent_loop, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(fs_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(shell_runner, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(git_tools, "DEFAULT_AUDIT_PATH", audit_path)
    monkeypatch.setattr(project_summary, "DEFAULT_AUDIT_PATH", audit_path)
    return root


def test_project_changes_uses_project_summary_tool(agent_env, monkeypatch):
    monkeypatch.setattr(
        "aos.agent.tool_registry.summarize_project_changes",
        lambda *args, **kwargs: ProjectChangeSummary(
            branch="main",
            clean=False,
            changed_files=["README.md"],
            diff_summary=None,  # type: ignore[arg-type]
            recent_commits=[GitCommitSummary("abc1234", "feat: test")],
            summary="Branch main has 1 changed file.",
        ),
    )
    result = ask("what changed in this repo", cwd=agent_env)
    assert result.success
    assert "changed file" in result.final_answer


def test_draft_commit_message_returns_draft_only(agent_env, monkeypatch):
    monkeypatch.setattr("aos.agent.tool_registry.draft_commit_message", lambda *args, **kwargs: CommitMessageDraft("feat(repo): update docs"))
    result = ask("draft a commit message", cwd=agent_env)
    assert result.success
    assert "feat(repo): update docs" in result.final_answer


def test_current_branch_and_recent_commits_use_git_tools(agent_env, monkeypatch):
    monkeypatch.setattr("aos.agent.tool_registry.git_branch", lambda *args, **kwargs: GitBranchInfo("feature/x"))
    monkeypatch.setattr("aos.agent.tool_registry.git_log", lambda *args, **kwargs: [GitCommitSummary("abc1234", "feat: test")])
    assert ask("what branch am I on", cwd=agent_env).final_answer == "feature/x"
    assert "abc1234" in ask("show recent commits", cwd=agent_env).final_answer


def test_git_push_and_mixed_push_prompt_do_not_execute(agent_env, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("unsafe git action should not run")

    monkeypatch.setattr("aos.agent.tool_registry.git_status", _boom)
    monkeypatch.setattr("aos.agent.tool_registry.summarize_project_changes", _boom)
    monkeypatch.setattr("aos.agent.tool_registry.draft_commit_message", _boom)
    assert ask("git push", cwd=agent_env).intent.value == "UNKNOWN"
    assert ask("draft commit and push", cwd=agent_env).intent.value == "UNKNOWN"


def test_agent_git_tool_cannot_escape_approved_root(agent_env):
    call = ToolCall("git.status", {"cwd": str(agent_env.parent)}, "T0", False)
    with pytest.raises(PermissionBlocked):
        ToolRegistry().preview(call, cwd=agent_env)
