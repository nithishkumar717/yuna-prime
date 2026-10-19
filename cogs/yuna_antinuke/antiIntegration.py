import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz

from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_audit_fetch
from core.antinuke_v2.router import v2_engine_router, EngineMode

class AntiIntegration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, guild, executor, action_col="serverup"):
        try:
            return await security_cache.check_executor_permission(guild, executor, action_col)
        except Exception:
            return security_cache.is_immune(guild, executor)

    async def fetch_audit_logs(self, guild, action, max_retries=6):
        return await guarded_audit_fetch(guild, action, max_retries=max_retries)

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild):
        if not guild:
            return
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_integration_update(guild)
            return
        return

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)
