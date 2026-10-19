import os
import json
import sqlite3
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

import discord
from services.discord_profile_manager import DiscordProfileManager, DiscordProfileError, ProfileRateLimited
from services.profile_storage import ProfileStorage, ProfileStorageError
from services.profile_sync_worker import ProfileSyncWorker

logger = logging.getLogger("yuna.profile_service")

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'db', 'guild_profiles.db'))

DEFAULT_BOT_AVATAR = "https://cdn.discordapp.com/avatars/1525256351171739678/afdef48ec8c8c62b9e084b59974d380e.png?size=1024"
DEFAULT_BOT_BANNER = "https://cdn.discordapp.com/banners/1525256351171739678/a_3f56ef61c1e08b643aab1484700e5e2e.gif?size=1024"

_live_bot_cache = {
    "avatar_url": DEFAULT_BOT_AVATAR,
    "banner_url": DEFAULT_BOT_BANNER,
    "name": "YUNA",
    "username": "YUNA",
    "last_fetched": 0.0
}

async def refresh_live_bot_defaults(bot: Optional[discord.Client]):
    """Asynchronously fetches live bot banner and avatar from Discord REST API and updates memory cache."""
    global _live_bot_cache
    if not bot or not getattr(bot, "user", None):
        return
    try:
        user = await bot.fetch_user(bot.user.id)
        if user:
            _live_bot_cache["name"] = user.name
            discrim = getattr(user, "discriminator", None)
            _live_bot_cache["username"] = f"{user.name}#{discrim}" if discrim and discrim != "0" else user.name
            if user.display_avatar:
                _live_bot_cache["avatar_url"] = str(user.display_avatar.url)
            if user.banner:
                _live_bot_cache["banner_url"] = str(user.banner.url)
            _live_bot_cache["last_fetched"] = time.time()
            logger.info(f"[ProfileService] Refreshed live bot defaults: avatar={bool(user.display_avatar)}, banner={bool(user.banner)}")
    except Exception as e:
        logger.debug(f"[ProfileService] Notice while refreshing live bot user profile: {e}")

class ProfileService:
    def __init__(self, bot: Optional[discord.Client] = None):
        self.bot = bot
        self.discord_manager = DiscordProfileManager(bot) if bot else None
        self.storage = ProfileStorage()
        self.sync_worker = ProfileSyncWorker(debounce_delay=2.5)
        self.sync_worker.set_sync_callback(self._on_debounced_sync)
        self._init_db()

    def set_bot(self, bot: discord.Client):
        """Sets or updates the bot reference and instantiates DiscordProfileManager."""
        self.bot = bot
        self.discord_manager = DiscordProfileManager(bot)

    def _get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with WAL mode enabled and Row factory."""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        """Initializes database schema for guild_profiles and profile_audit_logs."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS guild_profiles (
                        guild_id INTEGER PRIMARY KEY,
                        custom_nickname TEXT,
                        custom_avatar_url TEXT,
                        custom_banner_url TEXT,
                        custom_bio TEXT,
                        activity_type TEXT DEFAULT 'PLAYING',
                        activity_text TEXT,
                        activity_url TEXT,
                        status TEXT DEFAULT 'online',
                        sync_status TEXT DEFAULT 'SYNCED',
                        last_error TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Auto-migrate existing database to ensure custom_bio column exists
                try:
                    conn.execute("ALTER TABLE guild_profiles ADD COLUMN custom_bio TEXT;")
                except Exception:
                    pass

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS profile_audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER,
                        user_tag TEXT,
                        action TEXT NOT NULL,
                        changes_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_guild ON profile_audit_logs(guild_id);")
        finally:
            conn.close()

    def get_profile(self, guild_id: int) -> Dict[str, Any]:
        """
        Retrieves local database profile configuration for guild_id.
        Auto-heals any desync between local database/disk and live Discord state:
        - If Discord member has no server avatar/banner override, stale local asset is cleared.
        - Effective avatar and banner always match live Discord reality.
        """
        conn = self._get_connection()
        row = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM guild_profiles WHERE guild_id = ?;", (guild_id,))
            row = cur.fetchone()
        finally:
            conn.close()

        # Global bot fallbacks from live Discord bot cache
        global_name = (self.bot.user.name if (self.bot and self.bot.user) else None) or _live_bot_cache["name"]
        global_username = (
            (f"{self.bot.user.name}#{self.bot.user.discriminator}" if self.bot.user.discriminator and self.bot.user.discriminator != "0" else self.bot.user.name)
            if (self.bot and self.bot.user) else None
        ) or _live_bot_cache["username"]
        global_avatar = (str(self.bot.user.display_avatar.url) if (self.bot and self.bot.user and self.bot.user.display_avatar) else None) or _live_bot_cache["avatar_url"]
        
        banner_attr = getattr(self.bot.user, 'banner', None) if (self.bot and self.bot.user) else None
        global_banner = (str(banner_attr.url) if (banner_attr and hasattr(banner_attr, 'url')) else None) or _live_bot_cache["banner_url"]

        # Fetch guild member for per-server member nickname/avatar/banner
        member = None
        if self.bot:
            guild = self.bot.get_guild(guild_id)
            if guild:
                member = guild.me

        # Check local disk assets. If DB points to local asset that no longer exists on disk, discard it
        disk_avatar_path = self.storage.get_asset_file(guild_id, "avatar")
        db_avatar = row["custom_avatar_url"] if row else None
        if db_avatar:
            if db_avatar.startswith("/assets/profiles/"):
                if disk_avatar_path and os.path.exists(disk_avatar_path):
                    db_avatar = f"/assets/profiles/{guild_id}/{os.path.basename(disk_avatar_path)}"
                else:
                    db_avatar = None

        disk_banner_path = self.storage.get_asset_file(guild_id, "banner")
        db_banner = row["custom_banner_url"] if row else None
        if db_banner:
            if db_banner.startswith("/assets/profiles/"):
                if disk_banner_path and os.path.exists(disk_banner_path):
                    db_banner = f"/assets/profiles/{guild_id}/{os.path.basename(disk_banner_path)}"
                else:
                    db_banner = None

        # Determine Discord live member state
        has_discord_guild_avatar = False
        has_discord_guild_banner = False
        live_member_avatar = global_avatar
        live_member_banner = None

        if member:
            current_nickname = (member.nick if (hasattr(member, 'nick') and isinstance(member.nick, str)) else None) or (row["custom_nickname"] if row else None) or global_name

            guild_av = getattr(member, 'guild_avatar', None)
            if guild_av and hasattr(guild_av, 'url'):
                has_discord_guild_avatar = True
                live_member_avatar = str(guild_av.url)
            elif hasattr(member, 'display_avatar') and member.display_avatar:
                live_member_avatar = str(member.display_avatar.url)

            guild_bn = getattr(member, 'guild_banner', None)
            if guild_bn and hasattr(guild_bn, 'url'):
                has_discord_guild_banner = True
                live_member_banner = str(guild_bn.url)
            elif hasattr(member, 'display_banner') and member.display_banner:
                m_disp = str(member.display_banner.url)
                if "/guilds/" in m_disp:
                    has_discord_guild_banner = True
                    live_member_banner = m_disp
        else:
            current_nickname = (row["custom_nickname"] if row else None) or global_name

        is_pending_sync = bool(row and row["sync_status"] == "PENDING")

        # --- AUTO-HEALING DESYNC CORRECTION ---
        # 1. Auto-Heal Avatar:
        # If Discord has no custom guild avatar (member.guild_avatar is None) and no sync is pending,
        # any local asset or custom_avatar_url is a stale desync. Clean it up!
        if member and not has_discord_guild_avatar and not is_pending_sync:
            if db_avatar or disk_avatar_path:
                logger.info(f"[Auto-Heal] Guild {guild_id}: Purging stale avatar override (Discord has no guild avatar)")
                self.storage.delete_asset(guild_id, "avatar")
                self.update_profile_db(guild_id, {"custom_avatar_url": None})
                db_avatar = None

        # 2. Auto-Heal Banner:
        # Identical to avatar: if Discord has no custom guild banner (member.guild_banner is None) and no sync is pending,
        # any local asset or custom_banner_url is a stale desync. Clean it up!
        if member and not has_discord_guild_banner and not is_pending_sync:
            if db_banner or disk_banner_path:
                logger.info(f"[Auto-Heal] Guild {guild_id}: Purging stale banner override (Discord has no guild banner)")
                self.storage.delete_asset(guild_id, "banner")
                self.update_profile_db(guild_id, {"custom_banner_url": None})
                db_banner = None

        # Compute custom and effective URLs identically for avatar and banner
        custom_avatar = live_member_avatar if has_discord_guild_avatar else db_avatar
        if db_avatar and not db_avatar.startswith("/assets/profiles/"):
            effective_avatar = db_avatar
        elif has_discord_guild_avatar:
            effective_avatar = live_member_avatar
        else:
            effective_avatar = live_member_avatar or global_avatar

        custom_banner = live_member_banner if has_discord_guild_banner else db_banner
        if db_banner and not db_banner.startswith("/assets/profiles/"):
            effective_banner = db_banner
        elif has_discord_guild_banner:
            effective_banner = live_member_banner
        else:
            effective_banner = global_banner

        db_bio = row["custom_bio"] if (row and "custom_bio" in row.keys()) else None

        return {
            "guild_id": guild_id,
            "custom_nickname": row["custom_nickname"] if row else None,
            "effective_nickname": current_nickname,
            "custom_avatar_url": custom_avatar,
            "effective_avatar_url": effective_avatar,
            "custom_banner_url": custom_banner,
            "effective_banner_url": effective_banner,
            "custom_bio": db_bio,
            "activity_type": row["activity_type"] if row else "PLAYING",
            "activity_text": row["activity_text"] if row else "",
            "activity_url": row["activity_url"] if row else "",
            "status": row["status"] if row else "online",
            "sync_status": row["sync_status"] if row else "SYNCED",
            "last_error": row["last_error"] if row else None,
            "global_defaults": {
                "name": global_name,
                "username": global_username,
                "avatar_url": global_avatar,
                "banner_url": global_banner
            },
            "updated_at": row["updated_at"] if row else None
        }

    def update_profile_db(self, guild_id: int, data: Dict[str, Any]):
        """Upserts profile fields into database."""
        conn = self._get_connection()
        try:
            with conn:
                existing = conn.execute("SELECT guild_id FROM guild_profiles WHERE guild_id = ?;", (guild_id,)).fetchone()
                if existing:
                    fields = []
                    params = []
                    for key in ["custom_nickname", "custom_avatar_url", "custom_banner_url", "custom_bio",
                                "activity_type", "activity_text", "activity_url", "status",
                                "sync_status", "last_error"]:
                        if key in data:
                            fields.append(f"{key} = ?")
                            params.append(data[key])
                    fields.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(guild_id)
                    query = f"UPDATE guild_profiles SET {', '.join(fields)} WHERE guild_id = ?;"
                    conn.execute(query, params)
                else:
                    conn.execute("""
                        INSERT INTO guild_profiles (
                            guild_id, custom_nickname, custom_avatar_url, custom_banner_url, custom_bio,
                            activity_type, activity_text, activity_url, status, sync_status, last_error
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        guild_id,
                        data.get("custom_nickname"),
                        data.get("custom_avatar_url"),
                        data.get("custom_banner_url"),
                        data.get("custom_bio"),
                        data.get("activity_type", "PLAYING"),
                        data.get("activity_text", ""),
                        data.get("activity_url", ""),
                        data.get("status", "online"),
                        data.get("sync_status", "PENDING"),
                        data.get("last_error", None)
                    ))
        finally:
            conn.close()

    def log_audit(self, guild_id: int, user_info: Dict[str, Any], action: str, changes: Dict[str, Any]):
        """Records an audit log entry in profile_audit_logs."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO profile_audit_logs (guild_id, user_id, user_tag, action, changes_json)
                    VALUES (?, ?, ?, ?, ?);
                """, (
                    guild_id,
                    user_info.get("user_id", 0),
                    user_info.get("user_tag", "System"),
                    action,
                    json.dumps(changes)
                ))
        finally:
            conn.close()

    def get_audit_logs(self, guild_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches audit logs for guild_id."""
        conn = self._get_connection()
        logs = []
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, guild_id, user_id, user_tag, action, changes_json, created_at
                FROM profile_audit_logs
                WHERE guild_id = ?
                ORDER BY id DESC LIMIT ?;
            """, (guild_id, limit))
            for r in cur.fetchall():
                logs.append({
                    "id": r["id"],
                    "guild_id": r["guild_id"],
                    "user_id": r["user_id"],
                    "user_tag": r["user_tag"],
                    "action": r["action"],
                    "changes": json.loads(r["changes_json"]) if r["changes_json"] else {},
                    "created_at": r["created_at"]
                })
        finally:
            conn.close()
        return logs

    async def update_profile(self, guild_id: int, updates: Dict[str, Any], user_info: Dict[str, Any], immediate: bool = False) -> Dict[str, Any]:
        """
        Updates profile fields in DB, records audit log, and schedules or immediately executes Discord API sync.
        Strictly isolated to guild_id.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}. Operations must be scoped to a valid server.")

        allowed_keys = {
            "custom_nickname", "custom_avatar_url", "custom_banner_url", "custom_bio",
            "activity_type", "activity_text", "activity_url", "status"
        }
        db_updates = {k: v for k, v in updates.items() if k in allowed_keys}
        db_updates["sync_status"] = "PENDING"
        self.update_profile_db(guild_id, db_updates)
        self.log_audit(guild_id, user_info, "UPDATE_PROFILE", db_updates)

        if immediate:
            await self.sync_to_discord(guild_id)
        else:
            self.sync_worker.schedule_sync(guild_id, updates)

        return self.get_profile(guild_id)

    async def upload_avatar(self, guild_id: int, image_bytes: bytes, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates, optimizes, and saves server-specific avatar image, updates DB, and syncs to Discord.
        Guarantees that global bot avatar remains untouched.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}. Operations must be scoped to a valid server.")

        opt_bytes, opt_mime = self.storage.optimize_image(image_bytes, "avatar")
        saved_path = self.storage.save_asset(guild_id, "avatar", opt_bytes)
        relative_url = f"/assets/profiles/{guild_id}/{os.path.basename(saved_path)}"

        self.update_profile_db(guild_id, {
            "custom_avatar_url": relative_url,
            "sync_status": "PENDING"
        })
        self.log_audit(guild_id, user_info, "UPLOAD_AVATAR", {"custom_avatar_url": relative_url})

        # Sync to Discord without crashing if Discord member avatar fails (e.g. Nitro required)
        try:
            await self.sync_to_discord(guild_id, avatar_bytes=opt_bytes, avatar_mime=opt_mime, raise_on_error=False)
        except Exception as e:
            logger.warning(f"Discord avatar sync non-fatal notice for guild {guild_id}: {e}")
        return self.get_profile(guild_id)

    async def upload_banner(self, guild_id: int, image_bytes: bytes, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates, optimizes, and saves server-specific banner image, updates DB, and syncs to Discord.
        Guarantees that global bot banner remains untouched.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}. Operations must be scoped to a valid server.")

        opt_bytes, opt_mime = self.storage.optimize_image(image_bytes, "banner")
        saved_path = self.storage.save_asset(guild_id, "banner", opt_bytes)
        relative_url = f"/assets/profiles/{guild_id}/{os.path.basename(saved_path)}"

        self.update_profile_db(guild_id, {
            "custom_banner_url": relative_url,
            "sync_status": "PENDING"
        })
        self.log_audit(guild_id, user_info, "UPLOAD_BANNER", {"custom_banner_url": relative_url})

        try:
            await self.sync_to_discord(guild_id, banner_bytes=opt_bytes, banner_mime=opt_mime, raise_on_error=False)
        except Exception as e:
            logger.warning(f"Discord banner sync non-fatal notice for guild {guild_id}: {e}")
        return self.get_profile(guild_id)

    async def reset_avatar(self, guild_id: int, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deletes server-specific avatar asset from assets/profiles/{guild_id}/, clears custom_avatar_url
        in DB for this guild, and resets the member avatar on Discord.
        
        SAFETY GUARANTEE:
        This ONLY resets this specific guild's override so it falls back to the main bot avatar.
        The bot's global avatar is never deleted or modified.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}. Operations must be scoped to a valid server.")

        self.storage.delete_asset(guild_id, "avatar")
        self.update_profile_db(guild_id, {
            "custom_avatar_url": None,
            "sync_status": "PENDING"
        })
        self.log_audit(guild_id, user_info, "RESET_AVATAR", {})

        if self.discord_manager:
            try:
                await self.discord_manager.reset_server_avatar(guild_id)
                self.update_profile_db(guild_id, {"sync_status": "SYNCED", "last_error": None})
            except Exception as e:
                self.update_profile_db(guild_id, {"sync_status": "ERROR", "last_error": str(e)})
                raise
        return self.get_profile(guild_id)

    async def reset_banner(self, guild_id: int, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deletes server-specific banner asset from assets/profiles/{guild_id}/, clears custom_banner_url
        in DB for this guild, and resets banner on Discord/Dashboard.
        
        SAFETY GUARANTEE:
        This ONLY resets this specific guild's override so it falls back to the main bot banner.
        The bot's global banner is never deleted or modified.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}. Operations must be scoped to a valid server.")

        self.storage.delete_asset(guild_id, "banner")
        self.update_profile_db(guild_id, {
            "custom_banner_url": None,
            "sync_status": "PENDING"
        })
        self.log_audit(guild_id, user_info, "RESET_BANNER", {})

        if self.discord_manager:
            try:
                await self.discord_manager.reset_server_banner(guild_id)
                self.update_profile_db(guild_id, {"sync_status": "SYNCED", "last_error": None})
            except Exception as e:
                self.update_profile_db(guild_id, {"sync_status": "ERROR", "last_error": str(e)})
                raise
        return self.get_profile(guild_id)

    async def set_bio(self, guild_id: int, bio: str, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sets custom server bio for YUNA (up to 190 characters), updates DB, and syncs to Discord.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}. Operations must be scoped to a valid server.")

        bio_clean = (bio or "").strip()[:190]
        self.update_profile_db(guild_id, {
            "custom_bio": bio_clean,
            "sync_status": "PENDING"
        })
        self.log_audit(guild_id, user_info, "SET_BIO", {"custom_bio": bio_clean})

        if self.discord_manager:
            try:
                await self.discord_manager.update_server_profile(guild_id, bio=bio_clean)
                self.update_profile_db(guild_id, {"sync_status": "SYNCED", "last_error": None})
            except Exception as e:
                self.update_profile_db(guild_id, {"sync_status": "ERROR", "last_error": str(e)})
                raise
        return self.get_profile(guild_id)

    async def reset_bio(self, guild_id: int, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resets custom server bio back to global default.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}. Operations must be scoped to a valid server.")

        self.update_profile_db(guild_id, {
            "custom_bio": None,
            "sync_status": "PENDING"
        })
        self.log_audit(guild_id, user_info, "RESET_BIO", {})

        if self.discord_manager:
            try:
                await self.discord_manager.reset_server_bio(guild_id)
                self.update_profile_db(guild_id, {"sync_status": "SYNCED", "last_error": None})
            except Exception as e:
                self.update_profile_db(guild_id, {"sync_status": "ERROR", "last_error": str(e)})
                raise
        return self.get_profile(guild_id)

    async def reset_profile(self, guild_id: int, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resets all custom server profile settings for guild_id back to global defaults.
        
        SAFETY GUARANTEE:
        The bot's permanent global profile remains 100% safe and untouched.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}. Operations must be scoped to a valid server.")

        self.storage.delete_asset(guild_id, "avatar")
        self.storage.delete_asset(guild_id, "banner")

        self.update_profile_db(guild_id, {
            "custom_nickname": None,
            "custom_avatar_url": None,
            "custom_banner_url": None,
            "custom_bio": None,
            "activity_type": "PLAYING",
            "activity_text": "",
            "activity_url": "",
            "status": "online",
            "sync_status": "PENDING",
            "last_error": None
        })
        self.log_audit(guild_id, user_info, "RESET_ALL", {})

        if self.discord_manager:
            try:
                await self.discord_manager.reset_entire_profile(guild_id)
                self.update_profile_db(guild_id, {"sync_status": "SYNCED", "last_error": None})
            except Exception as e:
                self.update_profile_db(guild_id, {"sync_status": "ERROR", "last_error": str(e)})
                raise
        return self.get_profile(guild_id)

    async def _on_debounced_sync(self, guild_id: int, payload: Dict[str, Any]):
        """Internal callback invoked by ProfileSyncWorker when debounce timer expires."""
        await self.sync_to_discord(guild_id)

    async def sync_to_discord(
        self,
        guild_id: int,
        avatar_bytes: Optional[bytes] = None,
        avatar_mime: str = "image/png",
        banner_bytes: Optional[bytes] = None,
        banner_mime: str = "image/png",
        bio: Optional[str] = None,
        reset_avatar: bool = False,
        reset_banner: bool = False,
        reset_bio: bool = False,
        force_all: bool = False,
        raise_on_error: bool = False
    ):
        """
        Executes Discord HTTP API update using current DB profile state or passed image bytes.
        Only reads local assets from disk when force_all is True to avoid re-uploading unchanged binary assets.
        """
        if not self.discord_manager:
            from core.dashboard.utils import get_bot
            bot = self.bot or get_bot()
            if bot:
                self.set_bot(bot)

        if not self.discord_manager:
            logger.warning(f"[ProfileService] DiscordProfileManager not initialized, skipping sync for guild {guild_id}")
            return

        profile = self.get_profile(guild_id)

        # Only read local asset from disk if force_all is True and bytes were not provided
        if force_all and not avatar_bytes and not reset_avatar and profile.get("custom_avatar_url"):
            avatar_path = self.storage.get_asset_file(guild_id, "avatar")
            if avatar_path and os.path.exists(avatar_path):
                with open(avatar_path, "rb") as f:
                    avatar_bytes = f.read()

        if force_all and not banner_bytes and not reset_banner and profile.get("custom_banner_url"):
            banner_path = self.storage.get_asset_file(guild_id, "banner")
            if banner_path and os.path.exists(banner_path):
                with open(banner_path, "rb") as f:
                    banner_bytes = f.read()

        nickname = profile.get("custom_nickname")
        bio_to_sync = bio if bio is not None else profile.get("custom_bio")

        try:
            await self.discord_manager.update_server_profile(
                guild_id=guild_id,
                nickname=nickname,
                avatar_bytes=avatar_bytes,
                avatar_mime=avatar_mime,
                banner_bytes=banner_bytes,
                banner_mime=banner_mime,
                bio=bio_to_sync,
                reset_avatar=reset_avatar,
                reset_banner=reset_banner,
                reset_bio=reset_bio
            )
            guild = getattr(self.bot, "get_guild", lambda _: None)(guild_id) if hasattr(self, "bot") and self.bot else None
            g_label = f"'{guild.name}' ({guild_id})" if guild else str(guild_id)
            self.update_profile_db(guild_id, {"sync_status": "SYNCED", "last_error": None})
            logger.info(f"[ProfileService] Guild {g_label} profile successfully synced to Discord")
        except ProfileRateLimited as e:
            guild = getattr(self.bot, "get_guild", lambda _: None)(guild_id) if hasattr(self, "bot") and self.bot else None
            g_label = f"'{guild.name}' ({guild_id})" if guild else str(guild_id)
            self.update_profile_db(guild_id, {"sync_status": "PENDING", "last_error": str(e)})
            logger.warning(f"[ProfileService] Guild {g_label} hit Discord rate limit: {e}")
            if raise_on_error:
                raise
        except DiscordProfileError as e:
            guild = getattr(self.bot, "get_guild", lambda _: None)(guild_id) if hasattr(self, "bot") and self.bot else None
            g_label = f"'{guild.name}' ({guild_id})" if guild else str(guild_id)
            self.update_profile_db(guild_id, {"sync_status": "ERROR", "last_error": str(e)})
            logger.error(f"[ProfileService] Guild {g_label} profile sync failed: {e}")
            if raise_on_error:
                raise
        except Exception as e:
            guild = getattr(self.bot, "get_guild", lambda _: None)(guild_id) if hasattr(self, "bot") and self.bot else None
            g_label = f"'{guild.name}' ({guild_id})" if guild else str(guild_id)
            self.update_profile_db(guild_id, {"sync_status": "ERROR", "last_error": str(e)})
            logger.error(f"[ProfileService] Unexpected error syncing guild {g_label}: {e}")
            if raise_on_error:
                raise
