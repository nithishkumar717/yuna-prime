from typing import List
from .models import ForensicEvidence


class IncidentTimeline:
    """Manages chronological insertion and retrieval of evidence for a specific case."""

    def __init__(self) -> None:
        self.events: List[ForensicEvidence] = []

    def append_evidence(self, evidence: ForensicEvidence) -> None:
        self.events.append(evidence)
        # Sort chronologically to prevent temporal race conditions during high-volume spikes
        self.events.sort(key=lambda e: e.timestamp)

    def get_timeline(self) -> List[ForensicEvidence]:
        return self.events
