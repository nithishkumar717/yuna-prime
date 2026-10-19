import pytest
from unittest.mock import MagicMock, AsyncMock
from security.sentinel.models import ThreatLevel, SecurityAction
from security.sentinel.pipeline import ThreatPipeline
from security.sentinel.engines.risk_engine import RiskEngine
from security.sentinel.service import SentinelService
from security.sentinel.policy import PolicyEngine
from security.sentinel.response import ResponseEngine
from core.services.models import ServiceState


@pytest.mark.asyncio
async def test_threat_pipeline_risk_escalation():
    pipeline = ThreatPipeline(PolicyEngine(), ResponseEngine())
    pipeline.add_analyzer(RiskEngine())

    safe_event = await pipeline.evaluate("test", 999, {"suspicious": False})
    assert safe_event.threat_level == ThreatLevel.NONE
    assert safe_event.action_taken == SecurityAction.ALLOW

    suspicious_event = await pipeline.evaluate("test", 999, {"suspicious": True})
    assert suspicious_event.threat_level == ThreatLevel.HIGH
    assert suspicious_event.action_taken == SecurityAction.QUARANTINE

    critical_event = await pipeline.evaluate("test", 999, {"mass_ping": True})
    assert critical_event.threat_level == ThreatLevel.CRITICAL
    assert critical_event.action_taken == SecurityAction.BLOCK


@pytest.mark.asyncio
async def test_sentinel_service_lifecycle():
    container = MagicMock()
    bus = MagicMock()
    bus.publish = AsyncMock()
    service = SentinelService(container, bus)

    await service.start()
    assert service.state == ServiceState.READY
    assert len(service.pipeline.analyzers) > 0

    await service.stop()
    assert service.state == ServiceState.STOPPED
