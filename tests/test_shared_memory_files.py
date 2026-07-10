from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ROOT_FILES = [
    "README.md",
    "PROJECT_SCOPE.md",
    "ARCHITECTURE.md",
    "ROADMAP.md",
    "SECURITY.md",
    "DEVELOPMENT_WORKFLOW.md",
    "AGENTS.md",
    "PROJECT_STATE.md",
    "TASKS.md",
    "DECISIONS.md",
    "CHANGELOG.md",
    "HANDOFF.md",
    "BLOCKERS.md",
    "MODEL_PROVIDER.md",
    "TOOL_INTERFACE.md",
    "PERMISSION_MODEL.md",
    "AUDIT_LOG.md",
    "EVALS.md",
    "CODING_RULES.md",
    "TESTING_STRATEGY.md",
    "RELEASE_CHECKLIST.md",
    ".gitignore",
]

REQUIRED_AGENT_FILES = [
    "context.md",
    "current_goal.md",
    "phase_status.md",
    "coding_rules.md",
    "security_rules.md",
    "claude_notes.md",
    "codex_notes.md",
    "opencode_notes.md",
    "antigravity_notes.md",
    "templates/handoff_template.md",
    "templates/task_template.md",
    "templates/blocker_template.md",
    "templates/review_template.md",
]

REQUIRED_PHASE_FILES = [
    "PHASE_0_FOUNDATION_AUDIT.md",
    "PHASE_1_SAFE_FILE_TOOLS.md",
    "PHASE_2_SAFE_SHELL_RUNNER.md",
    "PHASE_3_MINIMAL_AGENT_LOOP.md",
    "PHASE_4_MEMORY_SYSTEM.md",
    "PHASE_5_GIT_PROJECT_ASSISTANT.md",
    "PHASE_6_MODEL_ROUTER.md",
    "PHASE_7_DASHBOARD.md",
    "PHASE_8_VOICE_INTERFACE.md",
    "PHASE_9_WORKSPACE_APP_CONTROL.md",
    "PHASE_10_BROWSER_TOOLS.md",
    "PHASE_11_SCREEN_UNDERSTANDING.md",
    "PHASE_12_ADVANCED_WORKFLOWS.md",
]

REQUIRED_ADR_FILES = [
    "0001-project-direction.md",
    "0002-audit-first-design.md",
    "0003-capability-security.md",
    "0004-cli-first-linux-first.md",
    "0005-models-are-not-executors.md",
    "0006-event-log-source-of-truth.md",
    "0007-no-custom-kernel-or-distro-v1.md",
]


def test_shared_memory_root_files_exist():
    for name in REQUIRED_ROOT_FILES:
        assert (ROOT / name).is_file(), f"missing {name}"


def test_shared_agent_files_exist():
    for name in REQUIRED_AGENT_FILES:
        assert (ROOT / ".agent" / name).is_file(), f"missing .agent/{name}"


def test_phase_docs_exist():
    for name in REQUIRED_PHASE_FILES:
        assert (ROOT / "docs" / "phases" / name).is_file(), f"missing docs/phases/{name}"


def test_adr_files_exist():
    for name in REQUIRED_ADR_FILES:
        assert (ROOT / "docs" / "adr" / name).is_file(), f"missing docs/adr/{name}"
