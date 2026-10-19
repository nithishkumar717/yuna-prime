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

class AntiBan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, guild, executor, action_col="ban"):
        try:
            return await security_cache.check_executor_permission(guild, executor, action_col)
        except Exception:
            return security_cache.is_immune(guild, executor)

    async def fetch_audit_logs(self, guild, action, target_id=None, max_retries=6):
        return await guarded_audit_fetch(guild, action, target_id, max_retries)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        if not guild or not guild.me or not guild.me.guild_permissions.ban_members or not guild.me.guild_permissions.view_audit_log:
            return

        # Fast-Path: 0ms in-memory check if antinuke or ban is enabled
        if not security_cache.is_action_enabled(guild.id, "ban"):
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_member_ban(guild, user)
            return

        from core.metrics.security_metrics import security_metrics
        trace = security_metrics.create_trace(
            event_type="member_ban",
            guild_id=guild.id,
            path="entity_listener",
            target_id=getattr(user, "id", None),
            event_dispatch_name="member_ban",
        )
        trace.mark_policy_checked(enabled=True)

        from core.security.incident_coordinator import security_coordinator
        # Coordinated micro-yield: Await AuditStreamAntiNuke to signal in <1-5ms instead of fixed delay.
        # If audit stream already handled it, wakes up immediately with zero REST calls!
        user_id = getattr(user, "id", None)
        stream_incident = await security_coordinator.wait_for_stream(guild.id, "ban", user_id, timeout=0.010)
        if stream_incident and stream_incident.is_handled:
            trace.finish("handled_by_audit_stream")
            return

        trace.mark_audit_started()
        entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.ban, user_id)
        trace.mark_audit_completed(found=entry is not None)
        if not entry:
            trace.finish("audit_miss")
            return

        executor = entry.user or (discord.Object(id=entry.user_id) if getattr(entry, "user_id", None) else None)
        if not executor:
            trace.finish("no_executor")
            return

        # Skip alerts if Yuna itself performed the ban (e.g. neutralizing an attacker)
        if guild.me and executor.id == guild.me.id:
            trace.finish("self_action")
            return

        is_an_on = True
        trace.mark_policy_checked(enabled=is_an_on)

        is_immune = security_cache.is_immune(guild, executor)
        is_allowed = True
        if is_an_on and not is_immune:
            is_allowed = await self.check_permissions(guild, executor, "ban")
        elif is_immune:
            is_allowed = True

        trace.mark_auth_decision(allowed=is_allowed)
        target_name = getattr(user, "name", str(user))
        exec_name = getattr(executor, "name", "Staff")

        if not is_allowed:
            # 1. IMMEDIATE INSTANT BAN (Priority #1 - Neutralize offender FIRST)
            trace.mark_containment_started()
            ban_success = await self.instant_ban(guild, executor, "Unauthorized Member Ban")
            trace.mark_containment_completed(success=ban_success)

            # 2. ONLY proceed with unbanning victim IF the offender was successfully banned!
            trace.mark_recovery_started()
            if ban_success:
                await self.unban_victim(guild, user)
                trace.mark_recovery_completed(success=True)
                action_msg = "Instant Banned Offender & Unbanned Target Member"
            else:
                trace.mark_recovery_completed(success=False)
                action_msg = "Ban Failed (Role Hierarchy) - Unban Aborted"

            # 3. Concurrently send security log (authoritatively dispatches admin security DM report)
            asyncio.create_task(send_antinuke_log(guild, "Anti Ban", executor, action_msg, target=user))
            trace.finish("banned" if ban_success else "role_hierarchy_fail")
        else:
            trace.finish("allowed")
            # Authorized staff ban -> DM all server admins
            reason_text = entry.reason or "No reason provided"
            asyncio.create_task(send_antinuke_dm_report(
                guild=guild,
                event_type="MEMBER BAN",
                executor=executor,
                target=user,
                is_authorized=True,
                punishment="Banned from Server",
                reason=reason_text,
                explanation=f"{exec_name} banned {target_name} from the server."
            ))


    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        if not guild:
            return

        from core.services.neutralizer import security_neutralizer
        security_neutralizer.unmark_neutralized(guild.id, getattr(user, "id", None) or 0)

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_member_unban(guild, user)
            return

        entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.unban, user.id)
        if not entry:
            return

        executor = entry.user or (discord.Object(id=entry.user_id) if getattr(entry, "user_id", None) else None)
        if not executor:
            return

        # Skip duplicate alert if Yuna unbanned the victim as part of an anti-nuke reversion
        if guild.me and executor.id == guild.me.id:
            return

        target_name = getattr(user, "name", str(user))
        exec_name = getattr(executor, "name", "Staff")
        reason_text = entry.reason or "No reason provided"

        asyncio.create_task(send_antinuke_dm_report(
            guild=guild,
            event_type="MEMBER UNBAN",
            executor=executor,
            target=user,
            is_authorized=True,
            punishment="Unbanned",
            reason=reason_text,
            explanation=f"{exec_name} unbanned {target_name} in the server."
        ))

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)

    async def unban_victim(self, guild, user):
        try:
            await guild.unban(user, reason="[Anti-Nuke] Reverting Unauthorized Ban")
        except Exception:
            pass
