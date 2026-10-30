"""Field sensitivity classification and value redaction.

Extends aos/model/redaction.py (Phase 6) with browser-specific field/label
heuristics (contract Sec7/Sec7a). Sensitive fields are denied at
classification time, before any approval prompt is offered -- no approval
path can override this classification.
"""
from __future__ import annotations

import re

from aos.browser.types import DENIED_FIELD_CLASSIFICATIONS, FieldClassification
from aos.model.redaction import redact_text

_PASSWORD_MARKERS = ("password", "passwd", "pwd")
_CREDENTIAL_MARKERS = ("credential", "username", "user_id", "login")
_TOKEN_MARKERS = ("token", "api_key", "apikey", "access_key", "secret")
_OTP_MARKERS = ("otp", "one_time_code", "one-time-code", "2fa", "mfa", "verification_code")
_FINANCIAL_MARKERS = ("card_number", "cardnumber", "cvv", "cvc", "routing_number", "account_number", "iban", "swift")
_RECOVERY_MARKERS = ("recovery_code", "recovery_email", "recovery_phone", "backup_code")
_SECURITY_ANSWER_MARKERS = ("security_answer", "security_question", "mothers_maiden_name")


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-]+", "_", text.strip().lower())


def classify_field(*, field_type: str = "", label: str = "", autocomplete: str = "") -> FieldClassification:
    """Classify a resolved accessibility-tree field node. Never trusts a
    caller-supplied label string alone as authoritative -- combines
    field_type/autocomplete (from the resolved DOM node) with label text.
    Matching is done on a normalized (space/hyphen -> underscore) haystack
    so "Recovery code" and "recovery_code" classify identically."""
    haystack = "_".join(_normalize(part) for part in (field_type, label, autocomplete) if part)
    if field_type.lower() == "password" or any(m in haystack for m in _PASSWORD_MARKERS):
        return FieldClassification.PASSWORD
    if autocomplete.lower().startswith("cc-") or any(m in haystack for m in _FINANCIAL_MARKERS):
        return FieldClassification.FINANCIAL
    if any(m in haystack for m in _OTP_MARKERS):
        return FieldClassification.ONE_TIME_CODE
    if any(m in haystack for m in _RECOVERY_MARKERS):
        return FieldClassification.RECOVERY
    if any(m in haystack for m in _SECURITY_ANSWER_MARKERS):
        return FieldClassification.SECURITY_ANSWER
    if any(m in haystack for m in _TOKEN_MARKERS):
        return FieldClassification.TOKEN
    if any(m in haystack for m in _CREDENTIAL_MARKERS):
        return FieldClassification.CREDENTIAL
    return FieldClassification.NON_SENSITIVE_TEXT


def is_denied_classification(classification: FieldClassification) -> bool:
    return classification in DENIED_FIELD_CLASSIFICATIONS


_CREDENTIAL_SHAPED = re.compile(r"(?i)\b[A-Za-z0-9_-]{20,}\b")


def redact_value(value: str) -> str:
    """Defense in depth for AUDIT/MEMORY/MODEL-PROMPT COPIES ONLY.

    Contract remediation Important #7: this function must never be applied
    to the actual value sent to ``page.fill`` -- doing so silently rewrites
    a Human-Owner-approved, allowed non-sensitive value before it reaches
    the browser, which is not the approved behavior. Callers must pass the
    real ``field_value`` to the engine and reserve ``redact_value`` strictly
    for building an audit/observation/model-prompt copy (contract Sec9's
    test requirement TP-CRED-05 tests the copy, not the live value)."""
    result = redact_text(value)
    return result.text


def redact_observation_text(text: str) -> str:
    return redact_text(text).text
