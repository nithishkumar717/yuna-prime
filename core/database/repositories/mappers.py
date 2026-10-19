from datetime import datetime
from typing import Dict, Any
from core.database.repositories.models import ConfigurationRecord
from configuration.models import GuildConfig


class ConfigurationMapper:
    """Maps between MongoDB dict documents, database records, and domain models."""

    @staticmethod
    def to_record(document: Dict[str, Any]) -> ConfigurationRecord:
        created_at = document.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif not created_at:
            created_at = datetime.utcnow()

        updated_at = document.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif not updated_at:
            updated_at = datetime.utcnow()

        return ConfigurationRecord(
            guild_id=str(document["id"]),
            config=GuildConfig(**document["config"]),
            version=document.get("version", 1),
            created_at=created_at,
            updated_at=updated_at,
            updated_by=document.get("updated_by"),
        )

    @staticmethod
    def to_document(record: ConfigurationRecord) -> Dict[str, Any]:
        return {
            "id": record.guild_id,
            "config": record.config.model_dump(),
            "version": record.version,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "updated_by": record.updated_by,
        }
