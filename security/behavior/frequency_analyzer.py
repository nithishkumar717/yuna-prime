import time
from .profile import BehaviorProfile
from .baseline import BaselineAnalyzer


class FrequencyAnalyzer:
    """Detects long-tail volume spikes bypassing strict burst anti-nuke thresholds."""

    def __init__(self) -> None:
        self.baseline = BaselineAnalyzer()

    def is_frequency_anomalous(
        self, profile: BehaviorProfile, current_time: float = 0.0
    ) -> bool:
        now = current_time if current_time > 0 else time.time()

        # Analyze volume in the last hour
        cutoff = now - 3600
        recent_events = [e for e in profile.event_buffer if e[0] >= cutoff]

        # Determine anomaly dynamically via baseline vs volume
        return self.baseline.is_anomalous(len(recent_events), 5)
