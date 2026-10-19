"""Anti-Nuke V2 Engine — WebSocket Audit Stream Health Tracker.

Tracks the real-time delivery health of Discord's GUILD_AUDIT_LOG_ENTRY_CREATE stream.
Ensures fallback entity listeners yield adaptively ONLY when the stream is proven healthy,
and proceed immediately with 0 ms delay when the stream is lagged, disconnected, or unverified.
"""
from __future__ import annotations

import time
from typing import Dict, Optional


class StreamHealthTracker:
    """Tracks per-guild audit stream freshness and determines adaptive fallback waiting."""

    __slots__ = ("_last_stream_event", "_stream_failures", "_default_healthy_window")

    def __init__(self, healthy_window_seconds: float = 300.0) -> None:
        # guild_id -> monotonic timestamp of last audit stream entry received
        self._last_stream_event: Dict[int, float] = {}
        # guild_id -> consecutive failure count
        self._stream_failures: Dict[int, int] = {}
        self._default_healthy_window = healthy_window_seconds

    def record_stream_event(self, guild_id: int, now: Optional[float] = None) -> None:
        """Records the successful receipt of a gateway audit stream entry for a guild."""
        if now is None:
            now = time.monotonic()
        self._last_stream_event[guild_id] = now
        self._stream_failures[guild_id] = 0

    def record_stream_failure(self, guild_id: int) -> None:
        """Records an audit stream desync or delivery failure."""
        self._stream_failures[guild_id] = self._stream_failures.get(guild_id, 0) + 1

    def is_stream_healthy(self, guild_id: int, now: Optional[float] = None) -> bool:
        """Checks if the gateway audit stream is actively healthy for the guild.
        
        Returns False if no stream event has been seen recently or if failures are recorded.
        """
        if now is None:
            now = time.monotonic()

        last_time = self._last_stream_event.get(guild_id)
        if last_time is None:
            # Stream has never delivered an event for this guild
            return False

        if self._stream_failures.get(guild_id, 0) > 0:
            return False

        return (now - last_time) <= self._default_healthy_window

    def get_adaptive_wait(self, guild_id: int, healthy_wait: float = 0.05, now: Optional[float] = None) -> float:
        """Returns the dynamic wait duration for fallback entity listeners.
        
        - If stream is healthy: returns a tiny micro-yield (default 50 ms) to let the stream claim.
        - If stream is unhealthy: returns 0.0 ms (proceed immediately with REST fallback).
        """
        if self.is_stream_healthy(guild_id, now=now):
            return healthy_wait
        return 0.0

    def prune_guild(self, guild_id: int) -> None:
        """Prunes health tracking state on guild removal."""
        self._last_stream_event.pop(guild_id, None)
        self._stream_failures.pop(guild_id, None)
