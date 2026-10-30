"""Phase 10 BrowserTool -- the single BaseTool integration point.

Mirrors aos/tools/workspace.py's shape. No T1 tier exists (contract Sec3).
A "task" execute call runs the entire bounded lifecycle in one call, per
docs/PHASE_10_BROWSER_AUTOMATION_CONTRACT.md Sec2a.

Remediation: the schema no longer accepts ``approvals`` or
``field_classification`` (see aos/browser/types.py, aos/browser/task.py).
Approval happens inside ``BrowserTaskRunner.run`` via a terminal-origin
``approval_callback`` supplied by the caller (the CLI); a structured
model/agent tool proposal can never carry an approval object through
``ToolCall.args`` (it is JSON-serializable, and neither a callback nor a
``BrowserApproval`` object is).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aos.browser.domains import ApprovedDomainRegistry
from aos.browser.engine import BrowserEngineFactory, PlaywrightEngineFactory
from aos.browser.quarantine import QuarantineStore
from aos.browser.task import ApprovalCallback, BrowserTaskRunner
from aos.browser.types import BrowserOperation, BrowserTaskSpec, FieldLocator, OperationEntry, new_task_id
from aos.safety.audit import DEFAULT_AUDIT_PATH
from aos.safety.errors import PermissionBlocked
from aos.safety.risk import RiskTier
from aos.tools.base import BaseTool, ToolDecision, ToolResult, ToolSchema


def _safe_error(exc: Exception) -> str:
    return "browser request denied" if isinstance(exc, PermissionBlocked) else "browser operation failed"


def _parse_locator(raw: dict[str, Any] | None) -> FieldLocator | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) - {"role", "name", "nth"}:
        raise PermissionBlocked("field_locator must contain only role/name/nth")
    return FieldLocator(role=str(raw.get("role", "")), name=str(raw.get("name", "")), nth=int(raw.get("nth", 0)))


def _parse_operation_entry(item: dict[str, Any]) -> OperationEntry:
    try:
        operation = BrowserOperation(str(item["operation"]))
    except (KeyError, ValueError) as exc:
        raise PermissionBlocked("unknown browser operation") from exc
    allowed_keys = {
        "operation", "url", "field_locator", "field_value",
        "upload_source_path", "upload_project_id",
    }
    if set(item) - allowed_keys:
        raise PermissionBlocked("unexpected browser operation arguments")
    return OperationEntry(
        operation=operation,
        url=item.get("url"),
        field_locator=_parse_locator(item.get("field_locator")),
        field_value=item.get("field_value"),
        upload_source_path=item.get("upload_source_path"),
        upload_project_id=item.get("upload_project_id"),
    )


class BrowserTool(BaseTool):
    def __init__(
        self,
        *,
        registry: ApprovedDomainRegistry | None = None,
        engine_factory: BrowserEngineFactory | None = None,
        audit_path: Path | None = None,
        approvals_consumed_path: Path | None = None,
        quarantine: QuarantineStore | None = None,
        runner: BrowserTaskRunner | None = None,
    ) -> None:
        self.registry = registry or ApprovedDomainRegistry()
        self.audit_path = audit_path or DEFAULT_AUDIT_PATH
        self.quarantine = quarantine or QuarantineStore()
        self.runner = runner or BrowserTaskRunner(
            registry=self.registry,
            engine_factory=engine_factory or PlaywrightEngineFactory(),
            audit_path=self.audit_path,
            approvals_consumed_path=approvals_consumed_path,
            quarantine=self.quarantine,
        )

    def describe(self) -> ToolSchema:
        return ToolSchema(name="browser", description="Bounded, per-task, permission-governed browser automation")

    def required_capabilities(self, args: dict[str, Any]) -> list[str]:
        return ["browser.task"]

    def risk_tier(self) -> RiskTier:
        return RiskTier.T2

    def _build_spec(self, args: dict[str, Any]) -> BrowserTaskSpec:
        domain_id = args.get("domain_id")
        if not isinstance(domain_id, str) or not domain_id.strip():
            raise PermissionBlocked("domain_id is required")
        operations_raw = args.get("operations")
        if not isinstance(operations_raw, list) or not operations_raw:
            raise PermissionBlocked("at least one operation is required")
        operations = tuple(_parse_operation_entry(item) for item in operations_raw)
        origin = str(args.get("origin", "terminal"))
        if origin not in {"terminal", "agent", "voice"}:
            raise PermissionBlocked("invalid origin")
        task_id = args.get("task_id") or new_task_id()
        if not isinstance(task_id, str):
            raise PermissionBlocked("invalid task_id")
        return BrowserTaskSpec(task_id=task_id, domain_id=domain_id, operations=operations, origin=origin)

    def dry_run(self, args: dict[str, Any]) -> ToolResult:
        try:
            spec = self._build_spec(args)
            result = self.runner.dry_run(spec)
            return ToolResult(ok=result.state.value == "validated", output=f"browser task validated (task_id={result.task_id})", decision=ToolDecision.REQUIRE_STRONG_APPROVAL)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, output=_safe_error(exc), decision=ToolDecision.DENY)

    def execute(self, args: dict[str, Any], *, approval_callback: ApprovalCallback | None = None) -> ToolResult:
        try:
            spec = self._build_spec(args)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, output=_safe_error(exc), decision=ToolDecision.DENY)
        result = self.runner.run(spec, approval_callback=approval_callback)
        ok = result.state.value == "completed"
        output = f"browser task {result.state.value} (task_id={result.task_id})"
        if result.error:
            output += f": {result.error}"
        if not result.cleanup_ok:
            output += " [cleanup_failed]"
        decision = ToolDecision.ALLOW if ok else ToolDecision.DENY
        return ToolResult(ok=ok, output=output, decision=decision)
