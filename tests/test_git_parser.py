from aos.project.git_parser import parse_branch, parse_diff_stat, parse_log_oneline, parse_status


def test_parse_clean_status():
    status = parse_status("", "main")
    assert status.clean
    assert status.branch == "main"


def test_parse_dirty_status_and_untracked_files():
    output = "M  README.md\n?? notes.txt\n M aos/app.py\n"
    status = parse_status(output, "feature/test")
    assert not status.clean
    assert status.staged_count == 1
    assert status.untracked_count == 1
    assert status.unstaged_count == 1
    assert status.changed_files[1].untracked


def test_parse_diff_stat():
    output = " README.md | 2 +-\n aos/app.py | 5 +++--\n 2 files changed, 4 insertions(+), 3 deletions(-)\n"
    summary = parse_diff_stat(output)
    assert summary.files_changed == 2
    assert summary.insertions == 4
    assert summary.deletions == 3
    assert "README.md" in summary.changed_files


def test_parse_log_oneline():
    commits = parse_log_oneline("abc1234 feat: add git tools\ndef5678 fix: tests\n")
    assert commits[0].commit_hash == "abc1234"
    assert commits[1].title == "fix: tests"


def test_parser_handles_unexpected_output():
    assert parse_branch("").name == "(unknown)"
    assert parse_log_oneline("not git output") == []
    assert parse_diff_stat("nonsense").files_changed == 0

