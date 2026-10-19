from typing import Any, List
from .models import ThreatLevel, SecurityAction
from core.logging import get_logger


class PolicyEngine:
    """Evaluates computed threat levels against configured server tolerances, exemptions, and overrides."""

    def __init__(self) -> None:
        self.logger = get_logger("SECURITY", "PolicyEngine")
        # In a future sprint, this will dynamically resolve from ConfigManager or Database
        self.whitelisted_ids: List[int] = [12345]

    async def evaluate(
        self, threat: ThreatLevel, payload: Any, target_id: int
    ) -> SecurityAction:
        if target_id in self.whitelisted_ids:
            self.logger.warning(
                f"Target {target_id} is whitelisted. Bypassing threat {threat.name}.",
                event="PolicyBypass",
            )
            return SecurityAction.ALLOW

        if threat == ThreatLevel.CRITICAL:
            return SecurityAction.BLOCK
        elif threat in (ThreatLevel.HIGH, ThreatLevel.MEDIUM):
            return SecurityAction.QUARANTINE

        return SecurityAction.ALLOW
