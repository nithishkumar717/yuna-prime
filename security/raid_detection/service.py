from core.services.base import BaseService
from core.services.models import ServiceCategory
from core.container import Container
from core.event_bus import EventDispatcher
from core.event_bus.models import SystemEvent
from .detector import RaidDetector
from security.sentinel.service import SentinelService


class MemberJoinEvent(SystemEvent):
    guild_id: int
    actor_id: int
    account_age_days: int


class RaidDetectionService(BaseService):
    """Subscribes to global join events. Synthesizes swarm data and pushes to Sentinel."""

    def __init__(self, container: Container, event_bus: EventDispatcher) -> None:
        super().__init__(
            name="RaidDetectionService",
            category=ServiceCategory.DOMAIN,
            event_bus=event_bus,
        )
        self.container = container
        self.detector = RaidDetector()

    async def _on_start(self) -> None:
        self.event_bus.register(MemberJoinEvent, self._handle_join_event)
        self.logger.info("Raid Detection Engine Online.", event="RaidStart")

    async def _on_stop(self) -> None:
        self.logger.info("Raid Detection Engine Offline.", event="RaidStop")

    async def _handle_join_event(self, event: MemberJoinEvent) -> None:
        is_raid = self.detector.process_join(event.guild_id, event.account_age_days)

        if is_raid:
            self.logger.warning(
                f"RAID DETECTED in Guild {event.guild_id}! Escaping payload to Sentinel.",
                event="RaidDetected",
            )

            sentinel = self.container.resolve(SentinelService)
            if sentinel:
                await sentinel.pipeline.evaluate(
                    source="RaidDetectionEngine",
                    target_id=event.actor_id,
                    payload={"raid_detected": True, "guild_id": event.guild_id},
                )
