from typing import Dict, Optional
from .models import IncidentCase, IncidentStatus


class EvidenceStore:
    """In-memory simulation of an immutable vault for Incident Cases."""

    def __init__(self) -> None:
        self.cases: Dict[str, IncidentCase] = {}

    def save(self, case: IncidentCase) -> None:
        self.cases[case.incident_id] = case

    def get_by_id(self, incident_id: str) -> Optional[IncidentCase]:
        return self.cases.get(incident_id)

    def get_open_case_for_actor(self, actor_id: int) -> Optional[IncidentCase]:
        for case in self.cases.values():
            if case.actor_id == actor_id and case.status == IncidentStatus.OPEN:
                return case
        return None
