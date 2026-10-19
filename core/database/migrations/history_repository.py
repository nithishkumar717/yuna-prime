from typing import Optional, List, Any
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository


class MigrationRecord(BaseModel):
    """Represents a persisted execution log record of an applied database migration."""
    version: str
    description: str
    applied_at: float
    execution_time_ms: float


class MigrationHistoryRepository(MongoRepository):
    """Asynchronous Repository tracking executed database migration versions and timestamps."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "schema_migrations")

    async def record_migration(self, record: MigrationRecord, session: Optional[Any] = None) -> None:
        doc = {
            "version": record.version,
            "description": record.description,
            "applied_at": record.applied_at,
            "execution_time_ms": record.execution_time_ms,
            "payload": record.model_dump()
        }
        await self.collection.replace_one({"version": record.version}, doc, upsert=True, session=session)

    async def remove_migration(self, version: str, session: Optional[Any] = None) -> None:
        await self.collection.delete_one({"version": version}, session=session)

    async def get_applied_migrations(self, session: Optional[Any] = None) -> List[MigrationRecord]:
        cursor = self.collection.find({}, session=session).sort("version", 1)
        docs = await cursor.to_list(length=1000)
        return [MigrationRecord(**doc["payload"]) for doc in docs]

    async def get_latest_version(self, session: Optional[Any] = None) -> Optional[str]:
        cursor = self.collection.find({}, session=session).sort("version", -1)
        docs = await cursor.to_list(length=1)
        if not docs:
            return None
        return str(docs[0]["version"])
