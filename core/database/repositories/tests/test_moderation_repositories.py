import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from core.database.repositories.case_repository import CaseRepository
from core.database.repositories.appeal_repository import AppealRepository
from core.database.repositories.report_repository import ReportRepository
from core.database.repositories.punishment_repository import PunishmentRepository
from moderation.cases.models import ModerationCase
from moderation.punishments.punishment_models import PunishmentType
from moderation.appeals.models import ModerationAppeal, AppealStatus
from moderation.reports.models import ModerationReport, ReportStatus, ReportPriority


@pytest.mark.asyncio
async def test_case_repository_save_and_retrieve():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    case = ModerationCase(
        case_uuid="uuid-12345",
        guild_id=1122,
        case_number=1,
        target_id=4444,
        moderator_id=5555,
        punishment_type=PunishmentType.BAN,
        reason="Hacking incident",
        created_at=datetime.now(timezone.utc).timestamp(),
    )

    repo = CaseRepository(db_mock)
    await repo.save_case(case)

    collection_mock.replace_one.assert_called_once()

    # Simulate get match
    stored_doc = {
        "id": "uuid-12345",
        "guild_id": 1122,
        "case_number": 1,
        "payload": case.model_dump(),
    }
    collection_mock.find_one.return_value = stored_doc

    retrieved = await repo.get_by_uuid("uuid-12345")
    assert retrieved is not None
    assert retrieved.reason == "Hacking incident"
    assert retrieved.punishment_type == PunishmentType.BAN


@pytest.mark.asyncio
async def test_appeal_repository_pending_list():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    appeal = ModerationAppeal(
        appeal_id="appeal-1",
        guild_id=1122,
        case_number=1,
        user_id=4444,
        appeal_reason="Accidental trigger",
        status=AppealStatus.PENDING,
        created_at=datetime.now(timezone.utc).timestamp(),
    )

    cursor_mock = AsyncMock()
    cursor_mock.to_list.return_value = [{"payload": appeal.model_dump()}]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    repo = AppealRepository(db_mock)
    pending_appeals = await repo.list_pending(1122)

    assert len(pending_appeals) == 1
    assert pending_appeals[0].appeal_reason == "Accidental trigger"
    collection_mock.find.assert_called_once_with(
        {"guild_id": 1122, "status": "PENDING"}, session=None
    )


@pytest.mark.asyncio
async def test_report_repository_open_queue():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    report = ModerationReport(
        report_id="report-1",
        guild_id=1122,
        reporter_id=9999,
        target_id=8888,
        reason="Spam links",
        status=ReportStatus.OPEN,
        priority=ReportPriority.HIGH,
        created_at=datetime.now(timezone.utc).timestamp(),
    )

    cursor_mock = AsyncMock()
    cursor_mock.to_list.return_value = [{"payload": report.model_dump()}]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    repo = ReportRepository(db_mock)
    open_reports = await repo.list_open_reports(1122)

    assert len(open_reports) == 1
    assert open_reports[0].reason == "Spam links"
    collection_mock.find.assert_called_once_with(
        {"guild_id": 1122, "status": {"$in": ["OPEN", "ASSIGNED"]}}, session=None
    )


@pytest.mark.asyncio
async def test_punishment_repository_expired_listings():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    punishment = {
        "id": "punish-1",
        "guild_id": 1122,
        "target_id": 4444,
        "punishment_type": "TIMEOUT",
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(minutes=5),
        "active": True,
    }

    cursor_mock = AsyncMock()
    cursor_mock.to_list.return_value = [punishment]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    repo = PunishmentRepository(db_mock)
    expired = await repo.list_expired_punishments()

    assert len(expired) == 1
    assert expired[0]["punishment_type"] == "TIMEOUT"
    collection_mock.find.assert_called_once()
