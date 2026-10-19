from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from moderation.appeals.models import ModerationAppeal


class AppealRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's moderation appeal workflow requests."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "moderation_appeals")

    async def get_by_id(
        self, appeal_id: str, session: Optional[Any] = None
    ) -> Optional[ModerationAppeal]:
        doc = await self.collection.find_one({"id": appeal_id}, session=session)
        if not doc:
            return None
        payload = doc["payload"]
        # Map status string back to Enum if needed
        return ModerationAppeal(**payload)

    async def get_by_case(
        self, guild_id: int, case_number: int, session: Optional[Any] = None
    ) -> Optional[ModerationAppeal]:
        doc = await self.collection.find_one(
            {"guild_id": guild_id, "case_number": case_number}, session=session
        )
        if not doc:
            return None
        return ModerationAppeal(**doc["payload"])

    async def list_pending(
        self, guild_id: int, session: Optional[Any] = None
    ) -> List[ModerationAppeal]:
        cursor = self.collection.find(
            {"guild_id": guild_id, "status": "PENDING"}, session=session
        )
        docs = await cursor.to_list(length=100)
        return [ModerationAppeal(**doc["payload"]) for doc in docs]

    async def save_appeal(
        self, appeal: ModerationAppeal, session: Optional[Any] = None
    ) -> None:
        # Map enum status to string for DB serialization
        payload = appeal.model_dump()
        payload["status"] = appeal.status.value
        doc = {
            "id": appeal.appeal_id,
            "guild_id": appeal.guild_id,
            "case_number": appeal.case_number,
            "status": appeal.status.value,
            "payload": payload,
        }
        await self.collection.replace_one(
            {"id": appeal.appeal_id}, doc, upsert=True, session=session
        )
