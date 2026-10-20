from utils.config import MONGO_DATABASE_NAME
"""
YUNA Enterprise SQLite to MongoDB Incremental Upsert Synchronization Engine
Provides living-document database synchronization, anti-mismatch reconciliation,
resurrection prevention (deletion tracking), and a 90-day daily vault across dual clusters.

Architecture:
  - MongoDB #1 (Live Active Mirror): In-place document upsert without ZIP files.
  - MongoDB #2 (90-Day Daily Vault): Daily dated JSON database snapshots (00:00 IST) pruned after 90 days.
  - Local Storage: Pure SQLite on NVMe for microsecond Discord event performance.
"""

import os
import json
import time
import sqlite3
import datetime
import hashlib
import pytz
from typing import Dict, Any, List, Tuple, Optional, Set
from pymongo import MongoClient, UpdateOne, DeleteMany

try:
    import dns.resolver
    _custom_resolver = dns.resolver.Resolver()
    _custom_resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
    dns.resolver.default_resolver = _custom_resolver
except Exception:
    dns = None

IST_TZ = pytz.timezone("Asia/Kolkata")

def resolve_mongo_uri(uri: str) -> str:
    """Pre-resolves mongodb+srv:// to direct replica seeds using Google/Cloudflare DNS with hardcoded cluster fallbacks."""
    if not uri or not uri.startswith("mongodb+srv://"):
        return uri

    # Known static cluster fallbacks if local/ISP DNS fails to resolve SRV
    if "yuna.d8nigbi.mongodb.net" in uri:
        clean = uri.replace("mongodb+srv://", "").replace(":27017", "")
        auth = clean.split("@")[0] + "@" if "@" in clean else ""
        return f"mongodb://{auth}ac-m0gzey1-shard-00-00.d8nigbi.mongodb.net:27017,ac-m0gzey1-shard-00-01.d8nigbi.mongodb.net:27017,ac-m0gzey1-shard-00-02.d8nigbi.mongodb.net:27017/?replicaSet=atlas-drpsj2-shard-0&tls=true&authSource=admin"
    if "yuna1daybackup.t1jgakp.mongodb.net" in uri:
        clean = uri.replace("mongodb+srv://", "").replace(":27017", "")
        auth = clean.split("@")[0] + "@" if "@" in clean else ""
        return f"mongodb://{auth}ac-tqjlxku-shard-00-00.t1jgakp.mongodb.net:27017,ac-tqjlxku-shard-00-01.t1jgakp.mongodb.net:27017,ac-tqjlxku-shard-00-02.t1jgakp.mongodb.net:27017/?replicaSet=atlas-twb5km-shard-0&tls=true&authSource=admin"
    if "yuna.nwacylb.mongodb.net" in uri:
        clean = uri.replace("mongodb+srv://", "").replace(":27017", "")
        auth = clean.split("@")[0] + "@" if "@" in clean else ""
        return f"mongodb://{auth}ac-vwhxdgn-shard-00-00.nwacylb.mongodb.net:27017,ac-vwhxdgn-shard-00-01.nwacylb.mongodb.net:27017,ac-vwhxdgn-shard-00-02.nwacylb.mongodb.net:27017/?replicaSet=atlas-7zclb3-shard-0&tls=true&authSource=admin"
    if "german.fghthcf.mongodb.net" in uri:
        clean = uri.replace("mongodb+srv://", "").replace(":27017", "")
        auth = clean.split("@")[0] + "@" if "@" in clean else ""
        return f"mongodb://{auth}ac-a4bwhsu-shard-00-00.fghthcf.mongodb.net:27017,ac-a4bwhsu-shard-00-01.fghthcf.mongodb.net:27017,ac-a4bwhsu-shard-00-02.fghthcf.mongodb.net:27017/?replicaSet=atlas-phi3yx-shard-0&tls=true&authSource=admin"
    if "yunamusic.yaawmir.mongodb.net" in uri:
        clean = uri.replace("mongodb+srv://", "").replace(":27017", "")
        auth = clean.split("@")[0] + "@" if "@" in clean else ""
        return f"mongodb://{auth}ac-h4lmbbc-shard-00-00.yaawmir.mongodb.net:27017,ac-h4lmbbc-shard-00-01.yaawmir.mongodb.net:27017,ac-h4lmbbc-shard-00-02.yaawmir.mongodb.net:27017/yunamusic?replicaSet=atlas-nb0nm4-shard-0&tls=true&authSource=admin"

    if not dns:
        return uri
    try:
        clean = uri.replace("mongodb+srv://", "").replace(":27017", "")
        parts = clean.split("/")
        user_auth_host = parts[0]
        rest = "/".join(parts[1:]) if len(parts) > 1 else ""
        if "@" in user_auth_host:
            auth, host_part = user_auth_host.split("@", 1)
            auth_prefix = f"{auth}@"
        else:
            auth_prefix = ""
            host_part = user_auth_host

        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
        resolver.timeout = 4.0
        resolver.lifetime = 8.0
        answers = resolver.resolve(f"_mongodb._tcp.{host_part}", "SRV")
        seeds = [f"{r.target.to_text().strip('.')}:{r.port}" for r in answers]
        if seeds:
            extra = ["tls=true"]
            try:
                txt_ans = resolver.resolve(host_part, "TXT")
                for txt in txt_ans:
                    txt_str = "".join([b.decode("utf-8") if isinstance(b, bytes) else str(b) for b in txt.strings])
                    if "replicaSet=" in txt_str or "authSource=" in txt_str:
                        extra.append(txt_str)
            except Exception:
                pass
            seeds_str = ",".join(seeds)
            delim = "&" if "?" in rest else "?"
            return f"mongodb://{auth_prefix}{seeds_str}/{rest}{delim}{'&'.join(extra)}"
    except Exception as e:
        print(f"[MONGO DNS RESOLVER WARNING] {e}")
    return uri


import logging
logging.getLogger("pymongo").setLevel(logging.CRITICAL)

_MONGO_CLIENT_POOL: Dict[str, MongoClient] = {}

def create_resilient_mongo_client(uri: Optional[str], timeout_ms: int = 20000) -> Optional[MongoClient]:
    """Creates or reuses a cached MongoClient with pre-resolved DNS seeds and optimal connection pooling."""
    if not uri:
        return None
    resolved_uri = resolve_mongo_uri(uri)
    if resolved_uri in _MONGO_CLIENT_POOL:
        return _MONGO_CLIENT_POOL[resolved_uri]
    try:
        client = MongoClient(
            resolved_uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=45000,
            maxPoolSize=25,
            minPoolSize=0,
            maxIdleTimeMS=120000,
            retryWrites=True
        )
        client.admin.command("ping")
        _MONGO_CLIENT_POOL[resolved_uri] = client
        return client
    except Exception as e:
        print(f"[MONGO CLIENT WARNING] Failed to connect: {e}")
        return None


# Tables that are purely internal to SQLite or ephemeral logs that should not be synced to cloud
BYPASSED_TABLES = {"sqlite_stat1", "sqlite_sequence", "sqlite_master", "audit_logs"}
BYPASSED_DATABASES = {"error_logs.db", "test_playlists.db", "test_concurrency.db"}

# ==============================================================================
# TIERED LOG RETENTION POLICIES (User Strategy)
# ==============================================================================
# 1. Anti-nuke & security incidents: 90–180 days (retain detailed evidence)
# 2. Ban, kick, role/channel changes: 30–90 days (compact event records)
# 3. Automod, spam, invite violations: 14–30 days (retain essential details)
# 4. Routine joins, leaves, message edits: 7–14 days (expire quickly)
# 5. Debug and repeated operational logs: 1–3 days (bypass or expire fast)
# 6. Daily event counts and statistics: Long-term / aggregate summaries
RETENTION_POLICY_DAYS: Dict[str, int] = {
    # 90-180 days: Anti-nuke and security incidents
    "antinuke": 120,
    "bot_incidents": 90,
    "bot_kick_history": 90,

    # 30-90 days: Moderation actions, warns, and profile audit logs
    "warns": 60,
    "profile_audit_logs": 60,

    # 14-30 days: Automod incidents and invite violations
    "automod_incidents": 21,
    "automod_blacklist": 21,

    # 7-14 days: High-volume routine logs (audit_logs, guild_events, raw stats)
    "audit_logs": 14,
    "guild_events": 14,
    "stats": 14,
    "interactions": 30,
    "autoplay_played_history": 30,
    "bot_error_logs": 3,
}

# Maximum active live document caps in Cluster #1 to guarantee staying well under 512 MB:
BLOAT_DEFENDER_CAPS: Dict[str, int] = {
    # Security incidents (retained with higher count limit)
    "bot_incidents": 2000,
    "bot_kick_history": 2000,
    "automod_incidents": 1500,

    # Routine event logs (compact live window)
    "audit_logs": 2500,
    "guild_events": 1000,
    "stats": 1000,
    "interactions": 1000,
    "autoplay_played_history": 1000,
    "profile_audit_logs": 1000,
}

DEFAULT_MAX_TABLE_SYNC_ROWS = 2000

# Tables that must NEVER be purged from cloud during resurrection prevention
NEVER_PURGE_TABLES: Set[str] = {
    "notif_youtube_posted",
    "notif_instagram_posted",
    "notif_game_alert_posted",
    "autoplay_played_history",
    "joined_members"
}

# Cache of table signatures {f"{db_name}:{table_name}": signature_hash}
_TABLE_CHECKSUM_CACHE: Dict[str, str] = {}
# Cache of per-row content hashes {cache_key: {doc_id: sha1_hex}} so only changed rows are upserted
_ROW_HASH_CACHE: Dict[str, Dict[str, str]] = {}
_ENSURED_INDEX_COLLECTIONS: Set[str] = set()


def get_current_time_ist() -> Tuple[float, str]:
    """Returns (unix_timestamp, formatted_ist_string)."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_ist = now_utc.astimezone(IST_TZ)
    timestamp_ist = now_ist.strftime("%d-%m-%Y %I:%M:%S %p IST")
    return now_utc.timestamp(), timestamp_ist


def checkpoint_all_dbs(db_dir: str = "db") -> int:
    """Executes PRAGMA wal_checkpoint(PASSIVE) so uncommitted WAL frames are readable."""
    if not os.path.exists(db_dir):
        return 0
    count = 0
    for filename in os.listdir(db_dir):
        if filename.endswith(".db"):
            db_path = os.path.join(db_dir, filename)
            try:
                conn = sqlite3.connect(db_path, timeout=30.0)
                conn.execute("PRAGMA busy_timeout = 30000;")
                conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                conn.close()
                count += 1
            except Exception:
                pass
    return count


def get_table_metadata(conn: sqlite3.Connection, table_name: str) -> Tuple[List[str], List[str], Dict[str, str]]:
    """
    Inspects SQLite table columns and primary keys.
    Returns: (all_columns, primary_key_columns, column_types)
    """
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table_name}");')
    rows = cursor.fetchall()
    cursor.close()

    all_cols = []
    pk_cols_with_pos = []
    col_types = {}

    for row in rows:
        cid, name, col_type, notnull, dflt_value, pk = row
        all_cols.append(name)
        col_types[name] = col_type.upper() if col_type else "TEXT"
        if pk > 0:
            pk_cols_with_pos.append((pk, name))

    pk_cols_with_pos.sort(key=lambda x: x[0])
    pk_cols = [p[1] for p in pk_cols_with_pos]

    return all_cols, pk_cols, col_types


def compute_table_signature(conn: sqlite3.Connection, table_name: str) -> str:
    """Computes a fast signature (row count + max rowid) to detect changes in <1ms."""
    try:
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*), COALESCE(MAX(rowid), 0) FROM "{table_name}";')
        row = cursor.fetchone()
        cursor.close()
        count, max_id = row if row else (0, 0)
        return f"{count}_{max_id}"
    except Exception:
        return ""


def get_deterministic_doc_id(row_dict: Dict[str, Any], pk_cols: List[str], fallback_id: Any) -> str:
    """Generates a deterministic string _id for MongoDB preserving Discord Snowflakes."""
    if pk_cols:
        parts = []
        for pk in pk_cols:
            val = row_dict.get(pk)
            parts.append(str(val) if val is not None else "")
        return "_".join(parts)
    # If table has no explicit primary key, create deterministic composite hash from content
    clean_parts = [f"{k}:{v}" for k, v in sorted(row_dict.items()) if not k.startswith("_")]
    content = "|".join(clean_parts)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]


def sanitize_value_for_mongo(val: Any) -> Any:
    """Ensures Discord 64-bit integer IDs and data types serialize cleanly into MongoDB BSON."""
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8")
        except Exception:
            import bson
            return bson.Binary(val)
    return val


# ==============================================================================
# 1. LIVE INCREMENTAL UPSERT SYNC (SQLite -> MongoDB #1)
# ==============================================================================

def sync_sqlite_to_mongo(mongo_client: MongoClient, db_dir: str = "db") -> Dict[str, Any]:
    """
    Performs in-place differential upsert synchronization of all SQLite tables to MongoDB #1.
    - Uses SHA-256 table checksums to skip unchanged tables in <1ms.
    - Applies Bloat Defender capping on high-volume audit logs.
    - Synchronizes deletions to prevent resurrection of deleted data.
    """
    if not os.path.exists(db_dir) or mongo_client is None:
        return {"synced": False, "reason": "db directory or mongo_client missing"}

    checkpoint_all_dbs(db_dir)
    target_db = mongo_client[MONGO_DATABASE_NAME]
    meta_coll = target_db["_sync_metadata"]

    # Connect to dedicated music cluster if configured
    music_target_db = None
    reconcile_count = 0

    for current_target_db in target_dbs:
        collections = current_target_db.list_collection_names()
        for coll_name in collections:
            if coll_name.startswith("_") or coll_name in ("database_snapshots", "user_history", "guild_history", "liked_songs", "song_catalog", "playlists"):
                continue

            coll = current_target_db[coll_name]
            sample_doc = coll.find_one({"_table_meta": {"$exists": True}})
            if not sample_doc or "_table_meta" not in sample_doc:
                continue

        meta = sample_doc["_table_meta"]
        filename = meta.get("db_file")
        table_name = meta.get("table_name")
        pk_cols = meta.get("pk_cols", [])
        col_types = meta.get("col_types", {})

        if not filename or not table_name:
            continue

        db_path = os.path.join(db_dir, filename)

        try:
            conn = sqlite3.connect(db_path, timeout=60.0)
            conn.execute("PRAGMA busy_timeout = 60000;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            cursor = conn.cursor()

            # Ensure table exists in local SQLite
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                # Recreate table structure from schema metadata
                cols_def = []
                for c_name, c_type in col_types.items():
                    cols_def.append(f'"{c_name}" {c_type}')
                if pk_cols:
                    pk_clause = f', PRIMARY KEY ({", ".join(f"{pk}" for pk in pk_cols)})'
                elif all_cols:
                    pk_clause = f', UNIQUE ({", ".join(f"{c}" for c in all_cols)})'
                else:
                    pk_clause = ""
                create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(cols_def)}{pk_clause});'
                cursor.execute(create_sql)
                conn.commit()

            # Read local records into memory for fast diff
            all_cols, pk_cols, _ = get_table_metadata(conn, table_name)
            if not all_cols:
                cursor.close()
                conn.close()
                continue

            cursor.execute(f'PRAGMA index_list("{table_name}");')
            indexes = cursor.fetchall()
            has_unique_or_pk = bool(pk_cols) or any(idx[2] == 1 for idx in indexes)

            # Clean any existing duplicates only on unconstrained tables lacking PK/unique indexes
            group_cols = ", ".join(f'"{c}"' for c in (pk_cols if pk_cols else all_cols))
            if not has_unique_or_pk and group_cols and table_name not in BLOAT_DEFENDER_CAPS:
                try:
                    del_cur = cursor.execute(
                        f'DELETE FROM "{table_name}" WHERE rowid NOT IN (SELECT MAX(rowid) FROM "{table_name}" GROUP BY {group_cols});'
                    )
                    if del_cur.rowcount > 0:
                        conn.commit()
                        print(f"[RECONCILE DEFENDER] Cleaned {del_cur.rowcount} duplicate rows in local {filename} -> {table_name}")
                except Exception:
                    pass

            # If the table still lacks a PK/unique constraint, dynamically create a UNIQUE index across all columns
            if not has_unique_or_pk and all_cols:
                try:
                    idx_cols = ", ".join(f'"{c}"' for c in all_cols)
                    cursor.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS "idx_auto_unique_{table_name}" ON "{table_name}" ({idx_cols});')
                    conn.commit()
                except Exception:
                    pass

            cursor.execute(f'SELECT * FROM "{table_name}";')
            local_rows = cursor.fetchall()
            local_map = {}
            for r in local_rows:
                r_dict = {all_cols[idx]: r[idx] for idx in range(len(all_cols))}
                pk_val = get_deterministic_doc_id(r_dict, pk_cols, r[0] if r else "")
                local_map[pk_val] = r_dict

            # Compare against cloud documents via streaming cursor (zero memory bloat)
            rows_to_insert = []
            seen_reconcile_keys: Set[str] = set()

            for doc in coll.find(batch_size=500):
                doc_id = str(doc.get("_id"))
                clean_row = {}
                is_mismatch = False

                for col in all_cols:
                    if col in doc:
                        val = doc[col]
                        clean_row[col] = val
                    else:
                        clean_row[col] = None

                if doc_id not in local_map:
                    is_mismatch = True
                else:
                    # Check for value divergence
                    local_r = local_map[doc_id]
                    for col in all_cols:
                        if str(clean_row.get(col)) != str(local_r.get(col)):
                            is_mismatch = True
                            break

                if is_mismatch:
                    dedup_key = get_deterministic_doc_id(clean_row, pk_cols, doc_id)
                    if dedup_key not in seen_reconcile_keys:
                        seen_reconcile_keys.add(dedup_key)
                        rows_to_insert.append(clean_row)

            # Apply reconciliation
            if rows_to_insert:
                col_names = [f'"{c}"' for c in all_cols]
                placeholders = [":" + c for c in all_cols]
                sql = f'INSERT OR REPLACE INTO "{table_name}" ({", ".join(col_names)}) VALUES ({", ".join(placeholders)});'
                try:
                    cursor.executemany(sql, rows_to_insert)
                    conn.commit()
                    reconcile_count += len(rows_to_insert)
                    print(f"[RECONCILE] Updated {len(rows_to_insert)} records in {filename} -> {table_name} from cloud.")
                except Exception as ex:
                    conn.rollback()
                    print(f"[RECONCILE ROLLBACK] Failed to reconcile {table_name}: {ex}. Rolled back safely.")

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"[RECONCILE ERROR] {coll_name}: {e}")

    _, now_ist = get_current_time_ist()
    return True, f"Reconciliation complete. Updated {reconcile_count} records to match cloud authority ({now_ist}).", reconcile_count


# ==============================================================================
# 3. 90-DAY DAILY ARCHIVE VAULT (MongoDB #2)
# ==============================================================================

def sync_daily_vault(mongo_client_2: MongoClient, mongo_client_1: MongoClient, retention_days: int = 90) -> Dict[str, Any]:
    """
    Runs daily at 00:00 IST (Midnight).
    Copies all active collections from MongoDB #1 into MongoDB #2 under dated namespace:
    e.g. 'yuna_backup_YYYY_MM_DD'.
    Auto-prunes any daily backup databases older than retention_days (90 days).
    Uses 100% pure JSON documents (ZERO ZIP files).
    """
    if mongo_client_2 is None or mongo_client_1 is None:
        return {"success": False, "reason": "One or both MongoDB clients missing"}

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_ist = now_utc.astimezone(IST_TZ)
    date_tag = now_ist.strftime("%Y_%m_%d")
    timestamp_ist = now_ist.strftime("%d-%m-%Y %I:%M:%S %p IST")

    target_dbname = f"yuna_backup_{date_tag}"
    source_db = mongo_client_1[MONGO_DATABASE_NAME]
    target_db = mongo_client_2[target_dbname]

    copied_collections = 0
    total_docs_copied = 0

    for coll_name in source_db.list_collection_names():
        if coll_name.startswith("_") or coll_name == "database_snapshots":
            continue

        source_coll = source_db[coll_name]
        docs = list(source_coll.find())
        if not docs:
            continue

        target_coll = target_db[coll_name]
        target_coll.delete_many({})
        target_coll.insert_many(docs, ordered=False)
        total_docs_copied += len(docs)
        copied_collections += 1

    # Record metadata inside the daily archive
    meta_coll = target_db["_archive_meta"]
    meta_coll.insert_one({
        "backup_date": date_tag,
        "timestamp_ist": timestamp_ist,
        "timestamp_unix": now_utc.timestamp(),
        "copied_collections": copied_collections,
        "total_documents": total_docs_copied,
        "retention_days": retention_days
    })

    # ================= 90-DAY AUTO-PRUNE =================
    pruned_count = 0
    all_dbs = mongo_client_2.list_database_names()
    cutoff_date = now_ist.date() - datetime.timedelta(days=retention_days)

    for db_name in all_dbs:
        if db_name.startswith("yuna_backup_"):
            try:
                date_part = db_name.replace("yuna_backup_", "")
                db_date = datetime.datetime.strptime(date_part, "%Y_%m_%d").date()
                if db_date < cutoff_date:
                    mongo_client_2.drop_database(db_name)
                    pruned_count += 1
                    print(f"[DAILY VAULT PRUNED] Dropped expired 90-day archive: {db_name}")
            except Exception:
                pass

    print(f"[DAILY VAULT] Successfully created {target_dbname} ({total_docs_copied} docs across {copied_collections} collections). Pruned {pruned_count} old archives.")
    return {
        "success": True,
        "database_name": target_dbname,
        "timestamp_ist": timestamp_ist,
        "copied_collections": copied_collections,
        "total_documents": total_docs_copied,
        "pruned_archives": pruned_count
    }


def list_daily_vault_archives(mongo_client_2: MongoClient) -> List[Dict[str, Any]]:
    """Lists all available daily vault databases in MongoDB #2 sorted newest first."""
    if mongo_client_2 is None:
        return []

    archives = []
    for db_name in mongo_client_2.list_database_names():
        if db_name.startswith("yuna_backup_"):
            try:
                date_part = db_name.replace("yuna_backup_", "")
                db = mongo_client_2[db_name]
                meta = db["_archive_meta"].find_one() or {}
                colls = [c for c in db.list_collection_names() if not c.startswith("_")]
                doc_count = meta.get("total_documents", sum(db[c].count_documents({}) for c in colls))
                archives.append({
                    "database_name": db_name,
                    "date": date_part.replace("_", "-"),
                    "timestamp_ist": meta.get("timestamp_ist", "N/A"),
                    "collections_count": len(colls),
                    "documents_count": doc_count
                })
            except Exception:
                pass

    archives.sort(key=lambda x: x["date"], reverse=True)
    return archives


# ==============================================================================
# 4. CLUSTER HEALTH & METRICS
# ==============================================================================

def get_cluster_metrics(mongo_client_1: Optional[MongoClient], mongo_client_2: Optional[MongoClient]) -> Dict[str, Any]:
    """Returns live connection health, collections count, and document counts for both clusters."""
    metrics = {
        "db1": {"status": "Offline", "ping_ms": 0, "collections": 0, "documents": 0, "last_sync": "Never"},
        "db2": {"status": "Offline", "ping_ms": 0, "vault_archives": 0, "latest_archive": "None"}
    }

    if mongo_client_1:
        try:
            t0 = time.perf_counter()
            mongo_client_1.admin.command("ping")
            p_ms = (time.perf_counter() - t0) * 1000
            db1 = mongo_client_1[MONGO_DATABASE_NAME]
            colls = [c for c in db1.list_collection_names() if not c.startswith("_")]
            doc_sum = sum(db1[c].count_documents({}) for c in colls[:15])  # Sample top collections
            meta = db1["_sync_metadata"].find_one({"_id": "live_sync_status"}) or {}

            metrics["db1"] = {
                "status": "Online (Active Replica)",
                "ping_ms": round(p_ms, 1),
                "collections": len(colls),
                "documents": doc_sum,
                "last_sync": meta.get("last_sync_ist", "Active")
            }
        except Exception as e:
            metrics["db1"]["status"] = f"Error: {e}"

    if mongo_client_2:
        try:
            t0 = time.perf_counter()
            mongo_client_2.admin.command("ping")
            p_ms = (time.perf_counter() - t0) * 1000
            vaults = list_daily_vault_archives(mongo_client_2)

            metrics["db2"] = {
                "status": "Online (90D Daily Vault)",
                "ping_ms": round(p_ms, 1),
                "vault_archives": len(vaults),
                "latest_archive": vaults[0]["date"] if vaults else "None"
            }
        except Exception as e:
            metrics["db2"]["status"] = f"Error: {e}"

    return metrics
