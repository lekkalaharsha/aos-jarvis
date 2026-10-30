from __future__ import annotations

from aos.browser.redaction import classify_field, is_denied_classification, redact_value
from aos.browser.types import FieldClassification


def test_password_field_classified_and_denied():
    c = classify_field(field_type="password")
    assert c is FieldClassification.PASSWORD
    assert is_denied_classification(c)


def test_credential_label_classified_and_denied():
    c = classify_field(label="Username")
    assert c is FieldClassification.CREDENTIAL
    assert is_denied_classification(c)


def test_token_field_classified_and_denied():
    c = classify_field(label="API Key")
    assert is_denied_classification(c)


def test_financial_autocomplete_classified_and_denied():
    c = classify_field(autocomplete="cc-number")
    assert c is FieldClassification.FINANCIAL
    assert is_denied_classification(c)


def test_recovery_field_classified_and_denied():
    c = classify_field(label="Recovery code")
    assert c is FieldClassification.RECOVERY
    assert is_denied_classification(c)


def test_security_answer_classified_and_denied():
    c = classify_field(label="Security Answer")
    assert c is FieldClassification.SECURITY_ANSWER
    assert is_denied_classification(c)


def test_ordinary_search_field_is_non_sensitive():
    c = classify_field(field_type="text", label="Search")
    assert c is FieldClassification.NON_SENSITIVE_TEXT
    assert not is_denied_classification(c)


def test_redact_value_scrubs_secret_shaped_text():
    redacted = redact_value("my token=sk-abcdefghijklmnopqrstuvwxyz")
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in redacted
