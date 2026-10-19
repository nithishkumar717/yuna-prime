from motor.motor_asyncio import AsyncIOMotorDatabase
from ..base import BaseMigration
from ..registry import MigrationRegistry


@MigrationRegistry.register
class V1InitialMigration(BaseMigration):
    version = "v1_initial"
    description = "Initial schema bootstrapping: create indexes for core system collections."

    async def upgrade(self, db: AsyncIOMotorDatabase) -> None:
        await db["guild_configs"].create_index("guild_id", unique=True)

    async def downgrade(self, db: AsyncIOMotorDatabase) -> None:
        await db["guild_configs"].drop_index("guild_id_1")
