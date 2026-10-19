from enum import Enum
from core.event_bus.models import SystemEvent


class BehaviorType(Enum):
    SEQUENCE_ANOMALY = "SEQUENCE_ANOMALY"
    FREQUENCY_ANOMALY = "FREQUENCY_ANOMALY"
    OUT_OF_HOURS = "OUT_OF_HOURS"


class BehaviorAnomalyEvent(SystemEvent):
    actor_id: int
    behavior_type: BehaviorType
    confidence_score: float
