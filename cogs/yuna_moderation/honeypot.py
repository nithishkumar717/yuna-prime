"""Runtime enforcement for the dashboard-configured honeypot."""

from __future__ import annotations

import os
import time
from datetime import timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks
from ui.honeypot import add_honeypot_reactions, build_honeypot_warning_view


DB_PATH = "db/honeypot.db"


class Honeypot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._config_cache = {}
        self._active_channels = {}
        os.makedirs("db", exist_ok=True)
        self.expired_tempbans.start()

    def cog_unload(self):
        self.expired_tempbans.cancel()

    async def cog_load(self):
        await self.load_active_channels()

    async def _init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS honeypot_config (
                guild_id INTEGER PRIMARY KEY, channel_id INTEGER, action TEXT NOT NULL DEFAULT 'ban',
                duration INTEGER, warning TEXT NOT NULL DEFAULT '', caught_count INTEGER NOT NULL DEFAULT 0,
                warning_message_id INTEGER, enabled INTEGER NOT NULL DEFAULT 1,
                exempt_bots INTEGER NOT NULL DEFAULT 1
            )""")
            async with db.execute("PRAGMA table_info(honeypot_config)") as cursor:
                columns = {row[1] for row in await cursor.fetchall()}
            if "enabled" not in columns:
                await db.execute("ALTER TABLE honeypot_config ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
            if "exempt_bots" not in columns:
                await db.execute("ALTER TABLE honeypot_config ADD COLUMN exempt_bots INTEGER NOT NULL DEFAULT 1")
            await db.execute("""CREATE TABLE IF NOT EXISTS honeypot_exempt_roles (
                guild_id INTEGER NOT NULL, role_id INTEGER NOT NULL, PRIMARY KEY (guild_id, role_id)
            )""")
            await db.execute("""CREATE TABLE IF NOT EXISTS honeypot_tempbans (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )""")
            await db.commit()

    async def _config(self, guild_id: int):
        if guild_id in self._config_cache:
            return self._config_cache[guild_id]
        await self._init_db()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM honeypot_config WHERE guild_id = ?", (guild_id,)) as cursor:
                config = await cursor.fetchone()
        self._config_cache[guild_id] = config
        self.set_channel(guild_id, config["channel_id"] if config and config["enabled"] else None)
        return config

    async def load_active_channels(self):
        await self._init_db()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT guild_id, channel_id FROM honeypot_config WHERE enabled = 1 AND channel_id IS NOT NULL") as cursor:
                self._active_channels = {guild_id: channel_id for guild_id, channel_id in await cursor.fetchall()}

    def set_channel(self, guild_id: int, channel_id: int | None):
        if channel_id:
            self._active_channels[guild_id] = channel_id
        else:
            self._active_channels.pop(guild_id, None)

    def is_honeypot_channel(self, guild_id: int, channel_id: int) -> bool:
        return self._active_channels.get(guild_id) == channel_id

    def invalidate_config(self, guild_id: int):
        self._config_cache.pop(guild_id, None)

    async def _refresh_warning(self, guild: discord.Guild):
        config = await self._config(guild.id)
        if not config or not config["channel_id"]:
            return
        channel = guild.get_channel(config["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return
        warning = config["warning"] or (
            "🚫 **DO NOT POST HERE**\n\n"
            "This channel is a trap for compromised accounts spreading scams. "
            "Any message here triggers automatic moderation.\n\n"
            "`{honeypot.count}` accounts caught so far."
        )
        content = warning.replace("{honeypot.count}", str(config["caught_count"]))
        view = build_honeypot_warning_view(content)
        message = None
        if config["warning_message_id"]:
            try:
                message = await channel.fetch_message(config["warning_message_id"])
                await message.edit(view=view, allowed_mentions=discord.AllowedMentions.none())
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                message = None
        if message is None:
            try:
                message = await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())
                try:
                    await message.pin(reason="Yuna honeypot warning")
                except (discord.Forbidden, discord.HTTPException):
                    pass
            except (discord.Forbidden, discord.HTTPException):
                return
        await add_honeypot_reactions(message)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE honeypot_config SET warning_message_id = ? WHERE guild_id = ?", (message.id, guild.id))
            await db.commit()

    async def process_honeypot_message(self, message: discord.Message):
        if not message.guild:
            return
        config = await self._config(message.guild.id)
        if not config or not config["enabled"] or not config["channel_id"] or message.channel.id != config["channel_id"]:
            return
        member = message.author
        if not isinstance(member, discord.Member):
            return
        from utils.config import SIBLING_BOT_IDS
        if member.id == getattr(self.bot.user, "id", None) or member.id in SIBLING_BOT_IDS:
            return


        # Remove every visitor post immediately; exceptions below only bypass
        # punishment, never deletion. No message is sent back into the trap.
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        if member.bot and config["exempt_bots"]:
            return
        if member.guild_permissions.administrator:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM honeypot_exempt_roles WHERE guild_id = ?", (message.guild.id,)) as cursor:
                exempt_ids = {row[0] for row in await cursor.fetchall()}
        if any(role.id in exempt_ids for role in member.roles):
            return

        reason = "Posted in the honeypot trap channel"
        try:
            if config["action"] == "ban":
                await member.ban(reason=reason, delete_message_seconds=0)
                if config["duration"]:
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("INSERT OR REPLACE INTO honeypot_tempbans VALUES (?, ?, ?)",
                                         (message.guild.id, member.id, int(time.time()) + config["duration"]))
                        await db.commit()
            elif config["action"] == "kick":
                await member.kick(reason=reason)
            elif config["action"] == "timeout" and config["duration"]:
                await member.timeout(discord.utils.utcnow() + timedelta(seconds=config["duration"]), reason=reason)
            else:
                return
        except (discord.Forbidden, discord.HTTPException):
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE honeypot_config SET caught_count = caught_count + 1 WHERE guild_id = ?", (message.guild.id,))
            await db.commit()
        self.invalidate_config(message.guild.id)
        await self._refresh_warning(message.guild)

    @tasks.loop(seconds=60)
    async def expired_tempbans(self):
        await self._init_db()
        now = int(time.time())
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT guild_id, user_id FROM honeypot_tempbans WHERE expires_at <= ?", (now,)) as cursor:
                expired = await cursor.fetchall()
        for guild_id, user_id in expired:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            try:
                try:
                    await guild.unban(discord.Object(id=user_id), reason="Yuna honeypot temporary ban expired")
                except discord.NotFound:
                    pass
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("DELETE FROM honeypot_tempbans WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
                    await db.commit()
            except (discord.Forbidden, discord.HTTPException):
                # Retain the row so a temporary ban can be retried after permissions recover.
                continue

    @expired_tempbans.before_loop
    async def before_expired_tempbans(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Honeypot(bot))
