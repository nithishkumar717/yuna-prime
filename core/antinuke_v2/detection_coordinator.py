"""Anti-Nuke V2 Engine — Centralized Detection Coordinator.

Unifies:
1. Real-Time Gateway Audit Stream (Primary)
2. Entity Event Listeners (Coordinated Fallback with Adaptive Stream-Health Wait)
3. Dynamic Attack Mode (N events in T seconds threshold escalation and server lockdown)
4. Pure Policy Evaluation and High-Priority Containment Dispatch
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional, Set, Tuple

import discord

from core.antinuke_v2.action_mapper import ActionMapper, AUDIT_ACTION_MAP
from core.antinuke_v2.attack_mode import AttackModeManager

AUDIT_CODE_TO_ACTION: Dict[str, Any] = {v: k for k, v in AUDIT_ACTION_MAP.items()}
from core.antinuke_v2.containment import ContainmentResult, V2Neutralizer
from core.antinuke_v2.engine import evaluate_policy
from core.antinuke_v2.incident_tracker import V2IncidentRecord, V2IncidentTracker
from core.antinuke_v2.models import DecisionAction, PolicyContext, PunishmentType
from core.antinuke_v2.snapshot import GuildSnapshotStore
from core.antinuke_v2.recovery import V2RecoveryEngine
from core.antinuke_v2.rate_limiter import SlidingWindowRateLimiter
from core.antinuke_v2.resolver import ActorResolver
from core.antinuke_v2.role_index import WhitelistedRoleMemberIndex
from core.antinuke_v2.state_store import GuildSecurityConfig, V2StateStore
from core.antinuke_v2.stream_health import StreamHealthTracker
from core.antinuke_v2.trace import V2SecurityTrace, v2_trace_aggregator
from core.antinuke_v2.warmer import discord_connection_warmer
from core.antinuke_v2.notifier import V2Notifier, v2_notifier

logger = logging.getLogger("antinuke.v2.detection")


class DetectionCoordinator:
    """Central engine orchestrating multi-path detection, health tracking, and attack mode."""

    def __init__(
        self,
        state_store: Optional[V2StateStore] = None,
        role_index: Optional[WhitelistedRoleMemberIndex] = None,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
        neutralizer: Optional[V2Neutralizer] = None,
        incident_tracker: Optional[V2IncidentTracker] = None,
        stream_health: Optional[StreamHealthTracker] = None,
        attack_mode: Optional[AttackModeManager] = None,
        notifier: Optional[V2Notifier] = None,
        snapshot_store: Optional[GuildSnapshotStore] = None,
        recovery: Optional[V2RecoveryEngine] = None,
    ) -> None:
        self.state_store = state_store or V2StateStore()
        self.role_index = role_index or WhitelistedRoleMemberIndex()
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter()
        self.neutralizer = neutralizer or V2Neutralizer()
        self.incident_tracker = incident_tracker or V2IncidentTracker()
        self.stream_health = stream_health or StreamHealthTracker()
        self.attack_mode = attack_mode or AttackModeManager()
        self.notifier = notifier or v2_notifier
        self.snapshot_store = snapshot_store or GuildSnapshotStore()
        self.recovery = recovery or V2RecoveryEngine(
            snapshot_store=self.snapshot_store,
            neutralizer=self.neutralizer,
            incident_tracker=self.incident_tracker,
        )
        self._debounced_refresh_tasks: Dict[int, asyncio.Task] = {}

    def schedule_baseline_refresh(self, guild: Any, delay: float = 30.0) -> None:
        """Schedules a debounced non-blocking baseline snapshot refresh after authorized staff edits."""
        if not guild or not hasattr(guild, "id"):
            return
        gid = guild.id
        if gid in self._debounced_refresh_tasks and not self._debounced_refresh_tasks[gid].done():
            self._debounced_refresh_tasks[gid].cancel()

        async def _debounced_worker():
            try:
                await asyncio.sleep(delay)
                self.snapshot_store.snapshot_guild(guild)
                try:
                    from core.antinuke_v2.recovery import sync_discord_server_template
                    await sync_discord_server_template(guild)
                except Exception:
                    pass
                logger.info("[V2Detection] 🔄 Debounced baseline template refresh completed for guild %s", gid)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug("[V2Detection] Baseline refresh error: %s", e)

        try:
            loop = asyncio.get_running_loop()
            self._debounced_refresh_tasks[gid] = loop.create_task(_debounced_worker())
        except Exception:
            pass

    async def _execute_recovery(
        self,
        guild: Any,
        action_code: str,
        target_id: Optional[int],
        containment_success: bool = True,
        target_entity: Optional[Any] = None,
    ) -> None:
        """Dispatches ultra-fast asset recovery / reversion without blocking hot paths."""
        if not guild or not containment_success:
            return
        if not target_id and not target_entity and action_code not in ("serverup", "vanity"):
            return

        # STRICT GUARD: If the incident was authorized (server owner, co-owner, whitelisted user), NEVER recover!
        if hasattr(self, "incident_tracker"):
            inc = self.incident_tracker.get_incident(guild.id, action_code, target_id)
            if inc and inc.containment_result and not inc.containment_result.is_containment_executed:
                logger.info("[Recovery] Skipping recovery for %s in guild %s because action was authorized by immune/whitelisted user", action_code, guild.id)
                return

        try:
            if action_code == "chcr":
                if target_id:
                    if hasattr(self, "incident_tracker"):
                        self.incident_tracker.mark_rogue_channel(target_id)
                    await self.recovery.delete_rogue_channel(guild, target_id)
            elif action_code == "chdl":
                if target_id:
                    if hasattr(self, "incident_tracker") and self.incident_tracker.is_rogue_channel(target_id):
                        logger.info("[Recovery] Suppressing recovery of rogue channel %s (created during raid)", target_id)
                        return
                    # Short 350ms settling yield allows partner bot recreate events to arrive over WebSocket
                    await asyncio.sleep(0.35)
                    await self.recovery.restore_channel(
                        guild, target_id, containment_success=containment_success, target_channel=target_entity
                    )
            elif action_code == "chup":
                if target_id:
                    await self.recovery.revert_channel(guild, target_id, target_channel=target_entity)
            elif action_code == "rlcr":
                if target_id:
                    await self.recovery.delete_rogue_role(guild, target_id)
            elif action_code == "rldl":
                if target_id:
                    # Short 350ms settling yield allows partner bot recreate events to arrive over WebSocket
                    await asyncio.sleep(0.35)
                    await self.recovery.restore_role(
                        guild, target_id, containment_success=containment_success, target_role=target_entity
                    )
            elif action_code == "rlup":
                if target_id:
                    await self.recovery.revert_role(guild, target_id, target_role=target_entity)
            elif action_code in ("webhook_create", "mngweb", "webhook_update"):
                if target_id:
                    await self.recovery.delete_rogue_webhook(guild, target_id)
            elif action_code == "webhook_delete":
                if target_id:
                    await self.recovery.restore_webhook(guild, target_id, containment_success=containment_success)
            elif action_code == "botadd":
                if target_id:
                    await self.recovery.kick_rogue_bot(guild, target_id)
            elif action_code == "memup":
                if target_id:
                    await self.recovery.strip_dangerous_roles(guild, target_id, target_member=target_entity)
            elif action_code in ("serverup", "vanity"):
                await self.recovery.revert_guild(guild, before_guild=target_entity)
            elif action_code in ("everyone", "antiEveryoneMention"):
                await self.recovery.delete_mass_mention(target_entity)
            elif action_code == "ban":
                if target_id:
                    await self.recovery.unban_innocent_member(guild, target_id)
            elif action_code == "unban":
                if target_id:
                    await self.recovery.reban_malicious_member(guild, target_id)
            elif action_code == "emodl":
                if target_id:
                    await self.recovery.restore_emoji(guild, target_id, containment_success=containment_success)
        except Exception as exc:
            logger.error("[V2Detection] Recovery error for %s on %s: %s", action_code, target_id, exc)

    async def handle_audit_stream_entry(self, entry: Any) -> Optional[ContainmentResult]:
        """Processes a real-time GUILD_AUDIT_LOG_ENTRY_CREATE gateway event.
        
        Primary detection path: zero artificial delay, sub-millisecond local policy decision.
        """
        guild = getattr(entry, "guild", None)
        user = getattr(entry, "user", None)
        user_id = getattr(entry, "user_id", getattr(user, "id", None))
        if not guild or not user_id:
            return None

        actor_id = int(user_id)
        guild_id = guild.id

        # 1. Record healthy heartbeat for this guild's stream
        self.stream_health.record_stream_event(guild_id)

        # 2. Map Discord audit action to V2 action code
        action_code, target_id, extra = ActionMapper.map_audit_entry(entry)
        if not action_code:
            return None

        # 3. Atomically claim incident in tracker
        claimed, incident = self.incident_tracker.claim_incident(
            guild_id=guild_id,
            action=action_code,
            target_id=target_id,
            source="audit_stream",
            actor_id=actor_id,
        )
        if not claimed:
            # The synchronous raw gateway path already made the decision and
            # dispatched containment. This parsed duplicate needs no wait if finished.
            if incident.claimed_by == "fast_gateway" and incident.containment_result is not None:
                return incident.containment_result

            # Other paths or still-running containment need the completed result for coordination.
            return await incident.wait_for_containment(timeout=1.0)

        # 4. Ensure guild security state is loaded (0ms if pre-warmed)
        if not self.state_store.is_guild_loaded(guild_id):
            await self.state_store.load_guild_from_db(guild_id)
        if not self.state_store.is_guild_loaded(guild_id):
            logger.error("[V2Detection] Security state unavailable for guild %s; skipped audit action %s", guild_id, action_code)
            result = ContainmentResult(
                success=False,
                punishment=PunishmentType.BAN,
                actor_id=actor_id,
                guild_id=guild_id,
                error_code="SECURITY_STATE_UNAVAILABLE",
            )
            self.incident_tracker.set_containment_result(guild_id, action_code, target_id, result)
            return result
        state = self.state_store.get_guild_config(guild_id)

        # Resolve actor: Check local cache first, bypass REST fetch if guild has no whitelisted roles
        if user is None:
            user = guild.get_member(actor_id) if hasattr(guild, "get_member") else None
            if user is None:
                if state and not state.whitelisted_roles:
                    # No roles can whitelist this actor, 0ms bypass without network fetch
                    user = discord.Object(id=actor_id)
                else:
                    resolved_actor, _is_resolved = await ActorResolver.resolve_actor(
                        guild=guild,
                        actor_id=actor_id,
                        role_index=self.role_index,
                        timeout=0.2,
                    )
                    user = resolved_actor or discord.Object(id=actor_id)

        if action_code == "botadd" and target_id:
            self.state_store.record_new_bot(guild_id, target_id, time.time())
        if self.attack_mode.record_event(guild_id):
            self.attack_mode.escalate_state(guild_id, state)

        # 5. Initialize nanosecond SecurityTrace
        trace = V2SecurityTrace(
            event_id=getattr(entry, "id", 0),
            guild_id=guild_id,
            action=action_code,
            path="audit_stream",
            actor_id=actor_id,
            target_id=target_id,
            dry_run=getattr(state, "dry_run", False),
            is_warm_connection=discord_connection_warmer.is_connection_warm(),
        )

        # 6. Build PolicyContext with strict target matching and age validation
        now = time.time()
        created_at = getattr(entry, "created_at", None)
        raw_target_id = getattr(entry, "target_id", None) or getattr(entry, "_target_id", None)
        if raw_target_id is None and hasattr(entry, "target") and hasattr(entry.target, "id"):
            raw_target_id = entry.target.id

        actor_unresolved = bool(isinstance(user, discord.Object) or not hasattr(user, "roles"))
        context = PolicyContext(
            event_time=now,
            audit_entry_created_at=created_at,
            target_id=target_id,
            raw_entry_target_id=raw_target_id,
            actor_is_bot=bool(getattr(user, "bot", False)),
            actor_unresolved=actor_unresolved,
            extra=extra,
        )

        # 7. Execute pure synchronous policy evaluation (< 0.05ms)
        decision = evaluate_policy(
            guild=guild,
            actor=user,
            action=action_code,
            target=getattr(entry, "target", None),
            context=context,
            state=state,
            role_index=self.role_index,
            rate_limiter=self.rate_limiter,
            bot_owner_ids=self.state_store.get_bot_owner_ids(),
        )
        trace.record_decision(decision.reason_code)

        # 8. Act on decision (with dry_run and trace recording)
        if decision.is_punish and decision.punishment:
            if getattr(state, "dry_run", False):
                logger.info(
                    "[V2-DRY-RUN] What V2 would do: Neutralize actor %s for action %s (Reason: %s)",
                    actor_id, action_code, decision.reason_code
                )
                trace.finish(result="dry_run")
                v2_trace_aggregator.record_trace(trace)
                result = ContainmentResult(
                    success=True,
                    punishment=decision.punishment,
                    actor_id=actor_id,
                    guild_id=guild_id,
                    error_code="DRY_RUN_SIMULATED",
                )
                self.incident_tracker.set_containment_result(guild_id, action_code, target_id, result)
                return result

            trace.record_ban_sent()

            # High-vigilance probation breach: escalate attack mode immediately
            if decision.reason_code == "NEW_BOT_UNAUTHORIZED_ACTION":
                self.attack_mode.escalate_state(guild_id, state)

            RECOVERY_AFTER_PUNISHMENT_ACTIONS = {
                "chcr", "rlcr", "chup", "rlup", "chdl", "rldl", "webhook_create", "webhook_update",
                "webhook_delete", "emodl", "mngweb", "botadd", "memup", "serverup", "vanity", "everyone",
                "antiEveryoneMention", "ban", "unban"
            }
            recovery_after_punishment = action_code in RECOVERY_AFTER_PUNISHMENT_ACTIONS
            recovery_target = getattr(entry, "target", None) or (
                guild.get_channel(target_id)
                if action_code in ("chdl", "chup") and target_id
                else guild.get_role(target_id)
                if action_code in ("rldl", "rlup") and target_id
                else None
            )
            if recovery_after_punishment:
                try:
                    result = await self.neutralizer.execute_containment(
                        guild=guild,
                        actor=user,
                        punishment=decision.punishment,
                        reason=f"[{action_code}] {decision.reason_code}",
                    )
                except Exception:
                    logger.exception("[V2] Punishment failed for actor %s in guild %s", actor_id, guild_id)
                    result = ContainmentResult(
                        success=False,
                        punishment=decision.punishment,
                        actor_id=actor_id,
                        guild_id=guild_id,
                        error_code="SEQUENTIAL_CONTAINMENT_ERROR",
                    )
                if not isinstance(result, ContainmentResult):
                    result = ContainmentResult(
                        success=False,
                        punishment=decision.punishment,
                        actor_id=actor_id,
                        guild_id=guild_id,
                        error_code="INVALID_CONTAINMENT_RESULT",
                    )
            else:
                result = await self.neutralizer.execute_containment(
                    guild=guild,
                    actor=user,
                    punishment=decision.punishment,
                    reason=f"[{action_code}] {decision.reason_code}",
                )
                if result.success and action_code in ("chdl", "rldl", "webhook_delete", "emodl"):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._execute_recovery(guild, action_code, target_id, containment_success=True))
                    except Exception:
                        pass
            discord_connection_warmer.record_http_activity()
            trace.record_ban_response(
                http_status=getattr(result, "http_status", 204 if result.success else 400),
                success=result.success,
                ratelimit_wait_ms=getattr(result, "ratelimit_wait_ms", 0.0),
                http_rtt_ms=getattr(result, "http_rtt_ms", 0.0),
            )
            trace.finish(result="success" if result.success else "failed")
            v2_trace_aggregator.record_trace(trace)

            # 1. Ban/containment result is recorded immediately (microsecond 0)
            self.incident_tracker.set_containment_result(guild_id, action_code, target_id, result)

            # 2. Recovery runs post-containment as a decoupled background task
            if recovery_after_punishment and result.success:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        self._execute_recovery(
                            guild=guild,
                            action_code=action_code,
                            target_id=target_id,
                            containment_success=result.success,
                            target_entity=recovery_target,
                        )
                    )
                except Exception as exc:
                    logger.debug("[V2] Could not schedule post-containment recovery: %s", exc)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.notifier.dispatch_incident(
                        guild=guild,
                        action=action_code,
                        actor=user,
                        target=getattr(entry, "target", None) or target_id,
                        result=result,
                        decision=decision,
                        state=state,
                        details=(
                            f"🚨 [High-Vigilance Probation] Newly joined bot intercepted performing unauthorized {action_code.upper()}! Instantly banned & action reversed."
                            if decision.reason_code == "NEW_BOT_UNAUTHORIZED_ACTION"
                            else f"[{action_code}] {decision.reason_code}"
                        ),
                    )
                )
            except Exception as e:
                logger.debug("[V2Detection] Could not dispatch notifier task: %s", e)

            return result
        else:
            # ALLOW or ALERT_ONLY
            trace.finish(result="skipped")
            v2_trace_aggregator.record_trace(trace)
            if decision.action == DecisionAction.ALLOW and action_code in (
                "chcr", "chup", "chdl", "rlcr", "rlup", "rldl", "serverup", "emodl", "emocr"
            ):
                self.schedule_baseline_refresh(guild, delay=30.0)

            result = ContainmentResult(
                success=False,
                punishment=decision.punishment or PunishmentType.BAN,
                actor_id=actor_id,
                guild_id=guild_id,
                error_code=f"NON_PUNISH_{decision.action.value.upper()}",
            )
            self.incident_tracker.set_containment_result(guild_id, action_code, target_id, result)
            return result

    async def handle_entity_fallback(
        self,
        guild: Any,
        action: str,
        target_id: Optional[int],
        actor: Optional[Any] = None,
        audit_resolver: Optional[Callable[[], Coroutine[Any, Any, Optional[Any]]]] = None,
        target_entity: Optional[Any] = None,
    ) -> Optional[ContainmentResult]:
        """Processes an entity event listener callback (coordinated fallback).
        
        The fallback waits ONLY when the stream has been healthy for that guild, never a fixed sleep.
        """
        if not guild:
            return None

        guild_id = guild.id
        action_code = action.lower()

        # 0. Fast-record live deleted/updated entity into snapshot store on-the-fly
        if target_entity and target_id:
            try:
                if action_code == "chdl" and hasattr(target_entity, "name"):
                    self.snapshot_store.record_channel(guild_id, target_entity)
                elif action_code == "rldl" and hasattr(target_entity, "name"):
                    self.snapshot_store.record_role(guild_id, target_entity)
            except Exception:
                pass

        # 1. Adaptive Yield: Wait ONLY if stream is healthy (max 15ms micro-yield)
        adaptive_wait = self.stream_health.get_adaptive_wait(guild_id, healthy_wait=0.010)
        if adaptive_wait > 0.0:
            existing_inc = self.incident_tracker.get_incident(guild_id, action_code, target_id)
            if existing_inc and existing_inc.is_claimed:
                res = await existing_inc.wait_for_containment(timeout=adaptive_wait)
                if res and res.is_containment_executed and action_code in ("chdl", "rldl"):
                    res_type = "channel" if action_code == "chdl" else "role"
                    if not self.snapshot_store.get_restored_id(guild_id, res_type, target_id):
                        await self._execute_recovery(
                            guild, action_code, target_id, containment_success=res.success, target_entity=target_entity
                        )
                return res
            # Micro-yield for real-time stream packet
            await asyncio.sleep(adaptive_wait)

        # Check if stream claimed during the adaptive yield
        existing_inc = self.incident_tracker.get_incident(guild_id, action_code, target_id)
        if existing_inc and existing_inc.is_claimed:
            res = await existing_inc.wait_for_containment(timeout=0.5)
            if res and res.is_containment_executed and action_code in ("chdl", "rldl"):
                res_type = "channel" if action_code == "chdl" else "role"
                if not self.snapshot_store.get_restored_id(guild_id, res_type, target_id):
                    await self._execute_recovery(
                        guild, action_code, target_id, containment_success=res.success, target_entity=target_entity
                    )
            return res

        # 2. Claim incident for entity fallback
        claimed, incident = self.incident_tracker.claim_incident(
            guild_id=guild_id,
            action=action_code,
            target_id=target_id,
            source="entity_fallback",
            actor_id=getattr(actor, "id", None),
        )
        if not claimed:
            return await incident.wait_for_containment(timeout=0.5)

        # 3. Resolve actor if not provided directly
        resolved_actor = actor
        if resolved_actor is None:
            if audit_resolver:
                resolved_actor = await audit_resolver()
            else:
                audit_action = AUDIT_CODE_TO_ACTION.get(action_code)
                if audit_action:
                    try:
                        from core.services.audit_log_service import AuditLogService
                        log_entry = await AuditLogService.get_instance().get_entry(
                            guild=guild,
                            action=audit_action,
                            target_id=target_id,
                            max_retries=2,
                            max_age_seconds=5.0,
                        )
                        if log_entry and log_entry.user:
                            resolved_actor = log_entry.user
                    except Exception as exc:
                        logger.debug("[V2Detection] AuditLogService fallback error: %s", exc)

                    if not resolved_actor and hasattr(guild, "audit_logs"):
                        try:
                            async for log_entry in guild.audit_logs(limit=1, action=audit_action):
                                t_match = getattr(log_entry, "target", None)
                                t_match_id = getattr(log_entry, "_target_id", getattr(t_match, "id", None))
                                if target_id is None or t_match_id == target_id:
                                    resolved_actor = log_entry.user
                                    break
                        except Exception as exc:
                            logger.debug("[V2Detection] Fast audit log lookup error: %s", exc)

        # Check if authoritative fast_gateway or audit_stream preempted containment
        if incident.claimed_by in ("fast_gateway", "audit_stream"):
            res = await incident.wait_for_containment(timeout=0.5)
            if res and res.is_containment_executed:
                if action_code in ("chdl", "rldl"):
                    res_type = "channel" if action_code == "chdl" else "role"
                    if not self.snapshot_store.get_restored_id(guild_id, res_type, target_id):
                        await self._execute_recovery(
                            guild, action_code, target_id, containment_success=res.success, target_entity=target_entity
                        )
                return res

        if not resolved_actor:
            if incident.claimed_by in ("fast_gateway", "audit_stream"):
                res = await incident.wait_for_containment(timeout=0.5)
                if res and res.success:
                    return res
            logger.warning("[V2Detection] Fallback could not resolve actor for %s in guild %s", action_code, guild_id)
            res = ContainmentResult(
                success=False,
                punishment=PunishmentType.BAN,
                actor_id=0,
                guild_id=guild_id,
                error_code="ACTOR_UNRESOLVED",
            )
            self.incident_tracker.set_containment_result(guild_id, action_code, target_id, res)
            return res

        # 4. Record event in AttackModeManager
        if not self.state_store.is_guild_loaded(guild_id):
            await self.state_store.load_guild_from_db(guild_id)
        if not self.state_store.is_guild_loaded(guild_id):
            actor_id = getattr(resolved_actor, "id", 0)
            logger.error("[V2Detection] Security state unavailable for guild %s; skipped fallback action %s", guild_id, action_code)
            result = ContainmentResult(
                success=False,
                punishment=PunishmentType.BAN,
                actor_id=actor_id,
                guild_id=guild_id,
                error_code="SECURITY_STATE_UNAVAILABLE",
            )
            self.incident_tracker.set_containment_result(guild_id, action_code, target_id, result)
            return result
        state = self.state_store.get_guild_config(guild_id)
        if action_code == "botadd" and target_id:
            self.state_store.record_new_bot(guild_id, target_id, time.time())
        if self.attack_mode.record_event(guild_id):
            self.attack_mode.escalate_state(guild_id, state)

        trace = V2SecurityTrace(
            event_id=target_id or 0,
            guild_id=guild_id,
            action=action_code,
            path="entity_fallback",
            actor_id=resolved_actor.id,
            target_id=target_id,
            dry_run=getattr(state, "dry_run", False),
            is_warm_connection=discord_connection_warmer.is_connection_warm(),
        )

        # 5. Evaluate policy
        context = PolicyContext(
            event_time=time.time(),
            target_id=target_id,
            raw_entry_target_id=target_id,
            actor_is_bot=bool(getattr(resolved_actor, "bot", False)),
        )

        decision = evaluate_policy(
            guild=guild,
            actor=resolved_actor,
            action=action_code,
            target=target_id,
            context=context,
            state=state,
            role_index=self.role_index,
            rate_limiter=self.rate_limiter,
            bot_owner_ids=self.state_store.get_bot_owner_ids(),
        )
        trace.record_decision(decision.reason_code)

        # 6. Execute containment if punished (with dry_run check)
        if decision.is_punish and decision.punishment:
            if getattr(state, "dry_run", False):
                logger.info(
                    "[V2-DRY-RUN] What V2 would do: Neutralize actor %s for action %s (Reason: %s)",
                    resolved_actor.id, action_code, decision.reason_code
                )
                trace.finish(result="dry_run")
                v2_trace_aggregator.record_trace(trace)
                result = ContainmentResult(
                    success=True,
                    punishment=decision.punishment,
                    actor_id=resolved_actor.id,
                    guild_id=guild_id,
                    error_code="DRY_RUN_SIMULATED",
                )
                self.incident_tracker.set_containment_result(guild_id, action_code, target_id, result)
                return result

            trace.record_ban_sent()

            # High-vigilance probation breach: escalate attack mode immediately
            if decision.reason_code == "NEW_BOT_UNAUTHORIZED_ACTION":
                self.attack_mode.escalate_state(guild_id, state)

            RECOVERY_AFTER_PUNISHMENT_ACTIONS = {
                "chcr", "rlcr", "chup", "rlup", "chdl", "rldl", "webhook_create", "webhook_update",
                "webhook_delete", "emodl", "mngweb", "botadd", "memup", "serverup", "vanity", "everyone",
                "antiEveryoneMention", "ban", "unban"
            }
            recovery_after_punishment = action_code in RECOVERY_AFTER_PUNISHMENT_ACTIONS
            if recovery_after_punishment:
                try:
                    result = await self.neutralizer.execute_containment(
                        guild=guild,
                        actor=resolved_actor,
                        punishment=decision.punishment,
                        reason=f"[{action_code}] {decision.reason_code}",
                    )
                except Exception:
                    logger.exception("[V2] Punishment failed for actor %s in guild %s", resolved_actor.id, guild_id)
                    result = ContainmentResult(
                        success=False,
                        punishment=decision.punishment,
                        actor_id=resolved_actor.id,
                        guild_id=guild_id,
                        error_code="SEQUENTIAL_CONTAINMENT_ERROR",
                    )
                if not isinstance(result, ContainmentResult):
                    result = ContainmentResult(
                        success=False,
                        punishment=decision.punishment,
                        actor_id=resolved_actor.id,
                        guild_id=guild_id,
                        error_code="INVALID_CONTAINMENT_RESULT",
                    )
            else:
                result = await self.neutralizer.execute_containment(
                    guild=guild,
                    actor=resolved_actor,
                    punishment=decision.punishment,
                    reason=f"[{action_code}] {decision.reason_code}",
                )
                if result.success and action_code in ("chdl", "rldl", "webhook_delete", "emodl"):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._execute_recovery(guild, action_code, target_id, containment_success=True))
                    except Exception:
                        pass
            discord_connection_warmer.record_http_activity()
            trace.record_ban_response(
                http_status=getattr(result, "http_status", 204 if result.success else 400),
                success=result.success,
                ratelimit_wait_ms=getattr(result, "ratelimit_wait_ms", 0.0),
                http_rtt_ms=getattr(result, "http_rtt_ms", 0.0),
            )
            trace.finish(result="success" if result.success else "failed")
            v2_trace_aggregator.record_trace(trace)

            # 1. Ban/containment result is recorded immediately (microsecond 0)
            self.incident_tracker.set_containment_result(guild_id, action_code, target_id, result)

            # 2. Recovery runs post-containment as a decoupled background task
            if recovery_after_punishment and result.success:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        self._execute_recovery(
                            guild=guild,
                            action_code=action_code,
                            target_id=target_id,
                            containment_success=result.success,
                            target_entity=target_entity,
                        )
                    )
                except Exception as exc:
                    logger.debug("[V2] Could not schedule post-containment recovery: %s", exc)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.notifier.dispatch_incident(
                        guild=guild,
                        action=action_code,
                        actor=resolved_actor,
                        target=target_entity or target_id,
                        result=result,
                        decision=decision,
                        state=state,
                        details=(
                            f"🚨 [High-Vigilance Probation] Newly joined bot intercepted performing unauthorized {action_code.upper()}! Instantly banned & action reversed."
                            if decision.reason_code == "NEW_BOT_UNAUTHORIZED_ACTION"
                            else f"[{action_code}] {decision.reason_code}"
                        ),
                    )
                )
            except Exception:
                pass

            return result
        else:
            trace.finish(result="skipped")
            v2_trace_aggregator.record_trace(trace)
            if decision.action == DecisionAction.ALLOW and action_code in (
                "chcr", "chup", "chdl", "rlcr", "rlup", "rldl", "serverup", "emodl", "emocr"
            ):
                self.schedule_baseline_refresh(guild, delay=30.0)

            result = ContainmentResult(
                success=False,
                punishment=decision.punishment or PunishmentType.BAN,
                actor_id=resolved_actor.id,
                guild_id=guild_id,
                error_code=f"NON_PUNISH_{decision.action.value.upper()}",
            )
            self.incident_tracker.set_containment_result(guild_id, action_code, target_id, result)
            return result
