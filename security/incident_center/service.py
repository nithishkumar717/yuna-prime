from core.services.base import BaseService
from core.services.models import ServiceCategory
from core.container import Container
from core.event_bus import EventDispatcher
from security.sentinel.models import SecurityEvent
from .incident_manager import IncidentManager


class IncidentCenterService(BaseService):
    """Subscribes globally to SecurityEvent to build unified Forensic Incident Cases."""

    def __init__(self, container: Container, event_bus: EventDispatcher) -> None:
        super().__init__(
            name="IncidentCenterService",
            category=ServiceCategory.DOMAIN,
            event_bus=event_bus,
        )
        self.container = container
        self.manager = IncidentManager()

    async def _on_start(self) -> None:
        self.event_bus.register(SecurityEvent, self._handle_security_event)
        self.logger.info(
            "Incident Center & Forensics Online.", event="IncidentCenterStart"
        )

    async def _on_stop(self) -> None:
        self.logger.info(
            "Incident Center & Forensics Offline.", event="IncidentCenterStop"
        )

    async def _handle_security_event(self, event: SecurityEvent) -> None:
        # Map the Sentinel pipeline event into a raw evidence payload
        payload = {
            "threat_level": event.threat_level.name,
            "action_taken": event.action_taken.name,
            "reason": event.reason,
        }

        case = self.manager.process_security_event(
            actor_id=event.target_id, source="ThreatPipeline", payload=payload
        )

        self.logger.info(
            f"Appended evidence to Incident Case {case.incident_id} for Actor {event.target_id}.",
            event="IncidentUpdate",
        )
