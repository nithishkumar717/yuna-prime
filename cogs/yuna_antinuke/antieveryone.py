import discord
from discord.ext import commands
import asyncio
from datetime import timedelta
from utils.Tools import slow_delete_message, send_antinuke_log
from core.cache.security_cache import security_cache
from core.database.connection_pool import db_pool
from core.metrics.security_metrics import security_metrics
from core.antinuke_v2.router import v2_engine_router, EngineMode


class AntiEveryone(commands.Cog):
    """AntiEveryone cog with selectable punishment (Default: None).
    If punishment is set to 'None' (default), no action or rate-limit penalties occur.
    If explicitly set to Mute/Kick/Ban in AutoMod, executes with rate-limit-safe slow delete.
    """
    def __init__(self, bot):
        self.bot = bot

    async def get_punishment(self, guild_id: int):
        try:
            row = await db_pool.fetch_one(
                "db/automod.db",
                "SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti everyone'",
                (guild_id,)
            )
            return row[0] if row else "None"
        except Exception:
            return "None"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or not message.mention_everyone:
            return

        guild = message.guild
        author = message.author

        is_am_on = security_cache.is_automod_enabled(guild.id)
        is_an_action_on = security_cache.is_action_enabled(guild.id, "antiEveryoneMention")
        if not is_am_on and not is_an_action_on:
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_everyone_mention(message)
            return

        trace = security_metrics.create_trace(
            event_type="mention_everyone",
            guild_id=guild.id,
            processing_path="entity_listener"
        )
        trace.record_stage("started")

        # Check configured punishment in AutoMod (Default is "None" -> No action taken)
        punishment = await self.get_punishment(guild.id)
        trace.record_stage("policy_checked")

        if not punishment or punishment in ("None", "Disabled", "Off"):
            trace.finish(result="punishment_disabled")
            return

        # Whitelist / Owner immunity
        if security_cache.is_immune(guild, author):
            trace.finish(result="skipped_immune")
            return

        # Check ignored channels & roles from AutoMod
        try:
            rows = await db_pool.fetch_all(
                "db/automod.db",
                "SELECT type, id FROM automod_ignored WHERE guild_id = ?",
                (guild.id,)
            )
            for itype, iid in rows:
                if itype == "channel" and message.channel.id == iid:
                    trace.finish(result="ignored_channel")
                    return
                if itype == "role" and any(r.id == iid for r in getattr(author, "roles", [])):
                    trace.finish(result="ignored_role")
                    return
                if itype == "user" and author.id == iid:
                    trace.finish(result="ignored_user")
                    return
        except Exception:
            pass

        trace.record_stage("threat_decision_completed")
        trace.record_stage("containment_dispatched")

        # Execute AutoMod punishment with custom message and logging
        from cogs.yuna_automod.executor import execute_automod_action
        await execute_automod_action(
            self.bot,
            guild,
            author,
            message.channel,
            message,
            'Anti everyone',
            'Unauthorized @everyone/@here mass ping'
        )
        trace.record_stage("containment_completed")
        trace.finish(result="containment_dispatched")
