from aos.agent.intent import classify_intent
from aos.agent.types import Intent


def test_project_summary_intent():
    assert classify_intent("summarize this project") == Intent.PROJECT_SUMMARY


def test_find_todos_intent():
    assert classify_intent("find TODOs in this repo") == Intent.FIND_TODOS


def test_run_tests_intent():
    assert classify_intent("run tests") == Intent.RUN_TESTS


def test_git_status_intent():
    assert classify_intent("show git status") == Intent.GIT_STATUS


def test_project_changes_intent():
    assert classify_intent("what changed in this repo") == Intent.PROJECT_CHANGES


def test_draft_commit_intent():
    assert classify_intent("draft a commit message") == Intent.DRAFT_COMMIT


def test_current_branch_intent():
    assert classify_intent("what branch am I on") == Intent.CURRENT_BRANCH


def test_recent_commits_intent():
    assert classify_intent("show recent commits") == Intent.RECENT_COMMITS


def test_read_file_intent():
    assert classify_intent("read README.md") == Intent.READ_FILE


def test_create_notes_intent():
    assert classify_intent("create notes.md") == Intent.CREATE_NOTES


def test_recall_memory_intent():
    assert classify_intent("what did I work on recently") == Intent.RECALL_MEMORY


def test_unknown_intent():
    assert classify_intent("deploy this project to production") == Intent.UNKNOWN


def test_git_push_prompt_is_unknown():
    assert classify_intent("run git push") == Intent.UNKNOWN


def test_workspace_path_request_is_not_a_workspace_intent():
    assert classify_intent("open workspace /tmp/project") == Intent.WORKSPACE_OPEN
