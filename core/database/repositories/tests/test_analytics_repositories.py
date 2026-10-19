import pytest
from unittest.mock import AsyncMock, MagicMock

from core.database.repositories.metrics_repository import MetricsRepository
from core.database.repositories.trend_repository import TrendRepository, ThreatTrendPoint, AILatencyPoint
from core.database.repositories.leaderboard_repository import LeaderboardRepository, LeaderboardEntry
from core.database.repositories.analytics_snapshot_repository import AnalyticsSnapshotRepository
from core.database.repositories.analytics_repository import AnalyticsRepository

from moderation.analytics.models import ModeratorKPI, AutoModMetrics, AnalyticsSnapshot


@pytest.mark.asyncio
async def test_metrics_repository():
    db_mock = MagicMock()
    moderator_collection_mock = AsyncMock()
    automod_collection_mock = AsyncMock()
    
    # Mock __getitem__ to return correct collections
    def get_collection(name):
        if name == "moderator_kpis":
            return moderator_collection_mock
        elif name == "automod_metrics":
            return automod_collection_mock
        return AsyncMock()
        
    db_mock.__getitem__.side_effect = get_collection

    repo = MetricsRepository(db_mock)

    # Test Moderator KPI CRUD
    kpi = ModeratorKPI(moderator_id=1234, total_actions=5, appeals_granted=1, accuracy_score=0.8)
    await repo.save_moderator_kpi(kpi, guild_id=1122)
    moderator_collection_mock.replace_one.assert_called_once()
    
    moderator_collection_mock.find_one.return_value = {
        "id": "1122:1234",
        "guild_id": 1122,
        "payload": kpi.model_dump()
    }
    retrieved_kpi = await repo.get_moderator_kpi(moderator_id=1234, guild_id=1122)
    assert retrieved_kpi is not None
    assert retrieved_kpi.moderator_id == 1234
    assert retrieved_kpi.accuracy_score == 0.8

    # Test list_moderator_kpis
    cursor_mock = AsyncMock()
    cursor_mock.to_list.return_value = [{
        "id": "1122:1234",
        "guild_id": 1122,
        "payload": kpi.model_dump()
    }]
    moderator_collection_mock.find = MagicMock(return_value=cursor_mock)
    
    kpis = await repo.list_moderator_kpis(guild_id=1122)
    assert len(kpis) == 1
    assert kpis[0].moderator_id == 1234

    # Test AutoMod Metrics CRUD
    automod = AutoModMetrics(total_violations=10, appeals_granted=2, false_positive_rate=0.2)
    await repo.save_automod_metrics(automod, guild_id=1122)
    automod_collection_mock.replace_one.assert_called_once()

    automod_collection_mock.find_one.return_value = {
        "id": "1122",
        "guild_id": 1122,
        "payload": automod.model_dump()
    }
    retrieved_automod = await repo.get_automod_metrics(guild_id=1122)
    assert retrieved_automod is not None
    assert retrieved_automod.total_violations == 10
    assert retrieved_automod.false_positive_rate == 0.2


@pytest.mark.asyncio
async def test_trend_repository():
    db_mock = MagicMock()
    threat_collection_mock = AsyncMock()
    latency_collection_mock = AsyncMock()
    
    def get_collection(name):
        if name == "threat_trends":
            return threat_collection_mock
        elif name == "ai_latency_history":
            return latency_collection_mock
        return AsyncMock()
        
    db_mock.__getitem__.side_effect = get_collection

    repo = TrendRepository(db_mock)

    # Test Threat Trends
    t_point = ThreatTrendPoint(guild_id=1122, timestamp=1620000000.0, threat_score=0.85)
    await repo.save_threat_trend(t_point)
    threat_collection_mock.insert_one.assert_called_once()

    cursor_mock = AsyncMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.to_list.return_value = [{
        "guild_id": 1122,
        "timestamp": 1620000000.0,
        "payload": t_point.model_dump()
    }]
    threat_collection_mock.find = MagicMock(return_value=cursor_mock)

    trends = await repo.list_threat_trends(guild_id=1122)
    assert len(trends) == 1
    assert trends[0].threat_score == 0.85
    cursor_mock.sort.assert_called_with("timestamp", -1)

    # Test AI Latency
    l_point = AILatencyPoint(guild_id=1122, timestamp=1620000000.0, latency_ms=120.5)
    await repo.save_ai_latency(l_point)
    latency_collection_mock.insert_one.assert_called_once()

    cursor_mock_latency = AsyncMock()
    cursor_mock_latency.sort = MagicMock(return_value=cursor_mock_latency)
    cursor_mock_latency.to_list.return_value = [{
        "guild_id": 1122,
        "timestamp": 1620000000.0,
        "payload": l_point.model_dump()
    }]
    latency_collection_mock.find = MagicMock(return_value=cursor_mock_latency)

    latencies = await repo.list_ai_latency(guild_id=1122)
    assert len(latencies) == 1
    assert latencies[0].latency_ms == 120.5
    cursor_mock_latency.sort.assert_called_with("timestamp", -1)


@pytest.mark.asyncio
async def test_leaderboard_repository():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    repo = LeaderboardRepository(db_mock)

    entry = LeaderboardEntry(guild_id=1122, name="Mod#0001", actions=50, type="Manual")
    await repo.save_leaderboard_entry(entry)
    collection_mock.replace_one.assert_called_once()

    cursor_mock = AsyncMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.to_list.return_value = [{
        "guild_id": 1122,
        "name": "Mod#0001",
        "actions": 50,
        "payload": entry.model_dump()
    }]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    leaderboard = await repo.list_leaderboard(guild_id=1122)
    assert len(leaderboard) == 1
    assert leaderboard[0].actions == 50
    cursor_mock.sort.assert_called_with("actions", -1)


@pytest.mark.asyncio
async def test_analytics_snapshot_repository():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    kpi = ModeratorKPI(moderator_id=1234, total_actions=5, appeals_granted=1, accuracy_score=0.8)
    automod = AutoModMetrics(total_violations=10, appeals_granted=2, false_positive_rate=0.2)
    snapshot = AnalyticsSnapshot(
        guild_id=1122,
        timestamp=1620000000.0,
        human_kpis={1234: kpi},
        automod_metrics=automod,
        heatmap_data={"12:00": 5}
    )

    repo = AnalyticsSnapshotRepository(db_mock)

    # Test Save
    await repo.save_snapshot(snapshot)
    collection_mock.replace_one.assert_called_once()

    # Test Get by Guild and Timestamp
    collection_mock.find_one.return_value = {
        "id": "1122:1620000000.0",
        "guild_id": 1122,
        "timestamp": 1620000000.0,
        "payload": snapshot.model_dump()
    }
    retrieved = await repo.get_by_guild_id_and_timestamp(guild_id=1122, timestamp=1620000000.0)
    assert retrieved is not None
    assert retrieved.guild_id == 1122
    assert 1234 in retrieved.human_kpis  # check integer key conversion
    assert retrieved.automod_metrics.total_violations == 10

    # Test List by Guild
    cursor_mock = AsyncMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.to_list.return_value = [{
        "id": "1122:1620000000.0",
        "guild_id": 1122,
        "timestamp": 1620000000.0,
        "payload": snapshot.model_dump()
    }]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    snapshots = await repo.list_by_guild(guild_id=1122)
    assert len(snapshots) == 1
    assert snapshots[0].timestamp == 1620000000.0
    cursor_mock.sort.assert_called_with("timestamp", -1)


@pytest.mark.asyncio
async def test_analytics_repository_aggregate():
    db_mock = MagicMock()
    repo = AnalyticsRepository(db_mock)

    assert repo.metrics is not None
    assert repo.trends is not None
    assert repo.leaderboards is not None
    assert repo.snapshots is not None
