import discord
from discord.ext import commands
import asyncio
from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_audit_fetch
from core.metrics.security_metrics import security_metrics
from core.antinuke_v2.router import v2_engine_router, EngineMode


class AntiChannelCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, guild, executor, action_col="chcr"):
        try:
            return await security_cache.check_executor_permission(guild, executor, action_col)
        except Exception:
            return security_cache.is_immune(guild, executor)

    async def fetch_audit_logs(self, guild, action, target_id, max_retries=6):
        return await guarded_audit_fetch(guild, action, target_id, max_retries)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild = getattr(channel, "guild", None)
        if not guild or not guild.me or not guild.me.guild_permissions.ban_members or not guild.me.guild_permissions.view_audit_log:
            return

        # Fast-Path: 0ms in-memory check if antinuke or chcr is enabled
        if not security_cache.is_action_enabled(guild.id, "chcr"):
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_channel_create(channel)
            return

        trace = security_metrics.create_trace(
            event_type="guild_channel_create",
            guild_id=guild.id,
            processing_path="entity_listener"
        )
        trace.record_stage("started")
        trace.record_stage("policy_checked")

        from core.security.incident_coordinator import security_coordinator

        # Coordinated micro-yield: Await AuditStreamAntiNuke to signal in <1-5ms instead of fixed 25ms delay.
        # If audit stream already handled it, wakes up immediately with zero REST calls!
        stream_incident = await security_coordinator.wait_for_stream(guild.id, "chcr", channel.id, timeout=0.010)

        if stream_incident and stream_incident.is_handled:
            trace.record_stage("threat_decision_completed")
            trace.record_stage("containment_completed")
            if stream_incident.ban_success and security_coordinator.mark_recovered(guild.id, "chcr", channel.id):
                await self.delete_channel(channel)
                trace.record_stage("recovery_completed")
            trace.finish(result="handled_by_audit_stream")
            return

        trace.record_stage("audit_attribution_started")
        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.channel_create, channel.id)
        trace.record_stage("audit_attribution_completed")

        if logs is None:
            trace.finish(result="no_audit_entry")
            return

        executor = logs.user or (discord.Object(id=logs.user_id) if getattr(logs, "user_id", None) else None)
        if not executor or security_cache.is_immune(guild, executor):
            trace.finish(result="skipped_immune")
            return

        is_allowed = await self.check_permissions(guild, executor, "chcr")
        trace.record_stage("threat_decision_completed")
        if is_allowed:
            from core.services.channel_snapshot import channel_snapshot_manager
            channel_snapshot_manager.snapshot_channel(channel)
            trace.finish(result="authorized_executor")
            return

        claimed, inc = security_coordinator.claim_incident(guild.id, "chcr", channel.id, "entity_listener", executor.id)

        # 1. IMMEDIATE INSTANT BAN (Priority #1 - Neutralize offender FIRST)
        trace.record_stage("containment_dispatched")
        ban_success = await self.instant_ban(guild, executor, "Channel Create | Unwhitelisted User")
        trace.record_stage("containment_completed")
        security_coordinator.set_ban_result(guild.id, "chcr", channel.id, ban_success)

        # 2. ONLY proceed with recovery IF the offender was successfully banned!
        # If ban failed (e.g. role hierarchy / missing permissions), DO NOT delete the channel,
        # otherwise rival security bots (Olympus, Wick) will flag Yuna as rogue and ban Yuna.
        if ban_success and security_coordinator.mark_recovered(guild.id, "chcr", channel.id):
            await self.delete_channel(channel)
            trace.record_stage("recovery_completed")
            action_msg = "Instant Banned Offender & Deleted Rogue Channel"
        else:
            action_msg = "Ban Failed (Role Hierarchy) - Preserved Entity to Prevent Rogue Flag"

        # 3. Send security log
        if security_coordinator.mark_logged(guild.id, "chcr", channel.id):
            asyncio.create_task(send_antinuke_log(guild, "Anti Channel Create", executor, action_msg, details=f"Created Channel: #{channel.name}"))
        trace.finish(result="containment_dispatched" if ban_success else "containment_failed")

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)

    async def delete_channel(self, channel):
        try:
            await channel.delete(reason="[Anti-Nuke] Auto-Delete Unauthorized Channel")
        except discord.NotFound:
            pass
        except Exception:
            from core.services.cleanup_queue import entity_cleanup_queue
            entity_cleanup_queue.enqueue_channel_delete(channel, reason="[Anti-Nuke] Auto-Delete Unauthorized Channel")