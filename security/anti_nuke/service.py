from core.services.base import BaseService
from core.services.models import ServiceCategory
from core.container import Container
from core.event_bus import EventDispatcher
from core.event_bus.models import SystemEvent
from .detector import AntiNukeDetector
from .models import NukeType
from security.sentinel.service import SentinelService


class RawDiscordEvent(SystemEvent):
    event_type: str
    target_id: int


class AntiNukeService(BaseService):
    """Subscribes globally to Discord Events. Pushes valid Nuke Events natively to the Sentinel ThreatPipeline."""

    def __init__(self, container: Container, event_bus: EventDispatcher) -> None:
        super().__init__(
            name="AntiNukeService", category=ServiceCategory.DOMAIN, event_bus=event_bus
        )
        self.container = container
        self.detector = AntiNukeDetector()

    async def _on_start(self) -> None:
        self.event_bus.register(RawDiscordEvent, self._handle_raw_event)
        self.logger.info("Anti-Nuke Engine Online.", event="AntiNukeStart")

    async def _on_stop(self) -> None:
        self.logger.info("Anti-Nuke Engine Offline.", event="AntiNukeStop")

    async def _handle_raw_event(self, event: RawDiscordEvent) -> None:
        nuke_type = None
        if event.event_type == "channel_delete":
            nuke_type = NukeType.CHANNEL_DELETE
        elif event.event_type == "member_ban":
            nuke_type = NukeType.MASS_BAN

        if nuke_type:
            nuke_event = await self.detector.process_event(
                event.event_type, event.target_id, nuke_type
            )
            if nuke_event:
                self.logger.warning(
                    f"Nuke Detected! {nuke_event.nuke_type.name} by Actor {nuke_event.actor_id}",
                    event="NukeDetected",
                )

                # Push securely into Sentinel Pipeline. Sentinel determines the Response (ALLOW vs BLOCK)
                sentinel = self.container.resolve(SentinelService)
                if sentinel:
                    await sentinel.pipeline.evaluate(
                        source="AntiNukeEngine",
                        target_id=nuke_event.actor_id,
                        payload={
                            "nuke_detected": True,
                            "nuke_type": nuke_event.nuke_type.name,
                        },
                    )
