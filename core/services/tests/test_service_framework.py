import pytest
from unittest.mock import AsyncMock
from core.event_bus import EventDispatcher
from core.services.base import BaseService
from core.services.models import ServiceState, ServiceCategory
from core.services.exceptions import ServiceLifecycleError
from core.services.manager import ServiceManager


class DummyService(BaseService):
    def __init__(self, event_bus: EventDispatcher):
        super().__init__("Dummy", ServiceCategory.DOMAIN, event_bus)
        self.start_called = False
        self.stop_called = False

    async def _on_start(self) -> None:
        self.start_called = True

    async def _on_stop(self) -> None:
        self.stop_called = True


@pytest.mark.asyncio
async def test_legal_lifecycle_transitions():
    bus = EventDispatcher()
    bus.publish = AsyncMock()  # type: ignore
    service = DummyService(bus)

    assert service.state == ServiceState.INITIALIZING
    await service.start()
    assert service.start_called is True
    assert service.state == ServiceState.READY

    await service.stop()
    assert service.stop_called is True
    assert service.state == ServiceState.STOPPED


@pytest.mark.asyncio
async def test_illegal_lifecycle_transitions():
    bus = EventDispatcher()
    service = DummyService(bus)

    with pytest.raises(ServiceLifecycleError):
        # Cannot stop if never started
        await service.stop()


@pytest.mark.asyncio
async def test_service_manager_orchestration():
    bus = EventDispatcher()
    bus.publish = AsyncMock()  # type: ignore
    manager = ServiceManager()
    svc1 = DummyService(bus)
    svc1.name = "Dummy1"
    svc2 = DummyService(bus)
    svc2.name = "Dummy2"

    manager.register(svc1)
    manager.register(svc2)

    await manager.start_all()
    assert svc1.state == ServiceState.READY
    assert svc2.state == ServiceState.READY

    report = manager.get_health_report()
    assert report["Dummy1"] == "READY"
    assert report["Dummy2"] == "READY"

    await manager.stop_all()
    assert svc1.state == ServiceState.STOPPED
    assert svc2.state == ServiceState.STOPPED
