from enum import Enum
from pydantic import BaseModel, Field
from core.event_bus.models import SystemEvent


class ThreatLevel(Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class SecurityAction(Enum):
    ALLOW = "ALLOW"
    LOG = "LOG"
    ALERT = "ALERT"
    QUARANTINE = "QUARANTINE"
    BLOCK = "BLOCK"


class TrustScore(BaseModel):
    """Evaluates user/guild reputation on a deterministic integer axis."""

    user_id: int
    score: int = Field(default=100, ge=0, le=100)
    confidence: float = Field(default=1.0)


class SecurityEvent(SystemEvent):
    """Auditable security record produced by the ThreatPipeline."""

    event_source: str
    target_id: int
    threat_level: ThreatLevel
    action_taken: SecurityAction
    reason: str
