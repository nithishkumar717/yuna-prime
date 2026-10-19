import time
from motor.motor_asyncio import AsyncIOMotorDatabase
from .base import BaseMigration
from .history_repository import MigrationHistoryRepository, MigrationRecord


class LockAcquisitionError(Exception):
    """Raised when a concurrent migration lock cannot be acquired."""
    pass


class MigrationRunner:
    """Executes database upgrades/downgrades with distributed locking and dry-run protection."""

    def __init__(self, db: AsyncIOMotorDatabase, history_repo: MigrationHistoryRepository) -> None:
        self.db = db
        self.history_repo = history_repo
        self.lock_collection = db["schema_migration_locks"]

    async def acquire_lock(self, lock_name: str = "global_migration_lock", timeout_seconds: float = 60.0) -> bool:
        now = time.time()
        # Clean expired lock or insert new lock
        result = await self.lock_collection.update_one(
            {
                "lock_name": lock_name,
                "$or": [
                    {"locked": False},
                    {"expires_at": {"$lt": now}}
                ]
            },
            {
                "$set": {
                    "lock_name": lock_name,
                    "locked": True,
                    "acquired_at": now,
                    "expires_at": now + timeout_seconds
                }
            },
            upsert=True
        )
        # Check if matched or upserted
        return result.modified_count > 0 or result.upserted_id is not None

    async def release_lock(self, lock_name: str = "global_migration_lock") -> None:
        await self.lock_collection.update_one(
            {"lock_name": lock_name},
            {"$set": {"locked": False, "expires_at": 0.0}}
        )

    async def run_upgrade(self, migration: BaseMigration, dry_run: bool = False) -> MigrationRecord:
        start_time = time.time()
        if not dry_run:
            await migration.upgrade(self.db)

        execution_time_ms = (time.time() - start_time) * 1000.0
        record = MigrationRecord(
            version=migration.version,
            description=migration.description,
            applied_at=start_time,
            execution_time_ms=execution_time_ms
        )

        if not dry_run:
            await self.history_repo.record_migration(record)

        return record

    async def run_downgrade(self, migration: BaseMigration, dry_run: bool = False) -> None:
        if not dry_run:
            await migration.downgrade(self.db)
            await self.history_repo.remove_migration(migration.version)
