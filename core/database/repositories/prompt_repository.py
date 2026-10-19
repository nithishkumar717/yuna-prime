from typing import Optional, Any, Dict
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository


class PromptVersionRecord(BaseModel):
    """Represents a versioned system prompt and JSON validation schema configuration."""
    prompt_id: str  # e.g., "moderation", "investigation", "security", "ocr", "translation", "ticket"
    version: int
    system_prompt: str
    json_schema: Dict[str, Any]
    timestamp: float


class PromptRepository(MongoRepository):
    """Asynchronous Repository managing versioned AI prompt configurations and schemas."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "ai_prompts")

    async def save_prompt_version(self, record: PromptVersionRecord, session: Optional[Any] = None) -> None:
        doc_id = f"{record.prompt_id}:{record.version}"
        doc = {
            "id": doc_id,
            "prompt_id": record.prompt_id,
            "version": record.version,
            "payload": record.model_dump()
        }
        await self.collection.replace_one({"id": doc_id}, doc, upsert=True, session=session)

    async def get_active_prompt(self, prompt_id: str, session: Optional[Any] = None) -> Optional[PromptVersionRecord]:
        cursor = self.collection.find({"prompt_id": prompt_id}, session=session).sort("version", -1)
        docs = await cursor.to_list(length=1)
        if not docs:
            return None
        return PromptVersionRecord(**docs[0]["payload"])

    async def get_prompt_version(self, prompt_id: str, version: int, session: Optional[Any] = None) -> Optional[PromptVersionRecord]:
        doc_id = f"{prompt_id}:{version}"
        doc = await self.collection.find_one({"id": doc_id}, session=session)
        if not doc:
            return None
        return PromptVersionRecord(**doc["payload"])
