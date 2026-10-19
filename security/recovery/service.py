from core.services.base import BaseService
from core.services.models import ServiceCategory
from core.container import Container
from core.event_bus import EventDispatcher
from .recovery_engine import RecoveryEngine


class RecoveryService(BaseService):
    """Provides public API integration for taking Backups and initiating Recovery Plans."""

    def __init__(self, container: Container, event_bus: EventDispatcher) -> None:
        super().__init__(
            name="RecoveryService", category=ServiceCategory.DOMAIN, event_bus=event_bus
        )
        self.container = container
        self.engine = RecoveryEngine()

    async def _on_start(self) -> None:
        self.logger.info(
            "Recovery Engine & Backup Vault Online.", event="RecoveryStart"
        )

    async def _on_stop(self) -> None:
        self.logger.info(
            "Recovery Engine & Backup Vault Offline.", event="RecoveryStop"
        )
