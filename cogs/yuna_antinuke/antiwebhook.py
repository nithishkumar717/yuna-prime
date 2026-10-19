import discord
from discord.ext import commands
import asyncio
from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_webhook_audit_fetch
from core.metrics.security_metrics import security_metrics
from core.antinuke_v2.router import v2_engine_router, EngineMode


class AntiWebhookUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, guild, executor, action_col="mngweb"):
        try:
            return await security_cache.check_executor_permission(guild, executor, action_col)
        except Exception:
            return security_cache.is_immune(guild, executor)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        guild = getattr(channel, "guild", None)
        if not guild or not guild.me or not guild.me.guild_permissions.ban_members or not guild.me.guild_permissions.view_audit_log:
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_webhook_update(channel)
            return

        # Fast-Path: 0ms in-memory check if antinuke or webhook protection is enabled
        if not security_cache.is_action_enabled(guild.id, "mngweb"):
            return

        trace = security_metrics.create_trace(
            event_type="webhooks_update",
            guild_id=guild.id,
            processing_path="entity_listener"
        )
        trace.record_stage("started")
        trace.record_stage("policy_checked")

        trace.record_stage("audit_attribution_started")
        logs = await guarded_webhook_audit_fetch(guild, channel)
        trace.record_stage("audit_attribution_completed")

        if logs is None or logs.action != discord.AuditLogAction.webhook_update:
            trace.finish(result="ignored_action_or_empty")
            return

        executor = logs.user or (discord.Object(id=logs.user_id) if getattr(logs, "user_id", None) else None)
        if not executor or security_cache.is_immune(guild, executor):
            trace.finish(result="skipped_immune")
            return

        is_allowed = await self.check_permissions(guild, executor, "mngweb")
        trace.record_stage("threat_decision_completed")
        if is_allowed:
            trace.finish(result="authorized_executor")
            return

        # 1. IMMEDIATE INSTANT BAN (Priority #1 - Neutralize offender FIRST)
        trace.record_stage("containment_dispatched")
        ban_success = await self.instant_ban(guild, executor, "Webhook Update | Unwhitelisted User")
        trace.record_stage("containment_completed")

        # 2. ONLY proceed with recovery IF the offender was successfully banned!
        # If ban failed (e.g. role hierarchy / missing permissions), DO NOT delete webhooks,
        # otherwise rival security bots will flag Yuna as rogue and ban Yuna.
        if ban_success:
            await self.cleanup_webhooks(channel)
            trace.record_stage("recovery_completed")
            action_msg = "Instant Banned Offender & Cleaned Webhooks"
        else:
            action_msg = "Ban Failed (Role Hierarchy) - Preserved Entity to Prevent Rogue Flag"

        # 3. Send security log
        asyncio.create_task(send_antinuke_log(guild, "Anti Webhook Update", executor, action_msg, details=f"Channel: #{channel.name}"))
        trace.finish(result="containment_dispatched" if ban_success else "containment_failed")

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)

    async def cleanup_webhooks(self, channel):
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                try:
                    await wh.delete(reason="[Anti-Nuke] Auto-Clean Unauthorized Webhook")
                except Exception:
                    pass
        except Exception:
            pass
