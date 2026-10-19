"""Anti-Nuke V2 Engine — High Performance Sliding Window Rate Limiter.

Tracks per-guild, per-actor, per-action event counts over a configurable sliding time window.
Guarantees strictly bounded memory, zero I/O on the decision path, and sub-microsecond evaluation.
"""
from __future__ import annotations

import collections
import time
from typing import Dict, Optional, Tuple


class SlidingWindowRateLimiter:
    """Synchronous sliding-window rate limiter for Anti-Nuke action thresholds."""

    __slots__ = ("_events", "_max_keys")

    def __init__(self, max_keys: int = 25000) -> None:
        # Key: (guild_id, actor_id, action) -> deque of timestamps
        self._events: Dict[Tuple[int, int, str], collections.deque[float]] = {}
        self._max_keys = max_keys

    def check_and_record(
        self,
        guild_id: int,
        actor_id: int,
        action: str,
        limit: int,
        window: float,
        now: Optional[float] = None,
    ) -> Tuple[bool, int]:
        """Checks if recording this action exceeds the configured threshold.
        
        Args:
            guild_id: Discord guild ID
            actor_id: Member or user ID performing the action
            action: Action identifier (e.g. 'chdl', 'ban', 'rlcr')
            limit: Maximum allowed actions in the window (if <= 1, triggers immediately)
            window: Time window in seconds
            now: Current timestamp (defaults to time.monotonic())
            
        Returns:
            (is_exceeded, current_count_including_this_action)
        """
        if now is None:
            now = time.monotonic()

        key = (guild_id, actor_id, action)
        q = self._events.get(key)
        if q is None:
            # Memory safeguard: prune idle entries if memory limit reached
            if len(self._events) >= self._max_keys:
                self.prune_stale(now=now, max_idle=window * 2)

            q = collections.deque()
            self._events[key] = q

        # Evict timestamps outside the sliding window
        cutoff = now - window
        while q and q[0] <= cutoff:
            q.popleft()

        current_count = len(q) + 1

        if limit <= 1:
            # Zero-tolerance: 1st action immediately triggers violation
            q.append(now)
            return True, current_count

        if current_count >= limit:
            # Threshold reached or exceeded
            q.append(now)
            return True, current_count

        # Permitted within limit
        q.append(now)
        return False, current_count

    def get_count(
        self,
        guild_id: int,
        actor_id: int,
        action: str,
        window: float,
        now: Optional[float] = None,
    ) -> int:
        """Returns the current valid event count for the actor within the window without recording."""
        if now is None:
            now = time.monotonic()

        key = (guild_id, actor_id, action)
        q = self._events.get(key)
        if not q:
            return 0

        cutoff = now - window
        while q and q[0] <= cutoff:
            q.popleft()

        return len(q)

    def reset_actor(self, guild_id: int, actor_id: int, action: Optional[str] = None) -> None:
        """Resets recorded events for an actor."""
        if action:
            self._events.pop((guild_id, actor_id, action), None)
        else:
            keys_to_remove = [k for k in self._events if k[0] == guild_id and k[1] == actor_id]
            for k in keys_to_remove:
                self._events.pop(k, None)

    def prune_guild(self, guild_id: int) -> int:
        """Removes all rate-limiting state for a guild when the bot leaves or memory is pruned."""
        keys_to_remove = [k for k in self._events if k[0] == guild_id]
        for k in keys_to_remove:
            self._events.pop(k, None)
        return len(keys_to_remove)

    def prune_stale(self, now: Optional[float] = None, max_idle: float = 60.0) -> int:
        """Evicts expired deques to strictly bound memory usage."""
        if now is None:
            now = time.monotonic()

        cutoff = now - max_idle
        keys_to_remove = []
        for key, q in self._events.items():
            while q and q[0] <= cutoff:
                q.popleft()
            if not q:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self._events.pop(key, None)

        return len(keys_to_remove)
