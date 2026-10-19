"""Anti-Nuke V2 Engine — Dynamic Feature Flag Router & Shadow Mode Comparator.

Governs multi-engine routing across:
1. 'legacy': Existing V1 anti-nuke execution path (V2 dormant).
2. 'shadow': Legacy performs live containment; V2 runs concurrently in dry-run mode,
   evaluating policy and logging any decision divergence without taking action.
3. 'v2': Next-generation sub-millisecond V2 engine handles full detection, containment,
   recovery, and notifications.

Supports instant, zero-downtime rollback globally and per-guild.
"""
from __future__ import annotations

import asyncio
import enum
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple, Union

import discord

from core.antinuke_v2.action_mapper import ActionMapper
from core.antinuke_v2.containment import ContainmentResult
from core.antinuke_v2.detection_coordinator import DetectionCoordinator
from core.antinuke_v2.models import Decision, DecisionAction, PolicyContext, PunishmentType
from core.antinuke_v2.resolver import ActorResolver

logger = logging.getLogger("antinuke.v2.router")


class EngineMode(str, enum.Enum):
    """The operational mode for Anti-Nuke execution."""
    LEGACY = "legacy"
    SHADOW = "shadow"
    V2 = "v2"

    @classmethod
    def from_str(cls, val: Any) -> "EngineMode":
        if not val:
            return cls.V2
        if isinstance(val, cls):
            return val
        s = getattr(val, "value", str(val)).strip().lower().split(".")[-1]
        if s in ("v2", "nextgen", "new"):
            return cls.V2
        if s in ("legacy", "v1", "old"):
            return cls.LEGACY
        if s in ("shadow", "dry_run", "audit"):
            return cls.SHADOW
        return cls.V2


@dataclass(slots=True)
class ShadowDivergenceRecord:
    """Detailed log record of a discrepancy between Legacy and V2 decisions in shadow mode."""
    timestamp: float
    guild_id: int
    action: str
    actor_id: int
    target_id: Optional[int]
    legacy_decision: str
    v2_decision: str
    v2_reason: str
    v2_punishment: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_log_string(self) -> str:
        dt_str = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return (
            f"[SHADOW DIVERGENCE] {dt_str} | Guild: {self.guild_id} | Action: {self.action} | "
            f"Actor: {self.actor_id} | Legacy: {self.legacy_decision} vs V2: {self.v2_decision} "
            f"(v2_reason={self.v2_reason}, v2_punishment={self.v2_punishment})"
        )


class V2EngineRouter:
    """Manages global and per-guild engine modes, shadow execution, and divergence auditing."""

    __slots__ = (
        "coordinator",
        "_global_mode",
        "_guild_modes",
        "_divergences",
        "_lock",
    )

    def __init__(
        self,
        coordinator: Optional[DetectionCoordinator] = None,
        default_mode: Optional[Union[str, EngineMode]] = None,
        max_divergence_history: int = 200,
    ) -> None:
        self.coordinator = coordinator or DetectionCoordinator()
        
        # Anti-Nuke V2 is the default primary engine across the entire bot
        env_mode = os.getenv("ANTINUKE_ENGINE")
        if default_mode is not None:
            self._global_mode = EngineMode.from_str(default_mode)
        elif env_mode:
            self._global_mode = EngineMode.from_str(env_mode)
        else:
            self._global_mode = EngineMode.V2

        # guild_id -> EngineMode override
        self._guild_modes: Dict[int, EngineMode] = {}
        # Bounded ring buffer for divergence auditing
        self._divergences: Deque[ShadowDivergenceRecord] = deque(maxlen=max_divergence_history)
        self._lock = asyncio.Lock()

    @property
    def global_mode(self) -> EngineMode:
        return self._global_mode

    def set_global_mode(self, mode: Union[str, EngineMode]) -> EngineMode:
        """Sets the global engine mode across all unconfigured guilds."""
        parsed = EngineMode.from_str(mode)
        self._global_mode = parsed
        logger.info("[V2EngineRouter] Global Anti-Nuke engine mode set to %s", parsed.value)
        return parsed

    def get_engine_mode(self, guild_id: Optional[int] = None) -> EngineMode:
        """Resolves the active engine mode for a specific guild."""
        if guild_id is not None and guild_id in self._guild_modes:
            return self._guild_modes[guild_id]
        return self._global_mode

    def set_guild_engine_mode(self, guild_id: int, mode: Union[str, EngineMode]) -> EngineMode:
        """Sets a per-guild engine override with sub-millisecond RAM effect."""
        parsed = EngineMode.from_str(mode)
        self._guild_modes[guild_id] = parsed
        logger.info("[V2EngineRouter] Guild %s engine mode set to %s", guild_id, parsed.value)
        return parsed

    def clear_guild_engine_mode(self, guild_id: int) -> None:
        """Removes the per-guild override, falling back to global mode."""
        self._guild_modes.pop(guild_id, None)
        logger.info("[V2EngineRouter] Cleared engine override for guild %s (now %s)", guild_id, self._global_mode.value)

    def record_divergence(
        self,
        guild_id: int,
        action: str,
        actor_id: int,
        legacy_decision: str,
        v2_decision: str,
        v2_reason: str,
        v2_punishment: Optional[str] = None,
        target_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ShadowDivergenceRecord:
        """Records a discrepancy between legacy and V2 decisions for observability."""
        rec = ShadowDivergenceRecord(
            timestamp=time.time(),
            guild_id=guild_id,
            action=action,
            actor_id=actor_id,
            target_id=target_id,
            legacy_decision=legacy_decision,
            v2_decision=v2_decision,
            v2_reason=v2_reason,
            v2_punishment=v2_punishment,
            details=details or {},
        )
        self._divergences.append(rec)
        logger.warning(rec.to_log_string())
        return rec

    def get_recent_divergences(self, limit: int = 20, guild_id: Optional[int] = None) -> List[ShadowDivergenceRecord]:
        """Returns the most recent divergence records, optionally filtered by guild."""
        records = list(self._divergences)
        if guild_id is not None:
            records = [r for r in records if r.guild_id == guild_id]
        return records[-limit:]

    async def handle_v2_audit_stream(self, entry: Any) -> Optional[ContainmentResult]:
        """Direct entry point for V2 primary audit log processing."""
        return await self.coordinator.handle_audit_stream_entry(entry)

    async def handle_v2_entity_fallback(
        self,
        guild: Any,
        action: str,
        target_id: Optional[int],
        actor: Optional[Any] = None,
        audit_resolver: Optional[Callable[[], Any]] = None,
        target_entity: Optional[Any] = None,
    ) -> Optional[ContainmentResult]:
        """Direct entry point for V2 primary entity fallback processing."""
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action=action,
            target_id=target_id,
            actor=actor,
            audit_resolver=audit_resolver,
            target_entity=target_entity,
        )

    async def handle_v2_channel_create(self, channel: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for guild channel create events."""
        guild = getattr(channel, "guild", None)
        if not guild:
            return None
        ch_id = getattr(channel, "id", None)
        ch_name = str(getattr(channel, "name", "")).lower()
        if ch_id and any(p in ch_name for p in ("nuked", "raided", "hacked", "wiped")):
            if hasattr(self.coordinator, "incident_tracker"):
                self.coordinator.incident_tracker.mark_rogue_channel(ch_id)
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="chcr",
            target_id=ch_id,
            target_entity=channel,
        )

    async def handle_v2_channel_delete(self, channel: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for guild channel delete events."""
        guild = getattr(channel, "guild", None)
        if not guild:
            return None
        ch_id = getattr(channel, "id", None)
        if ch_id and hasattr(self.coordinator, "incident_tracker") and self.coordinator.incident_tracker.is_rogue_channel(ch_id):
            logger.info("[Router] Ignoring deletion of rogue channel %s (created during raid)", ch_id)
            return None
        ch_name = str(getattr(channel, "name", "")).lower()
        if any(p in ch_name for p in ("nuked", "raided", "hacked", "wiped")):
            logger.info("[Router] Ignoring deletion of raid-named channel '%s' (%s)", ch_name, ch_id)
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="chdl",
            target_id=ch_id,
            target_entity=channel,
        )

    async def handle_v2_channel_update(self, before: Any, after: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for guild channel update events."""
        guild = getattr(after, "guild", None) or getattr(before, "guild", None)
        if not guild:
            return None
        # Fast-Path: Ignore harmless voice channel bitrate/status adjustments
        if hasattr(before, "bitrate") and hasattr(after, "bitrate"):
            if getattr(before, "name", None) == getattr(after, "name", None) and getattr(before, "category_id", None) == getattr(after, "category_id", None) and getattr(before, "overwrites", None) == getattr(after, "overwrites", None):
                return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="chup",
            target_id=getattr(after, "id", None),
            target_entity=before,
        )

    async def handle_v2_role_create(self, role: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for guild role create events."""
        guild = getattr(role, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="rlcr",
            target_id=getattr(role, "id", None),
            target_entity=role,
        )

    async def handle_v2_role_delete(self, role: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for guild role delete events."""
        guild = getattr(role, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="rldl",
            target_id=getattr(role, "id", None),
            target_entity=role,
        )

    async def handle_v2_role_update(self, before: Any, after: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for guild role update events."""
        guild = getattr(after, "guild", None) or getattr(before, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="rlup",
            target_id=getattr(after, "id", None),
            target_entity=before,
        )

    async def handle_v2_bot_add(self, member: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for unauthorized bot addition."""
        target_id = getattr(member, "id", None)
        from utils.config import SIBLING_BOT_IDS
        if target_id in SIBLING_BOT_IDS:
            return None
        guild = getattr(member, "guild", None)
        if not guild:
            return None

        try:
            j_ts = getattr(member, "joined_at", None)
            ts = j_ts.timestamp() if j_ts else time.time()
            self.coordinator.state_store.record_new_bot(guild.id, getattr(member, "id", 0), ts)
        except Exception:
            pass
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="botadd",
            target_id=getattr(member, "id", None),
            target_entity=member,
        )

    async def handle_v2_member_ban(self, guild: Any, user: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for member ban events."""
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="ban",
            target_id=getattr(user, "id", None),
            target_entity=user,
        )

    async def handle_v2_member_unban(self, guild: Any, user: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for member unban events."""
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="unban",
            target_id=getattr(user, "id", None),
            target_entity=user,
        )

    async def handle_v2_member_kick(self, member: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for member kick events."""
        guild = getattr(member, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="kick",
            target_id=getattr(member, "id", None),
            target_entity=member,
        )

    async def handle_v2_member_prune(self, member: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for member prune events."""
        guild = getattr(member, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="prune",
            target_id=getattr(member, "id", None),
            target_entity=member,
        )

    async def handle_v2_guild_update(self, before: Any, after: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for guild update events."""
        guild = before or after
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="serverup",
            target_id=getattr(guild, "id", None),
            target_entity=before,
        )

    async def handle_v2_webhook_create(self, channel: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for webhook create events."""
        guild = getattr(channel, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="webhook_create",
            target_id=getattr(channel, "id", None),
            target_entity=channel,
        )

    async def handle_v2_webhook_update(self, channel: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for webhook update events."""
        guild = getattr(channel, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="webhook_update",
            target_id=getattr(channel, "id", None),
            target_entity=channel,
        )

    async def handle_v2_webhook_delete(self, channel: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for webhook delete events."""
        guild = getattr(channel, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="webhook_delete",
            target_id=getattr(channel, "id", None),
            target_entity=channel,
        )

    async def handle_v2_member_update(self, before: Any, after: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for member update (role grant) events."""
        guild = getattr(after, "guild", None) or getattr(before, "guild", None)
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="memup",
            target_id=getattr(after, "id", None),
            target_entity=after,
        )

    async def handle_v2_everyone_mention(self, message: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for mass mention (@everyone/@here) events."""
        guild = getattr(message, "guild", None)
        author = getattr(message, "author", None)
        if not guild or not author:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="everyone",
            target_id=author.id,
            actor=author,
            target_entity=message,
        )

    async def handle_v2_integration_update(self, guild: Any) -> Optional[ContainmentResult]:
        """Zero-latency handler for guild integration update events."""
        if not guild:
            return None
        return await self.coordinator.handle_entity_fallback(
            guild=guild,
            action="integration",
            target_id=getattr(guild, "id", None),
            target_entity=guild,
        )

    async def run_shadow_audit_stream(
        self,
        entry: Any,
        legacy_decision: str,
    ) -> Optional[ShadowDivergenceRecord]:
        """Runs V2 in shadow mode against a live audit entry and audits divergence with legacy.
        
        Guaranteed zero mutations or bans (strictly dry_run=True).
        """
        try:
            guild = getattr(entry, "guild", None)
            if not guild:
                return None

            user_id = getattr(entry, "user_id", getattr(getattr(entry, "user", None), "id", None))
            if not user_id:
                return None

            actor_id = int(user_id)
            user = getattr(entry, "user", None) or discord.Object(id=actor_id)

            # Map action
            action_code, target_id, extra = ActionMapper.map_audit_entry(entry)
            if not action_code:
                return None

            state = self.coordinator.state_store.get_guild_config(guild.id)
            
            # Context explicitly marked dry_run=True
            created_at = getattr(entry, "created_at", None)
            raw_target_id = getattr(entry, "target_id", None) or getattr(entry, "_target_id", None)
            if raw_target_id is None and hasattr(entry, "target") and hasattr(entry.target, "id"):
                raw_target_id = entry.target.id

            context = PolicyContext(
                event_time=time.time(),
                audit_entry_created_at=created_at,
                target_id=target_id,
                raw_entry_target_id=raw_target_id,
                actor_is_bot=bool(getattr(user, "bot", False)),
                dry_run=True,
                extra=extra,
            )

            # Synchronous decision evaluation (0ms CPU)
            from core.antinuke_v2.engine import evaluate_policy
            decision = evaluate_policy(
                guild=guild,
                actor=user,
                action=action_code,
                target=getattr(entry, "target", None),
                context=context,
                state=state,
                role_index=self.coordinator.role_index,
                rate_limiter=self.coordinator.rate_limiter,
                bot_owner_ids=self.coordinator.state_store.get_bot_owner_ids(),
            )

            v2_decision_str = "BAN" if decision.is_punish else ("ALERT" if decision.is_alert_only else "ALLOW")
            normalized_legacy = "BAN" if legacy_decision.upper() in ("BAN", "PUNISH", "CONTAIN") else "ALLOW"

            if v2_decision_str != normalized_legacy:
                return self.record_divergence(
                    guild_id=guild.id,
                    action=action_code,
                    actor_id=actor_id,
                    legacy_decision=legacy_decision,
                    v2_decision=v2_decision_str,
                    v2_reason=decision.reason_code,
                    v2_punishment=decision.punishment.value if decision.punishment else None,
                    target_id=target_id,
                    details=decision.details,
                )
            return None
        except Exception as e:
            logger.debug("[V2EngineRouter] Shadow evaluation error: %s", e)
            return None


# Global singleton instance
v2_engine_router = V2EngineRouter()
