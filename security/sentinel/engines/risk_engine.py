from typing import Any
from ..models import ThreatLevel
from ..pipeline import ThreatAnalyzer


class RiskEngine(ThreatAnalyzer):
    """Calculates static risk score based on deterministic structural rules."""

    async def analyze(self, payload: Any, current_threat: ThreatLevel) -> ThreatLevel:
        threat = ThreatLevel.NONE

        if isinstance(payload, dict):
            if payload.get("suspicious", False) or payload.get(
                "behavior_anomaly", False
            ):
                threat = ThreatLevel.HIGH
            if (
                payload.get("mass_ping", False)
                or payload.get("nuke_detected", False)
                or payload.get("raid_detected", False)
            ):
                threat = ThreatLevel.CRITICAL

        # RiskEngine is an escalator; it won't downgrade a threat arbitrarily
        return ThreatLevel(max(current_threat.value, threat.value))
