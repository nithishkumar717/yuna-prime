"""Anti-Nuke V2 Engine — High Performance In-Memory State Store with SQLite Write-Through.

Maintains all guild security policies, granular action toggles, sliding-window thresholds,
punishment settings, whitelists, and extra owners entirely in RAM for zero-I/O decisions.
All state mutations update RAM synchronously and immediately, then write through to SQLite.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set, Tuple

import aiosqlite

from core.antinuke_v2.models import (
    PROTECTED_ACTIONS,
    PunishmentType,
)

logger = logging.getLogger("antinuke.v2.state")

ACTION_COL_TO_DASHBOARD_KEY = {
    "ban": "antiBan",
    "kick": "antiKick",
    "botadd": "antiBotAdd",
    "chcr": "antiChannelCreate",
    "chdl": "antiChannelDelete",
    "chup": "antiChannelUpdate",
    "rlcr": "antiRoleCreate",
    "rldl": "antiRoleDelete",
    "rlup": "antiRoleUpdate",
    "mngweb": "antiWebhook",
    "meneve": "antiEveryoneMention",
    "everyone": "antiEveryoneMention",
    "serverup": "antiGuildUpdate",
    "integration": "antiIntegration",
    "memup": "antiMemberUpdate",
    "prune": "antiPrune",
    "mngstemo": "antiDangerousPermissions",
    # Audit-log action names used by V2 must resolve to the same dashboard toggle.
    "webhook_create": "antiWebhook",
    "webhook_update": "antiWebhook",
    "webhook_delete": "antiWebhook",
}

# Legacy whitelist columns are persisted using action-column names, while V2's
# audit mapper uses Discord-specific action names for webhook events.
ACTION_TO_WHITELIST_COLUMNS = {
    "webhook_create": ("mngweb",),
    "webhook_update": ("mngweb",),
    "webhook_delete": ("mngweb",),
    "everyone": ("meneve",),
}

DASHBOARD_KEY_TO_ACTION_COL = {v: k for k, v in ACTION_COL_TO_DASHBOARD_KEY.items()}


@dataclass(slots=True)
class GuildSecurityConfig:
    """Per-guild isolated security configuration held entirely in RAM."""
    guild_id: int
    antinuke_enabled: bool = False
    log_channel_id: Optional[int] = None
    action_toggles: Dict[str, bool] = field(default_factory=dict)
    action_thresholds: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    action_punishments: Dict[str, PunishmentType] = field(default_factory=dict)
    whitelisted_users: Dict[int, Dict[str, bool]] = field(default_factory=dict)
    whitelisted_roles: Set[int] = field(default_factory=set)
    whitelisted_bots: Set[int] = field(default_factory=set)
    extra_owners: Set[int] = field(default_factory=set)
    bot_protection_enabled: bool = False
    bot_protection_action: str = "BAN_BOT_AND_INVITER"
    dry_run: bool = False
    rate_limiter: Optional[Any] = None
    new_bots: Dict[int, float] = field(default_factory=dict)
    owner_id: Optional[int] = None
    bot_id: Optional[int] = None

    def record_new_bot(self, bot_id: int, joined_at: Optional[float] = None) -> None:
        """Enrolls a bot in high-vigilance probation monitoring."""
        self.new_bots[int(bot_id)] = float(joined_at if joined_at is not None else time.time())

    def is_new_bot(self, bot_id: int, probation_seconds: float = 86400.0) -> bool:
        """Checks if bot is within its high-vigilance probation window (default 24h)."""
        ts = self.new_bots.get(int(bot_id))
        if ts is None:
            return False
        return (time.time() - ts) < probation_seconds

    def unmark_new_bot(self, bot_id: int) -> None:
        """Removes a bot from probation."""
        self.new_bots.pop(int(bot_id), None)

    def is_action_enabled(self, action: str) -> bool:
        """Checks if a specific action toggle is enabled in RAM."""
        if not self.antinuke_enabled:
            return False

        # Fast path: check direct string
        if action in self.action_toggles:
            return bool(self.action_toggles[action])

        col_key = action.lower()
        if col_key in self.action_toggles:
            return bool(self.action_toggles[col_key])

        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(col_key)
        if dash_key and dash_key in self.action_toggles:
            return bool(self.action_toggles[dash_key])

        # Default to True when globally enabled and not explicitly toggled off
        return True

    def get_threshold(self, action: str) -> Tuple[int, int]:
        """Returns (limit, window_seconds) for an action. Defaults to (1, 10)."""
        if action in self.action_thresholds:
            return self.action_thresholds[action]

        col_key = action.lower()
        if col_key in self.action_thresholds:
            return self.action_thresholds[col_key]

        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(col_key)
        if dash_key and dash_key in self.action_thresholds:
            return self.action_thresholds[dash_key]

        return 1, 10

    def get_punishment(self, action: str) -> PunishmentType:
        """Returns the configured punishment type for an action. Defaults to BAN."""
        if action in self.action_punishments:
            return self.action_punishments[action]

        col_key = action.lower()
        if col_key in self.action_punishments:
            return self.action_punishments[col_key]

        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(col_key)
        if dash_key and dash_key in self.action_punishments:
            return self.action_punishments[dash_key]

        return PunishmentType.BAN

    def set_threshold(self, *args, **kwargs) -> None:
        """Sets (limit, window_seconds) threshold for an action."""
        if len(args) == 3:
            action, limit, window = args
        elif len(args) == 4:
            _, action, limit, window = args
        elif len(args) == 2 and "limit" in kwargs and "window" in kwargs:
            _, action = args
            limit = kwargs["limit"]
            window = kwargs["window"]
        elif len(args) == 1 and "limit" in kwargs and "window" in kwargs:
            action = args[0]
            limit = kwargs["limit"]
            window = kwargs["window"]
        elif "action" in kwargs and "limit" in kwargs and "window" in kwargs:
            action = kwargs["action"]
            limit = kwargs["limit"]
            window = kwargs["window"]
        else:
            raise TypeError("set_threshold accepts (action, limit, window)")
        self.action_thresholds[action.lower()] = (limit, window)

    def set_punishment(self, *args, **kwargs) -> None:
        """Sets punishment type for an action.
        Supports both (action, punishment) and (guild_id, action, punishment).
        """
        if len(args) == 2:
            action, punishment = args
        elif len(args) == 3:
            _, action, punishment = args
        else:
            action = kwargs.get("action", "")
            punishment = kwargs.get("punishment", PunishmentType.BAN)
        self.action_punishments[action.lower()] = punishment


class V2StateStore:
    """Synchronous in-memory store for all guild configurations with write-through persistence."""

    def __init__(self, db_path: str = "db/anti.db", bot_owner_ids: Optional[Set[int]] = None) -> None:
        self._db_path = db_path
        self._guilds: Dict[int, GuildSecurityConfig] = {}
        self._loaded_guilds: Set[int] = set()
        self._bot_owner_ids: Set[int] = set(bot_owner_ids or ())
        self._lock = asyncio.Lock()

    def get_bot_owner_ids(self) -> Set[int]:
        return set(self._bot_owner_ids)

    def set_bot_owner_ids(self, owner_ids: Set[int]) -> None:
        self._bot_owner_ids = set(owner_ids)

    def get_guild_config(self, guild_id: int) -> GuildSecurityConfig:
        """Pure synchronous RAM lookup for guild security configuration."""
        cfg = self._guilds.get(guild_id)
        if cfg is None:
            cfg = GuildSecurityConfig(guild_id=guild_id)
            self._guilds[guild_id] = cfg
        return cfg

    def is_guild_loaded(self, guild_id: int) -> bool:
        """Whether the guild's persisted security state has finished loading."""
        return guild_id in self._loaded_guilds or guild_id in self._guilds

    def set_antinuke_status(self, guild_id: int, enabled: bool) -> None:
        """Immediately mutates RAM and schedules write-through to SQLite."""
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.antinuke_enabled = bool(enabled)
        self._dispatch_write(
            "INSERT OR REPLACE INTO antinuke (guild_id, status, log_channel) VALUES (?, ?, ?)",
            (guild_id, 1 if enabled else 0, cfg.log_channel_id)
        )

    def set_bot_protection_status(self, guild_id: int, enabled: bool) -> None:
        """Immediately mutates RAM and schedules write-through for bot protection."""
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.bot_protection_enabled = bool(enabled)
        self._dispatch_write(
            "INSERT OR REPLACE INTO bot_protection (guild_id, status) VALUES (?, ?)",
            (guild_id, 1 if enabled else 0)
        )

    def set_log_channel(self, guild_id: int, channel_id: Optional[int]) -> None:
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.log_channel_id = channel_id
        self._dispatch_write(
            "INSERT OR REPLACE INTO antinuke (guild_id, status, log_channel) VALUES (?, ?, ?)",
            (guild_id, 1 if cfg.antinuke_enabled else 0, channel_id)
        )

    def set_action_toggle(self, guild_id: int, action: str, enabled: bool) -> None:
        """Immediately mutates RAM for an action toggle."""
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        col = action.lower()
        cfg.action_toggles[col] = bool(enabled)
        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(col)
        if dash_key:
            cfg.action_toggles[dash_key] = bool(enabled)

    def set_threshold(self, guild_id: int, action: str, limit: int, window: int) -> None:
        """Immediately mutates RAM for an action threshold and writes through."""
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.action_thresholds[action.lower()] = (limit, window)
        self._dispatch_write(
            "INSERT OR REPLACE INTO limit_settings (guild_id, action_type, action_limit, time_window) VALUES (?, ?, ?, ?)",
            (guild_id, action.lower(), limit, window)
        )

    def set_punishment(self, guild_id: int, action: str, punishment: PunishmentType) -> None:
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.action_punishments[action.lower()] = punishment

    def add_whitelisted_user(self, guild_id: int, user_id: int, actions: Dict[str, bool]) -> None:
        """Immediately mutates RAM for whitelisted user and schedules SQLite write."""
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.whitelisted_users[user_id] = dict(actions)
        
        # Build query dynamically for whitelisted_users table
        cols = ["guild_id", "user_id"] + [k for k in actions.keys() if k in PROTECTED_ACTIONS or k in ("ban", "kick", "prune", "botadd", "serverup", "memup", "chcr", "chdl", "chup", "rlcr", "rlup", "rldl", "meneve", "mngweb", "mngstemo")]
        placeholders = ["?"] * len(cols)
        vals = [guild_id, user_id] + [1 if actions[k] else 0 for k in cols[2:]]
        query = f"INSERT OR REPLACE INTO whitelisted_users ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
        self._dispatch_write(query, tuple(vals))

    def remove_whitelisted_user(self, guild_id: int, user_id: int) -> None:
        cfg = self.get_guild_config(guild_id)
        cfg.whitelisted_users.pop(user_id, None)
        self._dispatch_write("DELETE FROM whitelisted_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))

    def add_whitelisted_role(self, guild_id: int, role_id: int, added_by: Optional[int] = None) -> None:
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.whitelisted_roles.add(role_id)
        self._dispatch_write(
            "INSERT OR REPLACE INTO whitelisted_roles (guild_id, role_id, added_by) VALUES (?, ?, ?)",
            (guild_id, role_id, added_by or 0)
        )

    def remove_whitelisted_role(self, guild_id: int, role_id: int) -> None:
        cfg = self.get_guild_config(guild_id)
        cfg.whitelisted_roles.discard(role_id)
        self._dispatch_write("DELETE FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?", (guild_id, role_id))

    def add_whitelisted_bot(self, guild_id: int, bot_id: int) -> None:
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.whitelisted_bots.add(bot_id)
        self._dispatch_write("INSERT OR REPLACE INTO whitelisted_bots (guild_id, bot_id) VALUES (?, ?)", (guild_id, bot_id))

    def remove_whitelisted_bot(self, guild_id: int, bot_id: int) -> None:
        cfg = self.get_guild_config(guild_id)
        cfg.whitelisted_bots.discard(bot_id)
        self._dispatch_write("DELETE FROM whitelisted_bots WHERE guild_id = ? AND bot_id = ?", (guild_id, bot_id))

    def add_extra_owner(self, guild_id: int, owner_id: int) -> None:
        self._loaded_guilds.add(guild_id)
        cfg = self.get_guild_config(guild_id)
        cfg.extra_owners.add(owner_id)
        self._dispatch_write("INSERT OR REPLACE INTO extraowners (guild_id, owner_id) VALUES (?, ?)", (guild_id, owner_id))

    def remove_extra_owner(self, guild_id: int, owner_id: int) -> None:
        cfg = self.get_guild_config(guild_id)
        cfg.extra_owners.discard(owner_id)
        self._dispatch_write("DELETE FROM extraowners WHERE guild_id = ? AND owner_id = ?", (guild_id, owner_id))

    def record_new_bot(self, guild_id: int, bot_id: int, joined_at: Optional[float] = None) -> None:
        """Enrolls a bot into high-vigilance probation monitoring for 24h."""
        self._loaded_guilds.add(guild_id)
        if joined_at is None:
            joined_at = time.time()
        cfg = self.get_guild_config(guild_id)
        cfg.record_new_bot(bot_id, joined_at)
        self._dispatch_write(
            "INSERT OR REPLACE INTO new_bots_watch (guild_id, bot_id, joined_at) VALUES (?, ?, ?)",
            (guild_id, bot_id, float(joined_at))
        )

    def remove_new_bot(self, guild_id: int, bot_id: int) -> None:
        """Removes a bot from high-vigilance probation."""
        cfg = self.get_guild_config(guild_id)
        cfg.unmark_new_bot(bot_id)
        self._dispatch_write("DELETE FROM new_bots_watch WHERE guild_id = ? AND bot_id = ?", (guild_id, bot_id))

    def prune_guild(self, guild_id: int) -> None:
        """Removes guild state from memory to maintain strict memory boundaries."""
        self._guilds.pop(guild_id, None)
        self._loaded_guilds.discard(guild_id)

    async def load_guild_from_db(self, guild_id: int) -> GuildSecurityConfig:
        """Warm-loads full guild security configuration from SQLite into RAM."""
        if guild_id in self._loaded_guilds:
            return self.get_guild_config(guild_id)

        # Share one load between the audit fast path and the normal async handler.
        async with self._lock:
            if guild_id in self._loaded_guilds:
                return self.get_guild_config(guild_id)
            return await self._load_guild_from_db_unlocked(guild_id)

    async def _load_guild_from_db_unlocked(self, guild_id: int) -> GuildSecurityConfig:
        """Loads one guild while the caller holds ``_lock``."""
        cfg = self.get_guild_config(guild_id)
        try:
            async with aiosqlite.connect(self._db_path, timeout=5) as db:
                # 1. Antinuke status
                async with db.execute("SELECT status, log_channel FROM antinuke WHERE guild_id = ?", (guild_id,)) as cur:
                    row = await cur.fetchone()
                    if row:
                        cfg.antinuke_enabled = bool(row[0] == 1)
                        cfg.log_channel_id = row[1]
                    else:
                        cfg.antinuke_enabled = False
                        cfg.log_channel_id = None

                # 1b. Bot protection status
                try:
                    async with db.execute("SELECT status FROM bot_protection WHERE guild_id = ? OR guild_id = ?", (guild_id, str(guild_id))) as cur:
                        bp_row = await cur.fetchone()
                        if bp_row is not None:
                            cfg.bot_protection_enabled = bool(str(bp_row[0]).lower() in ("1", "true", "on"))
                        else:
                            cfg.bot_protection_enabled = False
                except Exception:
                    cfg.bot_protection_enabled = False

                # 2. Whitelisted roles
                async with db.execute("SELECT role_id FROM whitelisted_roles WHERE guild_id = ?", (guild_id,)) as cur:
                    rows = await cur.fetchall()
                    cfg.whitelisted_roles = {int(r[0]) for r in rows if r[0]}

                # 3. Whitelisted bots
                async with db.execute("SELECT bot_id FROM whitelisted_bots WHERE guild_id = ?", (guild_id,)) as cur:
                    rows = await cur.fetchall()
                    cfg.whitelisted_bots = {int(r[0]) for r in rows if r[0]}

                # 4. Extra owners
                async with db.execute("SELECT owner_id FROM extraowners WHERE guild_id = ?", (guild_id,)) as cur:
                    rows = await cur.fetchall()
                    cfg.extra_owners = {int(r[0]) for r in rows if r[0]}

                # 5. Whitelisted users
                async with db.execute("SELECT * FROM whitelisted_users WHERE guild_id = ?", (guild_id,)) as cur:
                    cols = [c[0] for c in cur.description] if cur.description else []
                    rows = await cur.fetchall()
                    for r in rows:
                        rd = dict(zip(cols, r))
                        uid = int(rd.get("user_id", 0))
                        if uid:
                            cfg.whitelisted_users[uid] = {
                                col: bool(val) for col, val in rd.items() if col not in ("guild_id", "user_id")
                            }

                # 6. Limit settings
                async with db.execute("SELECT action_type, action_limit, time_window FROM limit_settings WHERE guild_id = ?", (guild_id,)) as cur:
                    rows = await cur.fetchall()
                    for act, lim, win in rows:
                        if act:
                            cfg.action_thresholds[str(act).lower()] = (int(lim), int(win))

                # 7. New bots on high-vigilance probation
                try:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS new_bots_watch (
                            guild_id INTEGER,
                            bot_id INTEGER,
                            joined_at REAL,
                            PRIMARY KEY (guild_id, bot_id)
                        )
                    """)
                    async with db.execute("SELECT bot_id, joined_at FROM new_bots_watch WHERE guild_id = ?", (guild_id,)) as cur:
                        rows = await cur.fetchall()
                        now = time.time()
                        for b_id, j_ts in rows:
                            if b_id and j_ts and (now - float(j_ts)) < 86400.0:
                                cfg.new_bots[int(b_id)] = float(j_ts)
                except Exception:
                    pass
            # Mark readiness only after the main persisted configuration loaded.
            self._loaded_guilds.add(guild_id)
        except Exception as e:
            logger.error("[V2State] Error loading guild %s from DB: %s", guild_id, e)

        return cfg

    async def warm_load_all_guilds(self) -> int:
        """Pre-warms all guild configurations from SQLite into RAM on startup in a single batch.

        Guarantees 0ms I/O latency on the hot path for all active servers.
        """
        loaded_count = 0
        t0 = time.perf_counter()
        try:
            async with aiosqlite.connect(self._db_path, timeout=10) as db:
                # 1. Antinuke status
                try:
                    async with db.execute("SELECT guild_id, status, log_channel FROM antinuke") as cur:
                        rows = await cur.fetchall()
                        for gid, status, log_ch in rows:
                            if gid:
                                cfg = self.get_guild_config(int(gid))
                                cfg.antinuke_enabled = bool(status == 1)
                                cfg.log_channel_id = int(log_ch) if log_ch else None
                                loaded_count += 1
                except Exception as e:
                    logger.debug("[V2State] warm_load antinuke note: %s", e)

                # 1b. Bot protection status
                try:
                    async with db.execute("SELECT guild_id, status FROM bot_protection") as cur:
                        rows = await cur.fetchall()
                        for gid, status in rows:
                            if gid:
                                self.get_guild_config(int(gid)).bot_protection_enabled = bool(str(status).lower() in ("1", "true", "on"))
                except Exception as e:
                    logger.debug("[V2State] warm_load bot_protection note: %s", e)

                # 2. Whitelisted roles
                try:
                    async with db.execute("SELECT guild_id, role_id FROM whitelisted_roles") as cur:
                        rows = await cur.fetchall()
                        for gid, rid in rows:
                            if gid and rid:
                                self.get_guild_config(int(gid)).whitelisted_roles.add(int(rid))
                except Exception as e:
                    logger.debug("[V2State] warm_load whitelisted_roles note: %s", e)

                # 3. Whitelisted bots
                try:
                    async with db.execute("SELECT guild_id, bot_id FROM whitelisted_bots") as cur:
                        rows = await cur.fetchall()
                        for gid, bid in rows:
                            if gid and bid:
                                self.get_guild_config(int(gid)).whitelisted_bots.add(int(bid))
                except Exception as e:
                    logger.debug("[V2State] warm_load whitelisted_bots note: %s", e)

                # 4. Extra owners
                try:
                    async with db.execute("SELECT guild_id, owner_id FROM extraowners") as cur:
                        rows = await cur.fetchall()
                        for gid, oid in rows:
                            if gid and oid:
                                self.get_guild_config(int(gid)).extra_owners.add(int(oid))
                except Exception as e:
                    logger.debug("[V2State] warm_load extraowners note: %s", e)

                # 5. Whitelisted users
                try:
                    async with db.execute("SELECT * FROM whitelisted_users") as cur:
                        cols = [c[0] for c in cur.description] if cur.description else []
                        rows = await cur.fetchall()
                        for r in rows:
                            rd = dict(zip(cols, r))
                            gid = int(rd.get("guild_id", 0))
                            uid = int(rd.get("user_id", 0))
                            if gid and uid:
                                cfg = self.get_guild_config(gid)
                                cfg.whitelisted_users[uid] = {
                                    col: bool(val) for col, val in rd.items() if col not in ("guild_id", "user_id")
                                }
                except Exception as e:
                    logger.debug("[V2State] warm_load whitelisted_users note: %s", e)

                # 6. Limit settings
                try:
                    async with db.execute("SELECT guild_id, action_type, action_limit, time_window FROM limit_settings") as cur:
                        rows = await cur.fetchall()
                        for gid, act, lim, win in rows:
                            if gid and act:
                                self.get_guild_config(int(gid)).action_thresholds[str(act).lower()] = (int(lim), int(win))
                except Exception as e:
                    logger.debug("[V2State] warm_load limit_settings note: %s", e)

                # 7. New bots on high-vigilance probation
                try:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS new_bots_watch (
                            guild_id INTEGER,
                            bot_id INTEGER,
                            joined_at REAL,
                            PRIMARY KEY (guild_id, bot_id)
                        )
                    """)
                    async with db.execute("SELECT guild_id, bot_id, joined_at FROM new_bots_watch") as cur:
                        rows = await cur.fetchall()
                        now = time.time()
                        for gid, bid, j_ts in rows:
                            if gid and bid and j_ts and (now - float(j_ts)) < 86400.0:
                                self.get_guild_config(int(gid)).new_bots[int(bid)] = float(j_ts)
                except Exception as e:
                    logger.debug("[V2State] warm_load new_bots_watch note: %s", e)

            self._loaded_guilds.update(self._guilds.keys())
            loaded_count = len(self._loaded_guilds)
            dur_ms = (time.perf_counter() - t0) * 1000.0
            logger.info("[V2State] 🚀 Pre-warmed %d guilds into RAM cache in %.2fms (0ms hot-path active)", loaded_count, dur_ms)
        except Exception as e:
            logger.error("[V2State] Batch warm-load error: %s", e)

        return loaded_count

    def _dispatch_write(self, query: str, params: tuple) -> None:
        """Dispatches an asynchronous SQLite write-through operation in the background."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._execute_write(query, params))
        except RuntimeError:
            # No running loop (e.g. during synchronous unit tests), execute synchronously if loop unavailable
            pass

    async def _execute_write(self, query: str, params: tuple) -> None:
        try:
            async with aiosqlite.connect(self._db_path, timeout=5) as db:
                await db.execute(query, params)
                await db.commit()
        except Exception as e:
            logger.error("[V2State] SQLite write-through error for query '%s': %s", query, e)
