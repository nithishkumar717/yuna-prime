from typing import Any
from security.sentinel.models import ThreatLevel
from security.sentinel.pipeline import ThreatAnalyzer
from .dangerous_permissions import DANGEROUS_PERMISSIONS


class PermissionGuard(ThreatAnalyzer):
    """Monitors incoming payloads for unauthorized distribution of sensitive permissions."""

    async def analyze(self, payload: Any, current_threat: ThreatLevel) -> ThreatLevel:
        if not isinstance(payload, dict):
            return current_threat

        granted_perms = payload.get("granted_permissions", [])

        for perm in granted_perms:
            if perm in DANGEROUS_PERMISSIONS:
                # Automatically escalate to HIGH when sensitive permissions are granted
                return ThreatLevel(max(current_threat.value, ThreatLevel.HIGH.value))

        return current_threat
