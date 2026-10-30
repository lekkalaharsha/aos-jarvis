"""Phase 1 permission engine for approved project file access.

Deny-by-default: absence of an explicit ALLOW decision means denied.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from aos.safety.errors import PermissionBlocked
from aos.safety.paths import validate_path
from aos.safety.risk import Decision, RiskTier, decision_for_risk

# Known Phase 1 capabilities and the access kind each one grants. Unknown
# capability names are denied rather than silently allowed -- see check_path.
CAPABILITY_KINDS = {
    "fs.list": "file.read",
    "fs.read": "file.read",
    "fs.search": "file.read",
    "fs.write": "file.write",
    "fs.edit": "file.write",
    "snapshot.restore": "file.restore",
    "run.command": "command.exec",
    "workspace.open": "workspace.launch",
    "workspace.editor": "workspace.launch",
    "workspace.terminal": "workspace.launch",
    "workspace.save": "workspace.state",
    "workspace.restore": "workspace.state",
    "workspace.serve": "workspace.server",
    "browser.upload": "browser.upload",
    "browser.promote": "browser.promote",
}


class Capability(BaseModel):
    name: str
    description: str = ""


class PermissionDecision(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    capability: Capability
    decision: Decision = Decision.DENY
    reason: str = "deny by default"
    risk_tier: RiskTier = RiskTier.T3
    path: str | None = None
    allowed: bool = False
    error: PermissionBlocked | None = None


class PermissionEngine:
    """Validates file paths against allowlists, deny rules, and risk tiers."""

    def __init__(self, approved_roots: list[str | Path] | None = None):
        self.approved_roots = approved_roots

    def check_path(
        self,
        path: str | Path,
        capability: str,
        risk_tier: RiskTier,
    ) -> PermissionDecision:
        cap = Capability(name=capability)
        if capability not in CAPABILITY_KINDS:
            return PermissionDecision(
                capability=cap,
                decision=Decision.DENY,
                reason=f"unknown capability: {capability}",
                risk_tier=RiskTier.T3,
                path=str(path),
                allowed=False,
            )

        try:
            resolved = validate_path(path, self.approved_roots)
        except PermissionBlocked as exc:
            return PermissionDecision(
                capability=cap,
                decision=Decision.DENY,
                reason=str(exc),
                risk_tier=RiskTier.T3,
                path=str(path),
                allowed=False,
                error=exc,
            )

        decision = decision_for_risk(risk_tier)
        return PermissionDecision(
            capability=cap,
            decision=decision,
            reason="path approved",
            risk_tier=risk_tier,
            path=str(resolved),
            allowed=decision != Decision.DENY,
        )

    def require_path(self, path: str | Path, capability: str, risk_tier: RiskTier) -> Path:
        result = self.check_path(path, capability, risk_tier)
        if not result.allowed or not result.path:
            if result.error is not None:
                raise result.error
            raise PermissionBlocked(result.reason)
        return Path(result.path)
