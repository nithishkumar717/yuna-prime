import pytest
from unittest.mock import MagicMock, AsyncMock
from security.behavior.anomaly_detector import AnomalyDetector as ConcreteDetector
from security.behavior.models import BehaviorType
from security.behavior.service import BehaviorService, BehavioralEvent
from security.sentinel.service import SentinelService


def test_sequence_analyzer_detects_hostile_chain():
    detector = ConcreteDetector()

    # Safe random events
    assert detector.process_event(123, "message_send", 1.0) is None
    assert detector.process_event(123, "reaction_add", 2.0) is None

    # Start Hostile Sequence (webhook_create -> role_modify -> channel_delete)
    assert detector.process_event(123, "webhook_create", 3.0) is None
    assert detector.process_event(123, "role_modify", 4.0) is None

    anomaly = detector.process_event(123, "channel_delete", 5.0)
    assert anomaly is not None
    assert anomaly.behavior_type == BehaviorType.SEQUENCE_ANOMALY


def test_frequency_analyzer_detects_long_tail_spike():
    detector = ConcreteDetector()

    # Inject 16 events rapidly (Baseline triggers at > 15 = 5 historical * 3)
    for i in range(15):
        assert detector.process_event(999, "role_modify", i * 1.0) is None

    anomaly = detector.process_event(999, "role_modify", 16.0)
    assert anomaly is not None
    assert anomaly.behavior_type == BehaviorType.FREQUENCY_ANOMALY


@pytest.mark.asyncio
async def test_behavior_service_integration():
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

    service = BehaviorService(container, bus)

    # Fire the exact hostile sequence mapped in the analyzer
    await service._handle_behavior_event(
        BehavioralEvent(actor_id=555, event_type="webhook_create")
    )
    await service._handle_behavior_event(
        BehavioralEvent(actor_id=555, event_type="role_modify")
    )
    await service._handle_behavior_event(
        BehavioralEvent(actor_id=555, event_type="channel_delete")
    )

    # Ensure Sentinel was invoked exactly once (on the 3rd sequenced event)
    sentinel_mock.pipeline.evaluate.assert_called_once()
