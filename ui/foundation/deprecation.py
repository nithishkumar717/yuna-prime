"""Deprecation warning utilities for the Yuna UI Library."""

import warnings
import functools
from typing import Callable, Any


def deprecated(replacement: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to mark functions or methods as deprecated.

    Emits a DeprecationWarning when the decorated callable is executed.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(
                f"{func.__name__} is deprecated and will be removed in a future stable release. "
                f"Use {replacement} instead.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator
