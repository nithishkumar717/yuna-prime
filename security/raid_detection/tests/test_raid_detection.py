import pytest
from unittest.mock import MagicMock, AsyncMock
from security.raid_detection.detector import RaidDetector
from security.raid_detection.service import RaidDetectionService, MemberJoinEvent
from security.sentinel.service import SentinelService


def test_raid_detector_ignores_veteran_influx():
    detector = RaidDetector()

    # 5 veterans join instantly (velocity breached, but age > 1)
    assert not detector.process_join(guild_id=1, account_age_days=365, current_time=1.0)
    assert not detector.process_join(guild_id=1, account_age_days=400, current_time=1.0)
    assert not detector.process_join(guild_id=1, account_age_days=100, current_time=1.0)
    assert not detector.process_join(guild_id=1, account_age_days=500, current_time=1.0)
    assert not detector.process_join(guild_id=1, account_age_days=365, current_time=1.0)

    # The detector should NOT flag a raid, because it recognizes a legitimate community migration!


def test_raid_detector_catches_bot_swarm():
    detector = RaidDetector()

    # 5 newly generated bots join instantly (velocity breached AND age < 1)
    assert not detector.process_join(guild_id=1, account_age_days=0, current_time=1.0)
    assert not detector.process_join(guild_id=1, account_age_days=0, current_time=1.0)
    assert not detector.process_join(guild_id=1, account_age_days=0, current_time=1.0)
    assert not detector.process_join(guild_id=1, account_age_days=0, current_time=1.0)

    # The 5th join pushes the velocity threshold and completes the raid condition
    assert detector.process_join(guild_id=1, account_age_days=0, current_time=1.0)


@pytest.mark.asyncio
async def test_raid_detection_service_integration():
    container = MagicMock()
    bus = MagicMock()
    bus.register = MagicMock()

    sentinel_mock = MagicMock(spec=SentinelService)
    sentinel_mock.pipeline = AsyncMock()

    def resolve_mock(cls):
        if cls == SentinelService:
            return sentinel_mock
        return None

    container.resolve = resolve_mock

    service = RaidDetectionService(container, bus)

    # Fire 5 bot joins rapidly
    for _ in range(4):
        await service._handle_join_event(
            MemberJoinEvent(guild_id=1, actor_id=100, account_age_days=0)
        )

    await service._handle_join_event(
        MemberJoinEvent(guild_id=1, actor_id=101, account_age_days=0)
    )

    # Ensure Sentinel was invoked exactly once (on the 5th breach)
    sentinel_mock.pipeline.evaluate.assert_called_once()
