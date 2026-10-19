import pytest
from security.sentinel.models import ThreatLevel, SecurityAction
from security.sentinel.policy import PolicyEngine
from security.sentinel.response import ResponseEngine


@pytest.mark.asyncio
async def test_policy_engine_whitelist_override():
    engine = PolicyEngine()

    # Standard behavior
    action_blocked = await engine.evaluate(ThreatLevel.CRITICAL, {}, target_id=999)
    assert action_blocked == SecurityAction.BLOCK

    # Whitelist bypass behavior (12345 is the hardcoded mock whitelist ID)
    action_allowed = await engine.evaluate(ThreatLevel.CRITICAL, {}, target_id=12345)
    assert action_allowed == SecurityAction.ALLOW


@pytest.mark.asyncio
async def test_response_engine_execution_logging():
    engine = ResponseEngine()

    # We can ensure it doesn't crash on standard action mappings
    await engine.execute(SecurityAction.BLOCK, {}, target_id=999)
    await engine.execute(SecurityAction.ALLOW, {}, target_id=999)
