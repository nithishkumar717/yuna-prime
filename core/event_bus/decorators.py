from typing import Type, Callable, Any
from .models import BaseEvent


def subscribe(event_type: Type[BaseEvent]) -> Callable[..., Any]:
    """Decorator to mark a method as an event handler."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if not hasattr(func, "__event_subscriptions__"):
            func.__event_subscriptions__ = []  # type: ignore
        func.__event_subscriptions__.append(event_type)  # type: ignore
        return func

    return decorator
