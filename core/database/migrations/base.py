from abc import ABC, abstractmethod
from motor.motor_asyncio import AsyncIOMotorDatabase


class BaseMigration(ABC):
    """Abstract Base Class for all Yuna database schema and index migration scripts."""

    version: str
    description: str

    @abstractmethod
    async def upgrade(self, db: AsyncIOMotorDatabase) -> None:
        """Applies schema changes or indexes to the database."""
        pass

    @abstractmethod
    async def downgrade(self, db: AsyncIOMotorDatabase) -> None:
        """Rolls back schema changes or indexes applied by this migration."""
        pass
