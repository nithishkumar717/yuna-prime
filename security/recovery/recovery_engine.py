from typing import Dict, Any, Optional
from .models import Snapshot, RollbackPlan, RecoveryStatus
from .backup_vault import BackupVault
from .snapshot_manager import SnapshotManager
from .restore_planner import RestorePlanner
from .rollback_executor import RollbackExecutor


class RecoveryEngine:
    """Orchestrates the RestorePlanner and RollbackExecutor against the BackupVault."""

    def __init__(self) -> None:
        self.vault = BackupVault()
        self.manager = SnapshotManager()
        self.planner = RestorePlanner()
        self.executor = RollbackExecutor()

    def backup(
        self, guild_id: int, state_payload: Dict[str, Any], current_time: float = 0.0
    ) -> Snapshot:
        snapshot = self.manager.create_snapshot(guild_id, state_payload, current_time)
        self.vault.store(snapshot)
        return snapshot

    def plan_recovery(
        self, snapshot_id: str, live_state: Dict[str, Any]
    ) -> Optional[RollbackPlan]:
        snapshot = self.vault.retrieve(snapshot_id)
        if not snapshot:
            return None
        return self.planner.generate_plan(snapshot, live_state)

    def execute_recovery(self, plan: RollbackPlan) -> RecoveryStatus:
        return self.executor.execute(plan)
