import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz

from utils.Tools import send_antinuke_log, send_antinuke_dm_report
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_audit_fetch
from core.antinuke_v2.router import v2_engine_router, EngineMode

class AntiKick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, guild, executor, action_col="kick"):
        try:
            return await security_cache.check_executor_permission(guild, executor, action_col)
        except Exception:
            return security_cache.is_immune(guild, executor)

    async def fetch_audit_logs(self, guild, action, target_id=None, max_retries=6):
        return await guarded_audit_fetch(guild, action, target_id, max_retries)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = getattr(member, "guild", None)
        if not guild or not guild.me or not guild.me.guild_permissions.ban_members or not guild.me.guild_permissions.view_audit_log:
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_member_kick(member)
            return

        from core.metrics.security_metrics import security_metrics
        trace = security_metrics.create_trace(
            event_type="member_kick",
            guild_id=guild.id,
            path="entity_listener",
            target_id=member.id,
            event_dispatch_name="member_remove",
        )

        # Fast-Path: 0ms in-memory check if antinuke or kick is enabled
        if not security_cache.is_action_enabled(guild.id, "kick"):
            trace.mark_policy_checked(enabled=False)
            trace.finish("action_disabled")
            return

        trace.mark_policy_checked(enabled=True)

        from core.security.incident_coordinator import security_coordinator

        # Coordinated micro-yield: Await AuditStreamAntiNuke to signal in <1-5ms instead of fixed 25ms delay.
        # If audit stream already handled it, wakes up immediately with zero REST calls!
        stream_incident = await security_coordinator.wait_for_stream(guild.id, "kick", member.id, timeout=0.010)

        if stream_incident and stream_incident.is_handled:
            trace.finish("handled_by_audit_stream")
            return

        trace.mark_audit_started()
        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.kick, member.id)
        trace.mark_audit_completed(found=logs is not None)
        if logs is None:
            trace.finish("audit_miss")
            return

        executor = logs.user or (discord.Object(id=logs.user_id) if getattr(logs, "user_id", None) else None)
        if not executor:
            trace.finish("no_executor")
            return

        # Skip alerts if Yuna itself performed the kick (e.g. rogue bot protection)
        if guild.me and executor.id == guild.me.id:
            trace.finish("self_action")
            return

        is_immune = security_cache.is_immune(guild, executor)
        if is_immune:
            trace.mark_auth_decision(allowed=True, reason="immune")
            trace.finish("immune")
            return

        is_allowed = await self.check_permissions(guild, executor, "kick")
        trace.mark_auth_decision(allowed=is_allowed)

        target_name = getattr(member, "name", str(member))
        exec_name = getattr(executor, "name", "Staff")

        claimed, inc = security_coordinator.claim_incident(guild.id, "kick", member.id, "entity_listener", executor.id)

        if not is_allowed:
            # 1. IMMEDIATE INSTANT BAN (Priority #1)
            trace.mark_containment_started()
            ban_success = await self.instant_ban(guild, executor, "Member Kick | Unwhitelisted User")
            trace.mark_containment_completed(success=ban_success)
            security_coordinator.set_ban_result(guild.id, "kick", member.id, ban_success)

            # 2. Concurrently send security log (send_antinuke_log authoritatively dispatches admin DM report)
            if security_coordinator.mark_logged(guild.id, "kick", member.id):
                action_msg = "Instant Banned Offender for Unauthorized Kick" if ban_success else "Attempted Ban for Unauthorized Kick"
                asyncio.create_task(send_antinuke_log(guild, "Anti Kick", executor, action_msg, target=member))

            trace.finish("banned" if ban_success else "role_hierarchy_fail")
        else:
            trace.finish("allowed")
            # Authorized staff kick -> DM all server admins
            reason_text = logs.reason or "No reason provided"
            asyncio.create_task(send_antinuke_dm_report(
                guild=guild,
                event_type="MEMBER KICK",
                executor=executor,
                target=member,
                is_authorized=True,
                punishment="Kicked from Server",
                reason=reason_text,
                explanation=f"{exec_name} kicked {target_name} from the server."
            ))

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)