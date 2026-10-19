import asyncio
import time
from typing import Dict, Tuple, Optional


class IncidentRecord:
    """Tracks the lifecycle of an ongoing or recently resolved Anti-Nuke incident.
    
    Coordinates the Gateway WebSocket stream (AuditStreamAntiNuke) and the entity event
    listeners, ensuring zero-latency handoffs, eliminating redundant REST audit log queries,
    and preventing duplicate bans and dual-delivery security logs.
    """
    __slots__ = (
        "key",
        "created_at",
        "handled_by",
        "offender_id",
        "ban_success",
        "event",
        "ban_event",
        "logged",
        "recovered",
    )

    def __init__(self, key: Tuple[int, str, Optional[int]]):
        self.key = key
        self.created_at = time.monotonic()
        self.handled_by: Optional[str] = None  # "audit_stream" or "entity_listener"
        self.offender_id: Optional[int] = None
        self.ban_success: bool = False
        self.event = asyncio.Event()
        self.ban_event = asyncio.Event()
        self.logged: bool = False
        self.recovered: bool = False

    @property
    def is_handled(self) -> bool:
        return self.handled_by is not None

    async def wait_for_ban(self, timeout: float = 1.0) -> bool:
        """Awaits the containment / ban completion for this incident."""
        if self.ban_event.is_set():
            return self.ban_success
        try:
            await asyncio.wait_for(self.ban_event.wait(), timeout=timeout)
            return self.ban_success
        except asyncio.TimeoutError:
            return self.ban_success


class SecurityIncidentCoordinator:
    """Zero-Latency Incident Coordinator for Yuna V7 Anti-Nuke.
    
    Bridges the Gateway WebSocket audit stream and entity event listeners:
    1. If the WebSocket stream arrives first or during a micro-yield, it signals the
       waiting entity listener via asyncio.Event in <1ms.
    2. The entity listener wakes up immediately, skips the expensive REST audit log GET query,
       skips duplicate offender banning, and executes entity recovery if required.
    3. If the WebSocket stream does not arrive within the micro-window (10ms), the entity
       listener proceeds to REST fallback, claiming the incident to suppress subsequent duplicate runs.
    4. Enforces single-dispatch for security logs and entity recovery.
    """

    _instance: Optional["SecurityIncidentCoordinator"] = None

    @classmethod
    def get_instance(cls) -> "SecurityIncidentCoordinator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, ttl: float = 15.0):
        # Key: (guild_id, action_col, target_id) -> IncidentRecord
        self._incidents: Dict[Tuple[int, str, Optional[int]], IncidentRecord] = {}
        self.ttl = ttl
        self._last_cleanup = time.monotonic()

    def _normalize_key(self, guild_id: int, action: str, target_id: Optional[int]) -> Tuple[int, str, Optional[int]]:
        tid = int(target_id) if target_id is not None else None
        return (int(guild_id), str(action).lower(), tid)

    def _maybe_cleanup(self):
        now = time.monotonic()
        if now - self._last_cleanup < 5.0:
            return
        self._last_cleanup = now
        expired = [k for k, inc in self._incidents.items() if now - inc.created_at > self.ttl]
        for k in expired:
            self._incidents.pop(k, None)

    def get_or_create(self, guild_id: int, action: str, target_id: Optional[int]) -> IncidentRecord:
        self._maybe_cleanup()
        key = self._normalize_key(guild_id, action, target_id)
        if key not in self._incidents:
            self._incidents[key] = IncidentRecord(key)
        return self._incidents[key]

    def claim_incident(
        self,
        guild_id: int,
        action: str,
        target_id: Optional[int],
        handler: str,
        offender_id: Optional[int] = None
    ) -> Tuple[bool, IncidentRecord]:
        """Attempts to claim an incident for containment processing.
        
        Returns:
            (True, incident) if successfully claimed by this caller.
            (False, incident) if already claimed by another path.
        """
        self._maybe_cleanup()
        key = self._normalize_key(guild_id, action, target_id)
        if key not in self._incidents:
            self._incidents[key] = IncidentRecord(key)
        inc = self._incidents[key]

        if inc.handled_by is not None:
            return False, inc

        inc.handled_by = handler
        if offender_id:
            inc.offender_id = int(offender_id)
        inc.event.set()
        return True, inc

    def set_ban_result(self, guild_id: int, action: str, target_id: Optional[int], ban_success: bool):
        key = self._normalize_key(guild_id, action, target_id)
        if key in self._incidents:
            inc = self._incidents[key]
            inc.ban_success = ban_success
            inc.ban_event.set()
            inc.event.set()

    def is_handled(self, guild_id: int, action: str, target_id: Optional[int]) -> bool:
        key = self._normalize_key(guild_id, action, target_id)
        inc = self._incidents.get(key)
        return bool(inc and inc.is_handled)

    def get_incident(self, guild_id: int, action: str, target_id: Optional[int]) -> Optional[IncidentRecord]:
        key = self._normalize_key(guild_id, action, target_id)
        return self._incidents.get(key)

    async def wait_for_stream(
        self,
        guild_id: int,
        action: str,
        target_id: Optional[int],
        timeout: float = 0.010
    ) -> Optional[IncidentRecord]:
        """Awaits Gateway WebSocket stream (AuditStreamAntiNuke) to claim and handle this incident.
        
        If already handled: returns immediately (<0.001ms).
        If signaled during wait: wakes up immediately (<0.01ms).
        If timeout expires: returns None so entity listener can proceed to REST fallback.
        """
        self._maybe_cleanup()
        key = self._normalize_key(guild_id, action, target_id)
        if key not in self._incidents:
            self._incidents[key] = IncidentRecord(key)
        inc = self._incidents[key]

        if inc.is_handled:
            return inc

        if timeout <= 0:
            return None

        try:
            await asyncio.wait_for(inc.event.wait(), timeout=timeout)
            return inc if inc.is_handled else None
        except asyncio.TimeoutError:
            return None

    def mark_logged(self, guild_id: int, action: str, target_id: Optional[int]) -> bool:
        """Atomically marks the incident as logged.
        
        Returns True if caller is the first to log this incident.
        Returns False if already logged (suppresses duplicate security embeds/DMs).
        """
        key = self._normalize_key(guild_id, action, target_id)
        inc = self.get_or_create(guild_id, action, target_id)
        if inc.logged:
            return False
        inc.logged = True
        return True

    def mark_recovered(self, guild_id: int, action: str, target_id: Optional[int]) -> bool:
        """Atomically marks the entity recovery as executed.
        
        Returns True if caller is the first to perform recovery.
        Returns False if already recovered (prevents duplicate recreation/restores).
        """
        inc = self.get_or_create(guild_id, action, target_id)
        if inc.recovered:
            return False
        inc.recovered = True
        return True

    def clear(self):
        """Resets coordinator state (primarily for test isolation)."""
        self._incidents.clear()


# Global singleton instance
security_coordinator = SecurityIncidentCoordinator.get_instance()
