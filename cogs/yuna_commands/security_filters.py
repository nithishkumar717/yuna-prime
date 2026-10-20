"""Standalone prefix commands for configuring the existing AutoMod filters."""
from __future__ import annotations

import logging

import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check

logger = logging.getLogger(__name__)

FILTERS = {
    "antispam": "Anti spam",
    "antilink": "Anti link",
    "antiinvite": "Anti invites",
    "anticaps": "Anti caps",
    "antimention": "Anti mass mention",
    "antiemoji": "Anti emoji spam",
}

DEFAULT_THRESHOLDS = {
    "Anti spam": 5,
    "Anti link": 1,
    "Anti invites": 1,
    "Anti caps": 70,
    "Anti mass mention": 5,
    "Anti emoji spam": 5,
}


class SecurityFilterCommands(commands.Cog):
    """Expose simple prefix controls over the existing AutoMod rule pipeline."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _run_filter_command(self, ctx: commands.Context, event: str, action: str | None):
        action = (action or "config").strip().lower()
        if action in {"on", "start", "enable"}:
            action = "enable"
        elif action in {"off", "stop", "disable"}:
            action = "disable"
        elif action in {"status", "show", "settings"}:
            action = "config"

        if action not in {"enable", "disable", "config"}:
            return await ctx.send(
                f"Usage: `{ctx.prefix}{ctx.command.qualified_name} enable|disable|config`"
            )

        guild_id = ctx.guild.id
        try:
            from cogs.yuna_automod.cache import automod_cache

            if action == "config":
                enabled = await automod_cache.is_rule_enabled(guild_id, event)
                punishment = await automod_cache.get_punishment(guild_id, event)
                from cogs.yuna_automod.executor import get_threshold

                threshold = await get_threshold(guild_id, event, DEFAULT_THRESHOLDS[event])
                return await ctx.send(
                    f"**{event}** is `{ 'enabled' if enabled else 'disabled' }`\n"
                    f"Action: `{punishment or 'not configured'}` · Threshold: `{threshold}`\n"
                    f"Manage it with `{ctx.prefix}{ctx.command.qualified_name} enable` or `disable`."
                )

            async with aiosqlite.connect("db/automod.db", timeout=5.0) as db:
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS automod (guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0)"
                )
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS automod_punishments ("
                    "guild_id INTEGER, event TEXT, punishment TEXT, PRIMARY KEY (guild_id, event))"
                )
                if action == "enable":
                    await db.execute(
                        "INSERT INTO automod (guild_id, enabled) VALUES (?, 1) "
                        "ON CONFLICT(guild_id) DO UPDATE SET enabled=1",
                        (guild_id,),
                    )
                    # Preserve a server's configured punishment; safe-delete is the default.
                    await db.execute(
                        "INSERT OR IGNORE INTO automod_punishments (guild_id, event, punishment) VALUES (?, ?, 'Delete')",
                        (guild_id, event),
                    )
                else:
                    # Change only this rule; preserve global AutoMod and peer filters.
                    await db.execute(
                        "INSERT INTO automod_punishments (guild_id, event, punishment) VALUES (?, ?, 'Disabled') "
                        "ON CONFLICT(guild_id, event) DO UPDATE SET punishment='Disabled'",
                        (guild_id, event),
                    )
                await db.commit()

            if action == "enable":
                from utils.settings_manager import set_guild_setting

                set_guild_setting(guild_id, "automod", True)
            automod_cache.invalidate(guild_id)
            status = "enabled" if action == "enable" else "disabled"
            await ctx.send(f"✅ **{event}** {status}. Use `{ctx.prefix}{ctx.command.qualified_name} config` to view its settings.")
        except Exception:
            logger.exception("Failed to %s AutoMod rule %s in guild %s", action, event, guild_id)
            await ctx.send("I couldn't update that security filter. Check the bot logs and try again.")

    @commands.command(name="antispam", help="Configure Anti-Spam: enable, disable, or config.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def antispam(self, ctx: commands.Context, action: str = "config"):
        await self._run_filter_command(ctx, FILTERS["antispam"], action)

    @commands.command(name="antilink", help="Configure Anti-Link: enable, disable, or config.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def antilink(self, ctx: commands.Context, action: str = "config"):
        await self._run_filter_command(ctx, FILTERS["antilink"], action)

    @commands.command(name="antiinvite", help="Configure Anti-Invite: enable, disable, or config.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def antiinvite(self, ctx: commands.Context, action: str = "config"):
        await self._run_filter_command(ctx, FILTERS["antiinvite"], action)

    @commands.command(name="anticaps", help="Configure Anti-Caps: enable, disable, or config.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def anticaps(self, ctx: commands.Context, action: str = "config"):
        await self._run_filter_command(ctx, FILTERS["anticaps"], action)

    @commands.command(name="antimention", help="Configure Anti-Mass-Mention: enable, disable, or config.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def antimention(self, ctx: commands.Context, action: str = "config"):
        await self._run_filter_command(ctx, FILTERS["antimention"], action)

    @commands.command(name="antiemoji", help="Configure Anti-Emoji-Spam: enable, disable, or config.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def antiemoji(self, ctx: commands.Context, action: str = "config"):
        await self._run_filter_command(ctx, FILTERS["antiemoji"], action)


async def setup(bot: commands.Bot):
    await bot.add_cog(SecurityFilterCommands(bot))
