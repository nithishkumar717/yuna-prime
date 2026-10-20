from __future__ import annotations
import os
import sys
import time
import typing
from typing import List, Dict, Optional
import aiohttp
import aiosqlite
import discord
from discord.ext import commands
from colorama import Fore, Style, init

import utils.embed_theme
from utils.config import OWNER_IDS, DEFAULT_PREFIX
from utils import getConfig
from utils.time_utils import format_ist_time, format_ist_full, now_ist
from .Context import Context

init(autoreset=True)

extensions: List[str] = [
    "cogs.yuna_commands.gitpull",
    "cogs"
]

# In-memory prefix cache: {guild_id: (prefix, timestamp)}
_prefix_cache: Dict[int, tuple] = {}
_PREFIX_CACHE_TTL = 120  # seconds

# In-memory No-Prefix (NP) cache: set of user IDs
_np_cache: set[int] = set()
_np_cache_time: float = 0
_NP_CACHE_TTL = 120  # seconds


def _cached_prefix(guild_id: int) -> Optional[str]:
    entry = _prefix_cache.get(guild_id)
    if entry and time.time() - entry[1] < _PREFIX_CACHE_TTL:
        return entry[0]
    return None


def invalidate_prefix_cache(guild_id: int):
    """Invalidates prefix cache for a specific guild."""
    _prefix_cache.pop(guild_id, None)


def invalidate_np_cache():
    """Invalidates the global No-Prefix cache."""
    global _np_cache_time
    _np_cache_time = 0


async def _get_cached_np_set() -> set[int]:
    """Returns the fast in-memory set of No-Prefix user IDs."""
    global _np_cache, _np_cache_time
    now = time.time()
    if now - _np_cache_time > _NP_CACHE_TTL:
        try:
            from core.database.connection_pool import db_pool
            async with db_pool.acquire('db/np.db') as db:
                async with db.execute("SELECT id FROM np") as cursor:
                    rows = await cursor.fetchall()
                    _np_cache = {r[0] for r in rows}
                    _np_cache_time = now
        except Exception:
            pass
    return _np_cache


class BotBase(commands.AutoShardedBot):
    """
    Yuna Supreme BotBase — Hyper-Optimized Dedicated Security & Moderation Core.
    Streamlined exclusively for sub-15ms Anti-Nuke containment, AutoMod, and Audit Logging.
    Zero Audio/Fun overhead, minimal gateway latency.
    """
    _instance: Optional[BotBase] = None

    @classmethod
    def get_instance(cls) -> Optional[BotBase]:
        return cls._instance

    def __init__(self, *args, **kwargs):
        BotBase._instance = self
        
        # Dedicated Security Intents: No presences, no voice states to eliminate 90% of gateway bloat
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True
        intents.moderation = True
        intents.bans = True
        intents.presences = False
        intents.voice_states = False
        intents.typing = False

        super().__init__(
            command_prefix=self.get_prefix,
            case_insensitive=True,
            intents=intents,
            status=discord.Status.do_not_disturb,
            strip_after_prefix=True,
            owner_ids=OWNER_IDS,
            allowed_mentions=discord.AllowedMentions(everyone=False, replied_user=False, roles=False),
            max_messages=100,
            chunk_guilds_at_startup=False,
            shard_count=None
        )
        self._synced = False
        self.start_time: float = time.time()
        self.session: Optional[aiohttp.ClientSession] = None
        self._presence_rotation_task: Optional[typing.Any] = None

        # Setup Discord Mobile Client status if configured
        try:
            from core.discord.mobile_client import setup_mobile_status
            setup_mobile_status()
        except Exception as e:
            print(f"[DISCORD CLIENT WARNING] Could not configure mobile status: {e}", flush=True)

        try:
            from utils.emojis import install_emoji_sanitizer_hooks
            install_emoji_sanitizer_hooks(self)
        except Exception as e:
            print(f"[EMOJI SANITIZER INIT WARNING] {e}", flush=True)

        try:
            from utils.time_utils import set_global_bot
            set_global_bot(self)
        except Exception:
            pass

        # Install Anti-Nuke V2 Fast-Path Direct Gateway Interceptor
        try:
            from core.antinuke_v2.fast_path import install_fast_path
            install_fast_path(self)
            print(Fore.GREEN + Style.BRIGHT + "[ANTINUKE V2 FAST-PATH] Interceptor installed into Discord Gateway parser.", flush=True)
        except Exception as e:
            print(Fore.YELLOW + Style.BRIGHT + f"[FAST-PATH INIT WARNING] {e}", flush=True)

    async def close(self):
        if hasattr(self, "_presence_rotation_task") and self._presence_rotation_task and not self._presence_rotation_task.done():
            self._presence_rotation_task.cancel()
            try:
                await self._presence_rotation_task
            except Exception:
                pass

        if hasattr(self, "session") and self.session and not self.session.closed:
            await self.session.close()

        try:
            from core.antinuke_v2.warmer import discord_connection_warmer
            discord_connection_warmer.stop()
        except Exception:
            pass

        try:
            from core.antinuke_v2.containment import turbo_ban_client
            await turbo_ban_client.close()
        except Exception:
            pass

        try:
            await super().close()
        except Exception:
            pass

    async def sync_application_emojis(self) -> tuple[int, int]:
        """Fetches all official application emojis from Discord Developer Portal / API and updates local mapping."""
        try:
            app_emojis = await self.fetch_application_emojis()
            self.application_emojis = app_emojis
            from utils.emojis import register_application_emojis
            new_added = register_application_emojis(app_emojis)
            return len(app_emojis), new_added
        except Exception as e:
            print(Fore.YELLOW + Style.BRIGHT + f"[APPLICATION EMOJIS SYNC ERROR] {e}", flush=True)
            return len(getattr(self, "application_emojis", []) or []), 0

    async def setup_hook(self):
        try:
            self.session = aiohttp.ClientSession()
        except Exception as e:
            print(f"[CLIENT SESSION INIT WARNING] {e}", flush=True)

        # 0. Sync & Install Application Emojis & Global Sanitizer Hooks
        try:
            total, new_added = await self.sync_application_emojis()
            from utils.emojis import install_emoji_sanitizer_hooks
            install_emoji_sanitizer_hooks(self)
            print(Fore.GREEN + Style.BRIGHT + f"[APPLICATION EMOJIS] Loaded {total} verified application emojis from Developer Portal.", flush=True)
        except Exception as e:
            print(Fore.YELLOW + f"[APPLICATION EMOJIS INIT WARNING] {e}", flush=True)

        # 1. Warm Discord Connection for sub-15ms REST responses
        try:
            from core.antinuke_v2.warmer import discord_connection_warmer
            discord_connection_warmer.start(self)
            print(Fore.GREEN + Style.BRIGHT + "[ANTINUKE V2 WARMER] Discord HTTP Connection Warmer initialized.", flush=True)
        except Exception as e:
            print(Fore.YELLOW + Style.BRIGHT + f"[ANTINUKE V2 WARMER WARNING] {e}", flush=True)

        # 2. Initialize Turbo-Ban Client (Ultra-low-latency raw REST dispatcher)
        try:
            from core.antinuke_v2.containment import turbo_ban_client
            tok = getattr(getattr(self, "http", None), "token", None)
            if tok:
                await turbo_ban_client.initialize(tok)
                print(Fore.GREEN + Style.BRIGHT + "[ANTINUKE V2 TURBO-BAN] Dedicated Ultra-Low-Latency Client initialized (TCP_NODELAY active).", flush=True)
        except Exception as e:
            print(Fore.YELLOW + Style.BRIGHT + f"[ANTINUKE V2 TURBO-BAN WARNING] {e}", flush=True)

        # 3. Setup SQLite Databases & Auto-Heal
        try:
            from setup.database.initialize_dbs import setup_all_dbs
            await setup_all_dbs()
            print(Fore.GREEN + Style.BRIGHT + "[DATABASE] Security schemas verified & initialized.", flush=True)
        except Exception as e:
            print(Fore.RED + Style.BRIGHT + f"[DATABASE INIT WARNING] {e}", flush=True)

        # 4. Priority Request Manager & Log Aggregator
        try:
            from core.discord.request_manager import request_manager
            from core.logging.log_aggregator import log_aggregator
            request_manager.start()
            log_aggregator.start()
            print(Fore.GREEN + Style.BRIGHT + "[SYSTEM ENGINE] Priority Request Manager & Log Aggregator worker pools active.", flush=True)
        except Exception as e:
            print(Fore.RED + Style.BRIGHT + f"[SYSTEM ENGINE WARNING] {e}", flush=True)

        # 5. Persistent Whitelist UI View
        try:
            from services.whitelist_panel import WhitelistPanelV2View
            self.add_view(WhitelistPanelV2View())
            print(Fore.GREEN + Style.BRIGHT + "[WHITELIST UI] Persistent WhitelistPanelV2View registered.", flush=True)
        except Exception as e:
            print(Fore.YELLOW + f"[WHITELIST UI INIT WARNING] {e}", flush=True)

        # 6. Load Cogs
        await self.load_extensions()

    async def load_extensions(self):
        for extension in extensions:
            try:
                await self.load_extension(extension)
                print(Fore.GREEN + Style.BRIGHT + f"[{format_ist_time()}] Loaded extension: {extension}", flush=True)
            except Exception as e:
                print(Fore.RED + Style.BRIGHT + f"[{format_ist_time()}] Failed to load extension {extension}: {e}", flush=True)
        print(Fore.GREEN + Style.BRIGHT + "*" * 20, flush=True)

    async def _rotate_presence(self):
        """Minimalist Security status indicator."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                guild_count = len(self.guilds)
                status_text = f"🛡️ Yuna Supreme | {guild_count} servers secured"
                activity = discord.CustomActivity(name=status_text)
                await self.change_presence(activity=activity, status=discord.Status.do_not_disturb)
                await asyncio.sleep(60.0)
            except Exception:
                await asyncio.sleep(30.0)

    async def on_ready(self):
        await self.wait_until_ready()
        import asyncio
        if self._presence_rotation_task is None or self._presence_rotation_task.done():
            self._presence_rotation_task = asyncio.create_task(self._rotate_presence())

        print(f"[{format_ist_full()}] 🛡️ Yuna Supreme Online & Ready!", flush=True)
        try:
            print(f"[{format_ist_time()}] Logged in as: {self.user} (ID: {self.user.id})", flush=True)
        except Exception:
            pass
        print(f"[{format_ist_time()}] Guarding {len(self.guilds)} guilds & {len(self.users)} members", flush=True)

        # Pre-warm Security Caches
        try:
            from core.cache.security_cache import security_cache
            await security_cache.warm_all_guilds(self.guilds)
            print(Fore.CYAN + Style.BRIGHT + f"[SECURITY CACHE] Pre-warmed security cache for {len(self.guilds)} guilds into RAM.", flush=True)
        except Exception as e:
            print(Fore.YELLOW + f"[SECURITY CACHE WARNING] {e}", flush=True)

        # Pre-warm V2 Engine States
        try:
            from core.antinuke_v2.router import v2_engine_router
            await v2_engine_router.coordinator.state_store.warm_load_all_guilds()
            print(Fore.CYAN + Style.BRIGHT + "[ANTINUKE V2 STATE] Pre-warmed V2 security states from db/anti.db into RAM.", flush=True)
        except Exception as e:
            print(Fore.YELLOW + f"[ANTINUKE V2 STATE WARNING] {e}", flush=True)

        # Ensure TurboBan token is refreshed and pre-warmed for 0ms REST latency
        try:
            from core.antinuke_v2.containment import turbo_ban_client
            tok = getattr(getattr(self, "http", None), "token", None)
            if tok and not turbo_ban_client.is_ready():
                await turbo_ban_client.initialize(tok)
            if turbo_ban_client.is_ready():
                await turbo_ban_client.warm_ping(pool_size=2)
                print(Fore.GREEN + Style.BRIGHT + "[ANTINUKE V2 TURBO-BAN] Pre-warmed 2 active TCP/TLS keepalive sockets for 0ms execution.", flush=True)
        except Exception as e:
            print(Fore.YELLOW + f"[TURBO-BAN WARM WARNING] {e}", flush=True)

        # Sync Slash Commands if enabled
        if not getattr(self, "_synced", False):
            import os, hashlib, json
            auto_sync = os.environ.get("AUTO_SYNC_COMMANDS", "true").lower() in ("true", "1", "yes")
            if auto_sync:
                try:
                    tree_commands = self.tree.get_commands()
                    if tree_commands:
                        synced = await self.tree.sync()
                        print(Fore.GREEN + Style.BRIGHT + f"[SLASH SYNC] Synced {len(synced)} Slash Commands to Discord Gateway.", flush=True)
                        self._synced = True
                except Exception as e:
                    print(Fore.YELLOW + f"[SLASH SYNC WARNING] {e}", flush=True)
                    self._synced = True

    async def get_context(self, origin: typing.Union[discord.Message, discord.Interaction], *, cls=Context) -> Context:
        return await super().get_context(origin, cls=cls)

    async def get_prefix(self, message: discord.Message):
        if not message.guild:
            try:
                np_set = await _get_cached_np_set()
                if message.author and (message.author.id in np_set or message.author.id in OWNER_IDS):
                    return commands.when_mentioned_or(DEFAULT_PREFIX, '')(self, message)
            except Exception:
                pass
            return commands.when_mentioned_or(DEFAULT_PREFIX)(self, message)

        guild_id = message.guild.id
        prefix = _cached_prefix(guild_id)
        if not prefix:
            try:
                data = await getConfig(guild_id)
                if isinstance(data, dict):
                    prefix = data.get("prefix", DEFAULT_PREFIX)
                elif isinstance(data, (list, tuple)) and len(data) > 0:
                    prefix = data[0]
                else:
                    prefix = DEFAULT_PREFIX
            except Exception:
                prefix = DEFAULT_PREFIX
            _prefix_cache[guild_id] = (prefix, time.time())

        try:
            np_set = await _get_cached_np_set()
            if message.author and (message.author.id in np_set or message.author.id in OWNER_IDS):
                return commands.when_mentioned_or(prefix, '')(self, message)
        except Exception:
            pass

        return commands.when_mentioned_or(prefix)(self, message)
