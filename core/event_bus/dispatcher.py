import asyncio
from typing import Type, Callable, Dict, List, Any
from .models import BaseEvent
from core.logging.logger import get_logger


class EventDispatcher:
    def __init__(self) -> None:
        self._subscribers: Dict[Type[BaseEvent], List[Callable[..., Any]]] = {}
        self.logger = get_logger("SYSTEM", "EventBus")

    def register(
        self, event_type: Type[BaseEvent], handler: Callable[..., Any]
    ) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    async def publish(self, event: BaseEvent) -> None:
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        tasks = []
        for handler in handlers:
            tasks.append(self._safe_execute(handler, event))

        if tasks:
            await asyncio.gather(*tasks)

    async def _safe_execute(
        self, handler: Callable[..., Any], event: BaseEvent
    ) -> None:
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            self.logger.error(
                f"Event handler {handler.__name__} failed processing {type(event).__name__}: {e}",
                event="EventError",
            )
