import json
import csv
import io
import time
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from .compression import CompressionUtil
from .integrity import IntegrityVerifier


class ExportService:
    """Asynchronous export service dumping MongoDB collections into structured compliance formats (JSON/CSV)."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db

    async def export_collection_json(
        self,
        collection_name: str,
        filter_query: Optional[Dict[str, Any]] = None,
        compress: bool = True
    ) -> Dict[str, Any]:
        cursor = self.db[collection_name].find(filter_query or {})
        docs = await cursor.to_list(length=10000)

        # Sanitize internal _id for serialization
        clean_docs = []
        for doc in docs:
            d = dict(doc)
            if "_id" in d:
                d["_id"] = str(d["_id"])
            clean_docs.append(d)

        json_str = json.dumps(clean_docs, indent=2)
        sha256 = IntegrityVerifier.calculate_sha256(json_str)

        output_data: Any = CompressionUtil.compress_gzip(json_str) if compress else json_str

        return {
            "collection": collection_name,
            "format": "json",
            "compressed": compress,
            "record_count": len(clean_docs),
            "sha256": sha256,
            "exported_at": time.time(),
            "payload": output_data
        }

    async def export_collection_csv(
        self,
        collection_name: str,
        filter_query: Optional[Dict[str, Any]] = None,
        compress: bool = True
    ) -> Dict[str, Any]:
        cursor = self.db[collection_name].find(filter_query or {})
        docs = await cursor.to_list(length=10000)

        output = io.StringIO()
        if docs:
            # Collect all field names
            fieldnames: set[str] = set()
            clean_docs = []
            for doc in docs:
                d = dict(doc)
                if "_id" in d:
                    d["_id"] = str(d["_id"])
                fieldnames.update(d.keys())
                clean_docs.append(d)

            sorted_fields = sorted(list(fieldnames))
            writer = csv.DictWriter(output, fieldnames=sorted_fields)
            writer.writeheader()
            for clean_doc in clean_docs:
                writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in clean_doc.items()})

        csv_str = output.getvalue()
        sha256 = IntegrityVerifier.calculate_sha256(csv_str)

        output_data: Any = CompressionUtil.compress_gzip(csv_str) if compress else csv_str

        return {
            "collection": collection_name,
            "format": "csv",
            "compressed": compress,
            "record_count": len(docs),
            "sha256": sha256,
            "exported_at": time.time(),
            "payload": output_data
        }
