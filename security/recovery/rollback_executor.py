from .models import RollbackPlan, RollbackAction, RecoveryStatus


class RollbackExecutor:
    """Consumes a validated RollbackPlan and simulates API execution safely."""

    def execute(self, plan: RollbackPlan) -> RecoveryStatus:
        for task in plan.tasks:
            if task.action == RollbackAction.CREATE:
                # Simulation: await discord.create_role(task.data)
                pass
            elif task.action == RollbackAction.UPDATE:
                # Simulation: await discord.edit_role(task.data)
                pass
            elif task.action == RollbackAction.DELETE:
                # Simulation: await discord.delete_role(task.resource_id)
                pass

        return RecoveryStatus.COMPLETED
