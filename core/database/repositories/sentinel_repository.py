from typing import Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from .incident_repository import IncidentRepository
from .security_event_repository import SecurityEventRepository
from .recovery_repository import RecoveryRepository
from .snapshot_repository import SnapshotRepository


class SentinelRepository:
    """Unified Aggregate Coordinator grouping Yuna's Sentinel security repositories."""

    def __init__(self, db: AsyncIOMotorDatabase, redis_client: Optional[Any] = None) -> None:
        self.incidents = IncidentRepository(db, redis_client=redis_client)
        self.events = SecurityEventRepository(db)
        self.recovery = RecoveryRepository(db)
        self.snapshots = SnapshotRepository(db)
