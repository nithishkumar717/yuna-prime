from typing import Optional
from .models import NukeType, NukeDetectedEvent
from .rate_tracker import SlidingWindowTracker
from .audit_log_correlator import AuditCorrelator
from .thresholds import NUKE_THRESHOLDS


class AntiNukeDetector:
    """Central evaluator identifying Nuke bursts through Audit Log correlation."""

    def __init__(self) -> None:
        self.tracker = SlidingWindowTracker()
        self.correlator = AuditCorrelator()

    async def process_event(
        self,
        event_type: str,
        target_id: int,
        nuke_type: NukeType,
        current_time: float = 0.0,
    ) -> Optional[NukeDetectedEvent]:
        actor_id = await self.correlator.identify_actor(event_type, target_id)

        if self.tracker.track(actor_id, nuke_type, current_time):
            limit, window = NUKE_THRESHOLDS[nuke_type]
            return NukeDetectedEvent(
                actor_id=actor_id,
                nuke_type=nuke_type,
                burst_count=limit,
                time_window_seconds=window,
            )
        return None
