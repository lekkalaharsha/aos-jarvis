from __future__ import annotations

import aos.browser.domains as domains_module
from aos.agent.tool_registry import ToolRegistry
from aos.agent.types import ToolCall
from aos.browser.domains import ApprovedDomainRegistry, DomainEnrollmentAuthority


def test_browser_domain_list_is_t0_and_agent_reachable(tmp_path, monkeypatch):
    # ApprovedDomainRegistry() with no explicit path resolves DEFAULT_REGISTRY_PATH
    # at call time from the module global -- patch that global directly so the
    # tool-registry's internal `ApprovedDomainRegistry()` construction (which
    # this test does not control) also lands in tmp_path.
    monkeypatch.setattr(domains_module, "DEFAULT_REGISTRY_PATH", tmp_path / "domains.json")
    registry = ApprovedDomainRegistry()
    approval = DomainEnrollmentAuthority().approve_one("example.com", human_owner_confirmed=True, origin="terminal")
    registry.enroll("example.com", approval=approval)

    tool_registry = ToolRegistry()
    call = ToolCall(tool="browser.domain_list", args={}, risk_tier="T0", requires_approval=False)
    observation = tool_registry.execute(call, cwd=str(tmp_path))
    assert observation.ok
    assert any(d["host"] == "example.com" for d in observation.data["domains"])


def test_no_t2_browser_operation_is_registered_for_agent_use():
    tool_registry = ToolRegistry()
    tools = tool_registry.list_tools()
    # Only the read-only listing is agent-reachable; every T2 browser action
    # requires the terminal-only `aos browser task` entrypoint (contract
    # Sec10/Sec11) since ToolCall.args is JSON-serializable and a
    # BrowserApproval object cannot be forwarded through it.
    browser_tools = [t for t in tools if t.startswith("browser.")]
    assert browser_tools == ["browser.domain_list"]
