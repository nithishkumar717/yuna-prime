import time
import asyncio
import datetime
import pytz
import discord
from typing import Dict, Tuple, Optional


class AuditLogCoordinator:
    """Centralized Audit Log Fetch Coordinator with short-term (3s TTL) in-memory caching.
    
    Deduplicates concurrent audit log queries across multiple AntiNuke cogs to prevent API rate limiting.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuditLogCoordinator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, ttl_seconds: float = 3.0):
        if self._initialized:
            return
        # Cache structure: {(guild_id, action_value, target_id): (entry, timestamp)}
        self._cache: Dict[Tuple[int, int, Optional[int]], Tuple[Optional[discord.AuditLogEntry], float]] = {}
        self.ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()
        self._initialized = True

    async def fetch_audit_log(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        target_id: Optional[int] = None
    ) -> Optional[discord.AuditLogEntry]:
        """Fetches latest audit log entry or returns cached entry if requested within TTL window."""
        if not guild or not guild.me.guild_permissions.view_audit_log:
            return None

        cache_key = (guild.id, action.value, target_id)
        now = time.time()

        async with self.lock_key(cache_key):
            # Check cache
            if cache_key in self._cache:
                entry, ts = self._cache[cache_key]
                if now - ts < self.ttl_seconds:
                    return entry

            # Perform REST fetch
            try:
                found_entry = None
                utc_now = datetime.datetime.now(pytz.utc)
                async for entry in guild.audit_logs(action=action, limit=5):
                    if target_id is None or (entry.target and entry.target.id == target_id):
                        # Ensure entry is recent (within last 1 hour)
                        if (utc_now - entry.created_at).total_seconds() < 3600:
                            found_entry = entry
                            break

                self._cache[cache_key] = (found_entry, now)
                return found_entry
            except Exception as e:
                print(f"[AUDIT COORDINATOR WARNING] Error fetching audit logs for guild {guild.id}: {e}")
                return None

    def lock_key(self, cache_key):
        return self._lock


# Global singleton instance
audit_coordinator = AuditLogCoordinator()
