from motor.motor_asyncio import AsyncIOMotorDatabase
from ..base import BaseMigration
from ..registry import MigrationRegistry


@MigrationRegistry.register
class V3ModerationMigration(BaseMigration):
    version = "v3_moderation"
    description = "Moderation subsystem migration: compound indexes for cases and punishments."

    async def upgrade(self, db: AsyncIOMotorDatabase) -> None:
        await db["mod_cases"].create_index([("guild_id", 1), ("case_id", 1)], unique=True)
        await db["mod_punishments"].create_index([("guild_id", 1), ("user_id", 1), ("active", 1)])

    async def downgrade(self, db: AsyncIOMotorDatabase) -> None:
        await db["mod_cases"].drop_index("guild_id_1_case_id_1")
        await db["mod_punishments"].drop_index("guild_id_1_user_id_1_active_1")
