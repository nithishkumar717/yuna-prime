from typing import Optional, List, Any
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository


class ThreatTrendPoint(BaseModel):
    """Data point representing a Sentinel threat trend spike/level at a given time."""
    guild_id: int
    timestamp: float
    threat_score: float


class AILatencyPoint(BaseModel):
    """Data point tracking AI operational latency over time."""
    guild_id: int
    timestamp: float
    latency_ms: float


class TrendRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's time-series trend history for threats and AI performance."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "threat_trends")
        self.latency_collection = db["ai_latency_history"]

    async def save_threat_trend(self, point: ThreatTrendPoint, session: Optional[Any] = None) -> None:
        doc = {
            "guild_id": point.guild_id,
            "timestamp": point.timestamp,
            "payload": point.model_dump()
        }
        await self.collection.insert_one(doc, session=session)

    async def list_threat_trends(self, guild_id: int, limit: int = 100, session: Optional[Any] = None) -> List[ThreatTrendPoint]:
        cursor = self.collection.find({"guild_id": guild_id}, session=session).sort("timestamp", -1)
        docs = await cursor.to_list(length=limit)
        return [ThreatTrendPoint(**doc["payload"]) for doc in docs]

    async def save_ai_latency(self, point: AILatencyPoint, session: Optional[Any] = None) -> None:
        doc = {
            "guild_id": point.guild_id,
            "timestamp": point.timestamp,
            "payload": point.model_dump()
        }
        await self.latency_collection.insert_one(doc, session=session)

    async def list_ai_latency(self, guild_id: int, limit: int = 100, session: Optional[Any] = None) -> List[AILatencyPoint]:
        cursor = self.latency_collection.find({"guild_id": guild_id}, session=session).sort("timestamp", -1)
        docs = await cursor.to_list(length=limit)
        return [AILatencyPoint(**doc["payload"]) for doc in docs]
