"""Anti-Nuke V2 Engine — Dynamic Attack Mode & Automated Lockdown.

Detects high-frequency raid attacks (N events in T seconds).
When triggered:
1. Immediately escalates all action thresholds to 1 (zero-tolerance).
2. Locks risky settings (blocks bot additions, webhooks, channel mass actions).
3. Automatically expires and restores normal operational limits once the attack subsides.
"""
from __future__ import annotations

import collections
import logging
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("antinuke.v2.attack_mode")


class AttackModeManager:
    """Manages high-frequency raid detection and automatic guild lockdown."""

    __slots__ = (
        "threshold_events",
        "window_seconds",
        "attack_duration",
        "_event_history",
        "_attack_until",
        "_locked_settings",
    )

    def __init__(
        self,
        threshold_events: int = 5,
        window_seconds: float = 10.0,
        attack_duration: float = 60.0,
    ) -> None:
        self.threshold_events = threshold_events
        self.window_seconds = window_seconds
        self.attack_duration = attack_duration

        # guild_id -> deque of event timestamps
        self._event_history: Dict[int, collections.deque[float]] = {}
        # guild_id -> expiration timestamp
        self._attack_until: Dict[int, float] = {}
        # guild_id -> original settings backup for clean restoration upon expiration
        self._locked_settings: Dict[int, Dict[str, Any]] = {}

    def is_in_attack_mode(self, guild_id: int, now: Optional[float] = None) -> bool:
        """Returns True if the guild is currently in escalated attack mode."""
        if now is None:
            now = time.monotonic()

        expiry = self._attack_until.get(guild_id)
        if expiry is None:
            return False

        if now >= expiry:
            # Attack mode has expired automatically
            self._expire_attack_mode(guild_id)
            return False

        return True

    def record_event(self, guild_id: int, now: Optional[float] = None) -> bool:
        """Records an event and evaluates if attack mode should trigger or extend.
        
        Returns True if the guild is currently in attack mode.
        """
        if now is None:
            now = time.monotonic()

        # If already in attack mode, extend the lockdown duration
        if self.is_in_attack_mode(guild_id, now=now):
            self._attack_until[guild_id] = now + self.attack_duration
            logger.debug("[AttackMode] Extended attack mode for guild %s until +%ss", guild_id, self.attack_duration)
            return True

        history = self._event_history.get(guild_id)
        if history is None:
            history = collections.deque()
            self._event_history[guild_id] = history

        # Evict timestamps outside the window
        cutoff = now - self.window_seconds
        while history and history[0] <= cutoff:
            history.popleft()

        history.append(now)

        if len(history) >= self.threshold_events:
            # Trigger Attack Mode!
            self._attack_until[guild_id] = now + self.attack_duration
            logger.warning(
                "[AttackMode] 🚨 ATTACK MODE TRIGGERED for guild %s! (%d events in %.1fs). Locking down server.",
                guild_id, len(history), self.window_seconds
            )
            return True

        return False

    def escalate_state(self, guild_id: int, state: Any, now: Optional[float] = None) -> None:
        """Escalates thresholds and locks risky settings on the guild's state."""
        if not self.is_in_attack_mode(guild_id, now=now):
            return

        # Backup original thresholds if not already backed up
        if guild_id not in self._locked_settings:
            original_thresholds = dict(getattr(state, "action_thresholds", {}))
            self._locked_settings[guild_id] = {
                "thresholds": original_thresholds,
            }

        # Escalate all action thresholds to 1 (zero tolerance for any destructive action)
        if hasattr(state, "action_thresholds"):
            for act in list(state.action_thresholds.keys()):
                state.action_thresholds[act] = (1, int(self.window_seconds))

    def _expire_attack_mode(self, guild_id: int) -> None:
        """Internal helper to automatically expire attack mode and clean up."""
        self._attack_until.pop(guild_id, None)
        self._locked_settings.pop(guild_id, None)
        self._event_history.pop(guild_id, None)
        logger.info("[AttackMode] 🛡️ Attack mode automatically expired for guild %s. Normal limits restored.", guild_id)

    def force_expire(self, guild_id: int) -> None:
        """Manually cancels attack mode for a guild."""
        self._expire_attack_mode(guild_id)

    def prune_guild(self, guild_id: int) -> None:
        """Removes all tracking data when the bot leaves the guild."""
        self._attack_until.pop(guild_id, None)
        self._locked_settings.pop(guild_id, None)
        self._event_history.pop(guild_id, None)
