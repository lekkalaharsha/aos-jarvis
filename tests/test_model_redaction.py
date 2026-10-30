from aos.model.redaction import redact_text


def test_secret_patterns_are_redacted():
    original = "\n".join(
        [
            "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz",
            "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz",
            "AWS_ACCESS_KEY_ID=AKIAABCDEFGHIJKLMNOP",
            "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
            "jwt=eyJaaaaaaaaaaaa.bbbbbbbbbbbb.cccccccccccc",
            "postgres://user:pass@localhost/db",
            "Authorization: Bearer secret-token",
            "Cookie: session=secret",
            "PASSWORD=hunter2",
        ]
    )
    result = redact_text(original)
    assert result.redacted
    assert "ghp_" not in result.text
    assert "sk-" not in result.text
    assert "hunter2" not in result.text
    assert "user:pass" not in result.text
    assert result.total_count >= 8
    assert all("secret-token" not in category for category in result.counts_by_category)
