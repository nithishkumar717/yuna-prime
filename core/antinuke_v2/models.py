"""Anti-Nuke V2 Engine — Data Models and Decision Structures.

Defines the pure policy decision results, punishment types, action codes,
and contextual metadata required for deterministic, zero-I/O security decisions.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


class DecisionAction(str, enum.Enum):
    """The high-level action to be taken by the containment layer."""
    ALLOW = "allow"
    PUNISH = "punish"
    ALERT_ONLY = "alert_only"


class PunishmentType(str, enum.Enum):
    """The type of punishment configured for a violation."""
    BAN = "ban"
    KICK = "kick"
    DEMOTE = "demote"
    TIMEOUT = "timeout"


# Standardized Anti-Nuke Action Identifiers
PROTECTED_ACTIONS = (
    "chcr",      # channel create
    "chdl",      # channel delete
    "chup",      # channel update
    "rlcr",      # role create
    "rldl",      # role delete
    "rlup",      # role update
    "ban",       # member ban
    "kick",      # member kick
    "prune",     # member prune
    "botadd",    # bot add
    "serverup",  # guild update
    "memup",     # member role update
    "mngweb",    # manage webhook
    "everyone",  # mass mention
)


@dataclass(frozen=True, slots=True)
class Decision:
    """The outcome of a pure, synchronous policy evaluation.
    
    Guaranteed zero I/O and zero latency in creation.
    """
    action: DecisionAction
    reason_code: str
    punishment: Optional[PunishmentType] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.action == DecisionAction.ALLOW

    @property
    def is_punish(self) -> bool:
        return self.action == DecisionAction.PUNISH

    @property
    def is_alert_only(self) -> bool:
        return self.action == DecisionAction.ALERT_ONLY


@dataclass(slots=True)
class PolicyContext:
    """Contextual metadata surrounding the security event.
    
    Contains timing, attribution details, and resolution state.
    """
    event_time: float
    audit_entry_created_at: Optional[datetime] = None
    target_id: Optional[int] = None
    raw_entry_target_id: Optional[int] = None
    age_limit_seconds: float = 5.0
    actor_is_bot: bool = False
    actor_unresolved: bool = False
    dry_run: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)
