from enum import Enum
from pydantic import BaseModel, Field


class SecurityProfile(Enum):
    RELAXED = "RELAXED"
    MODERATE = "MODERATE"
    STRICT = "STRICT"


class SentinelConfig(BaseModel):
    """Configuration mapping for global Sentinel boundaries."""

    profile: SecurityProfile = SecurityProfile.MODERATE

    # Feature Flags
    enable_anti_nuke: bool = True
    enable_raid_detection: bool = True
    enable_behavior_engine: bool = True

    # Subsystem Thresholds
    anti_nuke_threshold: int = Field(default=5)
    raid_join_threshold: int = Field(default=10)

    def apply_profile(self) -> None:
        """Dynamically tune thresholds based on standard Enterprise profiles."""
        if self.profile == SecurityProfile.STRICT:
            self.anti_nuke_threshold = 3
            self.raid_join_threshold = 5
        elif self.profile == SecurityProfile.RELAXED:
            self.anti_nuke_threshold = 10
            self.raid_join_threshold = 20
