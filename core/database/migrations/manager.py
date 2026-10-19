from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from .history_repository import MigrationHistoryRepository, MigrationRecord
from .registry import MigrationRegistry
from .runner import MigrationRunner, LockAcquisitionError


class MigrationManager:
    """High-level service coordinating database migration checks, execution, rollbacks, and status."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.history_repo = MigrationHistoryRepository(db)
        self.runner = MigrationRunner(db, self.history_repo)

    async def get_status(self) -> Dict[str, Any]:
        applied_records = await self.history_repo.get_applied_migrations()
        applied_versions = {r.version: r for r in applied_records}
        all_migrations = MigrationRegistry.get_all_migrations()

        pending = [m.version for m in all_migrations if m.version not in applied_versions]
        latest_applied = await self.history_repo.get_latest_version()

        return {
            "current_version": latest_applied or "v0_uninitialized",
            "applied_count": len(applied_records),
            "applied_versions": list(applied_versions.keys()),
            "pending_count": len(pending),
            "pending_versions": pending,
            "total_registered": len(all_migrations)
        }

    async def migrate_to_latest(self, dry_run: bool = False) -> List[MigrationRecord]:
        locked = await self.runner.acquire_lock()
        if not locked:
            raise LockAcquisitionError("Could not acquire migration lock; another process may be migrating.")

        executed_records: List[MigrationRecord] = []
        try:
            applied_records = await self.history_repo.get_applied_migrations()
            applied_versions = {r.version for r in applied_records}
            all_migrations = MigrationRegistry.get_all_migrations()

            for migration in all_migrations:
                if migration.version not in applied_versions:
                    record = await self.runner.run_upgrade(migration, dry_run=dry_run)
                    executed_records.append(record)
        finally:
            await self.runner.release_lock()

        return executed_records

    async def rollback_last(self, dry_run: bool = False) -> Optional[str]:
        locked = await self.runner.acquire_lock()
        if not locked:
            raise LockAcquisitionError("Could not acquire migration lock; another process may be migrating.")

        try:
            latest_version = await self.history_repo.get_latest_version()
            if not latest_version:
                return None

            migration = MigrationRegistry.get_migration(latest_version)
            if not migration:
                raise ValueError(f"Registered migration script for version {latest_version} not found.")

            await self.runner.run_downgrade(migration, dry_run=dry_run)
            return latest_version
        finally:
            await self.runner.release_lock()
