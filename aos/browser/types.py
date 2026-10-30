"""Phase 10 typed models (post-remediation).

Contract references are to docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md.
No T1 tier exists in Phase 10 (contract Sec3) -- every browser operation is
either T0 (local, no network effect) or T2 (network/disclosure effect).

Remediation (docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md Critical #2): callers
may no longer supply a raw CSS/XPath selector string or assert their own
``field_classification``. ``FieldLocator`` is a constrained, typed
accessibility-tree reference (ARIA role + accessible name); the engine
resolves it against the live page and the runtime-derived DOM attributes are
what classify a field, never a caller-supplied string.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from aos.safety.risk import RiskTier

# Constrained ARIA role vocabulary a FieldLocator may reference. This is not
# a CSS/XPath selector language -- it can only name a semantic role, not an
# arbitrary DOM query.
ALLOWED_LOCATOR_ROLES = frozenset({
    "textbox", "searchbox", "button", "checkbox", "radio", "combobox",
    "link", "menuitem",
})


class BrowserOperation(str, Enum):
    """Bounded operation vocabulary. No `login`, no arbitrary JS, no raw CDP."""

    NAVIGATE = "navigate"
    READ = "read"
    FILL = "fill"
    CLEAR = "clear"
    SUBMIT = "submit"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    CLOSE = "close"


# T0: no network/disclosure effect. Everything else in BrowserOperation is T2.
# Contract Sec3: there is no T1 tier in Phase 10.
T0_OPERATIONS = frozenset({BrowserOperation.READ, BrowserOperation.CLOSE})
T2_OPERATIONS = frozenset(BrowserOperation) - T0_OPERATIONS


def risk_tier_for_operation(operation: BrowserOperation) -> RiskTier:
    return RiskTier.T0 if operation in T0_OPERATIONS else RiskTier.T2


class FieldClassification(str, Enum):
    """Contract Sec7/Sec7a. PASSWORD..SECURITY_ANSWER are permanently denied.

    A value of this type is now produced ONLY by
    :func:`aos.browser.redaction.classify_field` from engine-resolved DOM
    attributes (type/autocomplete/accessible name) -- never accepted as
    caller input on an ``OperationEntry``.
    """

    NON_SENSITIVE_TEXT = "non_sensitive_text"
    PASSWORD = "password"
    CREDENTIAL = "credential"
    TOKEN = "token"
    ONE_TIME_CODE = "one_time_code"
    FINANCIAL = "financial"
    RECOVERY = "recovery"
    SECURITY_ANSWER = "security_answer"


DENIED_FIELD_CLASSIFICATIONS = frozenset(FieldClassification) - {FieldClassification.NON_SENSITIVE_TEXT}


class TaskState(str, Enum):
    """Contract Sec9b normative lifecycle state machine."""

    REQUESTED = "requested"
    VALIDATED = "validated"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    DENIED = "denied"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    CLEANUP = "cleanup"


TERMINAL_STATES = frozenset({
    TaskState.COMPLETED, TaskState.DENIED, TaskState.FAILED,
    TaskState.TIMED_OUT, TaskState.CANCELLED,
})


@dataclass(frozen=True)
class SafeBrowserTaskHandle:
    """Deliberately contains no PID, no Playwright object, no CDP endpoint."""

    task_id: str
    state: TaskState
    domain_id: str
    started_at: str
    action_count: int = 0


@dataclass(frozen=True)
class UntrustedBrowserObservation:
    """Contract Sec6. Never interpolated into an instruction channel; never
    convertible into a ToolCall; cannot select parameters for future
    operations; provenance is fixed and survives summarization."""

    source_domain_id: str
    source_url_digest: str
    content_type: Literal["visible_text", "structure_outline", "error_body"]
    bounded_text: str
    truncated: bool
    injection_suspected: bool
    provenance: Literal["browser"] = "browser"


# --- Contract Sec5a normative resource limits (defaults; Human Owner may
# adjust before/at activation, but Phase 10 must never launch with none). ---
@dataclass(frozen=True)
class ResourceLimits:
    task_timeout_seconds: int = 600
    idle_timeout_seconds: int = 120
    max_concurrent_tasks: int = 1
    max_tabs: int = 3
    max_navigation_depth: int = 10
    max_redirect_depth: int = 5
    max_buffered_responses: int = 100
    max_response_body_bytes: int = 25 * 1024 * 1024
    max_task_bandwidth_bytes: int = 100 * 1024 * 1024
    max_download_bytes: int = 50 * 1024 * 1024
    max_url_length: int = 2048
    max_host_length: int = 253
    max_path_length: int = 512
    max_field_identity_length: int = 256
    max_title_length: int = 512
    max_audit_field_length: int = 1024
    max_accessible_name_length: int = 200


DEFAULT_RESOURCE_LIMITS = ResourceLimits()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FieldLocator:
    """Constrained, typed accessibility-tree locator reference.

    Not a CSS/XPath selector and not arbitrary JavaScript -- the engine
    resolves ``(role, name)`` against the live accessibility tree
    (``page.get_by_role``). ``nth`` disambiguates multiple matches with the
    same role/name, defaulting to the first. This is the ONLY way an
    OperationEntry may reference a page element (contract remediation
    Critical #2).
    """

    role: str
    name: str
    nth: int = 0

    def __post_init__(self) -> None:
        if self.role not in ALLOWED_LOCATOR_ROLES:
            from aos.safety.errors import PermissionBlocked  # noqa: PLC0415
            raise PermissionBlocked(f"locator role is not permitted: {self.role!r}")
        if not self.name or not self.name.strip():
            from aos.safety.errors import PermissionBlocked  # noqa: PLC0415
            raise PermissionBlocked("locator accessible name must not be empty")
        if len(self.name) > DEFAULT_RESOURCE_LIMITS.max_accessible_name_length:
            from aos.safety.errors import PermissionBlocked  # noqa: PLC0415
            raise PermissionBlocked("locator accessible name exceeds length limit")
        if self.nth < 0:
            from aos.safety.errors import PermissionBlocked  # noqa: PLC0415
            raise PermissionBlocked("locator nth must be non-negative")

    def identity(self) -> str:
        """Stable, hashed binding identity for approval consumption -- never
        the raw accessible name is placed into an audit payload directly by
        callers of this method (callers hash it further if needed)."""
        return f"{self.role}:{self.name}:{self.nth}"


@dataclass(frozen=True)
class ResolvedField:
    """Engine-derived (not caller-derived) description of a resolved page
    element, used only to compute :class:`FieldClassification` at runtime."""

    role: str
    accessible_name: str
    input_type: str = ""
    autocomplete: str = ""
    exists: bool = True


@dataclass(frozen=True)
class OperationEntry:
    """One bounded operation inside a task-spec (contract Sec10).

    ``field_locator`` replaces the earlier raw ``element_locator`` string.
    ``field_classification`` no longer exists here -- it is derived from the
    live page at execution time via :func:`aos.browser.redaction.classify_field`
    and can never be asserted by a caller (contract remediation Critical #2).
    """

    operation: BrowserOperation
    url: str | None = None
    field_locator: FieldLocator | None = None
    field_value: str | None = None
    upload_source_path: str | None = None
    upload_project_id: str | None = None


@dataclass(frozen=True)
class BrowserTaskSpec:
    """Contract Sec10. A bounded, ahead-of-time-declared operation sequence.

    ``task_id`` must be generated by the caller (CLI/tool layer) BEFORE the
    task runs, via :func:`new_task_id`, so every approval minted during
    execution is bound to the exact task it is consumed within (contract
    Sec3a). There is no ``approvals`` field: per the remediated contract,
    approvals are minted and consumed one at a time, immediately before each
    T2 side effect, during ``BrowserTaskRunner.run`` -- never pre-minted in
    bulk by the caller (contract remediation Critical #3).
    """

    task_id: str
    domain_id: str
    operations: tuple[OperationEntry, ...]
    origin: Literal["terminal", "agent", "voice"] = "terminal"


def new_task_id() -> str:
    import uuid
    return uuid.uuid4().hex


@dataclass(frozen=True)
class ApprovalRequest:
    """What is shown to the Human Owner immediately before minting one
    per-operation approval. Contains only bounded, typed, human-meaningful
    fields -- never a raw URL query/fragment, never a field value."""

    operation: str
    task_id: str
    domain_id: str
    host: str = ""
    path_present: bool = False
    role: str = ""
    accessible_name: str = ""
    field_classification: str = ""
    file_identity_hash: str = ""
    redirect_from_host: str = ""
    redirect_to_host: str = ""
