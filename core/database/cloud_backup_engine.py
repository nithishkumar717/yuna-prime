from utils.config import MONGO_DATABASE_NAME
"""
YUNA Cloud Database Backup & Disaster Recovery Engine
Integrates SQLite with MongoDB Atlas to provide zero-command, change-driven cloud persistence.
All timestamps are strictly formatted in Indian Standard Time (Asia/Kolkata, UTC+5:30).
"""

import os
import io
import time
import zipfile
import sqlite3
import datetime
import pytz
import bson
from typing import Tuple, Dict, Any, List, Optional
from pymongo import MongoClient, DESCENDING

IST_TZ = pytz.timezone("Asia/Kolkata")
MAX_SNAPSHOTS_TO_KEEP = 5

# Critical databases that MUST be non-empty for a backup to be considered healthy
CRITICAL_DBS = {
    "anti.db", "np.db", "reminders.db", "invc.db",
    "notify.db", "leaderboard.db", "automod.db", "prefix.db"
}
# Minimum number of non-empty db files required before we allow saving to Atlas
MIN_HEALTHY_DB_COUNT = 15


def get_current_time_ist() -> Tuple[float, str]:
    """Returns (unix_timestamp, formatted_ist_string)."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_ist = now_utc.astimezone(IST_TZ)
    timestamp_ist = now_ist.strftime("%d-%m-%Y %I:%M:%S %p IST")
    return now_utc.timestamp(), timestamp_ist


def checkpoint_all_dbs(db_dir: str = "db") -> int:
    """
    Executes PRAGMA wal_checkpoint(PASSIVE) on all SQLite databases in db_dir
    to merge uncommitted WAL frames without acquiring exclusive locks that freeze the bot or dashboard.
    """
    if not os.path.exists(db_dir):
        return 0

    checkpointed_count = 0
    for filename in os.listdir(db_dir):
        if filename.endswith(".db"):
            db_path = os.path.join(db_dir, filename)
            try:
                conn = sqlite3.connect(db_path, timeout=5.0)
                cursor = conn.cursor()
                cursor.execute("PRAGMA wal_checkpoint(PASSIVE);")
                cursor.close()
                conn.close()
                checkpointed_count += 1
            except Exception as e:
                print(f"[DB CHECKPOINT WARNING] {filename}: {e}")
    return checkpointed_count


def create_db_archive(db_dir: str = "db") -> Tuple[bytes, List[str], int]:
    """
    Compresses all .db files into an in-memory zip buffer.
    Excludes transient -wal, -shm, or temporary cache files.
    Returns: (zip_bytes, list_of_db_filenames, total_uncompressed_bytes)
    """
    if not os.path.exists(db_dir):
        return b"", [], 0

    checkpoint_all_dbs(db_dir)

    buf = io.BytesIO()
    archived_files = []
    total_uncompressed = 0

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
        for filename in sorted(os.listdir(db_dir)):
            if filename.endswith(".db") or filename == "local_settings.json":
                full_path = os.path.join(db_dir, filename)
                if os.path.isfile(full_path):
                    f_size = os.path.getsize(full_path)
                    total_uncompressed += f_size
                    zip_file.write(full_path, arcname=filename)
                    archived_files.append(filename)

    zip_bytes = buf.getvalue()
    return zip_bytes, archived_files, total_uncompressed


def verify_db_integrity(db_dir: str = "db") -> Tuple[bool, List[str]]:
    """
    Runs PRAGMA integrity_check on all restored .db files to guarantee zero corruption.
    """
    if not os.path.exists(db_dir):
        return False, ["db directory does not exist"]

    errors = []
    for filename in os.listdir(db_dir):
        if filename.endswith(".db"):
            db_path = os.path.join(db_dir, filename)
            try:
                conn = sqlite3.connect(db_path, timeout=5.0)
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()
                cursor.close()
                conn.close()
                if not result or result[0] != "ok":
                    errors.append(f"{filename}: integrity check failed ({result})")
            except Exception as e:
                errors.append(f"{filename}: could not verify integrity ({e})")

    return len(errors) == 0, errors


def validate_archive_health(
    zip_bytes: bytes,
    last_uncompressed_size: int = 0
) -> tuple:
    """
    Pre-flight check before saving a snapshot to Atlas.
    Refuses to save if:
      - Any CRITICAL_DB is empty (0 bytes) inside the archive
      - Fewer than MIN_HEALTHY_DB_COUNT db files are non-empty
      - Total uncompressed size dropped more than 70% vs last saved snapshot
        (indicates db/ was wiped while bot was running)

    Returns: (is_healthy: bool, reason: str)
    """
    try:
        buf = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            members = {m.filename: m.file_size for m in zf.infolist()}

        # Check critical DBs are present and non-empty
        for critical in CRITICAL_DBS:
            size = members.get(critical, -1)
            if size == 0:
                return False, f"Critical DB '{critical}' is EMPTY in archive — db/ was likely deleted while bot was running"

        # Count healthy (non-empty) db files
        healthy = sum(1 for f, s in members.items() if f.endswith(".db") and s > 0)
        if healthy < MIN_HEALTHY_DB_COUNT:
            return False, f"Only {healthy} non-empty db files found (minimum {MIN_HEALTHY_DB_COUNT}) — refusing poisoned backup"

        # Size regression check: if total size dropped >70%, something is wrong
        total_size = sum(s for f, s in members.items() if f.endswith(".db"))
        if last_uncompressed_size > 0 and total_size < last_uncompressed_size * 0.30:
            return False, (
                f"Archive uncompressed size dropped from {last_uncompressed_size:,} to {total_size:,} bytes "
                f"(>{(1 - total_size/last_uncompressed_size)*100:.0f}% reduction) — likely db deletion event"
            )

        return True, "OK"
    except Exception as e:
        return False, f"Archive validation error: {e}"


def get_local_db_latest_mtime(db_dir: str = "db") -> float:
    """Returns the newest modification timestamp among all .db files in db/."""
    if not os.path.exists(db_dir):
        return 0.0

    latest_mtime = 0.0
    for filename in os.listdir(db_dir):
        if filename.endswith(".db"):
            full_path = os.path.join(db_dir, filename)
            if os.path.isfile(full_path):
                latest_mtime = max(latest_mtime, os.path.getmtime(full_path))
    return latest_mtime


def get_local_db_fingerprint(db_dir: str = "db") -> Dict[str, Tuple[float, int]]:
    """Returns a fingerprint map {filename: (mtime, size)} of all active .db and -wal files."""
    if not os.path.exists(db_dir):
        return {}

    fingerprint = {}
    for filename in os.listdir(db_dir):
        if filename.endswith(".db") or filename.endswith(".db-wal"):
            full_path = os.path.join(db_dir, filename)
            if os.path.isfile(full_path):
                fingerprint[filename] = (os.path.getmtime(full_path), os.path.getsize(full_path))
    return fingerprint


def save_snapshot_to_mongo(
    client: MongoClient,
    zip_bytes: bytes,
    archived_files: List[str],
    uncompressed_size: int,
    reason: str = "Database update detected"
) -> Dict[str, Any]:
    """
    Saves a compressed snapshot document into MongoDB Atlas (database_snapshots (isolated)).
    Stamps with IST timezone, sets is_latest=True, and automatically prunes snapshots older
    than the last 5 versions so MongoDB storage remains lightweight.
    """
    db = client[MONGO_DATABASE_NAME]
    coll = db["database_snapshots"]

    unix_ts, timestamp_ist = get_current_time_ist()
    snapshot_id = f"snap_{int(unix_ts)}"

    # 1. Unmark previous latest snapshots
    coll.update_many({"is_latest": True}, {"$set": {"is_latest": False}})

    # 2. Insert new snapshot document
    doc = {
        "snapshot_id": snapshot_id,
        "is_latest": True,
        "timestamp_unix": unix_ts,
        "timestamp_ist": timestamp_ist,
        "reason": reason,
        "files_count": len(archived_files),
        "files": archived_files,
        "compressed_size_bytes": len(zip_bytes),
        "uncompressed_size_bytes": uncompressed_size,
        "payload": bson.Binary(zip_bytes)
    }
    coll.insert_one(doc)

    # 3. Rolling Retention: keep only MAX_SNAPSHOTS_TO_KEEP most recent snapshots
    all_snapshots = list(coll.find({}, {"_id": 1, "snapshot_id": 1, "timestamp_unix": 1}).sort("timestamp_unix", DESCENDING))
    if len(all_snapshots) > MAX_SNAPSHOTS_TO_KEEP:
        to_delete = all_snapshots[MAX_SNAPSHOTS_TO_KEEP:]
        delete_ids = [s["_id"] for s in to_delete]
        coll.delete_many({"_id": {"$in": delete_ids}})
        print(f"[MONGODB CLOUD BACKUP] Pruned {len(delete_ids)} older snapshot(s). Kept newest {MAX_SNAPSHOTS_TO_KEEP}.")

    print(f"[MONGODB CLOUD BACKUP] Successfully saved snapshot {snapshot_id} to Atlas ({timestamp_ist}, {len(zip_bytes)} bytes)")
    return {
        "snapshot_id": snapshot_id,
        "timestamp_ist": timestamp_ist,
        "size_bytes": len(zip_bytes),
        "files_count": len(archived_files),
        "kept_snapshots": min(len(all_snapshots), MAX_SNAPSHOTS_TO_KEEP)
    }


def check_and_auto_restore_from_mongo(client: MongoClient, db_dir: str = "db") -> Tuple[bool, str, Optional[str], int]:
    """
    Startup Auto-Recovery: Checks MongoDB Atlas database_snapshots (isolated).
    If the cloud snapshot is newer than local files (e.g. VPS was deleted and PC codebase was deployed),
    it automatically extracts the SQLite databases into db/ and verifies integrity with PRAGMA integrity_check.
    
    Returns: (restored: bool, message: str, timestamp_ist: Optional[str], files_count: int)
    """
    try:
        db = client[MONGO_DATABASE_NAME]
        coll = db["database_snapshots"]

        latest_snap = coll.find_one({"is_latest": True})
        if not latest_snap:
            latest_snap = coll.find_one(sort=[("timestamp_unix", DESCENDING)])

        if not latest_snap or "payload" not in latest_snap:
            return False, "No cloud snapshots found in MongoDB Atlas", None, 0

        cloud_ts = latest_snap.get("timestamp_unix", 0.0)
        timestamp_ist = latest_snap.get("timestamp_ist", "Unknown IST")
        snapshot_id = latest_snap.get("snapshot_id", "Unknown ID")

        local_ts = get_local_db_latest_mtime(db_dir)

        # Inspect cloud snapshot payload to verify all expected databases are present locally
        zip_bytes = bytes(latest_snap["payload"])
        buf = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            cloud_db_files = [m.filename for m in zf.infolist() if m.filename.endswith(".db") or m.filename == "local_settings.json"]

        missing_or_empty = []
        if os.path.exists(db_dir):
            for cf in cloud_db_files:
                fp = os.path.join(db_dir, cf)
                if not os.path.exists(fp) or os.path.getsize(fp) == 0:
                    missing_or_empty.append(cf)
        else:
            missing_or_empty = cloud_db_files

        local_incomplete = len(missing_or_empty) > 0
        local_db_exists = os.path.exists(db_dir) and any(f.endswith(".db") for f in os.listdir(db_dir))
        is_cloud_newer = (cloud_ts - local_ts) > 5.0  # 5-second buffer to ignore clock jitter
        
        local_corrupted = False
        if local_db_exists and not local_incomplete:
            ok, corruption_errs = verify_db_integrity(db_dir)
            if not ok:
                local_corrupted = True
                print(f"[MONGODB AUTO-RESTORE] Corrupted local database detected: {corruption_errs[0]}. Forcing cloud restore...")

        if not local_db_exists or is_cloud_newer or local_corrupted or local_incomplete:
            if local_incomplete:
                reason = f"incomplete ({len(missing_or_empty)} missing/empty DBs, e.g. {missing_or_empty[:3]})"
            elif not local_db_exists:
                reason = "missing"
            elif local_corrupted:
                reason = "corrupted"
            else:
                reason = "outdated"

            print(f"[MONGODB AUTO-RESTORE] Local SQLite databases are {reason}. Restoring clean snapshot {snapshot_id} ({timestamp_ist})...")
            os.makedirs(db_dir, exist_ok=True)



            zip_bytes = bytes(latest_snap["payload"])
            buf = io.BytesIO(zip_bytes)
            extracted_files = []

            with zipfile.ZipFile(buf, "r") as zf:
                for member in zf.infolist():
                    # Security check against path traversal
                    if ".." in member.filename or member.filename.startswith("/"):
                        continue
                    if member.filename.endswith(".db") or member.filename == "local_settings.json":
                        # For incomplete restores, only extract genuinely missing/empty files
                        # — never overwrite healthy databases that setup_all_dbs or cog_load just created
                        if reason == "incomplete":
                            if member.filename not in missing_or_empty:
                                continue
                        zf.extract(member, path=db_dir)
                        extracted_files.append(member.filename)

            # Checkpoint & Integrity Check
            ok, errors = verify_db_integrity(db_dir)
            if not ok:
                err_str = "; ".join(errors)
                print(f"[MONGODB AUTO-RESTORE ERROR] Database integrity check failed after restore: {err_str}")
                return False, f"Integrity check failed: {err_str}", timestamp_ist, len(extracted_files)

            # Reload settings if local_settings.json was restored
            if "local_settings.json" in extracted_files:
                try:
                    from utils.settings_manager import settings
                    settings.load()
                except Exception:
                    pass

            print(f"[MONGODB AUTO-RESTORE] Successfully restored {len(extracted_files)} files/databases from Atlas snapshot {snapshot_id} ({timestamp_ist})!")
            return True, f"Successfully restored {len(extracted_files)} databases from Atlas ({snapshot_id})", timestamp_ist, len(extracted_files)
        else:
            return False, "Local SQLite database is already up to date with cloud", timestamp_ist, 0

    except Exception as e:
        print(f"[MONGODB AUTO-RESTORE EXCEPTION] {e}")
        return False, str(e), None, 0


def restore_single_db_from_mongo(client: MongoClient, db_name: str, db_dir: str = "db") -> bool:
    """
    Surgically restores a single SQLite database file from the latest MongoDB Atlas snapshot.
    Deletes any corrupt local file, extracts the clean copy from the snapshot ZIP in memory,
    and runs PRAGMA integrity_check on the restored file.
    """
    try:
        db = client[MONGO_DATABASE_NAME]
        coll = db["database_snapshots"]
        latest_snap = coll.find_one({"is_latest": True}) or coll.find_one(sort=[("timestamp_unix", DESCENDING)])
        if not latest_snap or "payload" not in latest_snap:
            return False

        zip_bytes = bytes(latest_snap["payload"])
        buf = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            matching = [m for m in zf.infolist() if m.filename == db_name]
            if not matching:
                return False

            os.makedirs(db_dir, exist_ok=True)
            target_path = os.path.join(db_dir, db_name)
            for p in [target_path, f"{target_path}-wal", f"{target_path}-shm"]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

            zf.extract(matching[0], path=db_dir)

        conn = sqlite3.connect(target_path, timeout=5.0)
        c = conn.cursor()
        c.execute("PRAGMA integrity_check;")
        res = c.fetchone()
        conn.close()
        if res and res[0] == "ok":
            print(f"[MONGODB AUTO-RESTORE] Surgically restored clean {db_name} from Atlas cloud snapshot!")
            return True
        return False
    except Exception as e:
        print(f"[MONGODB AUTO-RESTORE ERROR] Failed to surgically restore {db_name}: {e}")
        return False


