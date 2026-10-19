from typing import Any
from ..models import ThreatLevel
from ..pipeline import ThreatAnalyzer


class TrustEngine(ThreatAnalyzer):
    """Evaluates dynamic trust scores scoped to internal ecosystem context."""

    async def analyze(self, payload: Any, current_threat: ThreatLevel) -> ThreatLevel:
        if not isinstance(payload, dict):
            return current_threat

        trust_score = payload.get("trust_score", 50)
        membership_duration_days = payload.get("membership_duration_days", 0)

        # High trust veterans bypass standard High thresholds to prevent false positive locks
        if trust_score > 90 and membership_duration_days > 365:
            if current_threat == ThreatLevel.HIGH:
                return ThreatLevel.LOW

        return current_threat
