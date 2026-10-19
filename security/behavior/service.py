from core.services.base import BaseService
from core.services.models import ServiceCategory
from core.container import Container
from core.event_bus import EventDispatcher
from core.event_bus.models import SystemEvent
from .anomaly_detector import AnomalyDetector
from security.sentinel.service import SentinelService


class BehavioralEvent(SystemEvent):
    actor_id: int
    event_type: str


class BehaviorService(BaseService):
    """Subscribes globally to administrative events. Profiles actors and surfaces behavioral anomalies to Sentinel."""

    def __init__(self, container: Container, event_bus: EventDispatcher) -> None:
        super().__init__(
            name="BehaviorService", category=ServiceCategory.DOMAIN, event_bus=event_bus
        )
        self.container = container
        self.detector = AnomalyDetector()

    async def _on_start(self) -> None:
        self.event_bus.register(BehavioralEvent, self._handle_behavior_event)
        self.logger.info("Behavior Engine Online.", event="BehaviorStart")

    async def _on_stop(self) -> None:
        self.logger.info("Behavior Engine Offline.", event="BehaviorStop")

    async def _handle_behavior_event(self, event: BehavioralEvent) -> None:
        anomaly = self.detector.process_event(event.actor_id, event.event_type)

        if anomaly:
            self.logger.warning(
                f"BEHAVIOR ANOMALY DETECTED! Actor {anomaly.actor_id}: {anomaly.behavior_type.name}",
                event="BehaviorAnomaly",
            )

            sentinel = self.container.resolve(SentinelService)
            if sentinel:
                await sentinel.pipeline.evaluate(
                    source="BehaviorEngine",
                    target_id=anomaly.actor_id,
                    payload={
                        "behavior_anomaly": True,
                        "anomaly_type": anomaly.behavior_type.name,
                    },
                )
