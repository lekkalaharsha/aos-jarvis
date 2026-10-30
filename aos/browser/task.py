"""Bounded browser task orchestration (contract Sec2a), post-remediation.

One BrowserTaskRunner.run() call is the entire lifecycle: validate -> verify
preconditions (supply chain, sandbox, egress) -> launch one isolated
process+profile -> execute the bounded operation sequence, minting and
consuming ONE fresh approval immediately before each individual T2 side
effect (not in bulk beforehand) -> audit -> guaranteed teardown. Nothing
survives past one run() call. There is no cross-call state, no daemon, no
PID exposure.

Remediation (docs/PHASE_10_CODEX_FINAL_GATE_REPORT.md):
- Critical #2: field classification is derived from the ENGINE-RESOLVED page
  element (role/type/autocomplete), never from caller input, and a denied
  classification is enforced BEFORE any approval is offered.
- Critical #3: approvals are minted and consumed one at a time, immediately
  before each T2 side effect (navigation, each fill/clear, submit, download,
  upload, and each cross-domain redirect hop), via a synchronous
  ``approval_callback`` supplied only by a terminal-origin caller. There is
  no bulk pre-approval path and no ``--yes`` bypass inside this module.
- Important #6: cross-domain redirects require their own fresh, exact-bound
  approval per hop (not a blanket deny), authorized before the request is
  allowed to proceed (not after the response arrives).
- Important #3 / #7: the audit lifecycle now emits per-action
  requested/approval_required/approved/denied markers, cancellation is never
  recorded as a successful terminal event, and cleanup failure is a visible
  field on the returned result, not silently swallowed.
"""
from __future__ import annotations

import hashlib
import os
import stat as stat_module
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from aos.browser.approval import mint_browser_approval, consume_browser_approval
from aos.browser.domains import ApprovedDomain, ApprovedDomainRegistry
from aos.browser.egress import EgressVerificationResult, verify_egress_containment
from aos.browser.engine import BrowserEngineFactory, build_launch_args
from aos.browser.quarantine import QuarantineStore
from aos.browser.redaction import classify_field, is_denied_classification, redact_observation_text
from aos.browser.sandbox import SandboxVerificationResult, verify_sandbox
from aos.browser.supply_chain import SupplyChainVerificationResult, verify_supply_chain
from aos.browser.types import (
    DEFAULT_RESOURCE_LIMITS,
    ApprovalRequest,
    BrowserOperation,
    BrowserTaskSpec,
    FieldLocator,
    OperationEntry,
    ResourceLimits,
    TaskState,
    UntrustedBrowserObservation,
    risk_tier_for_operation,
)
from aos.browser.url_policy import validate_url
from aos.config.loader import DATA_DIR
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event
from aos.safety.approved_projects import ApprovedProjectRegistry
from aos.safety.errors import PermissionBlocked
from aos.safety.permissions import PermissionEngine
from aos.safety.risk import RiskTier

DEFAULT_PROFILE_ROOT = DATA_DIR / "browser" / "profiles"

ApprovalCallback = Callable[[ApprovalRequest], bool]


def _safe_error(exc: Exception) -> str:
    return "browser request denied" if isinstance(exc, PermissionBlocked) else "browser task failed"


def _url_digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _allowed_egress_targets(domain: ApprovedDomain) -> frozenset[tuple[str, int]]:
    """The exact (host, port) allowlist the AOS-controlled validating proxy
    for this task will enforce -- derived only from the one enrolled domain
    this task is bound to, never a process-wide or caller-declared set."""
    targets = {(domain.host, 443)}
    if domain.allow_http:
        targets.add((domain.host, 80))
    for port in domain.extra_ports:
        targets.add((domain.host, port))
    return frozenset(targets)


class TaskTimedOut(Exception):
    pass


class TaskCancelled(Exception):
    pass


@dataclass(frozen=True)
class OperationResult:
    operation: str
    ok: bool
    observation: UntrustedBrowserObservation | None = None
    detail: str = ""


@dataclass(frozen=True)
class BrowserTaskResult:
    task_id: str
    state: TaskState
    domain_id: str
    results: tuple[OperationResult, ...] = ()
    error: str | None = None
    cleanup_ok: bool = True


class _Deadline:
    def __init__(self, task_seconds: int, idle_seconds: int) -> None:
        self.deadline = time.monotonic() + task_seconds
        self.idle_seconds = idle_seconds
        self.last_activity = time.monotonic()

    def check(self) -> None:
        now = time.monotonic()
        if now > self.deadline:
            raise TaskTimedOut("task exceeded task_timeout_seconds")
        if now - self.last_activity > self.idle_seconds:
            raise TaskTimedOut("task exceeded idle_timeout_seconds")

    def mark_activity(self) -> None:
        self.last_activity = time.monotonic()


class BrowserTaskRunner:
    def __init__(
        self,
        *,
        registry: ApprovedDomainRegistry | None = None,
        engine_factory: BrowserEngineFactory,
        audit_path: Path | None = None,
        approvals_consumed_path: Path | None = None,
        quarantine: QuarantineStore | None = None,
        resource_limits: ResourceLimits = DEFAULT_RESOURCE_LIMITS,
        profile_root: Path | None = None,
        egress_checker=None,
        sandbox_checker=None,
        supply_chain_checker=None,
        url_resolver=None,
        approved_upload_roots: list[Path] | None = None,
        upload_project_registry: ApprovedProjectRegistry | None = None,
    ) -> None:
        self.registry = registry or ApprovedDomainRegistry()
        self.engine_factory = engine_factory
        self.audit_path = audit_path or DEFAULT_AUDIT_PATH
        self.approvals_consumed_path = approvals_consumed_path
        self.quarantine = quarantine or QuarantineStore()
        self.limits = resource_limits
        self.profile_root = profile_root or DEFAULT_PROFILE_ROOT
        self._egress_checker = egress_checker
        self._sandbox_checker = sandbox_checker
        self._supply_chain_checker = supply_chain_checker
        self._url_resolver = url_resolver
        # Contract Sec8a: upload source path must resolve inside an approved
        # project directory via the existing PermissionEngine -- an empty
        # list means no upload is ever permitted (fail closed, not fail open).
        self._approved_upload_roots = approved_upload_roots or []
        self._upload_project_registry = upload_project_registry or ApprovedProjectRegistry()

    def _audit(
        self,
        event_type: str,
        *,
        task_id: str,
        domain_id: str,
        operation: str,
        ok: bool,
        risk_tier: str,
        origin: str = "terminal",
        detail: str = "",
        status: str | None = None,
        path_present: bool | None = None,
        scheme: str | None = None,
        port_classification: str | None = None,
    ) -> None:
        # Contract Sec9a: opaque IDs/typed fields/booleans only. Never a raw
        # path, query, fragment, title, header, cookie, form value, accessible
        # name, or PID.
        payload: dict[str, Any] = {
            "task_id": task_id,
            "domain_id": domain_id,
            "operation": operation,
            "origin": origin,
            "detail": detail[: self.limits.max_audit_field_length],
        }
        if path_present is not None:
            payload["path_present"] = path_present
        if scheme is not None:
            payload["scheme"] = scheme
        if port_classification is not None:
            payload["port_classification"] = port_classification
        append_event(
            self.audit_path, actor="browser", event_type=event_type,
            action=operation, resource=domain_id or "browser",
            risk_tier=risk_tier, status=status or ("ALLOW" if ok else "DENY"), payload=payload,
        )

    def dry_run(self, spec: BrowserTaskSpec) -> BrowserTaskResult:
        """Contract Sec11: never creates a real process, real navigation, or
        any external effect; never consumes an approval; never persists
        state."""
        task_id = spec.task_id
        try:
            domain = self.registry.resolve(spec.domain_id)
        except PermissionBlocked as exc:
            self._audit("browser.task.denied", task_id=task_id, domain_id=spec.domain_id, operation="dry_run", ok=False, risk_tier="T0", origin=spec.origin, detail=_safe_error(exc))
            return BrowserTaskResult(task_id=task_id, state=TaskState.DENIED, domain_id=spec.domain_id, error=_safe_error(exc))
        self._audit("browser.task.requested", task_id=task_id, domain_id=domain.domain_id, operation="dry_run", ok=True, risk_tier="T0", origin=spec.origin, detail="dry_run_validated")
        return BrowserTaskResult(task_id=task_id, state=TaskState.VALIDATED, domain_id=domain.domain_id)

    def run(self, spec: BrowserTaskSpec, *, approval_callback: ApprovalCallback | None = None) -> BrowserTaskResult:
        task_id = spec.task_id
        self._audit("browser.task.requested", task_id=task_id, domain_id=spec.domain_id, operation="task", ok=True, risk_tier="T0", origin=spec.origin, detail="requested")

        # --- VALIDATED ---
        try:
            domain = self.registry.resolve(spec.domain_id)
            if spec.origin == "voice":
                raise PermissionBlocked("voice origin can never carry a browser task")
            if len(spec.operations) > self.limits.max_navigation_depth:
                raise PermissionBlocked("task exceeds max navigation depth")
            has_t2 = any(risk_tier_for_operation(entry.operation) is RiskTier.T2 for entry in spec.operations)
            if has_t2 and (approval_callback is None or spec.origin != "terminal"):
                raise PermissionBlocked("a terminal-origin approval callback is required for any T2 operation")
        except PermissionBlocked as exc:
            self._audit("browser.task.denied", task_id=task_id, domain_id=spec.domain_id, operation="task", ok=False, risk_tier="T0", origin=spec.origin, detail=_safe_error(exc))
            return BrowserTaskResult(task_id=task_id, state=TaskState.DENIED, domain_id=spec.domain_id, error=_safe_error(exc))
        self._audit("browser.url.validated", task_id=task_id, domain_id=domain.domain_id, operation="task", ok=True, risk_tier="T0", origin=spec.origin, detail="domain_resolved")

        # --- STARTING: mandatory fail-closed preconditions (contract Sec4a/Sec5b/Sec5c) ---
        precondition_error, egress, proxy = self._check_preconditions(domain)
        if precondition_error is not None:
            self._audit("browser.task.denied", task_id=task_id, domain_id=domain.domain_id, operation="task", ok=False, risk_tier="T2", origin=spec.origin, detail=precondition_error)
            return BrowserTaskResult(task_id=task_id, state=TaskState.DENIED, domain_id=domain.domain_id, error=precondition_error)

        self.quarantine.sweep_expired()  # bounded-retention sweep at task startup only (no daemon)

        # --- one fresh process, one fresh temporary profile per task ---
        self.profile_root.mkdir(parents=True, exist_ok=True)
        deadline = _Deadline(self.limits.task_timeout_seconds, self.limits.idle_timeout_seconds)
        try:
            with tempfile.TemporaryDirectory(dir=self.profile_root, prefix=f"task-{task_id}-") as profile_dir:
                handle = None
                try:
                    self._audit("browser.session.created", task_id=task_id, domain_id=domain.domain_id, operation="task", ok=True, risk_tier="T2", origin=spec.origin, detail="launching")
                    handle = self.engine_factory.launch(profile_dir=Path(profile_dir), launch_args=build_launch_args(proxy_url=egress.proxy_url), limits=self.limits)
                except Exception:  # noqa: BLE001
                    self._audit("browser.session.failed", task_id=task_id, domain_id=domain.domain_id, operation="task", ok=False, risk_tier="T2", origin=spec.origin, detail="launch_failed")
                    self._audit_task_terminal(task_id, domain.domain_id, spec.origin, TaskState.FAILED, "launch_failed")
                    return BrowserTaskResult(task_id=task_id, state=TaskState.FAILED, domain_id=domain.domain_id, error="browser launch failed")

                results: tuple[OperationResult, ...] = ()
                final_state = TaskState.FAILED
                final_error: str | None = None
                final_detail = "failed"
                try:
                    if not handle.verify_post_launch_sandbox():
                        final_state = TaskState.FAILED
                        final_error = "post_launch_sandbox_unverified"
                        final_detail = "post_launch_sandbox_unverified"
                    else:
                        run_results = self._run_operations(task_id, domain, spec, handle, approval_callback, deadline)
                        results = tuple(run_results)
                        final_state = TaskState.COMPLETED if all(r.ok for r in run_results) else TaskState.FAILED
                        final_detail = final_state.value
                except TaskTimedOut:
                    final_state = TaskState.TIMED_OUT
                    final_error = "task_timeout_exceeded"
                    final_detail = "timed_out"
                except (KeyboardInterrupt, TaskCancelled):
                    # Remediation Important #3: cancellation is NEVER recorded
                    # as a successful terminal event.
                    final_state = TaskState.CANCELLED
                    final_error = "cancelled"
                    final_detail = "cancelled"
                except Exception:  # noqa: BLE001
                    final_state = TaskState.FAILED
                    final_error = "browser task failed"
                    final_detail = "exception"
                finally:
                    # --- CLEANUP: guaranteed, bounded, distinct from the
                    # terminal event; a failure here is a VISIBLE field on
                    # the returned result and affects the single terminal
                    # task event.
                    cleanup_ok = True
                    if handle is not None:
                        try:
                            handle.close()
                            self._audit("browser.session.cleanup_completed", task_id=task_id, domain_id=domain.domain_id, operation="task", ok=True, risk_tier="T0", origin=spec.origin, detail="cleanup_ok")
                        except Exception:  # noqa: BLE001
                            cleanup_ok = False
                            self._audit("browser.session.cleanup_failed", task_id=task_id, domain_id=domain.domain_id, operation="task", ok=False, risk_tier="T0", origin=spec.origin, detail="cleanup_failed")
                if not cleanup_ok:
                    final_state = TaskState.FAILED
                    final_error = "cleanup_failed"
                    final_detail = "cleanup_failed"
                self._audit_task_terminal(task_id, domain.domain_id, spec.origin, final_state, final_detail)
                return BrowserTaskResult(task_id=task_id, state=final_state, domain_id=domain.domain_id, results=results, error=final_error, cleanup_ok=cleanup_ok)
        finally:
            # The AOS-controlled validating proxy is scoped to this one task
            # -- it is always stopped here, whether the task completed,
            # denied, failed, timed out, or was cancelled.
            if proxy is not None:
                try:
                    proxy.stop()
                except Exception:  # noqa: BLE001
                    pass

    def _audit_task_terminal(self, task_id: str, domain_id: str, origin: str, state: TaskState, detail: str) -> None:
        event_type = {
            TaskState.COMPLETED: "browser.task.completed",
            TaskState.DENIED: "browser.task.denied",
            TaskState.FAILED: "browser.task.failed",
            TaskState.TIMED_OUT: "browser.task.timed_out",
            TaskState.CANCELLED: "browser.task.cancelled",
        }.get(state, "browser.task.failed")
        status = {
            TaskState.TIMED_OUT: "TIMEOUT",
            TaskState.CANCELLED: "CANCELLED",
        }.get(state)
        self._audit(
            event_type, task_id=task_id, domain_id=domain_id, operation="task",
            ok=state is TaskState.COMPLETED, risk_tier="T2", origin=origin,
            detail=detail, status=status,
        )

    def _check_preconditions(self, domain: ApprovedDomain) -> tuple[str | None, EgressVerificationResult, object]:
        supply_chain: SupplyChainVerificationResult = verify_supply_chain() if self._supply_chain_checker is None else self._supply_chain_checker()
        if not supply_chain.verified:
            return "supply_chain_unverified", EgressVerificationResult(False, "not checked"), None
        sandbox: SandboxVerificationResult = verify_sandbox(self._sandbox_checker)
        if not sandbox.verified:
            return "sandbox_unverified", EgressVerificationResult(False, "not checked"), None
        allowed_targets = frozenset(_allowed_egress_targets(domain))
        egress, proxy = verify_egress_containment(allowed_targets, self._egress_checker)
        if not egress.verified:
            return "egress_containment_unverified", egress, None
        return None, egress, proxy

    # --- per-operation immediate approval -----------------------------------

    def _request_and_consume(
        self, *, task_id: str, domain_id: str, request: ApprovalRequest,
        approval_callback: ApprovalCallback | None, origin: str,
        url_digest: str = "", locator_identity: str = "",
        field_classification: str = "", file_identity: str = "",
    ) -> None:
        """Mints and durably consumes exactly one fresh approval, immediately
        before the caller performs the corresponding side effect. Raises
        PermissionBlocked on any denial. Never called in bulk ahead of time.

        Remediation (fresh Codex gate Important I-2): this method does NOT
        itself emit a terminal ``browser.action.denied`` event on denial --
        it only raises. Every caller of this method either (a) lets the
        exception propagate up to ``_run_one``'s single except-handler,
        which is the ONE place that audits ``browser.action.denied`` for a
        raised T2-approval failure, or (b) is the redirect validator inside
        ``_build_navigation_validator``, which swallows the exception and
        returns ``False`` -- that failure surfaces once, through the
        eventual ``browser.navigation.failed`` event, not a second explicit
        denial event here. A prior version audited here AND let the
        exception propagate to a second audit call, producing two
        terminal-shaped events for one denied action; this method never
        emits an audit event that duplicates a caller's.
        """
        self._audit("browser.action.approval_required", task_id=task_id, domain_id=domain_id, operation=request.operation, ok=True, risk_tier="T2", origin=origin, detail="approval_required")
        if approval_callback is None or origin != "terminal":
            raise PermissionBlocked("fresh terminal Human Owner approval is required")
        approved = approval_callback(request)
        if not approved:
            raise PermissionBlocked(f"Human Owner did not approve operation: {request.operation}")
        approval = mint_browser_approval(
            operation=request.operation, task_id=task_id, domain_id=domain_id,
            url_digest=url_digest, locator_identity=locator_identity,
            field_classification=field_classification, file_identity=file_identity,
            human_owner_confirmed=True, origin="terminal",
        )
        consume_browser_approval(
            approval, operation=request.operation, task_id=task_id, domain_id=domain_id,
            url_digest=url_digest, locator_identity=locator_identity,
            field_classification=field_classification, file_identity=file_identity,
            consumed_path=self.approvals_consumed_path,
        )
        self._audit("browser.action.approved", task_id=task_id, domain_id=domain_id, operation=request.operation, ok=True, risk_tier="T2", origin=origin, detail="approved")

    def _build_navigation_validator(
        self, task_id: str, domain: ApprovedDomain, origin: str, approval_callback: ApprovalCallback | None,
    ) -> Callable[[str], bool]:
        hop_count = {"n": 0}

        def validator(url: str) -> bool:
            try:
                validate_url(url, domain_host=domain.host, allow_http=domain.allow_http, allow_ip_literal=domain.allow_ip_literal, extra_ports=domain.extra_ports, resolver=self._url_resolver)
                return True  # same enrolled domain -- already covered by the operation-level approval
            except PermissionBlocked:
                pass
            hop_count["n"] += 1
            if hop_count["n"] > self.limits.max_redirect_depth:
                self._audit("browser.navigation.redirect_denied", task_id=task_id, domain_id=domain.domain_id, operation="redirect", ok=False, risk_tier="T2", origin=origin, detail="redirect_depth_exceeded")
                return False
            hostname = urlsplit(url).hostname or ""
            try:
                target_domain = self.registry.resolve_by_host(hostname)
                validate_url(url, domain_host=target_domain.host, allow_http=target_domain.allow_http, allow_ip_literal=target_domain.allow_ip_literal, extra_ports=target_domain.extra_ports, resolver=self._url_resolver)
            except PermissionBlocked:
                self._audit("browser.navigation.redirect_denied", task_id=task_id, domain_id=domain.domain_id, operation="redirect", ok=False, risk_tier="T2", origin=origin, detail="target_not_enrolled_or_invalid")
                return False
            # Contract Sec4b: a fresh, exact-bound approval is required for
            # EVERY cross-domain hop, even to an already-enrolled domain.
            request = ApprovalRequest(
                operation="redirect", task_id=task_id, domain_id=domain.domain_id,
                host=target_domain.host, redirect_from_host=domain.host, redirect_to_host=target_domain.host,
            )
            try:
                self._request_and_consume(
                    task_id=task_id, domain_id=domain.domain_id, request=request,
                    approval_callback=approval_callback, origin=origin,
                    url_digest=_url_digest(f"{domain.host}->{target_domain.host}"),
                )
            except PermissionBlocked:
                return False
            return True

        return validator

    def _run_operations(self, task_id: str, domain: ApprovedDomain, spec: BrowserTaskSpec, handle, approval_callback, deadline: _Deadline) -> list[OperationResult]:  # noqa: ANN001
        results: list[OperationResult] = []
        for entry in spec.operations:
            deadline.check()
            result = self._run_one(task_id, domain, entry, handle, approval_callback, spec.origin)
            deadline.mark_activity()
            results.append(result)
            if not result.ok:
                break
        return results

    def _run_one(self, task_id: str, domain: ApprovedDomain, entry: OperationEntry, handle, approval_callback, origin: str) -> OperationResult:  # noqa: ANN001
        op = entry.operation
        risk = risk_tier_for_operation(op)
        self._audit("browser.action.requested", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=True, risk_tier=risk.value, origin=origin, detail="requested")
        try:
            if op == BrowserOperation.NAVIGATE:
                return self._do_navigate(task_id, domain, entry, handle, approval_callback, origin)
            if op == BrowserOperation.READ:
                return self._do_read(task_id, domain, handle)
            if op in (BrowserOperation.FILL, BrowserOperation.CLEAR):
                return self._do_fill_or_clear(task_id, domain, entry, handle, approval_callback, origin)
            if op == BrowserOperation.SUBMIT:
                return self._do_submit(task_id, domain, entry, handle, approval_callback, origin)
            if op == BrowserOperation.DOWNLOAD:
                return self._do_download(task_id, domain, entry, handle, approval_callback, origin)
            if op == BrowserOperation.UPLOAD:
                return self._do_upload(task_id, domain, entry, handle, approval_callback, origin)
            if op == BrowserOperation.CLOSE:
                return OperationResult(op.value, True, detail="close_requested")
            raise PermissionBlocked("unknown browser operation")
        except PermissionBlocked as exc:
            self._audit("browser.action.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier=risk.value, origin=origin, detail=_safe_error(exc))
            return OperationResult(op.value, False, detail=_safe_error(exc))

    def _do_navigate(self, task_id, domain, entry, handle, approval_callback, origin):  # noqa: ANN001
        op = BrowserOperation.NAVIGATE
        validated = validate_url(entry.url or "", domain_host=domain.host, allow_http=domain.allow_http, allow_ip_literal=domain.allow_ip_literal, extra_ports=domain.extra_ports, resolver=self._url_resolver)
        request = ApprovalRequest(operation=op.value, task_id=task_id, domain_id=domain.domain_id, host=domain.host, path_present=validated.path != "/")
        self._request_and_consume(task_id=task_id, domain_id=domain.domain_id, request=request, approval_callback=approval_callback, origin=origin, url_digest=_url_digest(entry.url or ""))
        validator = self._build_navigation_validator(task_id, domain, origin, approval_callback)
        outcome = handle.navigate(entry.url or "", request_validator=validator)
        if not outcome.ok:
            self._audit("browser.navigation.failed", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T2", origin=origin, detail=outcome.error or "navigation_failed", path_present=bool(validated.path != "/"), scheme=validated.scheme)
            return OperationResult(op.value, False, detail=outcome.error or "navigation_failed")
        self._audit("browser.navigation.completed", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=True, risk_tier="T2", origin=origin, detail="navigated", path_present=bool(validated.path != "/"), scheme=validated.scheme, port_classification="default" if validated.port in (443, 80) else "enrolled_nondefault")
        return OperationResult(op.value, True, detail="navigated")

    def _do_read(self, task_id, domain, handle):  # noqa: ANN001
        op = BrowserOperation.READ
        read = handle.read_visible_text()
        if not read.ok:
            self._audit("browser.read.completed", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T0", detail=read.error or "read_failed")
            return OperationResult(op.value, False, detail=read.error or "read_failed")
        observation = UntrustedBrowserObservation(
            source_domain_id=domain.domain_id, source_url_digest="",
            content_type="visible_text", bounded_text=redact_observation_text(read.text),
            truncated=read.truncated, injection_suspected=_looks_like_injection(read.text),
        )
        self._audit("browser.read.completed", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=True, risk_tier="T0", detail="read_ok")
        if observation.injection_suspected:
            self._audit("browser.injection_suspected", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=True, risk_tier="T0", detail="pattern_matched")
        return OperationResult(op.value, True, observation=observation, detail="read_ok")

    def _resolve_and_classify(self, entry: OperationEntry, handle):  # noqa: ANN001
        locator: FieldLocator = entry.field_locator
        if locator is None:
            raise PermissionBlocked("a field_locator is required for this operation")
        resolved = handle.resolve_field(locator)
        if not resolved.exists:
            raise PermissionBlocked("field locator did not resolve to any live page element")
        classification = classify_field(field_type=resolved.input_type, label=resolved.accessible_name, autocomplete=resolved.autocomplete)
        return locator, classification

    def _do_fill_or_clear(self, task_id, domain, entry, handle, approval_callback, origin):  # noqa: ANN001
        op = entry.operation
        locator, classification = self._resolve_and_classify(entry, handle)
        # Remediation Critical #2: denial happens BEFORE any approval is
        # offered -- the classification is engine-derived, never caller-
        # asserted, and cannot be overridden by any approval.
        if is_denied_classification(classification):
            self._audit("browser.form.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T2", origin=origin, detail="denied_field_classification")
            return OperationResult(op.value, False, detail="denied_field_classification")
        request = ApprovalRequest(operation=op.value, task_id=task_id, domain_id=domain.domain_id, role=locator.role, accessible_name=locator.name, field_classification=classification.value)
        self._request_and_consume(
            task_id=task_id, domain_id=domain.domain_id, request=request, approval_callback=approval_callback, origin=origin,
            locator_identity=locator.identity(), field_classification=classification.value,
        )
        if op == BrowserOperation.FILL:
            ok = handle.fill(locator, entry.field_value or "")
        else:
            ok = handle.clear(locator)
        self._audit("browser.form.draft_filled" if op == BrowserOperation.FILL else "browser.form.field_cleared", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=ok, risk_tier="T2", origin=origin, detail="ok" if ok else "engine_denied")
        return OperationResult(op.value, ok, detail="ok" if ok else "engine_denied")

    def _do_submit(self, task_id, domain, entry, handle, approval_callback, origin):  # noqa: ANN001
        op = BrowserOperation.SUBMIT
        locator = entry.field_locator
        if locator is None:
            raise PermissionBlocked("a field_locator is required for submit")
        request = ApprovalRequest(operation=op.value, task_id=task_id, domain_id=domain.domain_id, role=locator.role, accessible_name=locator.name)
        self._request_and_consume(task_id=task_id, domain_id=domain.domain_id, request=request, approval_callback=approval_callback, origin=origin, locator_identity=locator.identity())
        ok = handle.submit(locator)
        self._audit("browser.form.submitted", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=ok, risk_tier="T2", origin=origin, detail="ok" if ok else "engine_denied")
        return OperationResult(op.value, ok, detail="ok" if ok else "engine_denied")

    def _do_download(self, task_id, domain, entry, handle, approval_callback, origin):  # noqa: ANN001
        op = BrowserOperation.DOWNLOAD
        locator = entry.field_locator
        if locator is None:
            raise PermissionBlocked("a field_locator is required for download")
        request = ApprovalRequest(operation=op.value, task_id=task_id, domain_id=domain.domain_id, role=locator.role, accessible_name=locator.name)
        self._request_and_consume(task_id=task_id, domain_id=domain.domain_id, request=request, approval_callback=approval_callback, origin=origin, locator_identity=locator.identity())
        validator = self._build_navigation_validator(task_id, domain, origin, approval_callback)
        with tempfile.TemporaryDirectory() as tmp:
            outcome = handle.download(locator, Path(tmp), request_validator=validator)
            if not outcome.ok:
                self._audit("browser.download.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T2", origin=origin, detail=outcome.error or "download_failed")
                return OperationResult(op.value, False, detail=outcome.error or "download_failed")
            try:
                data = Path(outcome.local_path).read_bytes()
                staged = self.quarantine.stage(filename=Path(outcome.local_path).name, content_type=outcome.declared_content_type, data=data)
            except PermissionBlocked as exc:
                self._audit("browser.download.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T2", origin=origin, detail=_safe_error(exc))
                return OperationResult(op.value, False, detail=_safe_error(exc))
        self._audit("browser.download.completed", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=True, risk_tier="T2", origin=origin, detail=f"file_id={staged.file_id}")
        return OperationResult(op.value, True, detail=f"file_id={staged.file_id}")

    def _do_upload(self, task_id, domain, entry, handle, approval_callback, origin):  # noqa: ANN001
        op = BrowserOperation.UPLOAD
        locator = entry.field_locator
        if locator is None:
            raise PermissionBlocked("a field_locator is required for upload")
        source = entry.upload_source_path or ""
        project_id = entry.upload_project_id or ""
        if not project_id:
            raise PermissionBlocked("upload requires an enrolled upload_project_id")
        try:
            project_root = self._upload_project_registry.resolve(project_id)
        except PermissionBlocked as exc:
            self._audit("browser.upload.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T2", origin=origin, detail=_safe_error(exc))
            return OperationResult(op.value, False, detail=_safe_error(exc))
        approved_roots = [project_root, *self._approved_upload_roots]
        try:
            validated_source = PermissionEngine(approved_roots).require_path(source, "browser.upload", RiskTier.T2)
        except PermissionBlocked as exc:
            self._audit("browser.upload.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T2", origin=origin, detail=_safe_error(exc))
            return OperationResult(op.value, False, detail=_safe_error(exc))
        try:
            file_hash, size, inode_identity = self._read_upload_identity(validated_source)
        except PermissionBlocked as exc:
            self._audit("browser.upload.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T2", origin=origin, detail=_safe_error(exc))
            return OperationResult(op.value, False, detail=_safe_error(exc))
        file_identity = f"{project_id}:{inode_identity}:{size}:{file_hash}"
        request = ApprovalRequest(operation=op.value, task_id=task_id, domain_id=domain.domain_id, role=locator.role, accessible_name=locator.name, file_identity_hash=hashlib.sha256(file_identity.encode()).hexdigest())
        self._request_and_consume(
            task_id=task_id, domain_id=domain.domain_id, request=request, approval_callback=approval_callback, origin=origin,
            locator_identity=locator.identity(), file_identity=file_identity,
        )
        # Revalidate immediately before use, then copy the exact verified
        # bytes into an owner-only private snapshot path. Playwright still
        # accepts a path, but it now reopens an AOS-controlled immutable
        # snapshot rather than the original caller-controlled path.
        try:
            with tempfile.TemporaryDirectory(prefix="aos-browser-upload-") as upload_tmp:
                staged_upload = self._stage_upload_snapshot(
                    validated_source,
                    expected_hash=file_hash,
                    expected_size=size,
                    expected_inode=inode_identity,
                    dest_dir=Path(upload_tmp),
                )
                ok = handle.upload(locator, staged_upload)
        except PermissionBlocked as exc:
            self._audit("browser.upload.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=False, risk_tier="T2", origin=origin, detail=_safe_error(exc))
            return OperationResult(op.value, False, detail=_safe_error(exc))
        self._audit("browser.upload.completed" if ok else "browser.upload.denied", task_id=task_id, domain_id=domain.domain_id, operation=op.value, ok=ok, risk_tier="T2", origin=origin, detail="ok" if ok else "upload_failed")
        return OperationResult(op.value, ok, detail="ok" if ok else "upload_failed")

    @staticmethod
    def _read_upload_identity(path: Path) -> tuple[str, int, str]:
        file_hash, size, inode_identity, _ = BrowserTaskRunner._read_upload_snapshot(path)
        return file_hash, size, inode_identity

    @staticmethod
    def _read_upload_snapshot(path: Path) -> tuple[str, int, str, bytes]:
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(str(path), flags)
        except OSError as exc:
            raise PermissionBlocked("upload source could not be opened safely") from exc
        try:
            st = os.fstat(fd)
            if not stat_module.S_ISREG(st.st_mode):
                raise PermissionBlocked("upload source is not a regular file")
            data = b""
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                data += chunk
                if len(data) > DEFAULT_RESOURCE_LIMITS.max_download_bytes:
                    raise PermissionBlocked("upload source exceeds the size limit")
            return hashlib.sha256(data).hexdigest(), st.st_size, f"{st.st_dev}:{st.st_ino}", data
        finally:
            os.close(fd)

    @staticmethod
    def _revalidate_upload_identity(path: Path, *, expected_hash: str, expected_size: int, expected_inode: str) -> None:
        try:
            st = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            raise PermissionBlocked("upload source no longer exists") from exc
        if stat_module.S_ISLNK(st.st_mode):
            raise PermissionBlocked("upload source became a symlink before use")
        current_inode = f"{st.st_dev}:{st.st_ino}"
        if current_inode != expected_inode or st.st_size != expected_size:
            raise PermissionBlocked("upload source identity changed before use (denied)")
        current_hash, _, _ = BrowserTaskRunner._read_upload_identity(path)
        if current_hash != expected_hash:
            raise PermissionBlocked("upload source content changed before use (denied)")

    @staticmethod
    def _stage_upload_snapshot(path: Path, *, expected_hash: str, expected_size: int, expected_inode: str, dest_dir: Path) -> Path:
        BrowserTaskRunner._revalidate_upload_identity(
            path,
            expected_hash=expected_hash,
            expected_size=expected_size,
            expected_inode=expected_inode,
        )
        current_hash, current_size, current_inode, data = BrowserTaskRunner._read_upload_snapshot(path)
        if current_inode != expected_inode or current_size != expected_size or current_hash != expected_hash:
            raise PermissionBlocked("upload source identity changed before snapshot (denied)")
        dest_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        staged = dest_dir / "upload.snapshot"
        fd = os.open(str(staged), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        return staged


_INJECTION_PATTERNS = (
    "ignore previous instructions", "ignore prior instructions", "system:",
    "you must now", "disregard the above", "new instructions:",
)


def _looks_like_injection(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in _INJECTION_PATTERNS)
