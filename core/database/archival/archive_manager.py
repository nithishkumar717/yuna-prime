from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from .retention_policy import RetentionPolicy
from .export_service import ExportService
from .restore_service import RestoreService
from .integrity import IntegrityVerifier


class ArchiveManager:
    """Master aggregate coordinator orchestrating database lifecycle retention, compliance exports, and restorations."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.export_service = ExportService(db)
        self.restore_service = RestoreService(db)
        self.default_policy = RetentionPolicy()

    async def run_retention_purge(
        self,
        policy: Optional[RetentionPolicy] = None,
        custom_now: float = 0.0
    ) -> Dict[str, int]:
        active_policy = policy or self.default_policy
        collections_to_purge = [
            "audit_logs",
            "security_events",
            "ai_recommendations",
            "mod_cases",
            "analytics_trends"
        ]

        purged_counts: Dict[str, int] = {}
        for coll in collections_to_purge:
            cutoff = active_policy.get_cutoff_timestamp(coll, custom_now=custom_now)
            result = await self.db[coll].delete_many({"timestamp": {"$lt": cutoff}})
            purged_counts[coll] = result.deleted_count

        return purged_counts

    async def create_archive(
        self,
        collection_name: str,
        retention_days: int = 90,
        fmt: str = "json",
        compress: bool = True
    ) -> Dict[str, Any]:
        policy = RetentionPolicy(**{f"{collection_name}_days": retention_days}) if hasattr(RetentionPolicy(), f"{collection_name}_days") else RetentionPolicy()
        cutoff = policy.get_cutoff_timestamp(collection_name)
        filter_query = {"timestamp": {"$lt": cutoff}}

        if fmt == "csv":
            return await self.export_service.export_collection_csv(collection_name, filter_query, compress=compress)
        return await self.export_service.export_collection_json(collection_name, filter_query, compress=compress)

    async def restore_archive(self, export_bundle: Dict[str, Any], target_collection: str = "") -> int:
        return await self.restore_service.restore_from_export(export_bundle, target_collection=target_collection)

    @staticmethod
    def verify_archive(bundle: Dict[str, Any]) -> bool:
        raw_payload = bundle["payload"]
        expected_sha256 = bundle["sha256"]
        compressed = bundle.get("compressed", False)

        text_data = raw_payload
        if compressed:
            from .compression import CompressionUtil
            text_data = CompressionUtil.decompress_gzip(raw_payload).decode("utf-8")
        elif isinstance(text_data, bytes):
            text_data = text_data.decode("utf-8")

        return IntegrityVerifier.verify_integrity(text_data, expected_sha256)
