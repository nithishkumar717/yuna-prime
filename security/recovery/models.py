from enum import Enum
from typing import List, Dict, Any
from dataclasses import dataclass, field


class RollbackAction(Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class RecoveryStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class Snapshot:
    snapshot_id: str
    guild_id: int
    timestamp: float
    payload: Dict[str, Any]
    hash_signature: str = ""


@dataclass
class RollbackTask:
    action: RollbackAction
    resource_type: str
    resource_id: str
    data: Dict[str, Any]


@dataclass
class RollbackPlan:
    target_snapshot_id: str
    tasks: List[RollbackTask] = field(default_factory=list)
