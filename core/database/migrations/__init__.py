"""
Database Migration System providing ordered schema evolution, history persistence, locking, and dry-run execution.
"""

from .base import BaseMigration
from .history_repository import MigrationHistoryRepository, MigrationRecord
from .registry import MigrationRegistry
from .runner import MigrationRunner, LockAcquisitionError
from .manager import MigrationManager

# Import versions so that their @MigrationRegistry.register decorators execute
from .versions import v1_initial, v2_configuration, v3_moderation

__all__ = [
    "BaseMigration",
    "MigrationHistoryRepository",
    "MigrationRecord",
    "MigrationRegistry",
    "MigrationRunner",
    "LockAcquisitionError",
    "MigrationManager",
    "v1_initial",
    "v2_configuration",
    "v3_moderation",
]
