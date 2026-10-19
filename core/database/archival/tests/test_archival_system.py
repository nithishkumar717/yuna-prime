import pytest
from unittest.mock import AsyncMock, MagicMock
from core.database.archival import (
    RetentionPolicy,
    CompressionUtil,
    IntegrityVerifier,
    ExportService,
    RestoreService,
    IntegrityMismatchError,
    ArchiveManager
)


def test_retention_policy_cutoffs():
    policy = RetentionPolicy(audit_logs_days=30, security_events_days=90)
    now = 1000000.0

    cutoff_audit = policy.get_cutoff_timestamp("audit_logs", custom_now=now)
    assert cutoff_audit == now - (30 * 86400.0)

    cutoff_sec = policy.get_cutoff_timestamp("security_events", custom_now=now)
    assert cutoff_sec == now - (90 * 86400.0)


def test_compression_gzip():
    text = "Enterprise Data Archival Content Log 12345"
    compressed = CompressionUtil.compress_gzip(text)
    assert isinstance(compressed, bytes)
    assert len(compressed) > 0

    decompressed = CompressionUtil.decompress_gzip(compressed)
    assert decompressed.decode("utf-8") == text


def test_compression_zip():
    files = {
        "log1.txt": "Log file line 1\nLog file line 2",
        "log2.json": '{"status": "ok"}'
    }
    zipped = CompressionUtil.compress_zip(files)
    assert isinstance(zipped, bytes)

    unzipped = CompressionUtil.decompress_zip(zipped)
    assert unzipped["log1.txt"] == files["log1.txt"]
    assert unzipped["log2.json"] == files["log2.json"]


def test_integrity_verifier():
    data = "Critical Audit Log Record Payload"
    digest = IntegrityVerifier.calculate_sha256(data)
    assert len(digest) == 64

    assert IntegrityVerifier.verify_integrity(data, digest) is True
    assert IntegrityVerifier.verify_integrity(data, "0" * 64) is False


@pytest.mark.asyncio
async def test_export_service_json():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    cursor_mock = AsyncMock()
    cursor_mock.to_list.return_value = [
        {"id": "doc-1", "user": "admin", "timestamp": 100.0},
        {"id": "doc-2", "user": "bot", "timestamp": 200.0}
    ]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    export_svc = ExportService(db_mock)
    bundle = await export_svc.export_collection_json("audit_logs", compress=True)

    assert bundle["collection"] == "audit_logs"
    assert bundle["record_count"] == 2
    assert bundle["format"] == "json"
    assert bundle["compressed"] is True
    assert len(bundle["sha256"]) == 64


@pytest.mark.asyncio
async def test_export_service_csv():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    cursor_mock = AsyncMock()
    cursor_mock.to_list.return_value = [
        {"id": "doc-1", "user": "admin", "timestamp": 100.0}
    ]
    collection_mock.find = MagicMock(return_value=cursor_mock)

    export_svc = ExportService(db_mock)
    bundle = await export_svc.export_collection_csv("audit_logs", compress=False)

    assert bundle["format"] == "csv"
    assert bundle["record_count"] == 1
    assert "user" in bundle["payload"]


@pytest.mark.asyncio
async def test_restore_service_success():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    json_data = '[{"id": "rec-1", "action": "ban"}]'
    sha256 = IntegrityVerifier.calculate_sha256(json_data)
    compressed_payload = CompressionUtil.compress_gzip(json_data)

    bundle = {
        "collection": "mod_cases",
        "format": "json",
        "compressed": True,
        "record_count": 1,
        "sha256": sha256,
        "payload": compressed_payload
    }

    restore_svc = RestoreService(db_mock)
    restored_count = await restore_svc.restore_from_export(bundle)

    assert restored_count == 1
    collection_mock.replace_one.assert_called_once()


@pytest.mark.asyncio
async def test_restore_service_corrupted_checksum():
    db_mock = MagicMock()

    json_data = '[{"id": "rec-1", "action": "ban"}]'
    compressed_payload = CompressionUtil.compress_gzip(json_data)

    bundle = {
        "collection": "mod_cases",
        "format": "json",
        "compressed": True,
        "record_count": 1,
        "sha256": "bad_corrupted_checksum_hash_1234567890123456789012345678901234",
        "payload": compressed_payload
    }

    restore_svc = RestoreService(db_mock)
    with pytest.raises(IntegrityMismatchError):
        await restore_svc.restore_from_export(bundle)


@pytest.mark.asyncio
async def test_archive_manager():
    db_mock = MagicMock()
    collection_mock = AsyncMock()
    db_mock.__getitem__.return_value = collection_mock

    delete_result = MagicMock()
    delete_result.deleted_count = 5
    collection_mock.delete_many.return_value = delete_result

    manager = ArchiveManager(db_mock)

    # Test retention purge
    purged = await manager.run_retention_purge(custom_now=1000000.0)
    assert "audit_logs" in purged
    assert purged["audit_logs"] == 5

    # Test integrity verification
    json_data = "Valid Archive Content"
    sha256 = IntegrityVerifier.calculate_sha256(json_data)
    bundle = {
        "compressed": False,
        "sha256": sha256,
        "payload": json_data
    }
    assert manager.verify_archive(bundle) is True
