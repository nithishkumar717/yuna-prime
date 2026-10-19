from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from configuration.models import GuildConfig


class ConfigurationRecord(BaseModel):
    """Database representation of a Guild Configuration containing metadata and audit logs."""

    guild_id: str
    config: GuildConfig
    version: int = 1
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_by: Optional[str] = None
