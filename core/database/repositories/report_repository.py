from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from moderation.reports.models import ModerationReport


class ReportRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's proactive User/AutoMod complaint reports."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "moderation_reports")

    async def get_by_id(
        self, report_id: str, session: Optional[Any] = None
    ) -> Optional[ModerationReport]:
        doc = await self.collection.find_one({"id": report_id}, session=session)
        if not doc:
            return None
        return ModerationReport(**doc["payload"])

    async def list_open_reports(
        self, guild_id: int, session: Optional[Any] = None
    ) -> List[ModerationReport]:
        cursor = self.collection.find(
            {"guild_id": guild_id, "status": {"$in": ["OPEN", "ASSIGNED"]}},
            session=session,
        )
        docs = await cursor.to_list(length=100)
        return [ModerationReport(**doc["payload"]) for doc in docs]

    async def save_report(
        self, report: ModerationReport, session: Optional[Any] = None
    ) -> None:
        payload = report.model_dump()
        payload["status"] = report.status.value
        payload["priority"] = report.priority.value
        doc = {
            "id": report.report_id,
            "guild_id": report.guild_id,
            "status": report.status.value,
            "payload": payload,
        }
        await self.collection.replace_one(
            {"id": report.report_id}, doc, upsert=True, session=session
        )
