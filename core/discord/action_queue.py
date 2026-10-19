from typing import Any, Callable, Coroutine
from .request_manager import request_manager, Priority


async def execute_priority_action(
    priority: Priority,
    task_id: str,
    coro_func: Callable[[], Coroutine[Any, Any, Any]]
) -> Any:
    """Convenience helper to enqueue and execute a priority task via DiscordRequestManager."""
    if not request_manager.running:
        request_manager.start()
    return await request_manager.enqueue(priority=priority, task_id=task_id, coro_func=coro_func)
