import asyncio
import logging
import time
from typing import Dict, Any, Callable, Awaitable, Optional

logger = logging.getLogger("yuna.profile_sync_worker")

class ProfileSyncWorker:
    def __init__(self, debounce_delay: float = 2.5):
        self.debounce_delay = debounce_delay
        self._pending_tasks: Dict[int, asyncio.Task] = {}
        self._pending_payloads: Dict[int, Dict[str, Any]] = {}
        self._sync_callback: Optional[Callable[[int, Dict[str, Any]], Awaitable[None]]] = None

    def set_sync_callback(self, callback: Callable[[int, Dict[str, Any]], Awaitable[None]]):
        """Sets the asynchronous callback function to be called when timer fires: callback(guild_id, merged_payload)"""
        self._sync_callback = callback

    def schedule_sync(self, guild_id: int, payload_update: Dict[str, Any]):
        """
        Schedules a sync request for guild_id with partial/full payload updates.
        Debounces multiple calls within self.debounce_delay seconds into a single execution.
        """
        if guild_id not in self._pending_payloads:
            self._pending_payloads[guild_id] = {}

        # Merge new updates into pending payload for guild
        self._pending_payloads[guild_id].update(payload_update)

        # Cancel existing pending timer task if active
        if guild_id in self._pending_tasks and not self._pending_tasks[guild_id].done():
            self._pending_tasks[guild_id].cancel()

        # Schedule new delayed execution task
        self._pending_tasks[guild_id] = asyncio.create_task(
            self._delayed_sync(guild_id)
        )
        logger.debug(f"[ProfileSyncWorker] Scheduled sync for guild {guild_id} in {self.debounce_delay}s")

    async def _delayed_sync(self, guild_id: int):
        try:
            await asyncio.sleep(self.debounce_delay)
            payload = self._pending_payloads.pop(guild_id, {})
            self._pending_tasks.pop(guild_id, None)

            if self._sync_callback and payload:
                logger.info(f"[ProfileSyncWorker] Executing debounced sync for guild {guild_id}")
                await self._sync_callback(guild_id, payload)
        except asyncio.CancelledError:
            # Debounce cancelled due to newer incoming payload
            pass
        except Exception as e:
            logger.error(f"[ProfileSyncWorker] Exception during sync for guild {guild_id}: {e}", exc_info=True)

    async def force_sync_now(self, guild_id: int):
        """Immediately executes any pending payload for guild_id without waiting for debounce timer."""
        if guild_id in self._pending_tasks and not self._pending_tasks[guild_id].done():
            self._pending_tasks[guild_id].cancel()
            self._pending_tasks.pop(guild_id, None)

        payload = self._pending_payloads.pop(guild_id, {})
        if self._sync_callback and payload:
            logger.info(f"[ProfileSyncWorker] Executing forced immediate sync for guild {guild_id}")
            await self._sync_callback(guild_id, payload)

    def cancel_all(self):
        """Cancels all active debounce timers."""
        for guild_id, task in list(self._pending_tasks.items()):
            if not task.done():
                task.cancel()
        self._pending_tasks.clear()
        self._pending_payloads.clear()
