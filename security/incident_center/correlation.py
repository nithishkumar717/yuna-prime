from typing import Optional
from .evidence_store import EvidenceStore
from .models import IncidentCase


class CorrelationEngine:
    """Evaluates incoming events against active cases using proximity rules."""

    def __init__(self, store: EvidenceStore) -> None:
        self.store = store

    def find_active_case(
        self, actor_id: int, current_time: float = 0.0
    ) -> Optional[IncidentCase]:
        """Finds an open case for the actor. Resolves stale cases automatically in the future."""
        # For Sprint 18, we natively group all incoming evidence for an actor to their currently OPEN case.
        return self.store.get_open_case_for_actor(actor_id)
