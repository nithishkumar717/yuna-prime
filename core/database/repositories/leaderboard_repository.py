from typing import Optional, List, Any
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository


class LeaderboardEntry(BaseModel):
    """Represents a human moderator or automated system action count for leaderboard rankings."""
    guild_id: int
    name: str
    actions: int
    type: str  # "Manual" or "Automated"


class LeaderboardRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's guild activity leaderboards for moderators and automated filters."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "analytics_leaderboards")

    async def save_leaderboard_entry(self, entry: LeaderboardEntry, session: Optional[Any] = None) -> None:
        doc_id = f"{entry.guild_id}:{entry.name}"
        doc = {
            "id": doc_id,
            "guild_id": entry.guild_id,
            "name": entry.name,
            "actions": entry.actions,
            "payload": entry.model_dump()
        }
        await self.collection.replace_one({"id": doc_id}, doc, upsert=True, session=session)

    async def list_leaderboard(self, guild_id: int, limit: int = 10, session: Optional[Any] = None) -> List[LeaderboardEntry]:
        cursor = self.collection.find({"guild_id": guild_id}, session=session).sort("actions", -1)
        docs = await cursor.to_list(length=limit)
        return [LeaderboardEntry(**doc["payload"]) for doc in docs]
