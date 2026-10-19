import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import json

from core.database.repositories.incident_repository import IncidentRepository
from core.database.repositories.security_event_repository import SecurityEventRepository
from core.database.repositories.recovery_repository import RecoveryRepository
from core.database.repositories.snapshot_repository import SnapshotRepository
from core.database.repositories.sentinel_repository import SentinelRepository

from security.incident_center.models import IncidentCase, IncidentStatus, ForensicEvidence
from security.sentinel.models import SecurityEvent, ThreatLevel, SecurityAction
from security.recovery.models import RollbackPlan, RollbackTask, RollbackAction, Snapshot


@pytest.mark.asyncio
async def test_incident_repository_caching_and_crud():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    # Mock Redis client
    redis_client_mock = MagicMock()
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None  # Ensure it returns None by default
    redis_client_mock.client = redis_mock

    evidence = ForensicEvidence(
        timestamp=1620000000.0,
        source="ThreatPipeline",
        payload={"threat": "HIGH"},
        hash_signature="hash123"
    )
    case = IncidentCase(
        incident_id="incident-uuid-1",
        actor_id=9876,
        start_time=1620000000.0,
        status=IncidentStatus.OPEN,
        evidence_timeline=[evidence]
    )

    repo = IncidentRepository(db_mock, redis_client=redis_client_mock)
    
    # 1. Test Save (OPEN case should cache in local & redis)
    await repo.save_case(case)
    collection_mock.replace_one.assert_called_once()
    redis_mock.set.assert_called_once()

    # Reset mocks
    collection_mock.replace_one.reset_mock()
    redis_mock.set.reset_mock()

    # 2. Test get_open_case_for_actor hits local cache directly (no DB, no Redis calls)
    collection_mock.find_one.return_value = None
    cached_case = await repo.get_open_case_for_actor(9876)
    assert cached_case is not None
    assert cached_case.incident_id == "incident-uuid-1"
    collection_mock.find_one.assert_not_called()
    redis_mock.get.assert_not_called()

    # 3. Test get_open_case_for_actor hits Redis cache
    repo._local_cache.clear()
    redis_mock.get.return_value = json.dumps(repo._to_document(case))
    
    redis_cached_case = await repo.get_open_case_for_actor(9876)
    assert redis_cached_case is not None
    assert redis_cached_case.incident_id == "incident-uuid-1"
    redis_mock.get.assert_called_once()
    collection_mock.find_one.assert_not_called()

    # Reset mock
    redis_mock.get.reset_mock()
    repo._local_cache.clear()

    # 4. Test DB fallback
    redis_mock.get.return_value = None
    db_doc = repo._to_document(case)
    collection_mock.find_one.return_value = db_doc

    db_case = await repo.get_open_case_for_actor(9876)
    assert db_case is not None
    assert db_case.incident_id == "incident-uuid-1"
    collection_mock.find_one.assert_called_once_with({"actor_id": 9876, "status": "OPEN"}, session=None)

    # 5. Invalidation when Status resolved/archived
    case.status = IncidentStatus.RESOLVED
    await repo.save_case(case)
    assert 9876 not in repo._local_cache
    redis_mock.delete.assert_called_once()


@pytest.mark.asyncio
async def test_security_event_repository_queries_and_purges():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    event = SecurityEvent(
        event_source="AuditLogWatcher",
        target_id=8888,
        threat_level=ThreatLevel.HIGH,
        action_taken=SecurityAction.QUARANTINE,
        reason="Rapid channel deletion"
    )

    repo = SecurityEventRepository(db_mock)

    # Test Save
    await repo.save_event(event)
    collection_mock.replace_one.assert_called_once()

    # Test list_by_target
    cursor_mock = AsyncMock()
    cursor_mock.to_list.return_value = [repo._to_document(event)]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    events = await repo.list_by_target(8888)
    assert len(events) == 1
    assert events[0].reason == "Rapid channel deletion"
    assert events[0].threat_level == ThreatLevel.HIGH
    collection_mock.find.assert_called_with({"target_id": 8888}, session=None)

    # Test list_by_threat_level
    cursor_mock.to_list.return_value = [repo._to_document(event)]
    collection_mock.find = MagicMock(return_value=cursor_mock)
    
    events_lvl = await repo.list_by_threat_level(ThreatLevel.HIGH)
    assert len(events_lvl) == 1
    assert events_lvl[0].threat_level == ThreatLevel.HIGH
    collection_mock.find.assert_called_with({"threat_level": "HIGH"}, session=None)

    # Test purge_older_than
    cutoff = datetime.now(timezone.utc)
    await repo.purge_older_than(cutoff)
    collection_mock.delete_many.assert_called_once_with({"timestamp": {"$lt": cutoff}}, session=None)


@pytest.mark.asyncio
async def test_recovery_repository_crud():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    task = RollbackTask(
        action=RollbackAction.CREATE,
        resource_type="role",
        resource_id="role-123",
        data={"name": "Moderator", "permissions": 8}
    )
    plan = RollbackPlan(
        target_snapshot_id="snapshot-uuid-456",
        tasks=[task]
    )

    repo = RecoveryRepository(db_mock)

    # Test save
    await repo.save_plan(plan)
    collection_mock.replace_one.assert_called_once()

    # Test retrieve
    collection_mock.find_one.return_value = repo._to_document(plan)
    retrieved = await repo.get_by_target_snapshot_id("snapshot-uuid-456")
    assert retrieved is not None
    assert retrieved.target_snapshot_id == "snapshot-uuid-456"
    assert len(retrieved.tasks) == 1
    assert retrieved.tasks[0].action == RollbackAction.CREATE

    # Test delete
    await repo.delete_plan("snapshot-uuid-456")
    collection_mock.delete_one.assert_called_once_with({"id": "snapshot-uuid-456"}, session=None)


@pytest.mark.asyncio
async def test_snapshot_repository_crud():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    snapshot = Snapshot(
        snapshot_id="snap-123",
        guild_id=1122,
        timestamp=1620000000.0,
        payload={"roles": [], "channels": []},
        hash_signature="signature-abc"
    )

    repo = SnapshotRepository(db_mock)

    # Test Save
    await repo.save_snapshot(snapshot)
    collection_mock.replace_one.assert_called_once()

    # Test Get by ID
    collection_mock.find_one.return_value = repo._to_document(snapshot)
    retrieved = await repo.get_by_id("snap-123")
    assert retrieved is not None
    assert retrieved.snapshot_id == "snap-123"
    assert retrieved.guild_id == 1122

    # Test List by Guild
    cursor_mock = AsyncMock()
    cursor_mock.to_list.return_value = [repo._to_document(snapshot)]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    snapshots = await repo.list_by_guild(1122)
    assert len(snapshots) == 1
    assert snapshots[0].hash_signature == "signature-abc"
    collection_mock.find.assert_called_with({"guild_id": 1122}, session=None)


@pytest.mark.asyncio
async def test_sentinel_repository_aggregate():
    db_mock = MagicMock()
    repo = SentinelRepository(db_mock)
    
    assert repo.incidents is not None
    assert repo.events is not None
    assert repo.recovery is not None
    assert repo.snapshots is not None
