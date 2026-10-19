from typing import Any
from security.sentinel.models import ThreatLevel
from security.sentinel.pipeline import ThreatAnalyzer
from .hierarchy import is_privilege_escalation, is_owner_targeted


class RoleGuard(ThreatAnalyzer):
    """Analyzes mathematical position hierarchies to prevent unauthorized Privilege Escalation."""

    async def analyze(self, payload: Any, current_threat: ThreatLevel) -> ThreatLevel:
        if not isinstance(payload, dict):
            return current_threat

        target_is_owner = payload.get("target_is_owner", False)
        if is_owner_targeted(target_is_owner):
            return ThreatLevel.CRITICAL

        actor_pos = payload.get("actor_top_role")
        target_pos = payload.get("target_top_role")

        if actor_pos is not None and target_pos is not None:
            if is_privilege_escalation(actor_pos, target_pos):
                return ThreatLevel.CRITICAL

        return current_threat
