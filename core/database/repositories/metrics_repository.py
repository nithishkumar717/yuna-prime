from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from moderation.analytics.models import ModeratorKPI, AutoModMetrics


class MetricsRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's human moderator KPIs and AutoMod effectiveness statistics."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "moderator_kpis")
        self.automod_collection = db["automod_metrics"]

    async def save_moderator_kpi(self, kpi: ModeratorKPI, guild_id: int, session: Optional[Any] = None) -> None:
        doc_id = f"{guild_id}:{kpi.moderator_id}"
        doc = {
            "id": doc_id,
            "guild_id": guild_id,
            "moderator_id": kpi.moderator_id,
            "payload": kpi.model_dump()
        }
        await self.collection.replace_one({"id": doc_id}, doc, upsert=True, session=session)

    async def get_moderator_kpi(self, moderator_id: int, guild_id: int, session: Optional[Any] = None) -> Optional[ModeratorKPI]:
        doc_id = f"{guild_id}:{moderator_id}"
        doc = await self.collection.find_one({"id": doc_id}, session=session)
        if not doc:
            return None
        return ModeratorKPI(**doc["payload"])

    async def list_moderator_kpis(self, guild_id: int, session: Optional[Any] = None) -> List[ModeratorKPI]:
        cursor = self.collection.find({"guild_id": guild_id}, session=session)
        docs = await cursor.to_list(length=100)
        return [ModeratorKPI(**doc["payload"]) for doc in docs]

    async def save_automod_metrics(self, metrics: AutoModMetrics, guild_id: int, session: Optional[Any] = None) -> None:
        doc_id = str(guild_id)
        doc = {
            "id": doc_id,
            "guild_id": guild_id,
            "payload": metrics.model_dump()
        }
        await self.automod_collection.replace_one({"id": doc_id}, doc, upsert=True, session=session)

    async def get_automod_metrics(self, guild_id: int, session: Optional[Any] = None) -> Optional[AutoModMetrics]:
        doc_id = str(guild_id)
        doc = await self.automod_collection.find_one({"id": doc_id}, session=session)
        if not doc:
            return None
        return AutoModMetrics(**doc["payload"])
