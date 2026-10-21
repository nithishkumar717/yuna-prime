import asyncio
import logging
import time
import discord
from discord.ext import commands

from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache
from core.services.neutralizer import security_neutralizer
from core.services.audit_log_service import audit_log_service, ACTION_TO_COL
from core.metrics.security_metrics import security_metrics
from core.antinuke_v2.router import v2_engine_router, EngineMode

logger = logging.getLogger("yuna.audit_stream")


class AuditStreamAntiNuke(commands.Cog):
    """
    Zero-Latency Gateway WebSocket Audit Stream Engine for YUNA.
    Listens directly to Discord's GUILD_AUDIT_LOG_ENTRY_CREATE WebSocket event.
    Dispatches punishments and reversions in sub-15ms without ANY HTTP GET polling.
    Beats Zynrax, Obsidian, and all competing security bots.
    """

    def __init__(self, bot):
        self.bot = bot
        try:
            from core.antinuke_v2.lag_sampler import event_loop_lag_sampler
            event_loop_lag_sampler.start()
        except Exception:
            pass
        try:
            from core.antinuke_v2.fast_path import install_fast_path
            install_fast_path(self.bot)
        except Exception as e:
            logger.debug("[AuditStreamAntiNuke] Could not install fast-path: %s", e)

    async def cog_load(self):
        try:
            from core.antinuke_v2.lag_sampler import event_loop_lag_sampler
            if not event_loop_lag_sampler.is_running:
                event_loop_lag_sampler.start()
        except Exception as e:
            logger.debug("[AuditStreamAntiNuke] Could not start lag sampler in cog_load: %s", e)

        try:
            from core.antinuke_v2.fast_path import install_fast_path
            install_fast_path(self.bot)
        except Exception:
            pass

        async def _staggered_baseline_warm():
            try:
                for g in getattr(self.bot, "guilds", []):
                    # Stagger baseline snapshots with 5s pause to prevent event loop lag spikes
                    v2_engine_router.coordinator.snapshot_store.snapshot_guild(g)
                    await asyncio.sleep(10.0)
            except Exception as e:
                logger.debug("[AuditStreamAntiNuke] Staggered baseline snapshot error: %s", e)

        asyncio.create_task(_staggered_baseline_warm())

        try:
            from core.antinuke_v2.warmer import discord_connection_warmer
            discord_connection_warmer.start(self.bot)
            await v2_engine_router.coordinator.state_store.warm_load_all_guilds()
        except Exception as e:
            logger.debug("[AuditStreamAntiNuke] Warmer / state warm-load error: %s", e)

    async def cog_unload(self):
        try:
            from core.antinuke_v2.lag_sampler import event_loop_lag_sampler
            event_loop_lag_sampler.stop()
        except Exception:
            pass
        try:
            from core.antinuke_v2.warmer import discord_connection_warmer
            discord_connection_warmer.stop()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            v2_engine_router.coordinator.snapshot_store.snapshot_guild(guild)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        guild = getattr(entry, "guild", None)
        if not guild:
            return

        # 0. Stream and persist real-time Discord audit log entry into SQLite for Dashboard display
        try:
            from core.dashboard_server import process_and_store_single_audit_entry
            asyncio.create_task(process_and_store_single_audit_entry(entry))
        except Exception:
            pass

        if not guild.me or not guild.me.guild_permissions.ban_members:
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        engine_mode = v2_engine_router.get_engine_mode(guild.id)
        if engine_mode == EngineMode.V2:
            await v2_engine_router.handle_v2_audit_stream(entry)
            return

        action = getattr(entry, "action", None)
        if not action:
            return

        action_col = ACTION_TO_COL.get(action)
        if not action_col:
            return

        trace = security_metrics.create_trace(
            event_type=f"audit_stream_{action_col}",
            guild_id=guild.id,
            processing_path="audit_stream"
        )
        trace.record_stage("started")

        # 1. Immediately update AuditLogService hot cache for zero-latency retrieval
        action_val = getattr(action, "value", action)
        audit_log_service._action_cache[(guild.id, action_val)] = ([entry], time.time())

        # 2. Fast check: Is this specific anti-nuke action enabled?
        if not security_cache.is_action_enabled(guild.id, action_col):
            trace.finish(result="skipped_disabled")
            if engine_mode == EngineMode.SHADOW:
                asyncio.create_task(v2_engine_router.run_shadow_audit_stream(entry, "ALLOW"))
            return
        trace.record_stage("policy_checked")

        # 3. Extract and check executor (WebSocket attribution is instant!)
        executor = entry.user or (discord.Object(id=entry.user_id) if getattr(entry, "user_id", None) else None)
        if not executor:
            trace.finish(result="no_executor")
            return
        trace.record_stage("audit_attribution_completed")

        # 4. Immediate Immunity Check
        if security_cache.is_immune(guild, executor):
            trace.finish(result="skipped_immune")
            if engine_mode == EngineMode.SHADOW:
                asyncio.create_task(v2_engine_router.run_shadow_audit_stream(entry, "ALLOW"))
            return

        # 5. Synchronous RAM Whitelist Check (<0.005ms)
        if security_cache.is_executor_allowed_sync(guild, executor, action_col):
            trace.finish(result="authorized_executor")
            if engine_mode == EngineMode.SHADOW:
                asyncio.create_task(v2_engine_router.run_shadow_audit_stream(entry, "ALLOW"))
            return

        # 5b. For Member Role Updates (memup): ONLY trigger if a DANGEROUS / ADMIN role was assigned!
        if action == discord.AuditLogAction.member_role_update or action_col == "memup":
            from security.authorization.dangerous_permissions import is_dangerous_role
            added_roles = self._get_added_roles_from_audit_entry(guild, entry)
            if added_roles:
                if not any(is_dangerous_role(r) for r in added_roles):
                    trace.finish(result="non_dangerous_role_update")
                    return
            else:
                target_id = getattr(entry, "_target_id", None) or getattr(getattr(entry, "target", None), "id", None)
                if target_id:
                    target_member = guild.get_member(target_id)
                    if target_member:
                        if not any(is_dangerous_role(r) for r in target_member.roles):
                            trace.finish(result="non_dangerous_role_update")
                            return

        # 5c. Target Attribution
        target = getattr(entry, "target", None)
        target_id = getattr(entry, "_target_id", None) or (getattr(target, "id", None) if target else None)
        target_int = int(target_id) if target_id is not None else None

        # Check if incident was already claimed or handled by entity listener
        from core.security.incident_coordinator import security_coordinator
        if target_int is not None and security_coordinator.is_handled(guild.id, action_col, target_int):
            trace.finish(result="already_handled_by_entity_listener")
            return

        trace.record_stage("threat_decision_completed")

        # Claim incident in coordinator so waiting entity listeners wake up and avoid redundant REST queries
        claimed, inc = security_coordinator.claim_incident(guild.id, action_col, target_int, "audit_stream", executor.id)
        if not claimed and inc.is_handled:
            trace.finish(result="already_handled")
            return

        # 6. UNAUTHORIZED ATTACKER DETECTED VIA WEBSOCKET STREAM! Priority #1: Instant Ban FIRST!
        trace.record_stage("containment_dispatched")
        reason = f"Audit Stream Violation: {action_col.upper()} | Unauthorized Action"
        ban_success = await security_neutralizer.neutralize_offender(guild, executor, reason)
        trace.record_stage("containment_completed")
        security_coordinator.set_ban_result(guild.id, action_col, target_int, ban_success)
        if engine_mode == EngineMode.SHADOW:
            asyncio.create_task(v2_engine_router.run_shadow_audit_stream(entry, "BAN" if ban_success else "FAIL_BAN"))

        # 7. Execute entity reversal/cleanup ONLY AFTER offender has been neutralized successfully!
        # If ban failed (e.g. role hierarchy / missing permissions), DO NOT revert the entity,
        # otherwise rival security bots (Olympus, Wick) will flag Yuna as rogue and ban Yuna.
        # NOTE: For channel_delete (chdl), role_delete (rldl), channel_update (chup), and role_update (rlup),
        # recovery requires rich in-memory entity objects and snapshot cache from entity listeners.
        # We do NOT mark recovered here so antichdl, antirldl, antichup, and antirlup can execute restoration!
        if ban_success:
            if action_col not in ("chdl", "rldl"):
                if security_coordinator.mark_recovered(guild.id, action_col, target_int):
                    await self._revert_action(guild, entry, action, action_col)
            trace.record_stage("recovery_completed")
            if action_col == "chdl":
                status = "Instant Banned Offender & Restoring Channel"
            elif action_col == "rldl":
                status = "Instant Banned Offender & Restoring Role"
            elif action_col in ("chup", "rlup"):
                status = "Instant Banned Offender & Reverting Changes"
            else:
                status = "Instant Banned Offender (WebSocket Stream)"
        else:
            status = "Ban Failed (Role Hierarchy - Recovery Aborted)"

        if target is None:
            target = discord.Object(id=target_int) if target_int else None

        # Single-flight logging: Ensure only one security alert is dispatched per incident
        if security_coordinator.mark_logged(guild.id, action_col, target_int):
            asyncio.create_task(send_antinuke_log(
                guild,
                f"Anti-Nuke Stream [{action_col.upper()}]",
                executor,
                status,
                details="Unauthorized action detected in the Discord audit log.",
                target=target,
                detection_time=getattr(entry, "created_at", None),
            ))
        trace.finish(result="containment_dispatched" if ban_success else "containment_failed")

    def _get_added_roles_from_audit_entry(self, guild: discord.Guild, entry: discord.AuditLogEntry) -> list:
        added_roles = []
        try:
            changes = getattr(entry, "changes", None)
            if changes:
                after_attr = getattr(changes, "after", None)
                if after_attr and hasattr(after_attr, "roles"):
                    for r in after_attr.roles:
                        role_obj = r if isinstance(r, discord.Role) else guild.get_role(getattr(r, "id", r.get("id") if isinstance(r, dict) else r))
                        if role_obj and role_obj not in added_roles:
                            added_roles.append(role_obj)

                if not added_roles and hasattr(changes, "__iter__"):
                    for change in changes:
                        key = getattr(change, "key", None)
                        if key in ("$add", "roles"):
                            new_val = getattr(change, "new", getattr(change, "after", None))
                            if isinstance(new_val, list):
                                for item in new_val:
                                    role_obj = item if isinstance(item, discord.Role) else guild.get_role(getattr(item, "id", item.get("id") if isinstance(item, dict) else item))
                                    if role_obj and role_obj not in added_roles:
                                        added_roles.append(role_obj)
        except Exception:
            pass
        return added_roles

    async def _revert_action(self, guild: discord.Guild, entry: discord.AuditLogEntry, action: discord.AuditLogAction, action_col: str):
        try:
            if action == discord.AuditLogAction.channel_create:
                target_id = getattr(entry, "_target_id", None) or getattr(getattr(entry, "target", None), "id", None)
                if target_id:
                    tid = int(target_id)
                    ch = guild.get_channel(tid)
                    if ch:
                        try:
                            await ch.delete(reason="[Anti-Nuke] Auto-Delete Rogue Channel")
                        except Exception:
                            pass
                    else:
                        try:
                            await guild._state.http.delete_channel(tid, reason="[Anti-Nuke] Auto-Delete Rogue Channel")
                        except Exception:
                            pass

            elif action == discord.AuditLogAction.role_create:
                target_id = getattr(entry, "_target_id", None) or getattr(getattr(entry, "target", None), "id", None)
                if target_id:
                    tid = int(target_id)
                    role = guild.get_role(tid)
                    if role:
                        try:
                            await role.delete(reason="[Anti-Nuke] Auto-Delete Rogue Role")
                        except Exception:
                            pass
                    else:
                        try:
                            await guild._state.http.delete_role(guild.id, tid, reason="[Anti-Nuke] Auto-Delete Rogue Role")
                        except Exception:
                            pass

            elif action == discord.AuditLogAction.channel_update or action_col == "chup":
                target_id = getattr(entry, "_target_id", None) or getattr(getattr(entry, "target", None), "id", None)
                if target_id:
                    tid = int(target_id)
                    from core.antinuke_v2.router import v2_engine_router
                    await v2_engine_router.coordinator.recovery.revert_channel(guild, tid)

            elif action == discord.AuditLogAction.role_update or action_col == "rlup":
                target_id = getattr(entry, "_target_id", None) or getattr(getattr(entry, "target", None), "id", None)
                if target_id:
                    tid = int(target_id)
                    from core.antinuke_v2.router import v2_engine_router
                    await v2_engine_router.coordinator.recovery.revert_role(guild, tid)

            elif action == discord.AuditLogAction.ban:
                target = getattr(entry, "target", None) or (discord.Object(id=entry._target_id) if getattr(entry, "_target_id", None) else None)
                if target:
                    await guild.unban(target, reason="[Anti-Nuke] Reverting Unauthorized Ban")

            elif action == discord.AuditLogAction.webhook_create:
                target_id = getattr(entry, "_target_id", None)
                if target_id:
                    tid = int(target_id)
                    try:
                        wh = await self.bot.fetch_webhook(tid)
                        if wh:
                            await wh.delete(reason="[Anti-Nuke] Auto-Delete Rogue Webhook")
                    except Exception:
                        try:
                            await guild._state.http.delete_webhook(tid, reason="[Anti-Nuke] Auto-Delete Rogue Webhook")
                        except Exception:
                            pass

            elif action == discord.AuditLogAction.member_role_update or action_col == "memup":
                target_id = getattr(entry, "_target_id", None) or getattr(getattr(entry, "target", None), "id", None)
                if target_id:
                    member = guild.get_member(target_id)
                    if not member and hasattr(guild, "fetch_member"):
                        try:
                            member = await guild.fetch_member(target_id)
                        except Exception:
                            member = None
                    if member:
                        from security.authorization.dangerous_permissions import is_dangerous_role
                        added_roles = self._get_added_roles_from_audit_entry(guild, entry)
                        roles_to_strip = [r for r in added_roles if is_dangerous_role(r)] if added_roles else [r for r in member.roles if is_dangerous_role(r)]
                        top_role = guild.me.top_role if (guild.me and hasattr(guild.me, 'top_role')) else None
                        removable = [r for r in roles_to_strip if r in member.roles and (top_role is None or r < top_role)]
                        if removable:
                            await member.remove_roles(*removable, reason="[Anti-Nuke WebSocket] Auto-Strip Unauthorized Dangerous Role")
        except Exception as ex:
            logger.debug(f"[AUDIT STREAM] Revert action error for {action_col}: {ex}")


async def setup(bot):
    await bot.add_cog(AuditStreamAntiNuke(bot))
