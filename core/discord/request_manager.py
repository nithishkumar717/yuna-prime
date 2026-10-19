import asyncio
import time
import logging
import random
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional, List, Dict

logger = logging.getLogger("yuna.request_manager")


class Priority(IntEnum):
    P0_CRITICAL = 0  # Security attack mitigation, anti-nuke bans, emergency lockdown
    P1_HIGH = 1      # Moderation punishments, anti-spam actions, permission revocation
    P2_NORMAL = 2    # General user commands, voice operations, bulk commands
    P3_LOW = 3       # Security logs, DM notifications, analytics, cosmetic updates


@dataclass(order=True)
class PrioritizedTask:
    priority: int
    timestamp: float
    task_id: str = field(compare=False)
    coro_func: Callable[[], Coroutine[Any, Any, Any]] = field(compare=False)
    guild_id: Optional[int] = field(default=None, compare=False)
    future: Optional[asyncio.Future] = field(default=None, compare=False)


class DiscordRequestManager:
    """Production-grade Priority Action Queue & Rate-Limit Controller for Yuna V7.00.
    
    Processes REST requests in strict priority order (P0 > P1 > P2 > P3) with
    per-guild rate-limit isolation, 429 backoff handling, and bulk action queueing.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DiscordRequestManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_concurrent_workers: int = 5):
        if self._initialized:
            return

        self.queue: asyncio.PriorityQueue[PrioritizedTask] = asyncio.PriorityQueue()
        self.max_concurrent_workers = max_concurrent_workers
        self.workers = []
        self.running = False
        self.rate_limited_until = 0.0
        self.guild_rate_limits: Dict[int, float] = {}
        self.attack_mode_active = False
        self._initialized = True

    def start(self):
        """Starts worker pool background task."""
        if self.running:
            return
        self.running = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        for i in range(self.max_concurrent_workers):
            worker = loop.create_task(self._worker_loop(worker_id=i))
            self.workers.append(worker)

    def stop(self):
        """Stops worker pool background tasks cleanly."""
        self.running = False
        for worker in self.workers:
            worker.cancel()
        self.workers.clear()

    def set_attack_mode(self, active: bool):
        """Toggles ATTACK mode state."""
        self.attack_mode_active = active

    async def enqueue(
        self,
        priority: Priority,
        task_id: str,
        coro_func: Callable[[], Coroutine[Any, Any, Any]],
        guild_id: Optional[int] = None
    ) -> Any:
        """Enqueues a task and returns an awaitable result Future."""
        if not self.running:
            self.start()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        future = loop.create_future()
        task = PrioritizedTask(
            priority=int(priority),
            timestamp=time.time(),
            task_id=task_id,
            coro_func=coro_func,
            guild_id=guild_id,
            future=future
        )

        await self.queue.put(task)
        return await future

    async def enqueue_bulk(
        self,
        priority: Priority,
        base_task_id: str,
        coro_funcs: List[Callable[[], Coroutine[Any, Any, Any]]],
        guild_id: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], Coroutine[Any, Any, None]]] = None,
        delay_between_tasks: float = 0.35
    ) -> List[Any]:
        """Queues a series of bulk actions with controlled execution pacing and optional progress reporting."""
        total = len(coro_funcs)
        results = []

        for idx, coro_func in enumerate(coro_funcs, start=1):
            task_id = f"{base_task_id}_{idx}"
            try:
                res = await self.enqueue(
                    priority=priority,
                    task_id=task_id,
                    coro_func=coro_func,
                    guild_id=guild_id
                )
                results.append(res)
            except Exception as e:
                err_str = str(e)
                # 404 Unknown Message = message was deleted before we could react — expected, not an error
                if "10008" in err_str or "Unknown Message" in err_str:
                    logger.debug(f"[BULK ACTION] Subtask {task_id} skipped (message deleted): {e}")
                else:
                    logger.warning(f"[BULK ACTION] Subtask {task_id} failed: {e}")
                results.append(None)

            if progress_callback and (idx % 10 == 0 or idx == total):
                try:
                    await progress_callback(idx, total)
                except Exception:
                    pass

            if delay_between_tasks > 0:
                await asyncio.sleep(delay_between_tasks)

        return results

    def slow_delete(self, message: Optional[Any], delay: float = 1.0, guild_id: Optional[int] = None):
        """Enqueues a non-blocking slow deletion at P3_LOW priority with pacing to prevent Discord API rate limits."""
        if not message:
            return

        async def _do_delete():
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                await message.delete()
            except Exception as e:
                import discord
                if isinstance(e, discord.HTTPException) and e.status == 429:
                    retry_after = float(e.response.headers.get("Retry-After", 1.5))
                    await asyncio.sleep(retry_after)
                    try:
                        await message.delete()
                    except Exception:
                        pass

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        g_id = guild_id or getattr(getattr(message, 'guild', None), 'id', None)
        task = PrioritizedTask(
            priority=int(Priority.P3_LOW),
            timestamp=time.time(),
            task_id=f"delete_msg_{getattr(message, 'id', time.time())}",
            coro_func=_do_delete,
            guild_id=g_id,
            future=None
        )
        loop.create_task(self.queue.put(task))

    async def _worker_loop(self, worker_id: int):
        while self.running:
            try:
                # Check global rate limit delay
                now = time.time()
                if now < self.rate_limited_until:
                    await asyncio.sleep(self.rate_limited_until - now + 0.05)

                task: PrioritizedTask = await self.queue.get()

                # Check per-guild rate limit delay if applicable
                if task.guild_id and task.guild_id in self.guild_rate_limits:
                    guild_until = self.guild_rate_limits[task.guild_id]
                    now = time.time()
                    if now < guild_until:
                        # Re-queue and pause worker briefly to respect per-guild rate limit
                        await self.queue.put(task)
                        self.queue.task_done()
                        await asyncio.sleep(min(guild_until - now, 0.5))
                        continue

                # Execute task coroutine safely
                try:
                    res = await task.coro_func()
                    if task.future and not task.future.done():
                        task.future.set_result(res)
                except Exception as exc:
                    import discord
                    if isinstance(exc, discord.HTTPException) and exc.status == 429:
                        retry_after = float(exc.response.headers.get("Retry-After", 2.0))
                        jitter = random.uniform(0.1, 0.5)
                        backoff_until = time.time() + retry_after + jitter
                        
                        if task.guild_id:
                            self.guild_rate_limits[task.guild_id] = backoff_until
                        else:
                            self.rate_limited_until = backoff_until

                        logger.warning(
                            f"[RATE LIMIT 429] Worker {worker_id} hit 429 for task {task.task_id} "
                            f"(Guild: {task.guild_id}). Backing off for {retry_after + jitter:.2f}s."
                        )
                        # Re-queue task to retry after backoff
                        await self.queue.put(task)
                    else:
                        if task.future and not task.future.done():
                            task.future.set_exception(exc)
                finally:
                    self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"[WORKER ERROR] Worker {worker_id} encountered exception: {exc}")
                await asyncio.sleep(0.5)


# Global singleton instance
request_manager = DiscordRequestManager()

