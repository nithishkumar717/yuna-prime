from pydantic import BaseModel, Field, SecretStr, MongoDsn, RedisDsn
from typing import Optional, List
from .validators import validate_discord_token
from pydantic import field_validator


class BotConfig(BaseModel):
    token: SecretStr
    prefix: str = "!"
    owner_ids: List[int] = Field(default_factory=list)

    @field_validator("token")
    @classmethod
    def check_token(cls, v: SecretStr):
        validate_discord_token(v.get_secret_value())
        return v


class DiscordConfig(BaseModel):
    client_id: Optional[str] = None
    shards: Optional[int] = None


class LoggingConfig(BaseModel):
    level: str = "INFO"
    retention: str = "10 days"
    rotation: str = "5 MB"


class DatabaseConfig(BaseModel):
    mongodb_uri: MongoDsn


class RedisConfig(BaseModel):
    url: RedisDsn = "redis://localhost:6379/0"  # type: ignore


class DashboardConfig(BaseModel):
    port: int = 3000
    host: str = "0.0.0.0"
    base_url: str = "http://localhost:3000"


class SecurityConfig(BaseModel):
    panic_mode: bool = False
    max_warnings: int = 3


class AIConfig(BaseModel):
    gemini_api_key: Optional[SecretStr] = None


class PremiumConfig(BaseModel):
    enabled: bool = False


class YunaConfiguration(BaseModel):
    bot: BotConfig
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig
    redis: RedisConfig = Field(default_factory=RedisConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    premium: PremiumConfig = Field(default_factory=PremiumConfig)
