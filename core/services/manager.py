from typing import List, Dict
from .base import BaseService
from core.logging import get_logger


class ServiceManager:
    """Aggregates active services and orchestrates their lifecycles seamlessly."""

    def __init__(self) -> None:
        self.logger = get_logger("SYSTEM", "ServiceManager")
        self._services: List[BaseService] = []

    def register(self, service: BaseService) -> None:
        self._services.append(service)

    async def start_all(self) -> None:
        self.logger.info("Starting all registered services...", event="ManagerStart")
        for service in self._services:
            await service.start()
        self.logger.info(
            "All services successfully transitioned to READY.", event="ManagerReady"
        )

    async def stop_all(self) -> None:
        self.logger.info("Stopping all registered services...", event="ManagerStop")
        for service in reversed(self._services):
            try:
                await service.stop()
            except Exception as e:
                self.logger.error(
                    f"Error stopping service {service.name}: {e}",
                    event="ManagerStopError",
                )
        self.logger.info(
            "All services successfully transitioned to STOPPED.", event="ManagerStopped"
        )

    def get_health_report(self) -> Dict[str, str]:
        """Provides a map of service names to their active states."""
        return {s.name: s.state.value for s in self._services}
