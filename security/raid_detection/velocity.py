import time
from typing import Dict, List


class JoinTracker:
    """Tracks cohort velocity globally per guild rather than individually per actor."""

    def __init__(self, window_seconds: int = 10, threshold: int = 5) -> None:
        self.history: Dict[int, List[float]] = {}
        self.window_seconds = window_seconds
        self.threshold = threshold

    def track_and_check(self, guild_id: int, current_time: float = 0.0) -> bool:
        """Logs a join event and returns True if the global velocity threshold breaches."""
        now = current_time if current_time > 0 else time.time()

        if guild_id not in self.history:
            self.history[guild_id] = []

        self.history[guild_id].append(now)

        # Purge stale events outside the sliding window
        cutoff = now - self.window_seconds
        self.history[guild_id] = [t for t in self.history[guild_id] if t >= cutoff]

        return len(self.history[guild_id]) >= self.threshold
