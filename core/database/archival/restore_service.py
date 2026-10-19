import json
import csv
import io
from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from .compression import CompressionUtil
from .integrity import IntegrityVerifier


class IntegrityMismatchError(Exception):
    """Raised when SHA-256 archive checksum validation fails prior to restore."""
    pass


class RestoreService:
    """Asynchronous restore engine validating SHA-256 signatures and restoring compressed archives to MongoDB."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db

    async def restore_from_export(self, export_bundle: Dict[str, Any], target_collection: str = "") -> int:
        compressed = export_bundle.get("compressed", False)
        raw_payload = export_bundle["payload"]
        expected_sha256 = export_bundle["sha256"]
        fmt = export_bundle.get("format", "json")
        collection_name = target_collection or export_bundle["collection"]

        # Decompress if needed
        if compressed:
            decompressed_bytes = CompressionUtil.decompress_gzip(raw_payload)
            text_data = decompressed_bytes.decode("utf-8")
        else:
            text_data = raw_payload if isinstance(raw_payload, str) else raw_payload.decode("utf-8")

        # Verify integrity
        if not IntegrityVerifier.verify_integrity(text_data, expected_sha256):
            raise IntegrityMismatchError(
                f"Archive integrity checksum validation failed for collection {collection_name}."
            )

        # Parse records
        records: List[Dict[str, Any]] = []
        if fmt == "json":
            records = json.loads(text_data)
        elif fmt == "csv":
            reader = csv.DictReader(io.StringIO(text_data))
            for row in reader:
                parsed_row = {}
                for k, v in row.items():
                    try:
                        parsed_row[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        parsed_row[k] = v
                records.append(parsed_row)

        if not records:
            return 0

        # Perform bulk upsert/insert
        collection = self.db[collection_name]
        inserted_count = 0
        for rec in records:
            # If primary id exists, perform replace/upsert
            record_id = rec.get("id") or rec.get("_id")
            if record_id:
                query = {"id": record_id} if "id" in rec else {"_id": record_id}
                await collection.replace_one(query, rec, upsert=True)
            else:
                await collection.insert_one(rec)
            inserted_count += 1

        return inserted_count
