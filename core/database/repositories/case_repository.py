from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from moderation.cases.models import ModerationCase


class CaseRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's persistent administrative moderation cases."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "moderation_cases")

    async def get_by_uuid(
        self, case_uuid: str, session: Optional[Any] = None
    ) -> Optional[ModerationCase]:
        doc = await self.collection.find_one({"id": case_uuid}, session=session)
        if not doc:
            return None
        return ModerationCase(**doc["payload"])

    async def get_by_number(
        self, guild_id: int, case_number: int, session: Optional[Any] = None
    ) -> Optional[ModerationCase]:
        doc = await self.collection.find_one(
            {"guild_id": guild_id, "case_number": case_number}, session=session
        )
        if not doc:
            return None
        return ModerationCase(**doc["payload"])

    async def list_by_target(
        self, guild_id: int, target_id: int, session: Optional[Any] = None
    ) -> List[ModerationCase]:
        cursor = self.collection.find(
            {"guild_id": guild_id, "target_id": target_id}, session=session
        )
        docs = await cursor.to_list(length=100)
        return [ModerationCase(**doc["payload"]) for doc in docs]

    async def save_case(
        self, case: ModerationCase, session: Optional[Any] = None
    ) -> None:
        doc = {
            "id": case.case_uuid,
            "guild_id": case.guild_id,
            "case_number": case.case_number,
            "target_id": case.target_id,
            "payload": case.model_dump(),
        }
        await self.collection.replace_one(
            {"id": case.case_uuid}, doc, upsert=True, session=session
        )
