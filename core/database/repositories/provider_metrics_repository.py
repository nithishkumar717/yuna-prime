from typing import Optional, List, Any
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository


class ProviderMetricRecord(BaseModel):
    """Tracks token consumption rates and invocation performance speeds of AI vendors."""
    provider_name: str  # e.g., "openai", "google", "mock"
    latency_ms: float
    token_usage: int
    timestamp: float


class FailoverEventRecord(BaseModel):
    """Represents a service degradation fallback trigger log between provider endpoints."""
    failed_provider: str
    fallback_provider: str
    reason: str
    timestamp: float


class ProviderMetricsRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's operational AI provider execution latency logs and fallback events."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "ai_provider_metrics")
        self.failover_collection = db["ai_provider_failovers"]

    async def save_metric(self, record: ProviderMetricRecord, session: Optional[Any] = None) -> None:
        doc = {
            "provider_name": record.provider_name,
            "timestamp": record.timestamp,
            "payload": record.model_dump()
        }
        await self.collection.insert_one(doc, session=session)

    async def save_failover(self, record: FailoverEventRecord, session: Optional[Any] = None) -> None:
        doc = {
            "failed_provider": record.failed_provider,
            "timestamp": record.timestamp,
            "payload": record.model_dump()
        }
        await self.failover_collection.insert_one(doc, session=session)

    async def get_average_latency(self, provider_name: str, session: Optional[Any] = None) -> float:
        cursor = self.collection.find({"provider_name": provider_name}, session=session).sort("timestamp", -1)
        docs = await cursor.to_list(length=100)
        if not docs:
            return 0.0
        latencies = [doc["payload"]["latency_ms"] for doc in docs]
        return sum(latencies) / len(latencies)

    async def list_failovers(self, limit: int = 50, session: Optional[Any] = None) -> List[FailoverEventRecord]:
        cursor = self.failover_collection.find({}, session=session).sort("timestamp", -1)
        docs = await cursor.to_list(length=limit)
        return [FailoverEventRecord(**doc["payload"]) for doc in docs]
