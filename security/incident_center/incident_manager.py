import uuid
import time
from typing import Dict, Any
from .models import IncidentCase, IncidentStatus
from .evidence_store import EvidenceStore
from .correlation import CorrelationEngine
from .case_builder import CaseBuilder


class IncidentManager:
    """Coordinates the correlation, case generation, and timeline insertion natively."""

    def __init__(self) -> None:
        self.store = EvidenceStore()
        self.correlation = CorrelationEngine(self.store)
        self.builder = CaseBuilder()

    def process_security_event(
        self,
        actor_id: int,
        source: str,
        payload: Dict[str, Any],
        current_time: float = 0.0,
    ) -> IncidentCase:
        now = current_time if current_time > 0 else time.time()

        # 1. Correlate against existing Incident
        case = self.correlation.find_active_case(actor_id, now)

        if not case:
            # Generate new case
            case = IncidentCase(
                incident_id=str(uuid.uuid4()),
                actor_id=actor_id,
                start_time=now,
                status=IncidentStatus.OPEN,
            )
            self.store.save(case)

        # 2. Build Evidence
        evidence = self.builder.create_evidence(source, payload, now)

        # 3. Append to Timeline
        case.evidence_timeline.append(evidence)

        return case
