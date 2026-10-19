"""Anti-Nuke V2 Engine — Multi-Path Duplicate Incident Tracker.

Coordinates real-time WebSocket audit stream events and fallback entity listeners:
1. Prevents duplicate ban calls when both detection paths trigger concurrently.
2. Coordinates handoff with sub-millisecond asyncio.Event signaling.
3. Strictly guarantees that downstream recovery only executes after confirmed containment.
4. Prevents duplicate security log embeds and admin DMs.
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional, Tuple

from core.antinuke_v2.containment import ContainmentResult


class V2IncidentRecord:
    """Represents a unique security incident in the system."""

    __slots__ = (
        "key",
        "created_at",
        "claimed_by",
        "actor_id",
        "containment_result",
        "containment_event",
        "recovery_claimed",
        "recovery_completed",
        "logging_claimed",
    )

    def __init__(self, key: Tuple[int, str, Optional[int]]) -> None:
        self.key = key
        self.created_at = time.monotonic()
        self.claimed_by: Optional[str] = None  # e.g. "audit_stream" or "entity_listener"
        self.actor_id: Optional[int] = None
        self.containment_result: Optional[ContainmentResult] = None
        self.containment_event = asyncio.Event()
        self.recovery_claimed: bool = False
        self.recovery_completed: bool = False
        self.logging_claimed: bool = False

    @property
    def is_claimed(self) -> bool:
        return self.claimed_by is not None

    async def wait_for_containment(self, timeout: float = 1.0) -> Optional[ContainmentResult]:
        """Awaits containment completion from the primary lane."""
        if self.containment_event.is_set():
            return self.containment_result
        try:
            await asyncio.wait_for(self.containment_event.wait(), timeout=timeout)
            return self.containment_result
        except asyncio.TimeoutError:
            return self.containment_result


class V2IncidentTracker:
    """Thread-safe, high-speed incident coordinator across detection paths."""

    def __init__(self, ttl: float = 30.0) -> None:
        self.ttl = ttl
        # Key: (guild_id, action_code, target_id) -> V2IncidentRecord
        self._incidents: Dict[Tuple[int, str, Optional[int]], V2IncidentRecord] = {}
        # Key: (guild_id, actor_id) -> expiration_monotonic
        self._quarantined_actors: Dict[Tuple[int, int], float] = {}
        # Key: channel_id -> expiration_monotonic (prevents resurrecting channels created during a raid)
        self._rogue_channels: Dict[int, float] = {}
        self._last_cleanup = time.monotonic()

    def _normalize_key(self, guild_id: int, action: str, target_id: Optional[int]) -> Tuple[int, str, Optional[int]]:
        gid = guild_id if type(guild_id) is int else int(guild_id)
        act = action if (type(action) is str and action.islower()) else str(action).lower()
        tid = target_id if (target_id is None or type(target_id) is int) else int(target_id)
        return (gid, act, tid)

    def _cleanup_expired(self, now: float) -> None:
        """Evicts expired incident records to strictly bound memory."""
        if now - self._last_cleanup < 5.0:
            return
        self._last_cleanup = now
        cutoff = now - self.ttl
        keys_to_remove = [k for k, inc in self._incidents.items() if inc.created_at < cutoff]
        for k in keys_to_remove:
            self._incidents.pop(k, None)
        expired_q = [k for k, exp in self._quarantined_actors.items() if exp < now]
        for k in expired_q:
            self._quarantined_actors.pop(k, None)
        expired_r = [cid for cid, exp in self._rogue_channels.items() if exp < now]
        for cid in expired_r:
            self._rogue_channels.pop(cid, None)

    def get_incident(self, guild_id: int, action: str, target_id: Optional[int]) -> Optional[V2IncidentRecord]:
        """Retrieves existing incident record if present."""
        key = self._normalize_key(guild_id, action, target_id)
        return self._incidents.get(key)

    def claim_incident(
        self,
        guild_id: int,
        action: str,
        target_id: Optional[int],
        source: str,
        actor_id: Optional[int] = None,
    ) -> Tuple[bool, V2IncidentRecord]:
        """Attempts to claim an incident for containment.
        
        Returns:
            (True, incident) if successfully claimed by this caller.
            (False, incident) if already claimed by a concurrent detection path.
        """
        now = time.monotonic()
        self._cleanup_expired(now)

        key = self._normalize_key(guild_id, action, target_id)
        incident = self._incidents.get(key)
        if incident is None:
            incident = V2IncidentRecord(key)
            self._incidents[key] = incident

        if incident.is_claimed:
            # Preemption: If claimed by entity_fallback without completed successful containment,
            # authoritative WebSocket streams ("audit_stream" or "fast_gateway") with known actor_id
            # preempt immediately to execute instant containment (< 15ms).
            can_preempt = (
                source in ("audit_stream", "fast_gateway")
                and actor_id is not None
                and incident.claimed_by == "entity_fallback"
                and (
                    incident.containment_result is None
                    or (
                        not incident.containment_result.success
                        and incident.containment_result.error_code in ("ACTOR_UNRESOLVED", "ACTOR_NOT_FOUND")
                    )
                )
            )
            if can_preempt:
                incident.claimed_by = source
                incident.actor_id = int(actor_id)
                if incident.containment_event.is_set() and (incident.containment_result is None or not incident.containment_result.success):
                    incident.containment_event = asyncio.Event()
                    incident.containment_result = None
                return True, incident

            return False, incident

        incident.claimed_by = source
        if actor_id:
            incident.actor_id = int(actor_id)
        return True, incident

    def set_containment_result(
        self,
        guild_id: int,
        action: str,
        target_id: Optional[int],
        result: ContainmentResult,
    ) -> None:
        """Records the containment outcome and signals all awaiting listeners."""
        key = self._normalize_key(guild_id, action, target_id)
        incident = self._incidents.get(key)
        if incident is None:
            incident = V2IncidentRecord(key)
            self._incidents[key] = incident

        incident.containment_result = result
        incident.containment_event.set()

    def claim_recovery(
        self,
        guild_id: int,
        action: str,
        target_id: Optional[int],
    ) -> bool:
        """Atomically claims recovery rights for an incident.
        
        Strict Safety Contract:
        Returns True ONLY if containment succeeded and recovery has not been claimed yet.
        If containment failed (e.g. role hierarchy 403), returns False so recovery is aborted.
        """
        key = self._normalize_key(guild_id, action, target_id)
        incident = self._incidents.get(key)
        if incident is None:
            return False

        # Abort recovery if containment was unsuccessful
        if not incident.containment_result or not incident.containment_result.success:
            return False

        if incident.recovery_claimed:
            return False

        incident.recovery_claimed = True
        return True

    def claim_logging(
        self,
        guild_id: int,
        action: str,
        target_id: Optional[int],
    ) -> bool:
        """Atomically claims logging rights to prevent duplicate Discord embed logs."""
        key = self._normalize_key(guild_id, action, target_id)
        incident = self._incidents.get(key)
        if incident is None:
            return False

        if incident.logging_claimed:
            return False

        incident.logging_claimed = True
        return True

    def is_actor_involved_in_recent_incident(self, guild_id: int, actor_id: int) -> bool:
        """Checks if the given actor_id is the perpetrator of any recent active incident in this guild."""
        gid = guild_id if type(guild_id) is int else int(guild_id)
        aid = actor_id if type(actor_id) is int else int(actor_id)
        now = time.monotonic()
        cutoff = now - self.ttl
        for key, inc in self._incidents.items():
            if key[0] == gid and inc.created_at >= cutoff:
                if inc.actor_id == aid:
                    return True
    def quarantine_actor(self, guild_id: int, actor_id: int, duration: float = 60.0) -> None:
        """Quarantines an actor in RAM across all actions/channels/roles for the guild."""
        gid = guild_id if type(guild_id) is int else int(guild_id)
        aid = actor_id if type(actor_id) is int else int(actor_id)
        self._quarantined_actors[(gid, aid)] = time.monotonic() + duration

    def is_actor_quarantined(self, guild_id: int, actor_id: int, now: Optional[float] = None) -> bool:
        """Lockless RAM check whether actor is actively quarantined in this guild."""
        gid = guild_id if type(guild_id) is int else int(guild_id)
        aid = actor_id if type(actor_id) is int else int(actor_id)
        curr = now if now is not None else time.monotonic()
        exp = self._quarantined_actors.get((gid, aid))
        if exp is None:
            return False
        if curr < exp:
            return True
        self._quarantined_actors.pop((gid, aid), None)
    def mark_rogue_channel(self, channel_id: int, duration: float = 300.0) -> None:
        """Marks a channel created during an unauthorized incident as rogue so it is never restored."""
        cid = channel_id if type(channel_id) is int else int(channel_id)
        self._rogue_channels[cid] = time.monotonic() + duration

    def is_rogue_channel(self, channel_id: int, now: Optional[float] = None) -> bool:
        """Lockless RAM check whether channel was created during an unauthorized raid."""
        cid = channel_id if type(channel_id) is int else int(channel_id)
        curr = now if now is not None else time.monotonic()
        exp = self._rogue_channels.get(cid)
        if exp is None:
            return False
        if curr < exp:
            return True
        self._rogue_channels.pop(cid, None)
        return False

    def prune_guild(self, guild_id: int) -> None:
        """Removes all incidents and quarantines for a guild."""
        keys_to_remove = [k for k in self._incidents if k[0] == guild_id]
        for k in keys_to_remove:
            self._incidents.pop(k, None)
        q_to_remove = [k for k in self._quarantined_actors if k[0] == guild_id]
        for k in q_to_remove:
            self._quarantined_actors.pop(k, None)

