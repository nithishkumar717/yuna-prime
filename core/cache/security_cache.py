import asyncio
import aiosqlite
from typing import Any, Dict, List, Optional, Set
from utils.settings_manager import settings
from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER, OWNER_IDS, SIBLING_BOT_IDS, is_sibling_bot

GLOBAL_BOT_OWNER_SET: Set[int] = {PRIMARY_BOT_OWNER, 1048900823314354197}
if OWNER_IDS:
    GLOBAL_BOT_OWNER_SET.update(int(x) for x in OWNER_IDS if str(x).isdigit())
if GLOBAL_OWNER_IDS:
    GLOBAL_BOT_OWNER_SET.update(int(x) for x in GLOBAL_OWNER_IDS if str(x).isdigit())



ACTION_COL_TO_DASHBOARD_KEY: Dict[str, str] = {
    "ban": "antiBan",
    "antiban": "antiBan",
    "kick": "antiKick",
    "antikick": "antiKick",
    "botadd": "antiBotAdd",
    "antibotadd": "antiBotAdd",
    "bot": "antiBotAdd",
    "chcr": "antiChannelCreate",
    "antichcr": "antiChannelCreate",
    "channel_create": "antiChannelCreate",
    "channelcreate": "antiChannelCreate",
    "chdl": "antiChannelDelete",
    "antichdl": "antiChannelDelete",
    "channel_delete": "antiChannelDelete",
    "channeldelete": "antiChannelDelete",
    "chup": "antiChannelUpdate",
    "antichup": "antiChannelUpdate",
    "channel_update": "antiChannelUpdate",
    "channelupdate": "antiChannelUpdate",
    "rlcr": "antiRoleCreate",
    "antirlcr": "antiRoleCreate",
    "role_create": "antiRoleCreate",
    "rolecreate": "antiRoleCreate",
    "rldl": "antiRoleDelete",
    "antirldl": "antiRoleDelete",
    "role_delete": "antiRoleDelete",
    "roledelete": "antiRoleDelete",
    "rlup": "antiRoleUpdate",
    "antirlup": "antiRoleUpdate",
    "role_update": "antiRoleUpdate",
    "roleupdate": "antiRoleUpdate",
    "mngweb": "antiWebhook",
    "webhook": "antiWebhook",
    "antiwebhook": "antiWebhook",
    "webhook_update": "antiWebhook",
    "webhook_create": "antiWebhook",
    "webhook_delete": "antiWebhook",
    "serverup": "antiGuildUpdate",
    "antiguild": "antiGuildUpdate",
    "guild": "antiGuildUpdate",
    "guildupdate": "antiGuildUpdate",
    "server": "antiGuildUpdate",
    "integration": "antiIntegration",
    "antiintegration": "antiIntegration",
    "memup": "antiMemberUpdate",
    "antimemberupdate": "antiMemberUpdate",
    "member_update": "antiMemberUpdate",
    "memberupdate": "antiMemberUpdate",
    "prune": "antiPrune",
    "antiprune": "antiPrune",
    "everyone": "antiEveryoneMention",
    "antieveryone": "antiEveryoneMention",
    "mention": "antiEveryoneMention",
    "dangerous_permissions": "antiDangerousPermissions",
    "antidangerouspermissions": "antiDangerousPermissions",
}


class SecurityStateCache:
    """Zero-Latency In-Memory Cache for Guild Security Settings and Anti-Nuke Permissions.
    
    Provides instant O(1) synchronous lookups for AntiNuke status, granular Whitelists,
    ExtraOwners, individual action toggles, and AutoMod settings without disk or network I/O on the hot path.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecurityStateCache, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._antinuke: Dict[int, bool] = {}
        self._antinuke_actions: Dict[int, Dict[str, bool]] = {}
        self._automod: Dict[int, bool] = {}
        self._bot_protection: Dict[int, bool] = {}
        self._whitelisted_bots: Dict[int, Set[int]] = {}
        self._extraowners: Dict[int, Set[int]] = {}
        self._whitelists: Dict[int, Dict[int, Dict[str, bool]]] = {}
        self._whitelisted_roles: Dict[int, Set[int]] = {}
        self._loaded_guilds: Set[int] = set()
        self._lock = asyncio.Lock()
        self._initialized = True

    async def warm_all_guilds(self, guilds=None):
        """Batch pre-loads all guilds' security configurations into memory in single bulk SQL queries."""
        async with self._lock:
            try:
                async with aiosqlite.connect('db/anti.db', timeout=5) as db:
                    # 1. Antinuke status
                    try:
                        async with db.execute("SELECT guild_id, status FROM antinuke") as cursor:
                            rows = await cursor.fetchall()
                            for gid, status in rows:
                                self._antinuke[int(gid)] = bool(status == 1)
                    except Exception:
                        pass

                    # 2. Bot protection
                    try:
                        async with db.execute("SELECT guild_id, status FROM bot_protection") as cursor:
                            rows = await cursor.fetchall()
                            for gid, status in rows:
                                self._bot_protection[int(gid)] = bool(str(status).lower() in ("1", "true", "on"))
                    except Exception:
                        pass

                    # 3. Whitelisted bots
                    try:
                        async with db.execute("SELECT guild_id, bot_id FROM whitelisted_bots") as cursor:
                            rows = await cursor.fetchall()
                            for gid, bot_id in rows:
                                gid_int = int(gid)
                                if gid_int not in self._whitelisted_bots:
                                    self._whitelisted_bots[gid_int] = set()
                                if bot_id:
                                    self._whitelisted_bots[gid_int].add(int(bot_id))
                            for gid_set in self._whitelisted_bots.values():
                                gid_set.update(SIBLING_BOT_IDS)
                    except Exception:
                        pass


                    # 4. Extra owners
                    try:
                        async with db.execute("SELECT guild_id, owner_id FROM extraowners") as cursor:
                            rows = await cursor.fetchall()
                            for gid, owner_id in rows:
                                gid_int = int(gid)
                                if gid_int not in self._extraowners:
                                    self._extraowners[gid_int] = set()
                                if owner_id:
                                    self._extraowners[gid_int].add(int(owner_id))
                    except Exception:
                        pass

                    # 5. Whitelisted roles
                    try:
                        await db.execute("""
                            CREATE TABLE IF NOT EXISTS whitelisted_roles (
                                guild_id INTEGER, role_id INTEGER, added_by INTEGER, PRIMARY KEY (guild_id, role_id)
                            )
                        """)
                        async with db.execute("SELECT guild_id, role_id FROM whitelisted_roles") as cursor:
                            rows = await cursor.fetchall()
                            for gid, role_id in rows:
                                gid_int = int(gid)
                                if gid_int not in self._whitelisted_roles:
                                    self._whitelisted_roles[gid_int] = set()
                                if role_id:
                                    self._whitelisted_roles[gid_int].add(int(role_id))
                    except Exception:
                        pass

                    # 6. Whitelisted users
                    try:
                        async with db.execute("SELECT * FROM whitelisted_users") as cursor:
                            columns = [col[0] for col in cursor.description] if cursor.description else []
                            rows = await cursor.fetchall()
                            for r in rows:
                                row_dict = dict(zip(columns, r))
                                gid = int(row_dict.get("guild_id", 0))
                                uid = int(row_dict.get("user_id", 0))
                                if gid and uid:
                                    if gid not in self._whitelists:
                                        self._whitelists[gid] = {}
                                    self._whitelists[gid][uid] = {
                                        col: bool(val) for col, val in row_dict.items() if col not in ("guild_id", "user_id")
                                    }
                    except Exception:
                        pass

                # Mark all connected guilds (or guilds found in db) as loaded
                if guilds:
                    for g in guilds:
                        gid = getattr(g, "id", g)
                        self._loaded_guilds.add(int(gid))
                for gid in list(self._antinuke.keys()):
                    self._loaded_guilds.add(gid)
            except Exception:
                pass

    async def warm_guild(self, guild_id: int):
        """Pre-loads a guild's security configuration into memory from SQLite if not already loaded."""
        if guild_id in self._loaded_guilds:
            return

        async with self._lock:
            if guild_id in self._loaded_guilds:
                return
            try:
                async with aiosqlite.connect('db/anti.db', timeout=2) as db:
                    # 1. Antinuke status
                    async with db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild_id,)) as cursor:
                        row = await cursor.fetchone()
                        self._antinuke[guild_id] = bool(row and row[0] == 1)

                    # 1b. Antinuke individual action toggles
                    stored_actions = settings.get_guild_setting(guild_id, "antinuke_actions", default={}) or {}
                    if isinstance(stored_actions, dict):
                        self._antinuke_actions[guild_id] = {str(k): bool(v) for k, v in stored_actions.items()}
                    else:
                        self._antinuke_actions[guild_id] = {}

                    # 2. Bot protection status (Strictly independent; never inherits antinuke status)
                    try:
                        async with db.execute("SELECT status FROM bot_protection WHERE guild_id = ? OR guild_id = ?", (guild_id, str(guild_id))) as cursor:
                            bp_row = await cursor.fetchone()
                            if bp_row is not None:
                                self._bot_protection[guild_id] = bool(str(bp_row[0]).lower() in ("1", "true", "on"))
                            else:
                                self._bot_protection[guild_id] = False
                    except Exception:
                        self._bot_protection[guild_id] = False

                    # 3. Whitelisted bots
                    try:
                        async with db.execute("SELECT bot_id FROM whitelisted_bots WHERE guild_id = ? OR guild_id = ?", (guild_id, str(guild_id))) as cursor:
                            wb_rows = await cursor.fetchall()
                            self._whitelisted_bots[guild_id] = {int(r[0]) for r in wb_rows if r[0]}
                    except Exception:
                        self._whitelisted_bots[guild_id] = set()
                    self._whitelisted_bots[guild_id].update(SIBLING_BOT_IDS)


                    # 4. Extra owners
                    async with db.execute("SELECT owner_id FROM extraowners WHERE guild_id = ?", (guild_id,)) as cursor:
                        rows = await cursor.fetchall()
                        self._extraowners[guild_id] = {int(r[0]) for r in rows if r[0]}

                    # 5. Whitelisted roles
                    try:
                        await db.execute("""
                            CREATE TABLE IF NOT EXISTS whitelisted_roles (
                                guild_id INTEGER, role_id INTEGER, added_by INTEGER, PRIMARY KEY (guild_id, role_id)
                            )
                        """)
                        async with db.execute("SELECT role_id FROM whitelisted_roles WHERE guild_id = ?", (guild_id,)) as cursor:
                            rows = await cursor.fetchall()
                            self._whitelisted_roles[guild_id] = {int(r[0]) for r in rows if r[0]}
                    except Exception:
                        self._whitelisted_roles[guild_id] = set()

                    # 6. Whitelisted users
                    if guild_id not in self._whitelists:
                        self._whitelists[guild_id] = {}
                    async with db.execute("SELECT * FROM whitelisted_users WHERE guild_id = ?", (guild_id,)) as cursor:
                        columns = [col[0] for col in cursor.description] if cursor.description else []
                        rows = await cursor.fetchall()
                        for r in rows:
                            row_dict = dict(zip(columns, r))
                            u_id = int(row_dict.get("user_id", 0))
                            if u_id:
                                self._whitelists[guild_id][u_id] = {
                                    col: bool(val) for col, val in row_dict.items() if col not in ("guild_id", "user_id")
                                }

                self._loaded_guilds.add(guild_id)
            except Exception:
                pass

            # 7. AutoMod status (separate db, isolated try block so anti.db loading is unaffected)
            try:
                async with aiosqlite.connect('db/automod.db', timeout=2) as am_db:
                    async with am_db.execute("SELECT enabled FROM automod WHERE guild_id = ?", (guild_id,)) as cursor:
                        am_row = await cursor.fetchone()
                        if am_row is not None:
                            self._automod[guild_id] = bool(am_row[0] == 1)
                        else:
                            self._automod[guild_id] = False
            except Exception:
                # If automod.db doesn't exist yet or is locked, fall back to SettingsManager
                if guild_id not in self._automod:
                    self._automod[guild_id] = bool(
                        settings.get_guild_setting(guild_id, "automod", default=False)
                    )

            # 8. Synchronize V2 State Store
            try:
                from core.antinuke_v2.router import v2_engine_router
                await v2_engine_router.coordinator.state_store.load_guild_from_db(guild_id)
            except Exception:
                pass

    def is_immune(self, guild, executor) -> bool:
        """Immediate zero-latency check if executor is permanently immune (Guild Owner, Bot itself, Sibling Bots, Global Bot Owner, or Extra Owner)."""
        if not guild or not executor:
            return True
        exec_id = getattr(executor, 'id', None)
        if exec_id in SIBLING_BOT_IDS:
            return True
        bot_id = guild.me.id if (guild.me and hasattr(guild.me, 'id')) else 0
        if exec_id in (guild.owner_id, bot_id) or exec_id in GLOBAL_BOT_OWNER_SET:
            return True
        if self.is_extra_owner(guild.id, exec_id):
            return True
        return False

    async def check_executor_permission(self, guild, executor, action_col: str = "ban") -> bool:
        """Zero-latency in-memory check for Anti-Nuke executor permissions.
        
        Evaluated 100% in RAM (<0.05ms) with zero blocking disk or network I/O on the hot path.
        Returns True if the action is ALLOWED.
        Returns False if the action is UNAUTHORIZED and must be neutralized immediately.
        """
        if self.is_immune(guild, executor):
            return True

        gid = getattr(guild, "id", None)
        if not gid:
            return True

        # Ensure guild security cache is warmed (O(1) set membership)
        if gid not in self._loaded_guilds:
            await self.warm_guild(gid)

        # 1. Fast check: Is Anti-Nuke enabled for this guild?
        is_an_on = self._antinuke.get(gid)
        if is_an_on is None:
            is_an_on = bool(settings.get_guild_setting(gid, "antinuke", default=False))
            self._antinuke[gid] = is_an_on

        if not is_an_on:
            return True

        # 1b. Fast check: Is this specific action option enabled on Dashboard?
        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(action_col.lower(), action_col)
        guild_actions = self.get_antinuke_actions(gid)
        if guild_actions and dash_key in guild_actions:
            if guild_actions[dash_key] is False:
                return True  # Action is turned OFF on the Dashboard -> Allowed / Skip penalty!

        # 1c. Bot check: Whitelisted bots and Sibling bots are allowed; unauthorized bots are instantly banned!
        if getattr(executor, 'bot', False):
            if executor.id in SIBLING_BOT_IDS:
                return True
            wl_bots = self._whitelisted_bots.get(gid, set())
            if executor.id in wl_bots:
                return True
            return False

        # 2. Fast check: Is executor an Extra Owner?
        extra_owners = self._extraowners.get(gid, set())
        if executor.id in extra_owners:
            return True


        setting_eo = settings.get_guild_setting(gid, "extraowner", default=None)
        if setting_eo and str(executor.id) == str(setting_eo):
            return True

        # 3. Fast check: Whitelisted User / Member in memory (<0.001ms dictionary lookup)
        guild_wl = self._whitelists.get(gid, {})
        exec_id_int = int(executor.id) if str(executor.id).isdigit() else 0
        exec_id_str = str(executor.id)

        if exec_id_int in guild_wl or exec_id_str in guild_wl:
            user_wl = guild_wl.get(exec_id_int) or guild_wl.get(exec_id_str) or {}
            if not user_wl or user_wl.get("all", False) or user_wl.get(action_col, False) or user_wl.get(dash_key, False) or any(user_wl.values()):
                return True

        # Fallback check: General whitelist in settings manager
        general_wl = settings.get_guild_setting(gid, "whitelist", default=[]) or []
        general_wl_strs = {str(x) for x in general_wl}
        if exec_id_str in general_wl_strs or exec_id_int in general_wl:
            return True

        # 4. Fast check: Whitelisted Role or Exempt Role
        wl_roles = self._whitelisted_roles.get(gid, set())
        setting_wl_roles = set(settings.get_guild_setting(gid, "whitelist_roles", default=[]) or [])
        setting_exempt_roles = set(settings.get_guild_setting(gid, "exempt_roles", default=[]) or [])
        all_wl_roles = wl_roles.union({int(r) for r in setting_wl_roles if str(r).isdigit()}).union({int(r) for r in setting_exempt_roles if str(r).isdigit()})

        # Only evaluate roles if guild actually has whitelisted roles defined
        if all_wl_roles:
            all_wl_roles_str = {str(r) for r in all_wl_roles}
            member = executor if hasattr(executor, 'roles') else guild.get_member(executor.id)
            if member and hasattr(member, 'roles'):
                for role in member.roles:
                    if role.id in all_wl_roles or str(role.id) in all_wl_roles_str:
                        return True

        # Unauthorized executor!
        return False

    def is_executor_allowed_sync(self, guild, executor, action_col: str = "ban") -> bool:
        """Synchronous zero-latency in-memory check for Anti-Nuke executor permissions.
        
        Evaluated 100% in RAM (<0.005ms) with zero asyncio awaits or context switches.
        Returns True if the executor is immune or whitelisted (safe).
        Returns False if the action is unauthorized and the executor is an attacker.
        """
        if self.is_immune(guild, executor):
            return True

        gid = getattr(guild, "id", None)
        if not gid:
            return True

        # Fast check: Is Anti-Nuke enabled for this guild?
        is_an_on = self._antinuke.get(gid)
        if is_an_on is None:
            is_an_on = bool(settings.get_guild_setting(gid, "antinuke", default=False))
            self._antinuke[gid] = is_an_on

        if not is_an_on:
            return True

        # Fast check: Is this specific action enabled on Dashboard?
        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(action_col.lower(), action_col)
        guild_actions = self.get_antinuke_actions(gid)
        if guild_actions and dash_key in guild_actions:
            if guild_actions[dash_key] is False:
                return True

        # Fast check: Whitelisted bots and Sibling bots
        if getattr(executor, 'bot', False):
            if executor.id in SIBLING_BOT_IDS:
                return True
            wl_bots = self._whitelisted_bots.get(gid, set())
            if executor.id in wl_bots:
                return True
            return False


        # Fast check: Extra Owners
        if executor.id in self._extraowners.get(gid, set()):
            return True

        setting_eo = settings.get_guild_setting(gid, "extraowner", default=None)
        if setting_eo and str(executor.id) == str(setting_eo):
            return True

        # Fast check: Whitelisted Users
        guild_wl = self._whitelists.get(gid, {})
        exec_id_int = int(executor.id) if str(executor.id).isdigit() else 0
        exec_id_str = str(executor.id)

        if exec_id_int in guild_wl or exec_id_str in guild_wl:
            user_wl = guild_wl.get(exec_id_int) or guild_wl.get(exec_id_str) or {}
            if not user_wl or user_wl.get("all", False) or user_wl.get(action_col, False) or user_wl.get(dash_key, False) or any(user_wl.values()):
                return True

        # Fast check: Whitelisted Roles
        wl_roles = self._whitelisted_roles.get(gid, set())
        if wl_roles:
            member = executor if hasattr(executor, 'roles') else guild.get_member(executor.id)
            if member and hasattr(member, 'roles'):
                for role in member.roles:
                    if role.id in wl_roles:
                        return True

        return False

    def is_antinuke_enabled(self, guild_id: int | str) -> bool:
        """Returns True if AntiNuke is enabled for guild."""
        gid = int(guild_id)
        if gid in self._antinuke:
            return self._antinuke[gid]
        return bool(settings.get_guild_setting(guild_id, "antinuke", default=False))

    def get_antinuke_actions(self, guild_id: int | str) -> Dict[str, bool]:
        """Returns the dictionary of granular action toggles for a guild."""
        gid = int(guild_id)
        if gid in self._antinuke_actions:
            return self._antinuke_actions[gid]
        stored = settings.get_guild_setting(gid, "antinuke_actions", default={}) or {}
        if isinstance(stored, dict):
            actions = {str(k): bool(v) for k, v in stored.items()}
            self._antinuke_actions[gid] = actions
            return actions
        return {}

    def is_action_enabled(self, guild_id: int | str, action_col_or_name: str) -> bool:
        """Returns True if the specific anti-nuke action is enabled on the dashboard."""
        gid = int(guild_id)
        if not self.is_antinuke_enabled(gid):
            return False

        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(action_col_or_name.lower(), action_col_or_name)
        actions = self.get_antinuke_actions(gid)
        if actions and dash_key in actions:
            return bool(actions[dash_key])

        return True

    def set_action_status(self, guild_id: int | str, action_name: str, enabled: bool):
        """Updates a single action toggle in the memory cache and settings."""
        gid = int(guild_id)
        if gid not in self._antinuke_actions:
            self._antinuke_actions[gid] = {}
        self._antinuke_actions[gid][action_name] = bool(enabled)
        curr = settings.get_guild_setting(gid, "antinuke_actions", default={}) or {}
        if not isinstance(curr, dict):
            curr = {}
        curr[action_name] = bool(enabled)
        settings.set_guild_setting(gid, "antinuke_actions", curr)

    def set_all_actions(self, guild_id: int | str, actions_dict: Dict[str, bool]):
        """Updates all action toggles in the memory cache and settings."""
        gid = int(guild_id)
        cleaned = {str(k): bool(v) for k, v in actions_dict.items()}
        self._antinuke_actions[gid] = cleaned
        settings.set_guild_setting(gid, "antinuke_actions", cleaned)

    def set_antinuke_status(self, guild_id: int | str, enabled: bool):
        """Updates the in-memory AntiNuke status for a guild."""
        gid = int(guild_id)
        self._antinuke[gid] = enabled
        self._loaded_guilds.add(gid)
        settings.set_guild_setting(guild_id, "antinuke", enabled)

    def add_extra_owner(self, guild_id: int | str, owner_id: int | str):
        """Adds an extra owner to memory cache."""
        gid = int(guild_id)
        oid = int(owner_id)
        if gid not in self._extraowners:
            self._extraowners[gid] = set()
        self._extraowners[gid].add(oid)
        self._loaded_guilds.add(gid)
        settings.set_guild_setting(guild_id, "extraowner", str(owner_id))

    def remove_extra_owner(self, guild_id: int | str, owner_id: Optional[int | str] = None):
        """Removes an extra owner from memory cache."""
        gid = int(guild_id)
        if gid in self._extraowners:
            if owner_id is not None:
                try:
                    self._extraowners[gid].discard(int(owner_id))
                except (ValueError, TypeError):
                    pass
            else:
                self._extraowners[gid].clear()
        settings.set_guild_setting(guild_id, "extraowner", None)

    def set_whitelist_permission(self, guild_id: int | str, user_id: int | str, action_col: str, enabled: bool):
        """Sets a granular whitelist permission in memory cache and settings."""
        gid = int(guild_id)
        uid = int(user_id)
        if gid not in self._whitelists:
            self._whitelists[gid] = {}
        if uid not in self._whitelists[gid]:
            self._whitelists[gid][uid] = {}
        self._whitelists[gid][uid][action_col] = enabled
        self._loaded_guilds.add(gid)
        # Sync to settings_manager
        current_wl = settings.get_guild_setting(gid, "whitelist", default=[]) or []
        if str(uid) not in [str(u) for u in current_wl]:
            current_wl.append(str(uid))
            settings.set_guild_setting(gid, "whitelist", current_wl)

    def remove_whitelist_user(self, guild_id: int | str, user_id: int | str):
        """Removes a user from the whitelist cache and settings."""
        gid = int(guild_id)
        uid = int(user_id)
        if gid in self._whitelists and uid in self._whitelists[gid]:
            del self._whitelists[gid][uid]
        # Sync to settings_manager
        current_wl = settings.get_guild_setting(gid, "whitelist", default=[]) or []
        current_wl = [u for u in current_wl if str(u) != str(uid)]
        settings.set_guild_setting(gid, "whitelist", current_wl)

    def add_whitelisted_role(self, guild_id: int | str, role_id: int | str):
        """Adds a whitelisted role to memory cache and settings."""
        gid = int(guild_id)
        rid = int(role_id)
        if gid not in self._whitelisted_roles:
            self._whitelisted_roles[gid] = set()
        self._whitelisted_roles[gid].add(rid)
        self._loaded_guilds.add(gid)
        # Sync to settings_manager
        current_roles = settings.get_guild_setting(gid, "whitelist_roles", default=[]) or []
        if str(rid) not in [str(r) for r in current_roles]:
            current_roles.append(str(rid))
            settings.set_guild_setting(gid, "whitelist_roles", current_roles)

    def remove_whitelisted_role(self, guild_id: int | str, role_id: int | str):
        """Removes a whitelisted role from memory cache and settings."""
        gid = int(guild_id)
        rid = int(role_id)
        if gid in self._whitelisted_roles:
            self._whitelisted_roles[gid].discard(rid)
        # Sync to settings_manager
        current_roles = settings.get_guild_setting(gid, "whitelist_roles", default=[]) or []
        current_roles = [r for r in current_roles if str(r) != str(rid)]
        settings.set_guild_setting(gid, "whitelist_roles", current_roles)

    def reset_whitelisted_roles(self, guild_id: int | str):
        """Resets all whitelisted roles for a guild in memory cache and settings."""
        gid = int(guild_id)
        self._whitelisted_roles[gid] = set()
        settings.set_guild_setting(gid, "whitelist_roles", [])

    def invalidate_guild(self, guild_id: int | str):
        """Invalidates in-memory security state for a guild to force fresh reload."""
        gid = int(guild_id)
        self._loaded_guilds.discard(gid)
        self._antinuke.pop(gid, None)
        self._antinuke_actions.pop(gid, None)
        self._automod.pop(gid, None)
        self._bot_protection.pop(gid, None)
        self._whitelisted_bots.pop(gid, None)
        self._extraowners.pop(gid, None)
        self._whitelists.pop(gid, None)
        self._whitelisted_roles.pop(gid, None)
        try:
            from core.antinuke_v2.router import v2_engine_router
            v2_engine_router.coordinator.state_store.prune_guild(gid)
        except Exception:
            pass

    def is_bot_protection_active(self, guild_id: int | str) -> bool:
        """Returns True if Bot Protection is active for guild."""
        gid = int(guild_id)
        if gid in self._bot_protection:
            return self._bot_protection[gid]
        return False

    def set_bot_protection_status(self, guild_id: int | str, enabled: bool):
        """Updates the in-memory Bot Protection status for a guild."""
        gid = int(guild_id)
        self._bot_protection[gid] = bool(enabled)
        self._loaded_guilds.add(gid)

    def get_whitelisted_bots(self, guild_id: int | str) -> Set[int]:
        """Returns a copy of the whitelisted bot IDs set for a guild, including trusted sibling bots."""
        gid = int(guild_id)
        bots = self._whitelisted_bots.get(gid, set()).copy()
        bots.update(SIBLING_BOT_IDS)
        return bots

    def add_whitelisted_bot(self, guild_id: int | str, bot_id: int | str):
        """Adds a bot to the in-memory whitelist."""
        gid = int(guild_id)
        bid = int(bot_id)
        if gid not in self._whitelisted_bots:
            self._whitelisted_bots[gid] = set()
        self._whitelisted_bots[gid].add(bid)
        try:
            from core.antinuke_v2.router import v2_engine_router
            cfg = v2_engine_router.coordinator.state_store.get_guild_config(gid)
            cfg.whitelisted_bots.add(bid)
        except Exception:
            pass

    def remove_whitelisted_bot(self, guild_id: int | str, bot_id: int | str):
        """Removes a bot from the in-memory whitelist."""
        gid = int(guild_id)
        bid = int(bot_id)
        if gid in self._whitelisted_bots:
            self._whitelisted_bots[gid].discard(bid)
        try:
            from core.antinuke_v2.router import v2_engine_router
            cfg = v2_engine_router.coordinator.state_store.get_guild_config(gid)
            cfg.whitelisted_bots.discard(bid)
        except Exception:
            pass

    def is_bot_whitelisted(self, guild_id: int | str, bot_id: int | str) -> bool:
        """Returns True if bot is whitelisted or a trusted sibling bot for guild."""
        gid = int(guild_id)
        try:
            bid = int(bot_id)
        except (ValueError, TypeError):
            return False
        if bid in SIBLING_BOT_IDS:
            return True
        if gid in self._whitelisted_bots:
            return bid in self._whitelisted_bots[gid]
        return False

    def is_automod_enabled(self, guild_id: int | str) -> bool:
        """Returns True if AutoMod is enabled for guild."""
        gid = int(guild_id)
        if gid in self._automod:
            return self._automod[gid]
        return bool(settings.get_guild_setting(guild_id, "automod", default=False))

    def set_automod_status(self, guild_id: int | str, enabled: bool):
        """Updates the in-memory AutoMod enabled status for a guild."""
        gid = int(guild_id)
        self._automod[gid] = bool(enabled)
        settings.set_guild_setting(guild_id, "automod", bool(enabled))

    def is_whitelisted(self, guild_id: int | str, user_id: int | str) -> bool:
        """Returns True if user is in guild's whitelist, is a global bot owner, or is a sibling bot."""
        try:
            uid = int(user_id)
            if uid in GLOBAL_BOT_OWNER_SET or uid in SIBLING_BOT_IDS:
                return True
        except (ValueError, TypeError):
            pass
        gid = int(guild_id)
        uid = int(user_id)
        if gid in self._whitelists and uid in self._whitelists[gid]:
            return True
        guild_data = settings.get_guild_settings(guild_id)
        whitelist = guild_data.get("whitelist", [])
        return str(user_id) in whitelist


    async def warm_all_guilds(self, guilds):
        """Pre-warms in-memory security state for all connected guilds directly from SQLite db/anti.db."""
        for guild in guilds:
            await self.warm_guild(guild.id)

    def get_extra_owner(self, guild_id: int | str) -> Optional[str]:
        """Returns extra owner user ID string if assigned."""
        return settings.get_guild_setting(guild_id, "extraowner", default=None)

    def is_extra_owner(self, guild_id: int | str, user_id: int | str) -> bool:
        """Returns True if user is assigned as extra owner for guild or is a global bot owner."""
        try:
            uid = int(user_id)
            if uid in GLOBAL_BOT_OWNER_SET:
                return True
        except (ValueError, TypeError):
            return False

        try:
            gid = int(guild_id)
        except (ValueError, TypeError):
            return False

        # 1. Fast in-memory check
        if gid in self._extraowners and uid in self._extraowners[gid]:
            return True

        # 2. Check settings manager
        extra_owner = self.get_extra_owner(gid)
        if extra_owner is not None:
            try:
                if int(extra_owner) == uid:
                    if gid not in self._extraowners:
                        self._extraowners[gid] = set()
                    self._extraowners[gid].add(uid)
                    return True
            except (ValueError, TypeError):
                pass

        # 3. Fallback check via settings manager cache if guild not explicitly in loaded set
        if gid not in self._loaded_guilds:
            try:
                extra_owner_id = settings.get_guild_setting(gid, "extraowner", default=None)
                if extra_owner_id and int(extra_owner_id) == uid:
                    if gid not in self._extraowners:
                        self._extraowners[gid] = set()
                    self._extraowners[gid].add(uid)
                    return True
            except Exception:
                pass

        return False



# Global singleton instance
security_cache = SecurityStateCache()

