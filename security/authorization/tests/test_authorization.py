import pytest
from security.sentinel.models import ThreatLevel
from security.authorization.permission_guard import PermissionGuard
from security.authorization.role_guard import RoleGuard


@pytest.mark.asyncio
async def test_permission_guard_escalation():
    guard = PermissionGuard()

    # Safe permissions
    safe_threat = await guard.analyze(
        {"granted_permissions": ["change_nickname"]}, ThreatLevel.NONE
    )
    assert safe_threat == ThreatLevel.NONE

    # Dangerous permissions
    danger_threat = await guard.analyze(
        {"granted_permissions": ["administrator"]}, ThreatLevel.NONE
    )
    assert danger_threat == ThreatLevel.HIGH


@pytest.mark.asyncio
async def test_role_guard_hierarchy_enforcement():
    guard = RoleGuard()

    # Actor (position 10) acting on Target (position 5). This is a safe downgrade/management.
    safe_threat = await guard.analyze(
        {"actor_top_role": 10, "target_top_role": 5}, ThreatLevel.NONE
    )
    assert safe_threat == ThreatLevel.NONE

    # Actor (position 5) acting on Target (position 10). This is PRIVILEGE ESCALATION.
    danger_threat = await guard.analyze(
        {"actor_top_role": 5, "target_top_role": 10}, ThreatLevel.NONE
    )
    assert danger_threat == ThreatLevel.CRITICAL

    # Attempting to target the Guild Owner
    owner_threat = await guard.analyze({"target_is_owner": True}, ThreatLevel.NONE)
    assert owner_threat == ThreatLevel.CRITICAL
