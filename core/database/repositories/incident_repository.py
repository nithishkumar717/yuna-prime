import json
import logging
from dataclasses import asdict
from typing import Optional, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from security.incident_center.models import IncidentCase, IncidentStatus, ForensicEvidence


class IncidentRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's persistent security incident cases with local & Redis caching."""

    def __init__(self, db: AsyncIOMotorDatabase, redis_client: Optional[Any] = None) -> None:
        super().__init__(db, "security_incidents")
        self.redis_client = redis_client
        self._local_cache: Dict[int, IncidentCase] = {}

    def _get_cache_key(self, actor_id: int) -> str:
        return f"active_incident:{actor_id}"

    def _to_document(self, case: IncidentCase) -> Dict[str, Any]:
        data = asdict(case)
        data["status"] = case.status.value
        return {
            "id": case.incident_id,
            "actor_id": case.actor_id,
            "status": case.status.value,
            "payload": data
        }

    def _to_entity(self, doc: Dict[str, Any]) -> IncidentCase:
        payload = doc["payload"]
        timeline = [
            ForensicEvidence(
                timestamp=ev["timestamp"],
                source=ev["source"],
                payload=ev["payload"],
                hash_signature=ev["hash_signature"]
            )
            for ev in payload.get("evidence_timeline", [])
        ]
        return IncidentCase(
            incident_id=payload["incident_id"],
            actor_id=payload["actor_id"],
            start_time=payload["start_time"],
            status=IncidentStatus(payload["status"]),
            evidence_timeline=timeline
        )

    async def _write_to_redis(self, case: IncidentCase) -> None:
        if not self.redis_client:
            return
        try:
            client = getattr(self.redis_client, "client", self.redis_client)
            if client:
                cache_key = self._get_cache_key(case.actor_id)
                doc = self._to_document(case)
                await client.set(cache_key, json.dumps(doc), ex=3600)
        except Exception as e:
            logging.warning(f"Failed to write to Redis cache: {e}")

    async def _invalidate_redis(self, actor_id: int) -> None:
        if not self.redis_client:
            return
        try:
            client = getattr(self.redis_client, "client", self.redis_client)
            if client:
                cache_key = self._get_cache_key(actor_id)
                await client.delete(cache_key)
        except Exception as e:
            logging.warning(f"Failed to invalidate Redis cache: {e}")

    async def get_by_id(self, incident_id: str, session: Optional[Any] = None) -> Optional[IncidentCase]:
        doc = await self.collection.find_one({"id": incident_id}, session=session)
        if not doc:
            return None
        return self._to_entity(doc)

    async def get_open_case_for_actor(self, actor_id: int, session: Optional[Any] = None) -> Optional[IncidentCase]:
        # 1. Try Local Cache
        if actor_id in self._local_cache:
            case = self._local_cache[actor_id]
            if case.status == IncidentStatus.OPEN:
                return case

        # 2. Try Redis Cache
        if self.redis_client:
            try:
                client = getattr(self.redis_client, "client", self.redis_client)
                if client:
                    cache_key = self._get_cache_key(actor_id)
                    cached_data = await client.get(cache_key)
                    if cached_data:
                        doc = json.loads(cached_data)
                        case = self._to_entity(doc)
                        self._local_cache[actor_id] = case
                        return case
            except Exception as e:
                logging.warning(f"Failed to read from Redis cache: {e}")

        # 3. Query MongoDB
        doc = await self.collection.find_one({"actor_id": actor_id, "status": "OPEN"}, session=session)
        if not doc:
            return None

        case = self._to_entity(doc)
        self._local_cache[actor_id] = case
        await self._write_to_redis(case)
        return case


    async def save_case(self, case: IncidentCase, session: Optional[Any] = None) -> None:
        doc = self._to_document(case)
        await self.collection.replace_one({"id": case.incident_id}, doc, upsert=True, session=session)

        # Update cache layers
        if case.status == IncidentStatus.OPEN:
            self._local_cache[case.actor_id] = case
            await self._write_to_redis(case)
        else:
            if case.actor_id in self._local_cache:
                del self._local_cache[case.actor_id]
            await self._invalidate_redis(case.actor_id)
