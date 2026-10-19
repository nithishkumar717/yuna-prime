import pytest
from unittest.mock import AsyncMock, MagicMock
from core.database.migrations import (
    BaseMigration,
    MigrationRegistry,
    MigrationHistoryRepository,
    MigrationRunner,
    LockAcquisitionError,
    MigrationManager
)


class DummyMigration1(BaseMigration):
    version = "v01_test"
    description = "Test migration 1"

    async def upgrade(self, db) -> None:
        pass

    async def downgrade(self, db) -> None:
        pass


class DummyMigration2(BaseMigration):
    version = "v02_test"
    description = "Test migration 2"

    async def upgrade(self, db) -> None:
        pass

    async def downgrade(self, db) -> None:
        pass


@pytest.fixture(autouse=True)
def setup_test_registry():
    MigrationRegistry.clear()
    MigrationRegistry.register(DummyMigration1)
    MigrationRegistry.register(DummyMigration2)
    yield
    MigrationRegistry.clear()


@pytest.mark.asyncio
async def test_migration_registry():
    migrations = MigrationRegistry.get_all_migrations()
    assert len(migrations) == 2
    assert migrations[0].version == "v01_test"
    assert migrations[1].version == "v02_test"

    m1 = MigrationRegistry.get_migration("v01_test")
    assert m1 is not None
    assert m1.description == "Test migration 1"


@pytest.mark.asyncio
async def test_migration_history_repository():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    history_repo = MigrationHistoryRepository(db_mock)

    # Test record_migration
    record_mock = MagicMock()
    record_mock.version = "v01_test"
    record_mock.description = "Test migration 1"
    record_mock.applied_at = 100.0
    record_mock.execution_time_ms = 10.0
    record_mock.model_dump.return_value = {
        "version": "v01_test",
        "description": "Test migration 1",
        "applied_at": 100.0,
        "execution_time_ms": 10.0
    }

    await history_repo.record_migration(record_mock)
    collection_mock.replace_one.assert_called_once()

    # Test get_applied_migrations
    cursor_mock = AsyncMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.to_list.return_value = [{
        "version": "v01_test",
        "payload": {
            "version": "v01_test",
            "description": "Test migration 1",
            "applied_at": 100.0,
            "execution_time_ms": 10.0
        }
    }]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    applied = await history_repo.get_applied_migrations()
    assert len(applied) == 1
    assert applied[0].version == "v01_test"

    # Test remove_migration
    await history_repo.remove_migration("v01_test")
    collection_mock.delete_one.assert_called_with({"version": "v01_test"}, session=None)


@pytest.mark.asyncio
async def test_migration_runner_lock():
    db_mock = MagicMock()
    history_repo = AsyncMock()
    lock_collection = AsyncMock()

    def get_coll(name):
        if name == "schema_migration_locks":
            return lock_collection
        return AsyncMock()

    db_mock.__getitem__.side_effect = get_coll

    runner = MigrationRunner(db_mock, history_repo)

    # Lock success case
    result_mock = MagicMock()
    result_mock.modified_count = 1
    result_mock.upserted_id = None
    lock_collection.update_one.return_value = result_mock

    acquired = await runner.acquire_lock()
    assert acquired is True

    # Release lock
    await runner.release_lock()
    lock_collection.update_one.assert_called()


@pytest.mark.asyncio
async def test_migration_manager_migrate_and_status():
    db_mock = MagicMock()
    history_coll = AsyncMock()
    lock_coll = AsyncMock()

    def get_coll(name):
        if name == "schema_migrations":
            return history_coll
        elif name == "schema_migration_locks":
            return lock_coll
        return AsyncMock()

    db_mock.__getitem__.side_effect = get_coll

    # Setup lock acquisition success
    lock_result = MagicMock()
    lock_result.modified_count = 1
    lock_coll.update_one.return_value = lock_result

    # Initially no applied migrations
    cursor_empty = AsyncMock()
    cursor_empty.sort = MagicMock(return_value=cursor_empty)
    cursor_empty.to_list.return_value = []
    history_coll.find = MagicMock(return_value=cursor_empty)

    manager = MigrationManager(db_mock)

    # Status check
    status = await manager.get_status()
    assert status["current_version"] == "v0_uninitialized"
    assert status["pending_count"] == 2

    # Execute migrations
    records = await manager.migrate_to_latest()
    assert len(records) == 2
    assert records[0].version == "v01_test"
    assert records[1].version == "v02_test"


@pytest.mark.asyncio
async def test_migration_manager_rollback():
    db_mock = MagicMock()
    history_coll = AsyncMock()
    lock_coll = AsyncMock()

    def get_coll(name):
        if name == "schema_migrations":
            return history_coll
        elif name == "schema_migration_locks":
            return lock_coll
        return AsyncMock()

    db_mock.__getitem__.side_effect = get_coll

    # Setup lock acquisition success
    lock_result = MagicMock()
    lock_result.modified_count = 1
    lock_coll.update_one.return_value = lock_result

    # Mock latest version returning v02_test
    cursor_latest = AsyncMock()
    cursor_latest.sort = MagicMock(return_value=cursor_latest)
    cursor_latest.to_list.return_value = [{"version": "v02_test"}]
    history_coll.find = MagicMock(return_value=cursor_latest)

    manager = MigrationManager(db_mock)
    rolled_back = await manager.rollback_last()
    assert rolled_back == "v02_test"


@pytest.mark.asyncio
async def test_migration_dry_run():
    db_mock = MagicMock()
    history_coll = AsyncMock()
    lock_coll = AsyncMock()

    def get_coll(name):
        if name == "schema_migrations":
            return history_coll
        elif name == "schema_migration_locks":
            return lock_coll
        return AsyncMock()

    db_mock.__getitem__.side_effect = get_coll

    # Lock success
    lock_result = MagicMock()
    lock_result.modified_count = 1
    lock_coll.update_one.return_value = lock_result

    cursor_empty = AsyncMock()
    cursor_empty.sort = MagicMock(return_value=cursor_empty)
    cursor_empty.to_list.return_value = []
    history_coll.find = MagicMock(return_value=cursor_empty)

    manager = MigrationManager(db_mock)
    records = await manager.migrate_to_latest(dry_run=True)
    assert len(records) == 2
    # Ensure no database insert happened on history_coll in dry_run
    history_coll.replace_one.assert_not_called()


@pytest.mark.asyncio
async def test_migration_lock_failure():
    db_mock = MagicMock()
    lock_coll = AsyncMock()
    db_mock.__getitem__.return_value = lock_coll

    # Lock failure case
    lock_result = MagicMock()
    lock_result.modified_count = 0
    lock_result.upserted_id = None
    lock_coll.update_one.return_value = lock_result

    manager = MigrationManager(db_mock)
    with pytest.raises(LockAcquisitionError):
        await manager.migrate_to_latest()
