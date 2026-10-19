import asyncio
import logging
import time
import random
from typing import Dict, List, Optional
import discord
from services.log_components_v2 import build_log_v2_views

logger = logging.getLogger("yuna.log_dispatcher")


class ChannelLogDispatcher:
    """
    Rate-Limit Immune Log Dispatcher for YUNA.
    
    Discord strictly limits messages in a channel to 5 messages per 5 seconds.
    During an antinuke test, raid, or mass security event, multiple cogs and tasks
    fire rapid security alerts, easily exceeding the per-channel limit and triggering
    an avalanche of HTTP 429 rate limit warnings.
    
    ChannelLogDispatcher solves this by:
    1. Buffering outgoing log entries per channel in memory.
    2. Batching entries into compact Components V2 cards while respecting Discord's
       text and component limits.
    3. Enforcing a minimum 1.2-second interval between message dispatches per channel.
    4. Automatically handling 429 retries with backoff and jitter.
    """

    _instance: Optional["ChannelLogDispatcher"] = None

    @classmethod
    def get_instance(cls) -> "ChannelLogDispatcher":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, flush_interval: float = 1.0, min_send_interval: float = 1.2):
        # Structure: {channel_id: [discord.Embed, ...]} (converted to Components V2 at dispatch)
        self._buffers: Dict[int, List[discord.Embed]] = {}
        # Structure: {channel_id: discord.abc.Messageable}
        self._channels: Dict[int, discord.abc.Messageable] = {}
        # Structure: {channel_id: float (last dispatch timestamp)}
        self._last_send: Dict[int, float] = {}
        # Structure: {channel_id: asyncio.Task}
        self._flush_tasks: Dict[int, asyncio.Task] = {}
        # Structure: {channel_id: asyncio.Lock}
        self._channel_locks: Dict[int, asyncio.Lock] = {}
        # Structure: {channel_id: Optional[bool]}
        self._silent_prefs: Dict[int, bool] = {}
        
        self.flush_interval = flush_interval
        self.min_send_interval = min_send_interval

    def _get_lock(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self._channel_locks:
            self._channel_locks[channel_id] = asyncio.Lock()
        return self._channel_locks[channel_id]

    def enqueue_log(self, channel: discord.abc.Messageable, embed: discord.Embed, silent: Optional[bool] = None):
        """Enqueues an embed to be dispatched to the given channel."""
        if not channel or not embed or not hasattr(channel, "id"):
            return

        channel_id = channel.id
        self._channels[channel_id] = channel

        if channel_id not in self._buffers:
            self._buffers[channel_id] = []

        self._buffers[channel_id].append(embed)

        if silent is not None:
            self._silent_prefs[channel_id] = silent

        # Schedule or reset flush task
        if channel_id not in self._flush_tasks or self._flush_tasks[channel_id].done():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()

            self._flush_tasks[channel_id] = loop.create_task(self._process_channel(channel_id))

    async def _process_channel(self, channel_id: int):
        """Processes buffered log embeds for a specific channel until queue is drained."""
        lock = self._get_lock(channel_id)

        async with lock:
            # Small initial wait to allow micro-bursts to assemble into multi-embed batches
            await asyncio.sleep(0.3)

            while channel_id in self._buffers and self._buffers[channel_id]:
                channel = self._channels.get(channel_id)
                if not channel:
                    self._buffers.pop(channel_id, None)
                    break

                # Extract a burst; the formatter splits it by V2 character/component limits.
                buffer = self._buffers[channel_id]
                batch = buffer[:10]
                self._buffers[channel_id] = buffer[10:]

                if not batch:
                    break

                # Determine whether notifications should be suppressed
                ch_name = getattr(channel, "name", "").lower()
                is_security_alert = "antinuke" in ch_name or "security" in ch_name
                is_silent = self._silent_prefs.get(channel_id, not is_security_alert)
                allowed_mentions = discord.AllowedMentions.none() if is_silent else discord.AllowedMentions(everyone=True, roles=True, users=True)

                views = build_log_v2_views(batch, getattr(channel, "name", "server"))
                all_sent = bool(views)
                for view in views:
                    # Enforce inter-message spacing (token bucket: min 1.2s per channel).
                    now = time.time()
                    last = self._last_send.get(channel_id, 0.0)
                    elapsed = now - last
                    if elapsed < self.min_send_interval:
                        await asyncio.sleep(self.min_send_interval - elapsed)

                    sent = False
                    for attempt in range(3):
                        try:
                            await channel.send(view=view, silent=is_silent, allowed_mentions=allowed_mentions)
                            self._last_send[channel_id] = time.time()
                            sent = True
                            break
                        except discord.Forbidden:
                            logger.warning(f"Missing permissions to send logs in channel {channel_id}")
                            self._buffers.pop(channel_id, None)
                            return
                        except discord.NotFound:
                            logger.warning(f"Log channel {channel_id} not found")
                            self._buffers.pop(channel_id, None)
                            return
                        except discord.HTTPException as e:
                            if e.status == 429:
                                retry_after = float(e.response.headers.get("Retry-After", 1.0))
                                jitter = random.uniform(0.3, 0.8)
                                logger.info(f"Log channel {channel_id} 429 rate limit, sleeping {retry_after + jitter:.2f}s")
                                await asyncio.sleep(retry_after + jitter)
                            else:
                                logger.warning(f"HTTP error sending logs to {channel_id}: {e}")
                                break
                        except Exception as ex:
                            logger.warning(f"Error sending logs to {channel_id}: {ex}")
                            break

                    if not sent:
                        all_sent = False
                        break

                if not all_sent:
                    # Break loop on unrecoverable failure to prevent infinite retries
                    break

            # Clean up empty buffers
            if channel_id in self._buffers and not self._buffers[channel_id]:
                self._buffers.pop(channel_id, None)
                self._channels.pop(channel_id, None)


# Singleton instance
log_dispatcher = ChannelLogDispatcher.get_instance()
