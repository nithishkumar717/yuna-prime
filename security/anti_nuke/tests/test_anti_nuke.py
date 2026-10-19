import pytest
from unittest.mock import MagicMock, AsyncMock
from security.anti_nuke.models import NukeType
from security.anti_nuke.rate_tracker import SlidingWindowTracker
from security.anti_nuke.service import AntiNukeService, RawDiscordEvent
from security.sentinel.service import SentinelService


def test_sliding_window_tracker_burst():
    tracker = SlidingWindowTracker()

    # Simulate 2 fast channel deletes (Threshold is 2)
    assert not tracker.track(999, NukeType.CHANNEL_DELETE, current_time=1.0)
    assert tracker.track(999, NukeType.CHANNEL_DELETE, current_time=2.0)


def test_sliding_window_tracker_stale_events():
    tracker = SlidingWindowTracker()

    # 1st delete at 1.0s
    assert not tracker.track(999, NukeType.CHANNEL_DELETE, current_time=1.0)

    # 2nd delete happens 20 seconds later (window is 10s). The first delete should be purged.
    assert not tracker.track(999, NukeType.CHANNEL_DELETE, current_time=21.0)


@pytest.mark.asyncio
async def test_anti_nuke_service_integration():
    container = MagicMock()
    bus = MagicMock()
    bus.subscribe = MagicMock()

    sentinel_mock = MagicMock(spec=SentinelService)
    sentinel_mock.pipeline = AsyncMock()

    def resolve_mock(cls):
        if cls == SentinelService:
            return sentinel_mock
        return None

    container.resolve = resolve_mock

    service = AntiNukeService(container, bus)

    # Fire 2 CHANNEL_DELETE events rapidly
    await service._handle_raw_event(
        RawDiscordEvent(event_type="channel_delete", target_id=101)
    )
    await service._handle_raw_event(
        RawDiscordEvent(event_type="channel_delete", target_id=102)
    )

    # Ensure Sentinel was invoked exactly once (on the 2nd event breaching the threshold)
    sentinel_mock.pipeline.evaluate.assert_called_once()
