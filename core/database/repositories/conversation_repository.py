from typing import Optional, List, Any
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository


class ConversationRecord(BaseModel):
    """Represents a ticket conversation log history with pre-computed summaries."""
    conversation_id: str
    guild_id: int
    user_id: int
    messages: List[str]
    summary: str
    timestamp: float


class ConversationRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's persistent AI Ticket assistant conversations."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "ai_conversations")

    async def save_conversation(self, record: ConversationRecord, session: Optional[Any] = None) -> None:
        doc = {
            "id": record.conversation_id,
            "guild_id": record.guild_id,
            "user_id": record.user_id,
            "timestamp": record.timestamp,
            "payload": record.model_dump()
        }
        await self.collection.replace_one({"id": record.conversation_id}, doc, upsert=True, session=session)

    async def get_conversation(self, conversation_id: str, session: Optional[Any] = None) -> Optional[ConversationRecord]:
        doc = await self.collection.find_one({"id": conversation_id}, session=session)
        if not doc:
            return None
        return ConversationRecord(**doc["payload"])

    async def list_user_conversations(self, guild_id: int, user_id: int, session: Optional[Any] = None) -> List[ConversationRecord]:
        cursor = self.collection.find({"guild_id": guild_id, "user_id": user_id}, session=session).sort("timestamp", -1)
        docs = await cursor.to_list(length=100)
        return [ConversationRecord(**doc["payload"]) for doc in docs]
