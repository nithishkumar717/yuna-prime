import pytest
from unittest.mock import AsyncMock
from core.event_bus.dispatcher import EventDispatcher
from core.event_bus.models import DomainEvent, SystemEvent


class DummyDomainEvent(DomainEvent):
    data: str


class DummySystemEvent(SystemEvent):
    pass


@pytest.mark.asyncio
async def test_event_dispatch():
    dispatcher = EventDispatcher()
    handler1 = AsyncMock()
    handler2 = AsyncMock()

    dispatcher.register(DummyDomainEvent, handler1)
    dispatcher.register(DummyDomainEvent, handler2)

    event = DummyDomainEvent(data="test")
    await dispatcher.publish(event)

    handler1.assert_called_once_with(event)
    handler2.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_event_segregation():
    dispatcher = EventDispatcher()
    domain_handler = AsyncMock()

    dispatcher.register(DummyDomainEvent, domain_handler)

    sys_event = DummySystemEvent()
    await dispatcher.publish(sys_event)

    # Domain handler should NOT trigger on system events
    domain_handler.assert_not_called()


@pytest.mark.asyncio
async def test_safe_execution_avoids_crash():
    dispatcher = EventDispatcher()
    failing_handler = AsyncMock(side_effect=ValueError("Boom"))
    working_handler = AsyncMock()

    dispatcher.register(DummySystemEvent, failing_handler)
    dispatcher.register(DummySystemEvent, working_handler)

    event = DummySystemEvent()
    await dispatcher.publish(event)

    # Working handler should still fire despite the crash in the first
    working_handler.assert_called_once_with(event)
