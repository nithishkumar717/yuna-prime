from motor.motor_asyncio import AsyncIOMotorDatabase
from .metrics_repository import MetricsRepository
from .trend_repository import TrendRepository
from .leaderboard_repository import LeaderboardRepository
from .analytics_snapshot_repository import AnalyticsSnapshotRepository


class AnalyticsRepository:
    """Unified Aggregate Coordinator grouping Yuna's Analytics and Telemetry repositories."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.metrics = MetricsRepository(db)
        self.trends = TrendRepository(db)
        self.leaderboards = LeaderboardRepository(db)
        self.snapshots = AnalyticsSnapshotRepository(db)
