import time
from typing import List, Tuple


class BehaviorProfile:
    """Stores the chronological action footprint of a specific actor."""

    def __init__(self, actor_id: int) -> None:
        self.actor_id = actor_id
        # List of (timestamp, event_type)
        self.event_buffer: List[Tuple[float, str]] = []

    def log_event(self, event_type: str, current_time: float = 0.0) -> None:
        now = current_time if current_time > 0 else time.time()
        self.event_buffer.append((now, event_type))

        # Keep only the last 50 events in the active buffer to prevent memory bloat
        if len(self.event_buffer) > 50:
            self.event_buffer.pop(0)
