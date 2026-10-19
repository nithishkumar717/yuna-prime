from typing import Any
from ..models import ThreatLevel
from ..pipeline import ThreatAnalyzer


class ReputationEngine(ThreatAnalyzer):
    """Evaluates external historical context globally overriding minor threats."""

    async def analyze(self, payload: Any, current_threat: ThreatLevel) -> ThreatLevel:
        if not isinstance(payload, dict):
            return current_threat

        known_scammer = payload.get("known_scammer", False)

        if known_scammer:
            # Overrides all previous evaluations to CRITICAL
            return ThreatLevel.CRITICAL

        return current_threat
