import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from core.database.repositories.configuration_repository import (
    ConfigurationRepository,
    OptimisticConcurrencyError,
)
from configuration.models import GuildConfig


@pytest.mark.asyncio
async def test_config_bootstrap_on_missing_guild():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    # Simulate missing document in Mongo
    collection_mock.find_one.return_value = None

    repo = ConfigurationRepository(db_mock)

    config = await repo.get_by_guild_id("123456")

    assert config is not None
    assert config.spam_limit == 3  # Matches DEFAULT_CONFIG
    collection_mock.find_one.assert_called_once_with({"id": "123456"}, session=None)
    collection_mock.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_config_save_concurrency_error():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    # Simulate existing config with version 1
    existing_doc = {
        "id": "123456",
        "config": {
            "bad_words": [],
            "whitelisted_users": [],
            "whitelisted_roles": [],
            "whitelisted_channels": [],
            "whitelisted_domains": [],
            "spam_limit": 5,
            "anti_nuke_enabled": True,
        },
        "version": 1,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
    collection_mock.find_one.return_value = existing_doc

    # Simulate update failure (modified_count = 0) signifying stale version
    update_result = AsyncMock()
    update_result.modified_count = 0
    collection_mock.update_one.return_value = update_result

    repo = ConfigurationRepository(db_mock)

    new_config = GuildConfig(
        bad_words=["spam"],
        whitelisted_users=[],
        whitelisted_roles=[],
        whitelisted_channels=[],
        whitelisted_domains=[],
        spam_limit=3,
        anti_nuke_enabled=False,
    )

    with pytest.raises(OptimisticConcurrencyError):
        await repo.save_config("123456", new_config)


@pytest.mark.asyncio
async def test_config_redis_caching():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    redis_client_mock = MagicMock()
    redis_mock = AsyncMock()
    redis_client_mock.client = redis_mock

    # Simulate Redis hit
    cached_doc = {
        "id": "123456",
        "config": {
            "bad_words": ["cached_word"],
            "whitelisted_users": [],
            "whitelisted_roles": [],
            "whitelisted_channels": [],
            "whitelisted_domains": [],
            "spam_limit": 10,
            "anti_nuke_enabled": True,
        },
        "version": 2,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
    redis_mock.get.return_value = json.dumps(cached_doc)

    repo = ConfigurationRepository(db_mock, redis_client=redis_client_mock)

    config = await repo.get_by_guild_id("123456")

    assert config.spam_limit == 10
    assert "cached_word" in config.bad_words
    collection_mock.find_one.assert_not_called()  # Verified Mongo query skipped
    redis_mock.get.assert_called_once_with("config:123456")
