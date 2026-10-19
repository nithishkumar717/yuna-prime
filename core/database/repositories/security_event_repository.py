from datetime import datetime
from typing import Optional, List, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from security.sentinel.models import SecurityEvent, ThreatLevel, SecurityAction


class SecurityEventRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's immutable security event logs with retention controls."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "security_events")

    def _to_document(self, event: SecurityEvent) -> Dict[str, Any]:
        payload = event.model_dump()
        payload["threat_level"] = event.threat_level.name
        payload["action_taken"] = event.action_taken.value
        # MongoDB handles datetime object natively
        return {
            "id": event.id,
            "target_id": event.target_id,
            "threat_level": event.threat_level.name,
            "timestamp": event.timestamp,
            "payload": payload
        }

    def _to_entity(self, doc: Dict[str, Any]) -> SecurityEvent:
        payload = doc["payload"]
        payload["threat_level"] = ThreatLevel[payload["threat_level"]]
        payload["action_taken"] = SecurityAction(payload["action_taken"])
        # If timestamp is stored as a datetime, parse or pass directly
        if isinstance(payload.get("timestamp"), str):
            payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])
        return SecurityEvent(**payload)

    async def save_event(self, event: SecurityEvent, session: Optional[Any] = None) -> None:
        doc = self._to_document(event)
        await self.collection.replace_one({"id": event.id}, doc, upsert=True, session=session)

    async def get_by_id(self, event_id: str, session: Optional[Any] = None) -> Optional[SecurityEvent]:
        doc = await self.collection.find_one({"id": event_id}, session=session)
        if not doc:
            return None
        return self._to_entity(doc)

    async def list_by_target(self, target_id: int, session: Optional[Any] = None) -> List[SecurityEvent]:
        cursor = self.collection.find({"target_id": target_id}, session=session)
        docs = await cursor.to_list(length=100)
        return [self._to_entity(doc) for doc in docs]

    async def list_by_threat_level(self, threat_level: ThreatLevel, session: Optional[Any] = None) -> List[SecurityEvent]:
        cursor = self.collection.find({"threat_level": threat_level.name}, session=session)
        docs = await cursor.to_list(length=100)
        return [self._to_entity(doc) for doc in docs]

    async def purge_older_than(self, dt: datetime, session: Optional[Any] = None) -> None:
        await self.collection.delete_many({"timestamp": {"$lt": dt}}, session=session)
