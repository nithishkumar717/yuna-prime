import time
from typing import Dict
from pydantic import BaseModel, Field


class RetentionPolicy(BaseModel):
    """Defines TTL storage retention windows (in days) for Yuna collection namespaces."""
    audit_logs_days: int = Field(default=90, ge=1)
    security_events_days: int = Field(default=180, ge=1)
    ai_recommendations_days: int = Field(default=30, ge=1)
    mod_cases_days: int = Field(default=365, ge=1)
    analytics_trends_days: int = Field(default=60, ge=1)

    def get_cutoff_timestamp(self, collection_name: str, custom_now: float = 0.0) -> float:
        """Calculates the UNIX timestamp threshold prior to which records are eligible for archival or purging."""
        now = custom_now if custom_now > 0 else time.time()
        policy_map: Dict[str, int] = {
            "audit_logs": self.audit_logs_days,
            "security_events": self.security_events_days,
            "ai_recommendations": self.ai_recommendations_days,
            "mod_cases": self.mod_cases_days,
            "analytics_trends": self.analytics_trends_days
        }
        days = policy_map.get(collection_name, 90)
        seconds = days * 86400.0
        return now - seconds
