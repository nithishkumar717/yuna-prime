import discord
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import timedelta
import time
import json
from typing import List, Dict
from core.discord.request_manager import request_manager, Priority
from core.logging.log_aggregator import log_aggregator


class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_threshold = 5
        self.mute_duration = 12 * 60
        self.recent_messages = {}
        self._active_incidents = set()

        # External App Spam Control State
        # Structure: {guild_id: [{author_id, content, is_external, timestamp, message_obj}]}
        self.external_app_history: Dict[int, List[dict]] = {}
        self.external_app_cooldowns: Dict[int, float] = {}  # {guild_id: unlock_timestamp}
        self.locked_roles: Dict[int, List[int]] = {}       # {guild_id: [role_id, ...]}
        self.channel_delete_counts: Dict[int, int] = {}    # {channel_id: delete_count}
        self.MAX_PER_CHANNEL_DELETE_LIMIT = 100
        self._delete_queue = asyncio.Queue()
        self._delete_worker_task = asyncio.create_task(self._slow_delete_worker())
        asyncio.create_task(self._init_active_lockdowns())

    async def safe_enqueue_delete(self, message: discord.Message):
        """Enqueues spam message for safe slow deletion up to a strict cap of 100 messages per channel to prevent rate limits."""
        if not message or not getattr(message, 'channel', None):
            return
        chan_id = message.channel.id
        current_count = self.channel_delete_counts.get(chan_id, 0)
        if current_count >= self.MAX_PER_CHANNEL_DELETE_LIMIT:
            return  # Cap of 100 per channel reached, skip adding to queue to avoid rate limits
        self.channel_delete_counts[chan_id] = current_count + 1
        await self._delete_queue.put(message)

    async def _init_active_lockdowns(self):
        try:
            await self.bot.wait_until_ready()
        except Exception:
            pass
        try:
            async with aiosqlite.connect("db/automod.db") as db:
                async with db.execute("SELECT guild_id, locked_roles, unlock_timestamp, channel_id FROM external_app_lockdown") as cursor:
                    rows = await cursor.fetchall()
                    for gid, roles_json, unlock_ts, chan_id in rows:
                        role_ids = json.loads(roles_json) if roles_json else []
                        self.locked_roles[gid] = role_ids
                        self.external_app_cooldowns[gid] = unlock_ts
                        remaining = max(5.0, unlock_ts - time.time())
                        asyncio.create_task(self._auto_restore_external_apps(gid, remaining, chan_id))
        except Exception:
            pass

    async def _slow_delete_worker(self):
        """Worker that deletes external bot/spam messages sequentially with a 1.0s confirmed delay."""
        while True:
            try:
                message = await self._delete_queue.get()
                if message:
                    try:
                        # Await API confirmation of message deletion
                        await message.delete()
                    except Exception:
                        pass
                    # Confirmed 1.0 second delay after deletion before deleting next message
                    await asyncio.sleep(1.0)
                self._delete_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    async def is_automod_enabled(self, guild_id):
        from cogs.yuna_automod.cache import automod_cache
        return await automod_cache.is_automod_enabled(guild_id)

    async def is_anti_spam_enabled(self, guild_id):
        from cogs.yuna_automod.cache import automod_cache
        return await automod_cache.is_rule_enabled(guild_id, "Anti spam")

    async def get_ignored_channels(self, guild_id):
        from cogs.yuna_automod.cache import automod_cache
        return await automod_cache.get_ignored_channels(guild_id)

    async def get_ignored_roles(self, guild_id):
        from cogs.yuna_automod.cache import automod_cache
        return await automod_cache.get_ignored_roles(guild_id)

    async def get_punishment(self, guild_id):
        from cogs.yuna_automod.cache import automod_cache
        return await automod_cache.get_punishment(guild_id, "Anti spam")

    async def log_action(self, guild, user, channel, action, reason):
        log_aggregator.log_event(
            guild_id=guild.id,
            action_type=f"Anti-Spam Action ({action})",
            executor=user,
            details=f"Channel: <#{channel.id}> | Reason: {reason}"
        )

    async def is_bot_spam_enabled(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS bot_spam_protection (guild_id TEXT PRIMARY KEY, enabled BOOLEAN DEFAULT 1)")
            await db.commit()
            cursor = await db.execute("SELECT enabled FROM bot_spam_protection WHERE guild_id = ?", (str(guild_id),))
            row = await cursor.fetchone()
            return bool(row and row[0] == 1)

    def _schedule_incident_clear(self, user_id: int, delay: float = 10.0):
        async def _clear():
            await asyncio.sleep(delay)
            self._active_incidents.discard(user_id)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_clear())
        except Exception:
            self._active_incidents.discard(user_id)

    async def get_threshold(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT threshold FROM automod_thresholds WHERE guild_id = ? AND event = 'Anti spam'", (guild_id,))
            result = await cursor.fetchone()
            return result[0] if (result and result[0]) else 5

    async def check_spam(self, message: discord.Message) -> bool:
        guild = message.guild
        guild_id = guild.id
        user = message.author
        channel = message.channel

        if not await self.is_automod_enabled(guild_id) or not await self.is_anti_spam_enabled(guild_id):
            return False

        current_time = message.created_at.timestamp()
        user_key = (guild_id, user.id)
        user_messages = self.recent_messages.get(user_key, [])
        user_messages = [msg for msg in user_messages if current_time - msg < 10]
        user_messages.append(current_time)
        self.recent_messages[user_key] = user_messages

        from cogs.yuna_automod.executor import execute_automod_action, get_threshold
        threshold = await get_threshold(guild_id, 'Anti spam', 5)

        if len(user_messages) >= threshold:
            await self.safe_enqueue_delete(message)

            if user_key in self._active_incidents:
                return True

            self._active_incidents.add(user_key)
            self._schedule_incident_clear(user_key, delay=10.0)

            async def _handle_user_punishment():
                await execute_automod_action(self.bot, guild, user, channel, None, 'Anti spam', 'Message Spam')

            await request_manager.enqueue(
                priority=Priority.P1_HIGH,
                task_id=f"user_spam_punish_{guild_id}_{user.id}_{time.time()}",
                coro_func=_handle_user_punishment,
                guild_id=guild_id
            )
            return True
        return False

    async def on_message(self, message):
        # Centralized in cogs.yuna_automod.pipeline
        pass
