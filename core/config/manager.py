from .loader import ConfigurationLoader
from .models import YunaConfiguration


class ConfigManager:
    """
    Singleton Configuration Manager.
    Provides strictly typed access to configuration via Pydantic models.
    Example: config.bot.token.get_secret_value()
    """

    _instance: YunaConfiguration = None  # type: ignore

    @classmethod
    def load(cls) -> YunaConfiguration:
        if cls._instance is None:
            loader = ConfigurationLoader()
            cls._instance = loader.build_config()
        return cls._instance

    @classmethod
    def get_config(cls) -> YunaConfiguration:
        if cls._instance is None:
            return cls.load()
        return cls._instance
