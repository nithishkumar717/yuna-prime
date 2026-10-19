from typing import Dict, List, Type, Optional
from .base import BaseMigration


class MigrationRegistry:
    """Central registry maintaining an ordered sequence of all registered database migrations."""

    _registry: Dict[str, BaseMigration] = {}

    @classmethod
    def register(cls, migration_cls: Type[BaseMigration]) -> Type[BaseMigration]:
        """Decorator or class registration method for migration classes."""
        instance = migration_cls()
        cls._registry[instance.version] = instance
        return migration_cls

    @classmethod
    def get_all_migrations(cls) -> List[BaseMigration]:
        """Returns registered migrations ordered naturally by version string."""
        return [cls._registry[k] for k in sorted(cls._registry.keys())]

    @classmethod
    def get_migration(cls, version: str) -> Optional[BaseMigration]:
        """Returns the migration instance matching the given version."""
        return cls._registry.get(version)

    @classmethod
    def clear(cls) -> None:
        """Clears registered migrations (primarily for test isolation)."""
        cls._registry.clear()
