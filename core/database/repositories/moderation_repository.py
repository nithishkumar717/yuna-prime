from motor.motor_asyncio import AsyncIOMotorDatabase
from .case_repository import CaseRepository
from .appeal_repository import AppealRepository
from .report_repository import ReportRepository
from .punishment_repository import PunishmentRepository


class ModerationRepository:
    """Unified Aggregate Coordinator grouping Yuna's moderation-specific repositories."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.cases = CaseRepository(db)
        self.appeals = AppealRepository(db)
        self.reports = ReportRepository(db)
        self.punishments = PunishmentRepository(db)
