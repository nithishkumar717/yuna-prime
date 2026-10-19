import time
from typing import Dict, List, Tuple
from .models import NukeType
from .thresholds import NUKE_THRESHOLDS


class SlidingWindowTracker:
    """Evaluates burst rates natively over a precise sliding time constraint."""

    def __init__(self) -> None:
        self.history: Dict[Tuple[int, NukeType], List[float]] = {}

    def track(
        self, actor_id: int, nuke_type: NukeType, current_time: float = 0.0
    ) -> bool:
        """Logs an event and returns True if the specific threshold breaches."""
        now = current_time if current_time > 0 else time.time()
        key = (actor_id, nuke_type)

        if key not in self.history:
            self.history[key] = []

        self.history[key].append(now)

        limit, window = NUKE_THRESHOLDS[nuke_type]

        # Purge strictly stale events
        cutoff = now - window
        self.history[key] = [t for t in self.history[key] if t >= cutoff]

        return len(self.history[key]) >= limit
