import discord
from discord.ext import commands
import asyncio
from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_audit_fetch
from core.metrics.security_metrics import security_metrics
from core.antinuke_v2.router import v2_engine_router, EngineMode


class AntiChannelDelete(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, guild, executor, action_col="chdl"):
        try:
            return await security_cache.check_executor_permission(guild, executor, action_col)
        except Exception:
            return security_cache.is_immune(guild, executor)

    async def fetch_audit_logs(self, guild, action, target_id, max_retries=6):
        return await guarded_audit_fetch(guild, action, target_id, max_retries)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = getattr(channel, "guild", None)
        if not guild or not guild.me or not guild.me.guild_permissions.ban_members or not guild.me.guild_permissions.view_audit_log:
            return

        # Fast-Path: 0ms in-memory check if antinuke or chdl is enabled
        if not security_cache.is_action_enabled(guild.id, "chdl"):
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_channel_delete(channel)
            return

        trace = security_metrics.create_trace(
            event_type="guild_channel_delete",
            guild_id=guild.id,
            processing_path="entity_listener"
        )
        trace.record_stage("started")
        trace.record_stage("policy_checked")

        from core.security.incident_coordinator import security_coordinator

        # Coordinated micro-yield: Await AuditStreamAntiNuke to signal in <1-5ms instead of fixed 25ms delay.
        # If audit stream already handled it, wakes up immediately with zero REST calls!
        stream_incident = await security_coordinator.wait_for_stream(guild.id, "chdl", channel.id, timeout=0.010)

        if stream_incident and stream_incident.is_handled:
            trace.record_stage("threat_decision_completed")
            ban_success = await stream_incident.wait_for_ban(timeout=1.0)
            trace.record_stage("containment_completed")
            if ban_success and security_coordinator.mark_recovered(guild.id, "chdl", channel.id):
                await self.recreate_channel(channel)
                trace.record_stage("recovery_completed")
            trace.finish(result="handled_by_audit_stream")
            return

        trace.record_stage("audit_attribution_started")
        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.channel_delete, channel.id)
        trace.record_stage("audit_attribution_completed")

        if logs is None:
            trace.finish(result="no_audit_entry")
            return

        executor = logs.user or (discord.Object(id=logs.user_id) if getattr(logs, "user_id", None) else None)
        if not executor or security_cache.is_immune(guild, executor):
            trace.finish(result="skipped_immune")
            return

        is_allowed = await self.check_permissions(guild, executor, "chdl")
        trace.record_stage("threat_decision_completed")
        if is_allowed:
            trace.finish(result="authorized_executor")
            return

        claimed, inc = security_coordinator.claim_incident(guild.id, "chdl", channel.id, "entity_listener", executor.id)

        # 1. IMMEDIATE INSTANT BAN (Priority #1 - Neutralize offender FIRST)
        is_category = getattr(channel, "type", None) == discord.ChannelType.category
        item_type = "Category" if is_category else "Channel"
        trace.record_stage("containment_dispatched")
        ban_success = await self.instant_ban(guild, executor, f"{item_type} Delete | Unwhitelisted User")
        trace.record_stage("containment_completed")
        security_coordinator.set_ban_result(guild.id, "chdl", channel.id, ban_success)

        # 2. ONLY proceed with recovery IF the offender was successfully banned!
        # If ban failed (e.g. role hierarchy / missing permissions), DO NOT recreate the channel,
        # otherwise rival security bots will flag Yuna as rogue and ban Yuna.
        if ban_success and security_coordinator.mark_recovered(guild.id, "chdl", channel.id):
            await self.recreate_channel(channel)
            trace.record_stage("recovery_completed")
            action_msg = f"Instant Banned Offender & Recreated {item_type}"
        else:
            action_msg = f"Ban Failed (Role Hierarchy) - Preserved Entity to Prevent Rogue Flag"

        # 3. Send security log
        if security_coordinator.mark_logged(guild.id, "chdl", channel.id):
            name_str = channel.name if is_category else f"#{channel.name}"
            asyncio.create_task(send_antinuke_log(guild, f"Anti {item_type} Delete", executor, action_msg, details=f"Deleted {item_type}: {name_str}"))
        trace.finish(result="containment_dispatched" if ban_success else "containment_failed")

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)

    async def recreate_channel(self, channel):
        guild = getattr(channel, "guild", None)
        if not guild:
            return None
        from core.services.channel_snapshot import channel_snapshot_manager
        new_channel = await channel_snapshot_manager.restore_channel_safely(
            channel,
            reason="[Anti-Nuke] Auto-Restore Deleted Channel"
        )
        if new_channel and hasattr(channel, "position") and getattr(channel, "type", None) != discord.ChannelType.category:
            from core.services.channel_position_manager import channel_position_manager
            channel_position_manager.queue_reposition(guild, new_channel, channel.position)
        return new_channel
