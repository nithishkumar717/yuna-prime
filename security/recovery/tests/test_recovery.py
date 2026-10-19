import pytest
from security.recovery.models import RollbackAction, RecoveryStatus
from security.recovery.recovery_engine import RecoveryEngine
from security.recovery.integrity_checker import IntegrityError


def test_restore_planner_generates_diffs():
    engine = RecoveryEngine()

    # 1. Take a safe baseline snapshot
    baseline_state = {"roles": {"Admin": {"permissions": 8}, "Mod": {"permissions": 4}}}
    snap = engine.backup(guild_id=123, state_payload=baseline_state, current_time=1.0)

    # 2. Simulate an attacker deleting Mod, altering Admin, and creating Rogue
    nuked_state = {"roles": {"Admin": {"permissions": 0}, "Rogue": {"permissions": 8}}}

    # 3. Generate a Rollback Plan
    plan = engine.plan_recovery(snap.snapshot_id, nuked_state)
    assert plan is not None
    assert len(plan.tasks) == 3

    actions = {task.action: task.resource_id for task in plan.tasks}

    # Missing from live -> Needs Creation
    assert actions.get(RollbackAction.CREATE) == "Mod"

    # Exists in live, but lacks in snap -> Needs Deletion
    assert actions.get(RollbackAction.DELETE) == "Rogue"

    # Altered in live -> Needs Updating
    assert actions.get(RollbackAction.UPDATE) == "Admin"


def test_integrity_checker_traps_tampering():
    engine = RecoveryEngine()

    snap = engine.backup(guild_id=999, state_payload={"roles": {}}, current_time=1.0)

    # Reach directly into the vault and simulate a hacker maliciously mutating a backup payload at rest
    tampered_snap = engine.vault.snapshots[snap.snapshot_id]
    tampered_snap.payload["roles"]["Admin"] = {"permissions": 8}

    # The Recovery Engine must fail attempting to retrieve or plan against it
    with pytest.raises(IntegrityError):
        engine.plan_recovery(snap.snapshot_id, {})


def test_rollback_executor_simulates_success():
    engine = RecoveryEngine()

    snap = engine.backup(
        guild_id=555, state_payload={"roles": {"A": {}}}, current_time=1.0
    )
    plan = engine.plan_recovery(snap.snapshot_id, live_state={"roles": {}})

    assert plan is not None
    status = engine.execute_recovery(plan)
    assert status == RecoveryStatus.COMPLETED
