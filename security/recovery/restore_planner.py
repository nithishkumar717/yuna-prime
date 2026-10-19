from typing import Dict, Any
from .models import Snapshot, RollbackPlan, RollbackTask, RollbackAction


class RestorePlanner:
    """Diffing engine that isolates structural divergence between a Snapshot and the Live State."""

    def generate_plan(
        self, snapshot: Snapshot, live_state: Dict[str, Any]
    ) -> RollbackPlan:
        plan = RollbackPlan(target_snapshot_id=snapshot.snapshot_id)

        # Simplified Structural Diff Logic on Roles
        snap_roles = snapshot.payload.get("roles", {})
        live_roles = live_state.get("roles", {})

        # 1. Identify Missing / Altered Roles (Snapshot has it, Live State lacks or differs)
        for role_id, role_data in snap_roles.items():
            if role_id not in live_roles:
                plan.tasks.append(
                    RollbackTask(RollbackAction.CREATE, "role", role_id, role_data)
                )
            elif live_roles[role_id] != role_data:
                plan.tasks.append(
                    RollbackTask(RollbackAction.UPDATE, "role", role_id, role_data)
                )

        # 2. Identify Rogue Infrastructure (Live State has it, Snapshot lacks it)
        for role_id in live_roles:
            if role_id not in snap_roles:
                plan.tasks.append(
                    RollbackTask(RollbackAction.DELETE, "role", role_id, {})
                )

        return plan
