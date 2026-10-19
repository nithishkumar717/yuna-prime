import asyncio
from typing import Callable, Dict, List, Type, Awaitable


class Event:
    """Base event class that all events must inherit from."""

    pass


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """
    Centralized Event Bus for asynchronous event-driven architecture.
    Allows decoupling of modules by publishing and subscribing to events.
    """

    def __init__(self):
        self._subscribers: Dict[Type[Event], List[EventHandler]] = {}

    def subscribe(self, event_type: Type[Event], handler: EventHandler) -> None:
        """Subscribes an async handler to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[Event], handler: EventHandler) -> None:
        """Unsubscribes a handler from a specific event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    async def publish(self, event: Event) -> None:
        """Publishes an event to all subscribed handlers asynchronously."""
        event_type = type(event)
        if event_type in self._subscribers:
            handlers = self._subscribers[event_type]
            if handlers:
                # Execute all handlers concurrently without blocking the publisher
                await asyncio.gather(
                    *(handler(event) for handler in handlers), return_exceptions=True
                )
