import discord
from discord.ext import commands
import asyncio
from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_audit_fetch
from core.metrics.security_metrics import security_metrics
from core.antinuke_v2.router import v2_engine_router, EngineMode


class AntiMemberUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, guild, executor, action_col="memup"):
        try:
            return await security_cache.check_executor_permission(guild, executor, action_col)
        except Exception:
            return security_cache.is_immune(guild, executor)

    async def fetch_audit_logs(self, guild, action, target_id=None, max_retries=6):
        return await guarded_audit_fetch(guild, action, target_id, max_retries)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = getattr(before, "guild", None)
        if not guild or not guild.me:
            return

        # =========================================================================
        # BOT SELF-DEFENSE: Anti-Tamper Check
        # =========================================================================
        if after.id == guild.me.id:
            removed_roles = [r for r in before.roles if r not in after.roles]
            if removed_roles:
                dangerous_removed = [
                    r for r in removed_roles
                    if any([
                        r.permissions.administrator,
                        r.permissions.ban_members,
                        r.permissions.kick_members,
                        r.permissions.manage_roles,
                        r.permissions.manage_guild,
                        r.permissions.manage_channels
                    ])
                ]
                if dangerous_removed:
                    asyncio.create_task(self._handle_bot_tamper(guild, dangerous_removed))
            return

        if not guild.me.guild_permissions.ban_members or not guild.me.guild_permissions.view_audit_log:
            return

        # Fast-Path: 0ms in-memory check if antinuke or memup is enabled
        if not security_cache.is_action_enabled(guild.id, "memup"):
            return

        # Check if new roles were added
        added_roles = [r for r in after.roles if r not in before.roles]
        if not added_roles:
            return

        from security.authorization.dangerous_permissions import is_dangerous_role

        # Only trigger Anti-Nuke if a DANGEROUS / ADMIN role was assigned!
        dangerous_added_roles = [r for r in added_roles if is_dangerous_role(r)]
        if not dangerous_added_roles:
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            await v2_engine_router.handle_v2_member_update(before, after)
            return

        trace = security_metrics.create_trace(
            event_type="member_update",
            guild_id=guild.id,
            processing_path="entity_listener"
        )
        trace.record_stage("started")
        trace.record_stage("policy_checked")

        from core.security.incident_coordinator import security_coordinator

        # Coordinated micro-yield: Await AuditStreamAntiNuke to signal in <1-5ms instead of fixed 25ms delay.
        # If audit stream already handled it, wakes up immediately with zero REST calls!
        stream_incident = await security_coordinator.wait_for_stream(guild.id, "memup", after.id, timeout=0.010)

        if stream_incident and stream_incident.is_handled:
            trace.record_stage("threat_decision_completed")
            trace.record_stage("containment_completed")
            if stream_incident.ban_success and security_coordinator.mark_recovered(guild.id, "memup", after.id):
                await self.strip_roles(after, dangerous_added_roles)
                trace.record_stage("recovery_completed")
            trace.finish(result="handled_by_audit_stream")
            return

        trace.record_stage("audit_attribution_started")
        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.member_role_update, after.id)
        trace.record_stage("audit_attribution_completed")

        if logs is None:
            trace.finish(result="no_audit_entry")
            return

        executor = logs.user or (discord.Object(id=logs.user_id) if getattr(logs, "user_id", None) else None)
        if not executor or security_cache.is_immune(guild, executor):
            trace.finish(result="skipped_immune")
            return

        is_allowed = await self.check_permissions(guild, executor, "memup")
        trace.record_stage("threat_decision_completed")
        if is_allowed:
            trace.finish(result="authorized_executor")
            return

        claimed, inc = security_coordinator.claim_incident(guild.id, "memup", after.id, "entity_listener", executor.id)

        # 1. IMMEDIATE INSTANT BAN OF EXECUTOR (Priority #1 - Neutralize offender FIRST)
        trace.record_stage("containment_dispatched")
        ban_success = await self.instant_ban(guild, executor, "Dangerous Role Escalation | Unwhitelisted User")
        trace.record_stage("containment_completed")
        security_coordinator.set_ban_result(guild.id, "memup", after.id, ban_success)

        # 2. ONLY proceed with recovery IF the offender was successfully banned!
        # If ban failed (e.g. role hierarchy / missing permissions), DO NOT strip roles,
        # otherwise rival security bots will flag Yuna as rogue and ban Yuna.
        if ban_success and security_coordinator.mark_recovered(guild.id, "memup", after.id):
            await self.strip_roles(after, dangerous_added_roles)
            trace.record_stage("recovery_completed")
            action_msg = "Instant Banned Offender & Stripped Escalated Role"
        else:
            action_msg = "Ban Failed (Role Hierarchy) - Preserved Entity to Prevent Rogue Flag"

        # 3. Send security log
        if security_coordinator.mark_logged(guild.id, "memup", after.id):
            asyncio.create_task(send_antinuke_log(guild, "Anti Member Role Update", executor, action_msg, target=after, details=f"Escalated Roles: {', '.join([r.name for r in dangerous_added_roles])}"))
        trace.finish(result="containment_dispatched" if ban_success else "containment_failed")

    async def _handle_bot_tamper(self, guild: discord.Guild, removed_roles):
        """Dispatched when high-privilege roles are stripped from Yuna Supreme itself."""
        try:
            logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.member_role_update, guild.me.id)
            executor = logs.user if logs else None
            executor_str = f"{executor} (`{executor.id}`)" if executor else "Unknown Executor"

            # Alert Anti-Nuke Channel
            role_names = ", ".join([r.name for r in removed_roles])
            await send_antinuke_log(
                guild,
                "🚨 CRITICAL: BOT TAMPER DETECTED",
                executor or guild.me,
                f"Security roles were stripped from Yuna Supreme!",
                details=f"Removed: {role_names} | Executor: {executor_str}"
            )

            # Check if executor was unauthorized and can be neutralized
            if executor and not security_cache.is_immune(guild, executor):
                if guild.me.guild_permissions.ban_members:
                    await self.instant_ban(guild, executor, "[Anti-Tamper] Attempted to disarm Yuna Supreme")

            # Emergency DM to Server Owner
            if guild.owner and not guild.owner.bot:
                embed = discord.Embed(
                    title="🚨 CRITICAL SECURITY ALERT: BOT DISARM ATTEMPT",
                    description=(
                        f"A user attempted to strip security permissions from **Yuna Supreme** in **{guild.name}**!\n\n"
                        f"• **Executor:** {executor_str}\n"
                        f"• **Stripped Roles:** `{role_names}`\n"
                        f"• **Action Required:** Check audit logs immediately and ensure Yuna's top role has full Administrator permissions."
                    ),
                    color=0xFF0000
                )
                await guild.owner.send(embed=embed)
        except Exception:
            pass

    async def instant_ban(self, guild, executor, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, executor, reason)

    async def strip_roles(self, member, roles_to_remove):
        try:
            guild = member.guild
            top_role = guild.me.top_role if (guild and guild.me and hasattr(guild.me, 'top_role')) else None
            removable = [r for r in roles_to_remove if r in member.roles and (top_role is None or r < top_role)]
            if removable:
                await member.remove_roles(*removable, reason="[Anti-Nuke] Auto-Strip Unauthorized Dangerous Role")
        except Exception:
            pass
