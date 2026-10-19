import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database.repository import MongoRepository
from core.database.repositories.models import ConfigurationRecord
from core.database.repositories.mappers import ConfigurationMapper
from configuration.models import GuildConfig
from configuration.defaults import DEFAULT_CONFIG


class OptimisticConcurrencyError(Exception):
    """Raised when an update conflicts with a newer document version."""

    pass


class ConfigurationRepository(MongoRepository):
    """Asynchronous Repository managing Yuna's centralized guild configurations with OCC and Redis caching."""

    def __init__(
        self, db: AsyncIOMotorDatabase, redis_client: Optional[Any] = None
    ) -> None:
        super().__init__(db, "guild_configurations")
        self.redis_client = redis_client
        self._local_cache: Dict[str, ConfigurationRecord] = {}

    def _get_cache_key(self, guild_id: str) -> str:
        return f"config:{guild_id}"

    async def get_by_guild_id(
        self, guild_id: str, session: Optional[Any] = None
    ) -> GuildConfig:
        # 1. Try Redis cache
        cache_key = self._get_cache_key(guild_id)
        if self.redis_client and self.redis_client.client:
            try:
                cached_data = await self.redis_client.client.get(cache_key)
                if cached_data:
                    record_dict = json.loads(cached_data)
                    record = ConfigurationMapper.to_record(record_dict)
                    self._local_cache[guild_id] = record
                    return record.config
            except Exception as e:
                logging.warning(
                    f"Failed to read from Redis cache: {e}. Falling back to database."
                )

        # 2. Try Local Cache
        if guild_id in self._local_cache:
            return self._local_cache[guild_id].config

        # 3. Query MongoDB
        doc = await self.get(guild_id, session=session)
        if doc:
            record = ConfigurationMapper.to_record(doc)
        else:
            # 4. Bootstrap default config
            record = ConfigurationRecord(
                guild_id=guild_id, config=DEFAULT_CONFIG.model_copy(deep=True)
            )
            await self.add(ConfigurationMapper.to_document(record), session=session)
            logging.info(
                f"Bootstrapped default configuration profile for guild {guild_id}."
            )

        # Update cache layers
        self._local_cache[guild_id] = record
        await self._write_to_redis(record)
        return record.config

    async def save_config(
        self,
        guild_id: str,
        config: GuildConfig,
        updated_by: Optional[str] = None,
        session: Optional[Any] = None,
    ) -> None:
        doc = await self.get(guild_id, session=session)
        if not doc:
            record = ConfigurationRecord(
                guild_id=guild_id, config=config, version=1, updated_by=updated_by
            )
            await self.add(ConfigurationMapper.to_document(record), session=session)
        else:
            current_record = ConfigurationMapper.to_record(doc)
            new_version = current_record.version + 1

            record = ConfigurationRecord(
                guild_id=guild_id,
                config=config,
                version=new_version,
                created_at=current_record.created_at,
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
                updated_by=updated_by,
            )

            doc_data = ConfigurationMapper.to_document(record)
            result = await self.collection.update_one(
                {"id": guild_id, "version": current_record.version},
                {"$set": doc_data},
                session=session,
            )

            if result.modified_count == 0:
                raise OptimisticConcurrencyError(
                    f"Optimistic concurrency conflict for guild {guild_id}. Current version in DB has changed."
                )

        # Invalidate/Write-Through Cache
        self._local_cache[guild_id] = record
        await self._write_to_redis(record)

    async def patch_config(
        self,
        guild_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None,
        session: Optional[Any] = None,
    ) -> None:
        current_config = await self.get_by_guild_id(guild_id, session=session)
        patched_data = current_config.model_dump()
        for k, v in updates.items():
            if k in patched_data:
                patched_data[k] = v
        patched_config = GuildConfig(**patched_data)
        await self.save_config(
            guild_id, patched_config, updated_by=updated_by, session=session
        )

    async def _write_to_redis(self, record: ConfigurationRecord) -> None:
        if self.redis_client and self.redis_client.client:
            try:
                cache_key = self._get_cache_key(record.guild_id)
                document = ConfigurationMapper.to_document(record)
                document["created_at"] = document["created_at"].isoformat()
                document["updated_at"] = document["updated_at"].isoformat()
                await self.redis_client.client.set(
                    cache_key, json.dumps(document), ex=3600
                )
            except Exception as e:
                logging.warning(f"Failed to write to Redis cache: {e}")
