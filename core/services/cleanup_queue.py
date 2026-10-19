import asyncio
import logging
from typing import Dict, Any, Optional
import discord

logger = logging.getLogger("yuna.cleanup_queue")


class EntityCleanupQueue:
    """
    Asynchronous rate-limited queue for cleaning up unauthorized entities
    (spam channels, spam roles, rogue bot accounts) created during attacks.
    Prevents Discord HTTP 429 rate-limit locks by spacing deletions cleanly.
    """

    def __init__(self, min_interval: float = 0.35):
        self.min_interval = min_interval
        self._queues: Dict[int, asyncio.Queue] = {}
        self._workers: Dict[int, asyncio.Task] = {}

    def enqueue_channel_delete(self, channel: discord.abc.GuildChannel, reason: str = "[Anti-Nuke] Auto-Delete Unauthorized Channel"):
        """Queue a channel for rate-spaced deletion."""
        guild = getattr(channel, "guild", None)
        if not guild:
            return
        self._enqueue(guild.id, ("channel", channel, reason))

    def enqueue_role_delete(self, role: discord.Role, reason: str = "[Anti-Nuke] Auto-Delete Unauthorized Role"):
        """Queue a role for rate-spaced deletion."""
        guild = getattr(role, "guild", None)
        if not guild:
            return
        self._enqueue(guild.id, ("role", role, reason))

    def enqueue_member_kick(self, member: discord.Member, reason: str = "[Anti-Nuke] Auto-Kick Unauthorized Bot"):
        """Queue an unauthorized member/bot for rate-spaced kick."""
        guild = getattr(member, "guild", None)
        if not guild:
            return
        self._enqueue(guild.id, ("kick", member, reason))

    def _enqueue(self, guild_id: int, item: tuple):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if guild_id not in self._queues:
            self._queues[guild_id] = asyncio.Queue()

        self._queues[guild_id].put_nowait(item)

        if guild_id not in self._workers or self._workers[guild_id].done():
            self._workers[guild_id] = loop.create_task(self._worker(guild_id))

    async def _worker(self, guild_id: int):
        q = self._queues.get(guild_id)
        if not q:
            return

        while not q.empty():
            action, entity, reason = await q.get()
            try:
                if action == "channel":
                    await self._delete_channel(entity, reason)
                elif action == "role":
                    await self._delete_role(entity, reason)
                elif action == "kick":
                    await self._kick_member(entity, reason)
            except Exception as e:
                logger.debug(f"[CLEANUP QUEUE] Error during {action} cleanup in guild {guild_id}: {e}")
            finally:
                q.task_done()

            # Enforce minimum spacing between entity mutations
            await asyncio.sleep(self.min_interval)

    async def _delete_channel(self, channel: discord.abc.GuildChannel, reason: str):
        for attempt in range(3):
            try:
                await channel.delete(reason=reason)
                return True
            except discord.NotFound:
                return True
            except discord.Forbidden:
                logger.warning(f"[CLEANUP QUEUE] Forbidden to delete channel {channel.id}")
                return False
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(e.response.headers.get("Retry-After", 1.0)) if hasattr(e, "response") and e.response else 1.0
                    await asyncio.sleep(retry_after + 0.1)
                else:
                    return False
            except Exception:
                return False
        return False

    async def _delete_role(self, role: discord.Role, reason: str):
        for attempt in range(3):
            try:
                await role.delete(reason=reason)
                return True
            except discord.NotFound:
                return True
            except discord.Forbidden:
                logger.warning(f"[CLEANUP QUEUE] Forbidden to delete role {role.id}")
                return False
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(e.response.headers.get("Retry-After", 1.0)) if hasattr(e, "response") and e.response else 1.0
                    await asyncio.sleep(retry_after + 0.1)
                else:
                    return False
            except Exception:
                return False
        return False

    async def _kick_member(self, member: discord.Member, reason: str):
        for attempt in range(3):
            try:
                await member.kick(reason=reason)
                return True
            except discord.NotFound:
                return True
            except discord.Forbidden:
                logger.warning(f"[CLEANUP QUEUE] Forbidden to kick member {member.id}")
                return False
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(e.response.headers.get("Retry-After", 1.0)) if hasattr(e, "response") and e.response else 1.0
                    await asyncio.sleep(retry_after + 0.1)
                else:
                    return False
            except Exception:
                return False
        return False


entity_cleanup_queue = EntityCleanupQueue()
