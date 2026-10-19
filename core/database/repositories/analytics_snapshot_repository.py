from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from moderation.analytics.models import AnalyticsSnapshot


class AnalyticsSnapshotRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's compiled master analytics snapshots."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "analytics_snapshots")

    async def save_snapshot(self, snapshot: AnalyticsSnapshot, session: Optional[Any] = None) -> None:
        doc_id = f"{snapshot.guild_id}:{snapshot.timestamp}"
        doc = {
            "id": doc_id,
            "guild_id": snapshot.guild_id,
            "timestamp": snapshot.timestamp,
            "payload": snapshot.model_dump()
        }
        await self.collection.replace_one({"id": doc_id}, doc, upsert=True, session=session)

    async def get_by_guild_id_and_timestamp(self, guild_id: int, timestamp: float, session: Optional[Any] = None) -> Optional[AnalyticsSnapshot]:
        doc_id = f"{guild_id}:{timestamp}"
        doc = await self.collection.find_one({"id": doc_id}, session=session)
        if not doc:
            return None
        payload = doc["payload"]
        
        # Ensure dict keys in human_kpis are converted back to int
        if "human_kpis" in payload:
            payload["human_kpis"] = {int(k): v for k, v in payload["human_kpis"].items()}
            
        return AnalyticsSnapshot(**payload)

    async def list_by_guild(self, guild_id: int, session: Optional[Any] = None) -> List[AnalyticsSnapshot]:
        cursor = self.collection.find({"guild_id": guild_id}, session=session).sort("timestamp", -1)
        docs = await cursor.to_list(length=100)
        snapshots = []
        for doc in docs:
            payload = doc["payload"]
            if "human_kpis" in payload:
                payload["human_kpis"] = {int(k): v for k, v in payload["human_kpis"].items()}
            snapshots.append(AnalyticsSnapshot(**payload))
        return snapshots
