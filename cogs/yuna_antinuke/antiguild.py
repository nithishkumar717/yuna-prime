import discord
from discord.ext import commands
import asyncio
from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_audit_fetch
from core.metrics.security_metrics import security_metrics
from core.antinuke_v2.router import v2_engine_router, EngineMode


class AntiGuildUpdate(commands.Cog):
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
    async def on_guild_update(self, before, after):
        guild = before
        if not guild or not guild.me or not guild.me.guild_permissions.ban_members or not guild.me.guild_permissions.view_audit_log:
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(before.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_guild_update(before, after)
            return

        # Fast-Path: 0ms in-memory check if antinuke or serverup is enabled
        if not security_cache.is_action_enabled(guild.id, "serverup"):
            return

        trace = security_metrics.create_trace(
            event_type="guild_update",
            guild_id=guild.id,
            processing_path="entity_listener"
        )
        trace.record_stage("started")
        trace.record_stage("policy_checked")

        trace.record_stage("audit_attribution_started")
        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.guild_update)
        trace.record_stage("audit_attribution_completed")

        if logs is None:
            trace.finish(result="no_audit_entry")
            return

        executor = logs.user or (discord.Object(id=logs.user_id) if getattr(logs, "user_id", None) else None)
        if not executor or security_cache.is_immune(guild, executor):
            trace.finish(result="skipped_immune")
            return

        is_allowed = await self.check_permissions(guild, executor, "serverup")
        trace.record_stage("threat_decision_completed")
        if is_allowed:
            trace.finish(result="authorized_executor")
            return

        # 1. IMMEDIATE INSTANT BAN (Priority #1 - Neutralize offender FIRST)
        trace.record_stage("containment_dispatched")
        ban_success = await self.instant_ban(guild, executor, "Guild Update | Unwhitelisted User")
        trace.record_stage("containment_completed")

        # 2. ONLY proceed with recovery IF the offender was successfully banned!
        # If ban failed (e.g. role hierarchy / missing permissions), DO NOT revert guild settings,
        # otherwise rival security bots will flag Yuna as rogue and ban Yuna.
        if ban_success:
            await self.revert_guild(before, after)
            trace.record_stage("recovery_completed")
            action_msg = "Instant Banned Offender & Reverted Guild Settings"
        else:
            action_msg = "Ban Failed (Role Hierarchy) - Preserved Entity to Prevent Rogue Flag"

        # 3. Send security log
        asyncio.create_task(send_antinuke_log(guild, "Anti Guild Update", executor, action_msg, details=f"Server: {after.name}"))
        trace.finish(result="containment_dispatched" if ban_success else "containment_failed")

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)

    async def revert_guild(self, before, after):
        try:
            kwargs = {"reason": "[Anti-Nuke] Reverting Unauthorized Guild Changes"}
            if before.name != after.name:
                kwargs["name"] = before.name
            if before.verification_level != after.verification_level:
                kwargs["verification_level"] = before.verification_level
            if before.default_notifications != after.default_notifications:
                kwargs["default_notifications"] = before.default_notifications
            if before.explicit_content_filter != after.explicit_content_filter:
                kwargs["explicit_content_filter"] = before.explicit_content_filter
            await after.edit(**kwargs)
        except Exception:
            pass
