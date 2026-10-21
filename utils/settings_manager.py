import os
import json
import asyncio
import shutil
import threading
import atexit
import time
import uuid
from typing import Any, Dict, Optional
from utils.config import DEFAULT_PREFIX, MONGO_DATABASE_NAME

LOCAL_SETTINGS_PATH = os.path.join("db", "local_settings.json")
BACKUP_SETTINGS_PATH = os.path.join("db", "local_settings.json.bak")

DEFAULT_GUILD_SETTINGS = {
    "prefix": DEFAULT_PREFIX,
    "vc_247": None,            # {"channel_id": int, "text_channel_id": int}
    "autoplay": False,
    "autoplay_lang": "auto",
    "autoplay_mood": "auto",
    "volume": 0.15,
    "loop": "off",
    "antinuke": False,
    "bot_protection": False,
    "botprotection": False,
    "extraowner": None,
    "nightmode": False,
    "nightmode_auto": False,
    "nightmode_manual": False,
    "antinuke_actions": [],
    "exempt_roles": [],
    "log_channel": None,
    "language": "en",
    "timezone": "UTC",
    "manager_roles": [],
    "dm_notifications": True,
    "leveling_enabled": False,
    "leveling_xp_multiplier": 1.0,
    "leveling_role_rewards": {},
    "welcome_channel": None,
    "welcome_message": None,
    "welcome_embed": True,
    "welcome_ping": False,
    "custom_commands": [],
    "server_logs_webhook": None,
    "server_logs_webhook_enabled": False,
    "server_logs_retention": 30,
    "whitelist": [],
    "whitelist_roles": [],
    "automod": False,
    "topcheck": False,
    "welcome": None,
    "custom_role": None,
    "invitetracker": None,
    "tempvc_creators": [],
    "tempvc_interface_channel_id": "",
    "tempvc_category_id": "",
    "tempvc_hub_channel_id": "",
    "tempvc_position": "top",
    "tempvc_access_roles": [],
    "tempvc_moderation_log_webhook": None,
    "tempvc_recover_owner_settings": True,
    "tempvc_sync_permissions": True,
    "tempvc_owner_permissions": [],
    "tempvc_language": "en",
    "tempvc_age_restriction": False,
    "tempvc_blocked_words": [],
    "tempvc_replacement_char": "*",
    "tempvc_name_template": "{user}'s Lounge",
    "tempvc_privacy_mode": "Public",
    "tempvc_user_limit": 0,
    "tempvc_bitrate": "64kbps",
    "tempvc_censor_channel_names": False,
    "tempvc_allowed_features": [
        "name", "limit", "privacy", "waitingroom", "chat",
        "trust", "untrust", "invite", "kick", "region",
        "block", "unblock", "claim", "transfer", "delete"
    ],
    "active_temp_vcs": {},
}

DEFAULT_BOT_SETTINGS = {
    "default_prefix": DEFAULT_PREFIX,
    "embed_color": 0x9B59B6,
    "maintenance_mode": False,
    "max_queue_size": 250,
    "auto_gc_interval_hours": 12,
    "dynamic_vc_status": True,
    "bot_avatar_url": None,
    "bot_banner_url": None,
    "bot_status_text": None,
    "bot_status_type": "playing",
    "bot_server_nick": None,
}


class SettingsManager:
    """Ultra-fast, thread-safe, crash-proof local settings store and DB fallback cache."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SettingsManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.file_path = LOCAL_SETTINGS_PATH
        self.backup_path = BACKUP_SETTINGS_PATH
        self._data: Dict[str, Any] = {
            "bot": DEFAULT_BOT_SETTINGS.copy(),
            "guilds": {}
        }
        self._dirty_guilds: set[str] = set()
        self._dirty = False
        self._save_lock = threading.RLock()
        self._async_flush_task = None
        self.mongo_client = None
        self.mongo_collection = None
        self._watcher_thread = None
        self._sync_thread = None
        self._initialized = True
        self.load_from_disk()
        self._start_periodic_sync(interval_seconds=5)
        atexit.register(self.save_immediate)

    def _init_mongo(self):
        try:
            from dotenv import load_dotenv
            load_dotenv()
            if os.getenv("DISABLE_MONGODB", "").strip().lower() in ("1", "true", "yes", "on"):
                self.mongo_client = None
                self.mongo_collection = None
                return

            mongo_uri = os.getenv("MONGODB_URI")
            if mongo_uri:
                # Pre-resolve SRV URIs once to direct seed list to eliminate runtime DNS SRV resolution
                if mongo_uri.startswith("mongodb+srv://"):
                    mongo_uri = mongo_uri.replace(":27017", "")
                    try:
                        import dns.resolver
                        parts = mongo_uri.replace("mongodb+srv://", "").split("/")
                        user_auth_host = parts[0]
                        rest = "/".join(parts[1:]) if len(parts) > 1 else ""

                        if "@" in user_auth_host:
                            auth, host_part = user_auth_host.split("@", 1)
                            auth_prefix = f"{auth}@"
                        else:
                            auth_prefix = ""
                            host_part = user_auth_host

                        srv_name = f"_mongodb._tcp.{host_part}"
                        answers = dns.resolver.resolve(srv_name, 'SRV')
                        seeds = [f"{r.target.to_text().strip('.')}:{r.port}" for r in answers]

                        if seeds:
                            extra_params = ["tls=true"]
                            try:
                                txt_answers = dns.resolver.resolve(host_part, 'TXT')
                                for txt in txt_answers:
                                    txt_str = "".join([b.decode('utf-8') if isinstance(b, bytes) else str(b) for b in txt.strings])
                                    if "replicaSet=" in txt_str or "authSource=" in txt_str:
                                        extra_params.append(txt_str)
                            except Exception:
                                pass

                            seeds_str = ",".join(seeds)
                            param_delim = "&" if "?" in rest else "?"
                            mongo_uri = f"mongodb://{auth_prefix}{seeds_str}/{rest}{param_delim}{'&'.join(extra_params)}"
                    except Exception as res_err:
                        print(f"[SETTINGS MONGO DNS RESOLVE WARNING] {res_err}")

                from pymongo import MongoClient
                self.mongo_client = MongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=20000,
                    connectTimeoutMS=20000,
                    socketTimeoutMS=30000,
                    maxPoolSize=25,
                    minPoolSize=0,
                    maxIdleTimeMS=120000,
                    retryWrites=True,
                    connect=True
                )
                self.mongo_client.admin.command('ping')
                self.mongo_collection = self.mongo_client[MONGO_DATABASE_NAME]["guild_settings"]
        except Exception as e:
            self.mongo_client = None
            self.mongo_collection = None
            print(f"[SETTINGS MONGO INIT WARNING] {e}")

    def _start_mongo_watcher(self):
        """Starts a resilient background daemon thread to listen for live MongoDB updates."""
        if self.mongo_collection is None:
            return
        if self._watcher_thread is not None and self._watcher_thread.is_alive():
            return

        def _watch_loop():
            while True:
                try:
                    if self.mongo_collection is None:
                        time.sleep(10)
                        continue
                    # MongoDB Change Streams listen for real-time insert/update/replace operations
                    with self.mongo_collection.watch(full_document='updateLookup') as stream:
                        for change in stream:
                            op_type = change.get("operationType")
                            if op_type in ("insert", "update", "replace"):
                                full_doc = change.get("fullDocument")
                                if full_doc:
                                    gid = str(full_doc.get("guild_id", ""))
                                    if gid:
                                        with self._save_lock:
                                            if gid not in self._data["guilds"]:
                                                self._data["guilds"][gid] = DEFAULT_GUILD_SETTINGS.copy()
                                            for k, v in full_doc.items():
                                                if k not in ("_id", "guild_id"):
                                                    self._data["guilds"][gid][k] = v
                                            self._save_to_disk_sync()
                            elif op_type == "delete":
                                doc_key = change.get("documentKey", {})
                                gid = str(doc_key.get("guild_id", ""))
                                if gid and gid in self._data["guilds"]:
                                    with self._save_lock:
                                        del self._data["guilds"][gid]
                                        self._save_to_disk_sync()
                except Exception:
                    # Retry delay if network drops or standalone mongo doesn't support replica change streams
                    time.sleep(15)

        self._watcher_thread = threading.Thread(target=_watch_loop, daemon=True, name="MongoCacheWatcher")
        self._watcher_thread.start()

    def _start_periodic_sync(self, interval_seconds: int = 5):
        """Starts a background daemon thread that connects to MongoDB, syncs cache, and auto-reconnects non-blockingly."""
        if self._sync_thread is not None and self._sync_thread.is_alive():
            return

        def _periodic_loop():
            # 0. Initial background connection and initial sync (zero import latency)
            try:
                self._init_mongo()
                if self.mongo_collection is not None:
                    self.load_from_mongo()
                    self._start_mongo_watcher()
            except Exception as e:
                print(f"[SETTINGS BG INIT WARNING] {e}")

            tick_count = 0
            while True:
                time.sleep(interval_seconds)
                tick_count += 1
                try:
                    # 1. Auto-reconnect if MongoDB connection was lost
                    if self.mongo_collection is None and tick_count % 10 == 0:
                        self._init_mongo()
                        if self.mongo_collection is not None:
                            self._start_mongo_watcher()

                    # 2. Flush dirty cache to DB/disk immediately if modified
                    if self._dirty or self._dirty_guilds:
                        with self._save_lock:
                            to_save = list(self._dirty_guilds) if self._dirty_guilds else list(self._data["guilds"].keys())
                            self._dirty_guilds.clear()
                            self._dirty = False
                            self._save_guilds_sync(to_save)

                    # 3. Pull latest updates from MongoDB periodically (every 5 seconds) if active
                    if self.mongo_collection is not None and tick_count % 5 == 0:
                        self.load_from_mongo()
                except Exception as e:
                    print(f"[SETTINGS AUTO-SYNC WARNING] {e}")

        self._sync_thread = threading.Thread(target=_periodic_loop, daemon=True, name="MongoAutoSyncThread")
        self._sync_thread.start()

    def refresh_guild_from_mongo(self, guild_id: int | str) -> bool:
        """Forces an instant reload of a specific guild document from MongoDB into local VPS RAM cache."""
        if self.mongo_collection is None:
            return False
        try:
            gid = str(guild_id)
            doc = self.mongo_collection.find_one({"guild_id": gid})
            if doc:
                with self._save_lock:
                    if gid not in self._data["guilds"]:
                        self._data["guilds"][gid] = DEFAULT_GUILD_SETTINGS.copy()
                    for k, v in doc.items():
                        if k not in ("_id", "guild_id"):
                            self._data["guilds"][gid][k] = v
                    self._save_to_disk_sync()
                return True
        except Exception as e:
            print(f"[SETTINGS REFRESH GUILD ERROR] {e}")
        return False

    def refresh_all_from_mongo(self) -> int:
        """Forces a full reload of all documents from MongoDB Atlas into local VPS RAM cache."""
        self.load_from_mongo()
        return len(self._data["guilds"])

    def load_from_disk(self):
        """Loads settings from local JSON file into fast in-memory cache (<1ms)."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self._data["bot"] = {**DEFAULT_BOT_SETTINGS, **loaded.get("bot", {})}
                        self._data["guilds"] = loaded.get("guilds", {})
            except Exception as e:
                print(f"[SETTINGS WARNING] Error reading {self.file_path}: {e}")

    def load(self):
        """Loads settings from local JSON file and MongoDB Atlas into fast in-memory cache."""
        self.load_from_disk()
        self.load_from_mongo()

    def load_from_mongo(self):
        """Fetches all guild settings documents directly from MongoDB Atlas into fast in-memory VPS cache."""
        if self.mongo_collection is None:
            return
        try:
            for doc in self.mongo_collection.find():
                gid = str(doc.get("guild_id", ""))
                if gid:
                    with self._save_lock:
                        if gid not in self._data["guilds"]:
                            self._data["guilds"][gid] = DEFAULT_GUILD_SETTINGS.copy()
                        # Merge Mongo values without racing a disk snapshot.
                        for k, v in doc.items():
                            if k not in ("_id", "guild_id"):
                                self._data["guilds"][gid][k] = v
        except Exception as e:
            print(f"[SETTINGS MONGO LOAD WARNING] {e}")

    def _save_to_disk_sync(self):
        """Atomically write the local cache, tolerating brief Windows file locks."""
        temp_path = None
        try:
            # RLock serializes threads in this process; unique temp names also
            # prevent two bot processes from overwriting each other's staging file.
            with self._save_lock:
                parent = os.path.dirname(self.file_path)
                os.makedirs(parent, exist_ok=True)
                temp_path = f"{self.file_path}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                if os.path.exists(self.file_path):
                    try:
                        shutil.copy2(self.file_path, self.backup_path)
                    except OSError as backup_error:
                        # A backup lock should not block committing the current settings.
                        print(f"[SETTINGS BACKUP WARNING] {backup_error}")

                last_error = None
                for attempt in range(6):
                    try:
                        os.replace(temp_path, self.file_path)
                        return True
                    except PermissionError as exc:
                        last_error = exc
                        if attempt < 5:
                            time.sleep(0.05 * (2 ** attempt))
                raise last_error
        except Exception as e:
            print(f"[SETTINGS DISK SAVE WARNING] {e}")
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _save_guilds_sync(self, guild_ids: list[str]):
        """Upserts guild documents into MongoDB Atlas in a single fast bulk operation and updates local disk cache."""
        if not guild_ids:
            return
        try:
            with self._save_lock:
                # 1. Update local disk cache immediately
                if not self._save_to_disk_sync():
                    raise OSError("local settings disk save failed")

                # 2. Bulk upsert to MongoDB Atlas
                if self.mongo_collection is not None:
                    from pymongo import UpdateOne
                    operations = []
                    for gid in guild_ids:
                        guild_data = self._data["guilds"].get(str(gid))
                        if guild_data:
                            doc = {
                                "guild_id": str(gid),
                                **guild_data
                            }
                            operations.append(UpdateOne({"guild_id": str(gid)}, {"$set": doc}, upsert=True))
                    if operations:
                        self.mongo_collection.bulk_write(operations, ordered=False)
        except Exception as e:
            # Retain dirty guilds so they are retried on the next periodic sync cycle
            for gid in guild_ids:
                self._dirty_guilds.add(str(gid))
            self._dirty = True
            print(f"[SETTINGS MONGO SAVE WARNING] {e}")

    def save_guild_to_mongo(self, guild_id: str):
        """Schedules non-blocking persistence of a single guild's configuration into MongoDB Atlas."""
        self._dirty_guilds.add(str(guild_id))
        self.schedule_save()

    def save_immediate(self):
        """Flushes all dirty guilds to MongoDB Atlas in a thread-safe manner."""
        with self._save_lock:
            try:
                all_gids = list(self._data["guilds"].keys())
                self._save_guilds_sync(all_gids)
                self._dirty = False
                self._dirty_guilds.clear()
            except Exception as e:
                print(f"[SETTINGS MONGO FLUSH ERROR] {e}")

    def schedule_save(self):
        """Schedules a non-blocking debounced save in the background."""
        self._dirty = True
        try:
            loop = asyncio.get_running_loop()
            if self._async_flush_task is None or self._async_flush_task.done():
                self._async_flush_task = loop.create_task(self._debounced_flush())
        except RuntimeError:
            # Not in an active async event loop, save in background thread or synchronously
            threading.Thread(target=self.save_immediate, daemon=True).start()

    async def _debounced_flush(self):
        """Debounces writes to prevent blocking I/O under rapid setting changes."""
        await asyncio.sleep(0.5)
        if self._dirty_guilds or self._dirty:
            to_save = list(self._dirty_guilds)
            self._dirty_guilds.clear()
            self._dirty = False
            if to_save:
                await asyncio.to_thread(self._save_guilds_sync, to_save)
            else:
                await asyncio.to_thread(self.save_immediate)

    # ================= GUILD SETTINGS API =================

    def get_guild_settings(self, guild_id: int | str) -> Dict[str, Any]:
        """Returns all settings for a guild with defaults."""
        gid = str(guild_id)
        current = self._data["guilds"].get(gid, {})
        merged = DEFAULT_GUILD_SETTINGS.copy()
        merged.update(current)
        return merged

    def get_guild_setting(self, guild_id: int | str, key: str, default: Any = None) -> Any:
        """Instant O(1) in-memory lookup for guild setting."""
        gid = str(guild_id)
        guild_data = self._data["guilds"].get(gid)
        if guild_data and key in guild_data:
            return guild_data[key]
        if key in DEFAULT_GUILD_SETTINGS:
            return DEFAULT_GUILD_SETTINGS[key]
        return default

    def set_guild_setting(self, guild_id: int | str, key: str, value: Any):
        """Sets a guild setting in memory instantly and schedules background non-blocking persistence."""
        gid = str(guild_id)
        with self._save_lock:
            if gid not in self._data["guilds"]:
                self._data["guilds"][gid] = DEFAULT_GUILD_SETTINGS.copy()
            self._data["guilds"][gid][key] = value
        self.save_guild_to_mongo(gid)

    def update_guild_settings(self, guild_id: int | str, updates: Dict[str, Any]):
        """Batch updates multiple settings for a guild and schedules background non-blocking persistence."""
        gid = str(guild_id)
        with self._save_lock:
            if gid not in self._data["guilds"]:
                self._data["guilds"][gid] = DEFAULT_GUILD_SETTINGS.copy()
            self._data["guilds"][gid].update(updates)
        self.save_guild_to_mongo(gid)

    def delete_guild(self, guild_id: int | str):
        """Removes a guild from local settings when bot leaves guild."""
        gid = str(guild_id)
        with self._save_lock:
            if gid not in self._data["guilds"]:
                return
            del self._data["guilds"][gid]
        self.schedule_save()

    # ================= BOT GLOBAL SETTINGS API =================

    def get_bot_setting(self, key: str, default: Any = None) -> Any:
        """Returns a global bot setting."""
        return self._data["bot"].get(key, default)

    def set_bot_setting(self, key: str, value: Any):
        """Sets a global bot setting and persists to file."""
        with self._save_lock:
            self._data["bot"][key] = value
        self.schedule_save()

    def sync_all_from_databases(self) -> Dict[str, int]:
        """Synchronizes all SQLite database settings into the local JSON store."""
        import sqlite3
        stats = {"guilds": 0, "qrs": 0, "orders": 0}

        # 1. Load Prefix DB
        if os.path.exists("db/prefix.db"):
            try:
                con = sqlite3.connect("db/prefix.db")
                rows = con.execute("SELECT guild_id, prefix FROM prefixes").fetchall()
                for gid, pfx in rows:
                    gid_str = str(gid)
                    if gid_str not in self._data["guilds"]:
                        self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                    self._data["guilds"][gid_str]["prefix"] = pfx
                con.close()
            except Exception as e:
                print(f"[SYNC WARNING] Prefix sync: {e}")

        # 2. Load Antinuke & Whitelist & Extraowners & Nightmode
        if os.path.exists("db/anti.db"):
            try:
                con = sqlite3.connect("db/anti.db")
                # Clean up old disabled antinuke records (preserve nightmode_config so custom timers persist across reboot)
                try:
                    con.execute("DELETE FROM antinuke WHERE status = 0 OR status IS NULL")
                    con.commit()
                except Exception:
                    pass

                # Antinuke status (only active enabled records)
                try:
                    rows = con.execute("SELECT guild_id, status FROM antinuke WHERE status = 1").fetchall()
                except sqlite3.OperationalError:
                    rows = con.execute("SELECT guild_id, enabled FROM antinuke WHERE enabled = 1").fetchall()

                for gid, status in rows:
                    gid_str = str(gid)
                    if gid_str not in self._data["guilds"]:
                        self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                    self._data["guilds"][gid_str]["antinuke"] = bool(status)

                # Bot Protection status (only active enabled records per guild)
                try:
                    bp_rows = con.execute("SELECT guild_id, status FROM bot_protection WHERE status = 1").fetchall()
                    for gid, status in bp_rows:
                        gid_str = str(gid)
                        if gid_str not in self._data["guilds"]:
                            self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                        self._data["guilds"][gid_str]["bot_protection"] = bool(status)
                except Exception:
                    pass
                
                # Whitelisted Users
                try:
                    con.execute("""
                        CREATE TABLE IF NOT EXISTS whitelisted_users (
                            guild_id INTEGER,
                            user_id INTEGER,
                            ban BOOLEAN DEFAULT TRUE,
                            kick BOOLEAN DEFAULT TRUE,
                            prune BOOLEAN DEFAULT TRUE,
                            botadd BOOLEAN DEFAULT TRUE,
                            serverup BOOLEAN DEFAULT TRUE,
                            memup BOOLEAN DEFAULT TRUE,
                            chcr BOOLEAN DEFAULT TRUE,
                            chdl BOOLEAN DEFAULT TRUE,
                            chup BOOLEAN DEFAULT TRUE,
                            rlcr BOOLEAN DEFAULT TRUE,
                            rlup BOOLEAN DEFAULT TRUE,
                            rldl BOOLEAN DEFAULT TRUE,
                            meneve BOOLEAN DEFAULT TRUE,
                            mngweb BOOLEAN DEFAULT TRUE,
                            mngstemo BOOLEAN DEFAULT TRUE,
                            PRIMARY KEY (guild_id, user_id)
                        )
                    """)
                    rows = con.execute("SELECT guild_id, user_id FROM whitelisted_users").fetchall()
                    guild_wl_map = {}
                    for gid, uid in rows:
                        gid_str = str(gid)
                        if gid_str not in guild_wl_map:
                            guild_wl_map[gid_str] = []
                        if str(uid) not in guild_wl_map[gid_str]:
                            guild_wl_map[gid_str].append(str(uid))

                    for gid_str, uids in guild_wl_map.items():
                        if gid_str not in self._data["guilds"]:
                            self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                        self._data["guilds"][gid_str]["whitelist"] = uids
                except Exception as e:
                    print(f"[SYNC WARNING] Whitelist users sync: {e}")

                # Whitelisted Roles
                try:
                    con.execute("""
                        CREATE TABLE IF NOT EXISTS whitelisted_roles (
                            guild_id INTEGER,
                            role_id INTEGER,
                            added_by INTEGER,
                            PRIMARY KEY (guild_id, role_id)
                        )
                    """)
                    rows = con.execute("SELECT guild_id, role_id FROM whitelisted_roles").fetchall()
                    guild_role_map = {}
                    for gid, rid in rows:
                        gid_str = str(gid)
                        if gid_str not in guild_role_map:
                            guild_role_map[gid_str] = []
                        if str(rid) not in guild_role_map[gid_str]:
                            guild_role_map[gid_str].append(str(rid))

                    for gid_str, rids in guild_role_map.items():
                        if gid_str not in self._data["guilds"]:
                            self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                        self._data["guilds"][gid_str]["whitelist_roles"] = rids
                except Exception as e:
                    print(f"[SYNC WARNING] Whitelist roles sync: {e}")

                # Extraowners
                try:
                    rows = con.execute("SELECT guild_id, owner_id FROM extraowners").fetchall()
                    for gid, oid in rows:
                        gid_str = str(gid)
                        if gid_str not in self._data["guilds"]:
                            self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                        self._data["guilds"][gid_str]["extraowner"] = str(oid)
                except Exception:
                    pass

                # Nightmode
                try:
                    rows = con.execute("SELECT guildId, roleId FROM Nightmode").fetchall()
                    for gid, rid in rows:
                        gid_str = str(gid)
                        if gid_str not in self._data["guilds"]:
                            self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                        self._data["guilds"][gid_str]["nightmode"] = True
                except Exception:
                    pass

                # Auto Nightmode Active Config
                try:
                    rows = con.execute("SELECT guild_id FROM nightmode_config WHERE auto_enabled = 1").fetchall()
                    for (gid,) in rows:
                        gid_str = str(gid)
                        if gid_str not in self._data["guilds"]:
                            self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                        self._data["guilds"][gid_str]["nightmode_auto"] = True
                except Exception:
                    pass

                con.close()
            except Exception as e:
                print(f"[SYNC WARNING] Anti.db sync: {e}")

        # 3. Load Automod
        if os.path.exists("db/automod.db"):
            try:
                con = sqlite3.connect("db/automod.db")
                # NOTE: Punishment/threshold/warn_message rows are intentionally preserved
                # even when automod is disabled (enabled=0). This ensures toggling
                # AutoMod OFF → restart → ON retains all configured settings.
                # Previously, a DELETE query here wiped punishments for disabled guilds,
                # causing the AutoMod regression.

                try:
                    rows = con.execute("SELECT guild_id, enabled FROM automod WHERE enabled = 1").fetchall()
                except sqlite3.OperationalError:
                    rows = con.execute("SELECT guild_id, status FROM automod WHERE status = 1").fetchall()

                for gid, status in rows:
                    gid_str = str(gid)
                    if gid_str not in self._data["guilds"]:
                        self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                    self._data["guilds"][gid_str]["automod"] = bool(status)
                con.close()
            except Exception as e:
                print(f"[SYNC WARNING] Automod sync: {e}")

        # 4. Load Payments & Static QRs
        if "payments" not in self._data:
            self._data["payments"] = {"static_qrs": {}, "total_orders": 0}
        if os.path.exists("db/payment.db"):
            try:
                con = sqlite3.connect("db/payment.db")
                rows = con.execute("SELECT amount, image_url, message FROM payments WHERE guild_id = 'global'").fetchall()
                for amt, img, msg in rows:
                    self._data["payments"]["static_qrs"][str(amt)] = {
                        "image_url": img,
                        "message": msg
                    }
                count = con.execute("SELECT COUNT(*) FROM payment_orders").fetchone()[0]
                self._data["payments"]["total_orders"] = count
                stats["qrs"] = len(rows)
                stats["orders"] = count
                con.close()
            except Exception:
                pass

        # 5. Music/voice persistence is loaded from the dedicated yunamusic store
        # by the music cog; it is intentionally not sourced from local SQLite.

        # 6. Load Invite Tracker
        if os.path.exists("db/invites.db"):
            try:
                con = sqlite3.connect("db/invites.db")
                # Clean up disabled invite configs
                try:
                    con.execute("DELETE FROM invite_config WHERE enabled = 0 OR enabled IS NULL")
                    con.commit()
                except Exception:
                    pass

                rows = con.execute("SELECT guild_id, enabled, log_channel, vc_channel, vc_format FROM invite_config WHERE enabled = 1").fetchall()
                for gid, en, log_ch, vc_ch, vc_fmt in rows:
                    gid_str = str(gid)
                    if gid_str not in self._data["guilds"]:
                        self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                    self._data["guilds"][gid_str]["invitetracker"] = {
                        "enabled": bool(en),
                        "log_channel": log_ch,
                        "vc_channel": vc_ch,
                        "vc_format": vc_fmt
                    }
                stats["invites_config"] = len(rows)
                con.close()
            except Exception:
                pass

        # 7. Load Topcheck
        if os.path.exists("db/topcheck.db"):
            try:
                con = sqlite3.connect("db/topcheck.db")
                try:
                    con.execute("DELETE FROM topcheck WHERE enabled = 0 OR enabled IS NULL")
                    con.commit()
                except Exception:
                    pass
                rows = con.execute("SELECT guild_id, enabled FROM topcheck WHERE enabled = 1").fetchall()
                for gid, en in rows:
                    gid_str = str(gid)
                    if gid_str not in self._data["guilds"]:
                        self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                    self._data["guilds"][gid_str]["topcheck"] = bool(en)
                con.close()
            except Exception:
                pass

        # 8. Load TempVC Creators from db/tempvc.db
        if os.path.exists("db/tempvc.db"):
            try:
                con = sqlite3.connect("db/tempvc.db")
                rows = con.execute("SELECT guild_id, creator_id, name, name_template, category_id, privacy_mode, user_limit, bitrate, sync_permissions FROM tempvc_creators").fetchall()
                guild_creators = {}
                for gid, cid, cname, ntmpl, catid, pmode, ulimit, brit, sperms in rows:
                    gid_str = str(gid)
                    if gid_str not in guild_creators:
                        guild_creators[gid_str] = []
                    guild_creators[gid_str].append({
                        "id": str(cid),
                        "name": cname,
                        "nameTemplate": ntmpl or "{user}'s Lounge",
                        "categoryId": str(catid or ""),
                        "privacyMode": pmode or "Public",
                        "userLimit": int(ulimit or 0),
                        "bitrate": brit or "64kbps",
                        "syncPermissions": sperms or "Sync with Category"
                    })
                for gid_str, crs in guild_creators.items():
                    if gid_str not in self._data["guilds"]:
                        self._data["guilds"][gid_str] = DEFAULT_GUILD_SETTINGS.copy()
                    self._data["guilds"][gid_str]["tempvc_creators"] = crs
                stats["tempvc_creators"] = len(rows)
                con.close()
            except Exception as e:
                print(f"[SYNC WARNING] TempVC sync: {e}")

        stats["guilds"] = len(self._data["guilds"])
        try:
            from core.cache.security_cache import security_cache
            security_cache._loaded_guilds.clear()
        except Exception:
            pass
        self._save_to_disk_sync()
        self.schedule_save()
        return stats

    def get_all(self) -> Dict[str, Any]:
        """Returns complete local settings structure."""
        return self._data


# Global Singleton Instance
settings = SettingsManager()
server_settings = settings
settings_manager = settings

# Easy functional exports
def get_guild_setting(guild_id: int | str, key: str, default: Any = None) -> Any:
    return settings.get_guild_setting(guild_id, key, default)

def set_guild_setting(guild_id: int | str, key: str, value: Any):
    settings.set_guild_setting(guild_id, key, value)

def update_guild_setting(guild_id: int | str, key: str, value: Any):
    settings.set_guild_setting(guild_id, key, value)

def update_guild_settings(guild_id: int | str, updates: Dict[str, Any]):
    settings.update_guild_settings(guild_id, updates)

def get_guild_settings(guild_id: int | str) -> Dict[str, Any]:
    return settings.get_guild_settings(guild_id)

def get_bot_setting(key: str, default: Any = None) -> Any:
    return settings.get_bot_setting(key, default)

def set_bot_setting(key: str, value: Any):
    settings.set_bot_setting(key, value)

def get_guild_bot_profile(guild_id: int | str) -> Dict[str, Any]:
    return {
        "nickname": get_guild_setting(guild_id, "bot_server_nick", None),
        "status_type": get_guild_setting(guild_id, "bot_status_type", "PLAYING"),
        "status_text": get_guild_setting(guild_id, "bot_status_text", "Watching over Yuna Protected Guilds | /help"),
        "avatar_url": get_guild_setting(guild_id, "bot_avatar_url", ""),
        "banner_url": get_guild_setting(guild_id, "bot_banner_url", ""),
    }

def sync_all_settings() -> Dict[str, int]:
    return settings.sync_all_from_databases()

