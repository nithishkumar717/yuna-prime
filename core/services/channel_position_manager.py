import asyncio
import logging
import random
from typing import Dict, Tuple, Optional
import discord

logger = logging.getLogger("yuna.channel_position_manager")


class ChannelPositionManager:
    """
    Debounced and Batched Channel Position Manager for YUNA.
    
    When multiple channels are deleted and recreated simultaneously (e.g. during an
    antinuke test, raid, or mass delete), individually calling channel.edit(position=...)
    fires multiple PATCH /guilds/{guild_id}/channels calls at the same second, instantly
    exhausting Discord's strict per-guild channel position rate limit (resulting in 429s).
    
    This service accumulates desired channel positions per guild over a 1.5-second debounce
    window and executes a single batched guild.edit_channel_positions(...) API request.
    If Discord returns a 429, it applies jittered backoff rather than a synchronized thundering herd.
    """

    _instance: Optional["ChannelPositionManager"] = None

    @classmethod
    def get_instance(cls) -> "ChannelPositionManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, debounce_delay: float = 1.5):
        # Structure: {guild_id: {channel_obj: target_position}}
        self._pending_positions: Dict[int, Dict[discord.abc.GuildChannel, int]] = {}
        # Structure: {guild_id: asyncio.Task}
        self._flush_tasks: Dict[int, asyncio.Task] = {}
        # Structure: {guild_id: asyncio.Lock}
        self._guild_locks: Dict[int, asyncio.Lock] = {}
        self.debounce_delay = debounce_delay

    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._guild_locks:
            self._guild_locks[guild_id] = asyncio.Lock()
        return self._guild_locks[guild_id]

    def queue_reposition(self, guild: discord.Guild, channel: discord.abc.GuildChannel, target_position: int):
        """
        Enqueues a channel for repositioning. Accumulates in memory and schedules a batched flush.
        """
        if not guild or not channel or target_position is None:
            return

        guild_id = guild.id
        if guild_id not in self._pending_positions:
            self._pending_positions[guild_id] = {}

        self._pending_positions[guild_id][channel] = target_position

        # Schedule or reset the debounce timer
        if guild_id in self._flush_tasks and not self._flush_tasks[guild_id].done():
            self._flush_tasks[guild_id].cancel()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        self._flush_tasks[guild_id] = loop.create_task(self._delayed_flush(guild))

    async def _delayed_flush(self, guild: discord.Guild):
        """Waits for the debounce interval, then flushes all queued channel positions in a single batch."""
        try:
            await asyncio.sleep(self.debounce_delay)
        except asyncio.CancelledError:
            return

        guild_id = guild.id
        lock = self._get_lock(guild_id)

        async with lock:
            positions_to_apply = self._pending_positions.pop(guild_id, {})
            if not positions_to_apply:
                return

            # Filter out any deleted or non-existent channels
            valid_positions = {}
            for ch, pos in positions_to_apply.items():
                if ch in guild.channels:
                    valid_positions[ch] = pos

            if not valid_positions:
                return

            payload = [{"id": ch.id, "position": pos} for ch, pos in valid_positions.items()]
            for attempt in range(3):
                try:
                    # Single Discord API request: PATCH /guilds/{guild_id}/channels via raw REST
                    await guild._state.http.bulk_channel_update(
                        guild.id,
                        payload,
                        reason="[Anti-Nuke] Batched Channel Reposition"
                    )
                    logger.info(f"Successfully applied batched channel positions for {len(valid_positions)} channels in guild {guild_id}")
                    break
                except discord.Forbidden:
                    logger.warning(f"Missing permissions to edit channel positions in guild {guild_id}")
                    break
                except discord.HTTPException as e:
                    if e.status == 429:
                        retry_after = float(e.response.headers.get("Retry-After", 1.0))
                        jitter = random.uniform(0.1, 0.5)
                        await asyncio.sleep(retry_after + jitter)
                    else:
                        logger.warning(f"HTTPException updating channel positions in guild {guild_id}: {e}")
                        break
                except Exception as ex:
                    logger.debug(f"[CHANNEL POSITION] Bulk update fallback to individual edits: {ex}")
                    for ch, pos in valid_positions.items():
                        try:
                            await ch.edit(position=pos, reason="[Anti-Nuke] Channel Reposition Fallback")
                            await asyncio.sleep(0.2)
                        except Exception:
                            pass
                    break


# Singleton instance
channel_position_manager = ChannelPositionManager.get_instance()
