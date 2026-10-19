from dataclasses import asdict
from typing import Optional, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from security.recovery.models import RollbackPlan, RollbackTask, RollbackAction


class RecoveryRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's system recovery plans (Rollback Plans)."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, "recovery_plans")

    def _to_document(self, plan: RollbackPlan) -> Dict[str, Any]:
        payload = asdict(plan)
        # Convert RollbackAction Enums to string values
        for t_dict, t_obj in zip(payload.get("tasks", []), plan.tasks):
            t_dict["action"] = t_obj.action.value
        return {
            "id": plan.target_snapshot_id,
            "payload": payload
        }

    def _to_entity(self, doc: Dict[str, Any]) -> RollbackPlan:
        payload = doc["payload"]
        tasks = [
            RollbackTask(
                action=RollbackAction(t["action"]),
                resource_type=t["resource_type"],
                resource_id=t["resource_id"],
                data=t["data"]
            )
            for t in payload.get("tasks", [])
        ]
        return RollbackPlan(
            target_snapshot_id=payload["target_snapshot_id"],
            tasks=tasks
        )

    async def save_plan(self, plan: RollbackPlan, session: Optional[Any] = None) -> None:
        doc = self._to_document(plan)
        await self.collection.replace_one({"id": plan.target_snapshot_id}, doc, upsert=True, session=session)

    async def get_by_target_snapshot_id(self, snapshot_id: str, session: Optional[Any] = None) -> Optional[RollbackPlan]:
        doc = await self.collection.find_one({"id": snapshot_id}, session=session)
        if not doc:
            return None
        return self._to_entity(doc)

    async def delete_plan(self, snapshot_id: str, session: Optional[Any] = None) -> None:
        await self.collection.delete_one({"id": snapshot_id}, session=session)
