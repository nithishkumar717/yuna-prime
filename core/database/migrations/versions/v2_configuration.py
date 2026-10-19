from motor.motor_asyncio import AsyncIOMotorDatabase
from ..base import BaseMigration
from ..registry import MigrationRegistry


@MigrationRegistry.register
class V2ConfigurationMigration(BaseMigration):
    version = "v2_configuration"
    description = "Configuration subsystem migration: index module toggles."

    async def upgrade(self, db: AsyncIOMotorDatabase) -> None:
        await db["guild_configs"].create_index("updated_at")

    async def downgrade(self, db: AsyncIOMotorDatabase) -> None:
        await db["guild_configs"].drop_index("updated_at_1")
