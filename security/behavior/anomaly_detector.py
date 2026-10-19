from typing import Dict, Optional
from .profile import BehaviorProfile
from .sequence_analyzer import SequenceAnalyzer
from .frequency_analyzer import FrequencyAnalyzer
from .models import BehaviorType, BehaviorAnomalyEvent


class AnomalyDetector:
    """Fuses sequential, frequency, and baseline analysis to surface behavioral anomalies."""

    def __init__(self) -> None:
        self.profiles: Dict[int, BehaviorProfile] = {}
        self.sequence_analyzer = SequenceAnalyzer()
        self.frequency_analyzer = FrequencyAnalyzer()

    def process_event(
        self, actor_id: int, event_type: str, current_time: float = 0.0
    ) -> Optional[BehaviorAnomalyEvent]:
        if actor_id not in self.profiles:
            self.profiles[actor_id] = BehaviorProfile(actor_id)

        profile = self.profiles[actor_id]
        profile.log_event(event_type, current_time)

        # 1. Sequence Checking
        if self.sequence_analyzer.detect_hostile_chain(profile):
            return BehaviorAnomalyEvent(
                actor_id=actor_id,
                behavior_type=BehaviorType.SEQUENCE_ANOMALY,
                confidence_score=0.9,
            )

        # 2. Frequency Checking
        if self.frequency_analyzer.is_frequency_anomalous(profile, current_time):
            return BehaviorAnomalyEvent(
                actor_id=actor_id,
                behavior_type=BehaviorType.FREQUENCY_ANOMALY,
                confidence_score=0.8,
            )

        return None
