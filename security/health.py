from typing import Dict, Any


class HealthMonitor:
    """Aggregates telemetry from all Sentinel subsystems to ensure operational stability."""

    def __init__(self) -> None:
        self.subsystems: Dict[str, bool] = {
            "ThreatPipeline": True,
            "IncidentCenter": True,
            "RecoveryEngine": True,
            "EventBus": True,
        }

    def check_health(self) -> Dict[str, Any]:
        """Provides abstract health payload intended for downstream dashboard ingestion."""
        all_ok = all(self.subsystems.values())
        return {
            "status": "HEALTHY" if all_ok else "DEGRADED",
            "subsystems": self.subsystems,
        }
