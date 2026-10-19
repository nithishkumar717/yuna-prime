import pytest
from security.sentinel.models import ThreatLevel, SecurityAction
from security.sentinel.engines.trust_engine import TrustEngine
from security.sentinel.engines.reputation_engine import ReputationEngine
from security.sentinel.pipeline import ThreatPipeline
from security.sentinel.engines.risk_engine import RiskEngine
from security.sentinel.policy import PolicyEngine
from security.sentinel.response import ResponseEngine


@pytest.mark.asyncio
async def test_trust_engine_downgrades_veterans():
    pipeline = ThreatPipeline(PolicyEngine(), ResponseEngine())
    pipeline.add_analyzer(RiskEngine())
    pipeline.add_analyzer(TrustEngine())

    # Normally, suspicious=True equals ThreatLevel.HIGH -> QUARANTINE
    # But this user is a veteran (trust > 90, duration > 365)
    event = await pipeline.evaluate(
        "test",
        999,
        {"suspicious": True, "trust_score": 95, "membership_duration_days": 400},
    )

    # The ThreatLevel should be buffered down to LOW by the TrustEngine
    assert event.threat_level == ThreatLevel.LOW
    assert event.action_taken == SecurityAction.ALLOW


@pytest.mark.asyncio
async def test_reputation_engine_escalates_scammers():
    pipeline = ThreatPipeline(PolicyEngine(), ResponseEngine())
    pipeline.add_analyzer(RiskEngine())
    pipeline.add_analyzer(ReputationEngine())

    # Completely innocent event locally...
    # But externally flagged as known_scammer
    event = await pipeline.evaluate(
        "test", 999, {"suspicious": False, "known_scammer": True}
    )

    # The ReputationEngine overrides to CRITICAL
    assert event.threat_level == ThreatLevel.CRITICAL
    assert event.action_taken == SecurityAction.BLOCK
