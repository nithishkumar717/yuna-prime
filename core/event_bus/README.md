# Yuna Event Bus

Decouples module communication utilizing Domain-Driven Design (DDD) patterns. Follows ADR-008 strictly segregating `SystemEvents` and `DomainEvents`.

## Usage
```python
from core.event_bus import SystemEvent, subscribe

class CustomEvent(SystemEvent):
    message: str

class MyService:
    @subscribe(CustomEvent)
    async def handle_custom_event(self, event: CustomEvent):
        print(event.message)
```
