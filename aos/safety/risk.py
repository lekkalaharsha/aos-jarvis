"""Phase 0 risk tier and decision model."""

from enum import Enum


class RiskTier(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    REQUIRE_STRONG_APPROVAL = "REQUIRE_STRONG_APPROVAL"
    DENY = "DENY"


_DECISION_BY_TIER = {
    RiskTier.T0: Decision.ALLOW,
    RiskTier.T1: Decision.REQUIRE_APPROVAL,
    RiskTier.T2: Decision.REQUIRE_STRONG_APPROVAL,
    RiskTier.T3: Decision.DENY,
}


def decision_for_risk(risk_tier: RiskTier) -> Decision:
    """Map a risk tier to its required decision. Unknown tiers deny by default."""
    return _DECISION_BY_TIER.get(risk_tier, Decision.DENY)


def classify_file_action(action: str, *, large_file: bool = False) -> RiskTier:
    """Classify Phase 1 file actions into documented risk tiers."""
    if action in {"list", "read", "search"}:
        return RiskTier.T0
    if action in {"write", "edit", "append", "create"}:
        return RiskTier.T2 if large_file else RiskTier.T1
    if action in {"delete", "restore"}:
        return RiskTier.T2
    return RiskTier.T3


def classify_command_risk(argv: list[str], category: str) -> RiskTier:
    """Classify Phase 2 command execution into documented risk tiers."""
    if not argv:
        return RiskTier.T3
    if category in {"DENY", "UNKNOWN"}:
        return RiskTier.T3
    if category == "ALLOW_PROJECT_TEST":
        return RiskTier.T1
    if category == "ALLOW_WITH_APPROVAL":
        return RiskTier.T2
    if category == "ALLOW_READONLY":
        if len(argv) >= 2 and argv[0] == "git" and argv[1] in {"diff", "log"}:
            return RiskTier.T1
        return RiskTier.T0
    return RiskTier.T3
