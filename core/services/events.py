from typing import Optional
from core.event_bus import SystemEvent
from .models import ServiceState


class ServiceStateChangedEvent(SystemEvent):
    service_name: str
    previous_state: Optional[ServiceState]
    new_state: ServiceState
