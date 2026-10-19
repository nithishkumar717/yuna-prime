from dataclasses import asdict
from typing import Optional, List, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from security.recovery.models import Snapshot


class SnapshotRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's guild configuration backups/snapshots."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "guild_snapshots")

    def _to_document(self, snapshot: Snapshot) -> Dict[str, Any]:
        return {
            "id": snapshot.snapshot_id,
            "guild_id": snapshot.guild_id,
            "timestamp": snapshot.timestamp,
            "payload": asdict(snapshot)
        }

    def _to_entity(self, doc: Dict[str, Any]) -> Snapshot:
        payload = doc["payload"]
        return Snapshot(
            snapshot_id=payload["snapshot_id"],
            guild_id=payload["guild_id"],
            timestamp=payload["timestamp"],
            payload=payload["payload"],
            hash_signature=payload.get("hash_signature", "")
        )

    async def save_snapshot(self, snapshot: Snapshot, session: Optional[Any] = None) -> None:
        doc = self._to_document(snapshot)
        await self.collection.replace_one({"id": snapshot.snapshot_id}, doc, upsert=True, session=session)

    async def get_by_id(self, snapshot_id: str, session: Optional[Any] = None) -> Optional[Snapshot]:
        doc = await self.collection.find_one({"id": snapshot_id}, session=session)
        if not doc:
            return None
        return self._to_entity(doc)

    async def list_by_guild(self, guild_id: int, session: Optional[Any] = None) -> List[Snapshot]:
        cursor = self.collection.find({"guild_id": guild_id}, session=session)
        docs = await cursor.to_list(length=100)
        return [self._to_entity(doc) for doc in docs]
