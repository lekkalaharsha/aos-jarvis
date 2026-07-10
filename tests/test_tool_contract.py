from aos.safety.permissions import Capability
from aos.safety.risk import Decision, RiskTier, decision_for_risk
from aos.tools.base import BaseTool, ToolResult


def test_risk_tier_decision_mapping():
    assert decision_for_risk(RiskTier.T0) == Decision.ALLOW
    assert decision_for_risk(RiskTier.T1) == Decision.REQUIRE_APPROVAL
    assert decision_for_risk(RiskTier.T2) == Decision.REQUIRE_STRONG_APPROVAL
    assert decision_for_risk(RiskTier.T3) == Decision.DENY


def test_base_tool_is_abstract_with_required_methods():
    required = {"describe", "dry_run", "execute", "required_capabilities", "risk_tier"}
    assert required.issubset(BaseTool.__abstractmethods__)

    class NotImplementedTool(BaseTool):
        pass

    try:
        NotImplementedTool()
        assert False, "BaseTool subclass missing methods should not be instantiable"
    except TypeError:
        pass


def test_tool_result_is_a_simple_model():
    result = ToolResult(ok=True, output="fine", decision="ALLOW")
    assert result.ok is True
    assert result.output == "fine"


def test_capability_model_serialization():
    capability = Capability(name="read_readme", description="read approved README")
    dumped = capability.model_dump()
    assert dumped == {"name": "read_readme", "description": "read approved README"}
    assert Capability.model_validate_json(capability.model_dump_json()) == capability
