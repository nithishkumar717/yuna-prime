import discord
from discord.ext import commands
import asyncio
from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_audit_fetch
from core.metrics.security_metrics import security_metrics
from core.antinuke_v2.router import v2_engine_router, EngineMode


class AntiPrune(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, guild, executor, action_col="prune"):
        try:
            return await security_cache.check_executor_permission(guild, executor, action_col)
        except Exception:
            return security_cache.is_immune(guild, executor)

    async def fetch_audit_logs(self, guild, action, max_retries=6):
        return await guarded_audit_fetch(guild, action, max_retries=max_retries)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = getattr(member, "guild", None)
        if not guild or not guild.me or not guild.me.guild_permissions.ban_members or not guild.me.guild_permissions.view_audit_log:
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_member_prune(member)
            return

        # Fast-Path: 0ms in-memory check if antinuke or prune is enabled
        if not security_cache.is_action_enabled(guild.id, "prune"):
            return

        trace = security_metrics.create_trace(
            event_type="member_remove",
            guild_id=guild.id,
            processing_path="entity_listener"
        )
        trace.record_stage("started")
        trace.record_stage("policy_checked")

        trace.record_stage("audit_attribution_started")
        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.member_prune)
        trace.record_stage("audit_attribution_completed")

        if logs is None:
            trace.finish(result="no_audit_entry")
            return

        executor = logs.user or (discord.Object(id=logs.user_id) if getattr(logs, "user_id", None) else None)
        if not executor or security_cache.is_immune(guild, executor):
            trace.finish(result="skipped_immune")
            return

        is_allowed = await self.check_permissions(guild, executor, "prune")
        trace.record_stage("threat_decision_completed")
        if is_allowed:
            trace.finish(result="authorized_executor")
            return

        # 1. IMMEDIATE INSTANT BAN (Priority #1)
        trace.record_stage("containment_dispatched")
        ban_success = await self.instant_ban(guild, executor, "Server Member Prune | Unwhitelisted User")
        trace.record_stage("containment_completed")

        # 2. Concurrently send security log
        action_msg = "Instant Banned Offender for Unauthorized Member Prune" if ban_success else "Attempted Ban for Member Prune"
        asyncio.create_task(send_antinuke_log(guild, "Anti Prune", executor, action_msg))
        trace.finish(result="containment_dispatched" if ban_success else "containment_failed")

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)
