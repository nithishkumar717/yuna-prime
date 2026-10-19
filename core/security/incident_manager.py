import time
import asyncio
from enum import Enum
from typing import Dict, List
from core.discord.request_manager import request_manager


class IncidentState(Enum):
    NORMAL = "NORMAL"
    SUSPICIOUS = "SUSPICIOUS"
    ATTACK = "ATTACK"
    RECOVERY = "RECOVERY"


class IncidentManager:
    """Incident & Attack Mode State Machine for Yuna V7.00.
    
    Monitors raid event frequencies per guild. When rapid attack triggers are detected,
    shifts the guild into ATTACK mode and signals RequestManager to allocate 100% capacity to P0/P1 actions.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IncidentManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, attack_threshold: int = 3, window_seconds: float = 5.0):
        if self._initialized:
            return
        self.attack_threshold = attack_threshold
        self.window_seconds = window_seconds
        # Structure: {guild_id: [timestamp, ...]}
        self.event_timestamps: Dict[int, List[float]] = {}
        self.states: Dict[int, IncidentState] = {}
        self._initialized = True

    def register_event(self, guild_id: int) -> IncidentState:
        """Registers a destructive security event and evaluates guild incident state."""
        now = time.time()
        if guild_id not in self.event_timestamps:
            self.event_timestamps[guild_id] = []
            self.states[guild_id] = IncidentState.NORMAL

        timestamps = self.event_timestamps[guild_id]
        timestamps.append(now)

        # Filter timestamps within window
        valid_timestamps = [t for t in timestamps if now - t <= self.window_seconds]
        self.event_timestamps[guild_id] = valid_timestamps

        count = len(valid_timestamps)
        current_state = self.states.get(guild_id, IncidentState.NORMAL)

        if count >= self.attack_threshold and current_state != IncidentState.ATTACK:
            self.states[guild_id] = IncidentState.ATTACK
            request_manager.set_attack_mode(True)
            print(f"[INCIDENT MANAGER ATTACK MODE] Guild {guild_id} shifted to ATTACK MODE ({count} events in {self.window_seconds}s).")
            # Schedule recovery reset after 30s
            loop = asyncio.get_event_loop()
            loop.create_task(self._schedule_recovery(guild_id, delay=30.0))
            return IncidentState.ATTACK

        elif count >= 2 and current_state == IncidentState.NORMAL:
            self.states[guild_id] = IncidentState.SUSPICIOUS
            return IncidentState.SUSPICIOUS

        return self.states.get(guild_id, IncidentState.NORMAL)

    async def _schedule_recovery(self, guild_id: int, delay: float):
        await asyncio.sleep(delay)
        self.states[guild_id] = IncidentState.RECOVERY
        request_manager.set_attack_mode(False)
        print(f"[INCIDENT MANAGER RECOVERY MODE] Guild {guild_id} shifted to RECOVERY MODE.")
        await asyncio.sleep(10)
        self.states[guild_id] = IncidentState.NORMAL

    def get_state(self, guild_id: int) -> IncidentState:
        return self.states.get(guild_id, IncidentState.NORMAL)


# Global singleton instance
incident_manager = IncidentManager()
