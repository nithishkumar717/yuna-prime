from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository


class PunishmentRepository(MongoRepository):
    """Asynchronous Repository tracking active timed punishments (timeouts, tempbans, jails) for auto-expiration."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "active_punishments")

    async def get_active_punishment(
        self, guild_id: int, target_id: int, session: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one(
            {"guild_id": guild_id, "target_id": target_id, "active": True},
            session=session,
        )

    async def list_expired_punishments(
        self, session: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cursor = self.collection.find(
            {"active": True, "expires_at": {"$lt": now}}, session=session
        )
        return await cursor.to_list(length=1000)

    async def save_punishment(
        self, punishment: Dict[str, Any], session: Optional[Any] = None
    ) -> None:
        await self.collection.replace_one(
            {"id": punishment["id"]}, punishment, upsert=True, session=session
        )
