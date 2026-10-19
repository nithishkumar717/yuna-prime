import pytest
import os
from pydantic import ValidationError
from core.config.models import BotConfig
from core.config.loader import ConfigurationLoader
from core.config.manager import ConfigManager


def test_bot_config_validation():
    # Valid token (fake but long enough for our validator)
    token = "MTAxMjM0NTY3ODkw.abcdef.1234567890abcdef1234567890abcdef1234567890"
    config = BotConfig(token=token, prefix="!")
    assert config.prefix == "!"
    assert config.token.get_secret_value() == token


def test_bot_config_invalid_token():
    # Token too short
    with pytest.raises(ValidationError):
        BotConfig(token="short_invalid_token")


def test_configuration_loader():
    # Set environment variables for testing loader injection
    os.environ["DISCORD_TOKEN"] = (
        "MTAxMjM0NTY3ODkw.abcdef.1234567890abcdef1234567890abcdef1234567890"
    )
    os.environ["MONGODB_URI"] = "mongodb://localhost:27017"

    loader = ConfigurationLoader()
    config = loader.build_config()

    assert config.bot.prefix == "!"
    assert (
        str(config.database.mongodb_uri) == "mongodb://localhost:27017/"
        or str(config.database.mongodb_uri) == "mongodb://localhost:27017"
    )


def test_config_manager_singleton():
    config1 = ConfigManager.get_config()
    config2 = ConfigManager.get_config()
    assert config1 is config2
