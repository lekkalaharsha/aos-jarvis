from __future__ import annotations

from aos.browser.domains import ApprovedDomainRegistry, DomainEnrollmentAuthority
from aos.browser.egress import EgressVerificationResult
from aos.browser.engine import FakeEngineFactory
from aos.browser.sandbox import SandboxVerificationResult
from aos.browser.supply_chain import SupplyChainVerificationResult
from aos.browser.task import BrowserTaskRunner
from aos.tools.base import ToolDecision
from aos.tools.browser import BrowserTool


class _FakeProxy:
    def stop(self):
        pass




def _tool(tmp_path):
    registry = ApprovedDomainRegistry(tmp_path / "domains.json")
    approval = DomainEnrollmentAuthority().approve_one("example.com", human_owner_confirmed=True, origin="terminal")
    domain = registry.enroll("example.com", approval=approval)
    factory = FakeEngineFactory(fixture_pages={"https://example.com/": {"text": "hello"}})
    runner = BrowserTaskRunner(
        registry=registry, engine_factory=factory, audit_path=tmp_path / "audit.db",
        approvals_consumed_path=tmp_path / "consumed.json", profile_root=tmp_path / "profiles",
        url_resolver=lambda host: ["93.184.216.34"],
        egress_checker=lambda targets: (EgressVerificationResult(True, "ok"), _FakeProxy()),
        sandbox_checker=lambda: SandboxVerificationResult(True, "ok"),
        supply_chain_checker=lambda: SupplyChainVerificationResult(True, "ok", "1.61.0"),
    )
    return BrowserTool(registry=registry, audit_path=tmp_path / "audit.db", runner=runner), domain, factory


def test_tool_implements_base_contract(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    assert tool.describe().name == "browser"
    assert tool.required_capabilities({}) == ["browser.task"]
    assert tool.risk_tier().value == "T2"


def test_dry_run_returns_task_id_without_launching(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    result = tool.dry_run({"domain_id": domain.domain_id, "operations": [{"operation": "read"}]})
    assert result.ok
    assert "task_id=" in result.output
    assert factory.launched_handles == []


def test_execute_missing_domain_id_denied(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    result = tool.execute({"operations": [{"operation": "read"}]})
    assert not result.ok
    assert result.decision == ToolDecision.DENY


def test_execute_full_task_with_approval_callback(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    preview = tool.dry_run({"domain_id": domain.domain_id, "operations": [{"operation": "navigate", "url": "https://example.com/"}]})
    task_id = preview.output.split("task_id=")[1].rstrip(")")
    result = tool.execute(
        {"domain_id": domain.domain_id, "task_id": task_id, "operations": [{"operation": "navigate", "url": "https://example.com/"}]},
        approval_callback=lambda request: True,
    )
    assert result.ok
    assert result.decision == ToolDecision.ALLOW


def test_execute_without_callback_denied(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    result = tool.execute({"domain_id": domain.domain_id, "operations": [{"operation": "navigate", "url": "https://example.com/"}]})
    assert not result.ok
    assert result.decision == ToolDecision.DENY


def test_execute_callback_denial_denies(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    result = tool.execute(
        {"domain_id": domain.domain_id, "operations": [{"operation": "navigate", "url": "https://example.com/"}]},
        approval_callback=lambda request: False,
    )
    assert not result.ok


def test_execute_rejects_unknown_operation(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    result = tool.execute({"domain_id": domain.domain_id, "operations": [{"operation": "login"}]})
    assert not result.ok


def test_execute_rejects_unexpected_operation_arguments(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    result = tool.execute({"domain_id": domain.domain_id, "operations": [{"operation": "navigate", "url": "https://example.com/", "field_classification": "non_sensitive_text"}]})
    assert not result.ok


def test_execute_rejects_raw_selector_style_locator(tmp_path):
    tool, domain, factory = _tool(tmp_path)
    result = tool.execute({
        "domain_id": domain.domain_id,
        "operations": [{"operation": "fill", "field_locator": {"role": "div[onclick]", "name": "x"}, "field_value": "y"}],
    })
    assert not result.ok
