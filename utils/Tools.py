import json
import sys
import os
import re
import unicodedata
from typing import Optional, Union, Dict, Any, List
import discord
from discord.ext import commands
import aiosqlite
import asyncio
import utils.embed_theme

def _init_tools_db():
    try:
        import sqlite3
        os.makedirs("db", exist_ok=True)
        con = sqlite3.connect('db/prefix.db')
        con.execute('''
          CREATE TABLE IF NOT EXISTS prefixes (
            guild_id INTEGER PRIMARY KEY,
            prefix TEXT NOT NULL
          )
        ''')
        con.commit()
        con.close()
    except Exception:
        pass

_init_tools_db()

async def is_topcheck_enabled(guild_id: int):
    async with aiosqlite.connect('db/topcheck.db') as db:
        async with db.execute("SELECT enabled FROM topcheck WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None and row[0] == 1
            


_JSON_FILE_CACHE: Dict[str, Any] = {}

def read_json(file_path):
    if file_path in _JSON_FILE_CACHE:
        return _JSON_FILE_CACHE[file_path]
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            _JSON_FILE_CACHE[file_path] = data
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        default_val = {"guilds": {}}
        _JSON_FILE_CACHE[file_path] = default_val
        return default_val

def write_json(file_path, data):
    _JSON_FILE_CACHE[file_path] = data
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
    except Exception:
        pass

def get_or_create_guild_config(file_path, guild_id, default_config):
    data = read_json(file_path)
    if "guilds" not in data:
        data["guilds"] = {}  

    guild_id_str = str(guild_id)
    if guild_id_str not in data["guilds"]:
        data["guilds"][guild_id_str] = default_config
        write_json(file_path, data)
    return data["guilds"][guild_id_str]

def update_guild_config(file_path, guild_id, new_data):
    data = read_json(file_path)
    if "guilds" not in data:
        data["guilds"] = {}  

    data["guilds"][str(guild_id)] = new_data
    write_json(file_path, data)

def getIgnore(guild_id):
    default_config = {
        "channel": [],
        "role": None,
        "user": [],
        "bypassrole": None,
        "bypassuser": [],
        "commands": []
    }
    return get_or_create_guild_config("ignore.json", guild_id, default_config)

def updateignore(guild_id, data):
    update_guild_config("ignore.json", guild_id, data)





async def getConfig(guildID):
    from utils.settings_manager import settings
    from utils.config import DEFAULT_PREFIX

    # The prefixes table is the source of truth for explicit guild prefixes.
    # SettingsManager supplies defaults for every setting, so reading its prefix
    # first can mask DEFAULT_PREFIX with a stale hard-coded value.
    try:
        async with aiosqlite.connect('db/prefix.db', timeout=3.0) as db:
            async with db.execute("SELECT prefix FROM prefixes WHERE guild_id = ?", (guildID,)) as cursor:
                row = await cursor.fetchone()
                if row and isinstance(row[0], str) and row[0]:
                    prefix = row[0]
                    settings.set_guild_setting(guildID, "prefix", prefix)
                    return {"prefix": prefix}
    except Exception as e:
        print(f"[DB FALLBACK] SQLite prefix fetch error for {guildID}: {e}")

    # No explicit per-guild prefix (or database unavailable): honor the env default.
    settings.set_guild_setting(guildID, "prefix", DEFAULT_PREFIX)
    return {"prefix": DEFAULT_PREFIX}

async def updateConfig(guildID, data):
    from utils.settings_manager import settings
    from utils.config import DEFAULT_PREFIX
    prefix = data.get("prefix", DEFAULT_PREFIX)
    # Save locally immediately
    settings.set_guild_setting(guildID, "prefix", prefix)
    try:
        async with aiosqlite.connect('db/prefix.db', timeout=3.0) as db:
            await db.execute(
                "INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)",
                (guildID, prefix)
            )
            await db.commit()
    except Exception as e:
        print(f"[DB FALLBACK] SQLite prefix write error: {e}. Preserved in local settings.")



def restart_program():
    try:
        from core import BotBase
        bot = BotBase.get_instance()
        if bot:
            music_cog = bot.get_cog("music")
            if music_cog and hasattr(music_cog, "save_all_playback_states"):
                music_cog.save_all_playback_states()
    except Exception as e:
        print(f"[RESTART] Failed to save playback state: {e}")

    try:
        from core.dashboard_server import trigger_dashboard_shutdown
        trigger_dashboard_shutdown()
    except Exception:
        pass

    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass

    # Close all open non-std file descriptors (>= 3) so child process doesn't inherit listening sockets
    try:
        if hasattr(os, 'closerange'):
            os.closerange(3, 4096)
        else:
            for fd in range(3, 1024):
                try:
                    os.close(fd)
                except OSError:
                    pass
    except Exception:
        pass

    python = sys.executable
    os.execl(python, python, *sys.argv)

def is_server_owner_or_extra_owner(guild_or_ctx, user_or_id) -> bool:
    """Returns True if user is the Primary Server Owner, a Global Bot Owner, or an assigned Extra Owner."""
    if not guild_or_ctx or not user_or_id:
        return False

    if isinstance(guild_or_ctx, discord.Guild):
        guild = guild_or_ctx
    elif hasattr(guild_or_ctx, "guild") and getattr(guild_or_ctx, "guild", None) is not None:
        guild = guild_or_ctx.guild
    else:
        guild = guild_or_ctx

    if not guild or not hasattr(guild, "id"):
        return False
    user_id = getattr(user_or_id, "id", user_or_id)
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return False

    # 1. Primary Server Owner checks (via owner_id or owner object)
    owner_id = getattr(guild, "owner_id", None)
    if owner_id is not None:
        try:
            if user_id == int(owner_id):
                return True
        except (ValueError, TypeError):
            pass

    guild_owner = getattr(guild, "owner", None)
    if guild_owner is not None:
        if user_or_id == guild_owner:
            return True
        owner_obj_id = getattr(guild_owner, "id", None)
        if owner_obj_id is not None:
            try:
                if user_id == int(owner_obj_id):
                    return True
            except (ValueError, TypeError):
                pass

    # 2. Global Bot Owner & Sibling Bot checks
    try:
        from utils.config import OWNER_IDS, GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER, SIBLING_BOT_IDS
        if user_id in OWNER_IDS or user_id in GLOBAL_OWNER_IDS or user_id == PRIMARY_BOT_OWNER or user_id in SIBLING_BOT_IDS:
            return True
    except Exception:
        pass

    try:
        from core.cache.security_cache import GLOBAL_BOT_OWNER_SET
        if user_id in GLOBAL_BOT_OWNER_SET:
            return True
    except Exception:
        pass


    # 3. Extra Owner checks (in-memory cache & fallback)
    try:
        from core.cache.security_cache import security_cache
        if security_cache.is_extra_owner(guild.id, user_id):
            return True
    except Exception:
        pass

    return False

def is_owner_or_guild_owner():
    """A check decorator that allows bot owners, guild owner, or extra owners to run a command."""
    async def predicate(ctx):
        if not ctx.guild:
            return await ctx.bot.is_owner(ctx.author)
        return is_server_owner_or_extra_owner(ctx.guild, ctx.author) or await ctx.bot.is_owner(ctx.author)
    return commands.check(predicate)


def blacklist_check():

  async def predicate(ctx):
    async with aiosqlite.connect('db/block.db') as db:
      cursor = await db.execute("SELECT 1 FROM user_blacklist WHERE user_id = ?", (str(ctx.author.id),))
      user_blacklisted = await cursor.fetchone()
      if user_blacklisted:
        return False

      if ctx.guild:
        cursor = await db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (str(ctx.guild.id),))
        guild_blacklisted = await cursor.fetchone()
        if guild_blacklisted:
          return False

    return True

  return commands.check(predicate)
    

async def get_ignore_data(guild_id: int) -> dict:
    async with aiosqlite.connect("db/ignore.db") as db:
        data = {
            "channel": set(),
            "user": set(),
            "command": set(),
            "bypassuser": set(),
        }

        async with db.execute("SELECT channel_id FROM ignored_channels WHERE guild_id = ?", (guild_id,)) as cursor:
            channels = await cursor.fetchall()
            data["channel"] = {str(channel_id) for (channel_id,) in channels}

        async with db.execute("SELECT user_id FROM ignored_users WHERE guild_id = ?", (guild_id,)) as cursor:
            users = await cursor.fetchall()
            data["user"] = {str(user_id) for (user_id,) in users}

        async with db.execute("SELECT command_name FROM ignored_commands WHERE guild_id = ?", (guild_id,)) as cursor:
            commands = await cursor.fetchall()
            data["command"] = {command_name.strip().lower() for (command_name,) in commands}

        async with db.execute("SELECT user_id FROM bypassed_users WHERE guild_id = ?", (guild_id,)) as cursor:
            bypass_users = await cursor.fetchall()
            data["bypassuser"] = {str(user_id) for (user_id,) in bypass_users}

    return data

def ignore_check():
    async def predicate(ctx):
        if not ctx.guild:
            return True

        if is_server_owner_or_extra_owner(ctx.guild, ctx.author):
            return True

        from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER
        if ctx.author.id == PRIMARY_BOT_OWNER or ctx.author.id in GLOBAL_OWNER_IDS:
            return True
        if ctx.guild and ctx.author.id == ctx.guild.owner_id:
            return True
            
        data = await get_ignore_data(ctx.guild.id)
        ch = data["channel"]
        iuser = data["user"]
        cmd = data["command"]
        buser = data["bypassuser"]

        if str(ctx.author.id) in buser:
            return True
        if str(ctx.channel.id) in ch or str(ctx.author.id) in iuser:
            return False

        cmd_obj = getattr(ctx, "command", None)
        command_name = (getattr(cmd_obj, "name", "") or "").strip().lower()
        raw_aliases = getattr(cmd_obj, "aliases", None) or getattr(getattr(cmd_obj, "wrapped", None), "aliases", None) or []
        aliases = [str(alias).strip().lower() for alias in raw_aliases]
        if command_name in cmd or any(alias in cmd for alias in aliases):
            return False

        return True

    return commands.check(predicate)

def top_check():
    async def predicate(ctx):
        if not ctx.guild:
            return True

        if getattr(ctx, "invoked_with", None) in ["help", "h"]:
            return True

        if is_server_owner_or_extra_owner(ctx.guild, ctx.author):
            return True

        from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER
        if ctx.author.id == PRIMARY_BOT_OWNER or ctx.author.id in GLOBAL_OWNER_IDS:
            return True
        if ctx.author == ctx.guild.owner:
            return True

        topcheck_enabled = await is_topcheck_enabled(ctx.guild.id)

        if not topcheck_enabled:
            return True

        if ctx.author.top_role.position <= ctx.guild.me.top_role.position:
            embed = discord.Embed(
                title="<:Denied:1294218790082711553> Access Denied", 
                description="Your top role must be at a **higher** position than my top role.",
                color=0x000000
            )
            embed.set_footer(
                text=f"“{ctx.command.qualified_name}” command executed by {ctx.author}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            await ctx.send(embed=embed)
            return False

        return True

    return commands.check(predicate)


async def get_or_create_yuna_logs_category(guild: discord.Guild) -> Optional[discord.CategoryChannel]:
    """
    Finds or creates the official 'Yuna Logs' category channel for a guild.
    Manages duplicate categories: if multiple categories named 'Yuna Logs' or 'yuna-logs' exist,
    consolidates their channels into a single primary category and removes empty duplicates.
    """
    if not guild:
        return None

    can_manage = getattr(guild.me, "guild_permissions", None) and guild.me.guild_permissions.manage_channels
    categories = getattr(guild, "categories", [])
    matching_categories = [
        c for c in categories
        if c.name in ("❀ YUNA・LOGS", "🌸 YUNA・LOGS")
        or c.name.lower() in ("❀ yuna・logs", "🌸 yuna・logs", "yuna logs", "yuna-logs", "yuna_logs")
    ]

    primary_category = None
    if matching_categories:
        # Prioritize category that already has text channels
        primary_category = max(matching_categories, key=lambda c: len(c.channels))

        # Consolidate duplicate categories if more than 1 exists
        if len(matching_categories) > 1 and can_manage:
            for dup_cat in matching_categories:
                if dup_cat.id == primary_category.id:
                    continue
                # Move any channels from dup_cat to primary_category
                for ch in list(dup_cat.channels):
                    try:
                        await ch.edit(category=primary_category, reason="Yuna: Consolidate duplicate Yuna Logs category")
                        await asyncio.sleep(0.2)
                    except Exception:
                        pass
                # Delete the now-empty duplicate category
                try:
                    await dup_cat.delete(reason="Yuna: Remove duplicate Yuna Logs category")
                except Exception:
                    pass

        # Standardize name to 'Yuna Logs' and enforce secure private category permissions
        if can_manage:
            everyone_role = guild.default_role
            overwrites = {
                everyone_role: discord.PermissionOverwrite(
                    view_channel=False,
                    send_messages=False,
                    send_messages_in_threads=False,
                    create_public_threads=False,
                    create_private_threads=False,
                    add_reactions=False,
                    read_message_history=False,
                    use_application_commands=False
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    send_messages_in_threads=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                    manage_webhooks=True,
                    manage_channels=True,
                    manage_messages=True,
                    use_external_emojis=True
                )
            }
            try:
                cat_kwargs = {"overwrites": overwrites, "reason": "Yuna Logs: Enforce secure private category permissions"}
                if primary_category.name != "❀ YUNA・LOGS":
                    cat_kwargs["name"] = "❀ YUNA・LOGS"
                await primary_category.edit(**cat_kwargs)
            except Exception:
                pass

        return primary_category

    if not can_manage:
        return None

    everyone_role = guild.default_role
    overwrites = {
        everyone_role: discord.PermissionOverwrite(
            view_channel=False,
            send_messages=False,
            send_messages_in_threads=False,
            create_public_threads=False,
            create_private_threads=False,
            add_reactions=False,
            read_message_history=False,
            use_application_commands=False
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            send_messages_in_threads=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            manage_webhooks=True,
            manage_channels=True,
            manage_messages=True,
            use_external_emojis=True
        )
    }

    try:
        category = await guild.create_category(
            name="❀ YUNA・LOGS",
            overwrites=overwrites,
            reason="Yuna Logs: Category Setup for security and server logs"
        )
        return category
    except Exception as e:
        print(f"[YUNA LOGS CATEGORY ERROR] Failed to create category in guild '{guild.name}' ({guild.id}): {e}", flush=True)
        return None


# =========================================================================
# YUNA LOGS UNIFIED STYLING, DETECTION & CHANNEL MANAGEMENT ENGINE
# =========================================================================

# Unicode aesthetic font mappings
SMALL_CAPS: Dict[str, str] = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ',
    'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
    's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
}
REVERSE_SMALL_CAPS: Dict[str, str] = {v: k for k, v in SMALL_CAPS.items()}
REVERSE_SMALL_CAPS.update({
    'ꞯ': 'q', 'ѕ': 's', '×': 'x', 'ⅹ': 'x', 'ᴠ': 'v', 'ᴡ': 'w', 'ʏ': 'y', 'ᴢ': 'z',
    'ꜱ': 's', 'ᴀ': 'a', 'ʙ': 'b', 'ᴄ': 'c', 'ᴅ': 'd', 'ᴇ': 'e', 'ꜰ': 'f', 'ɢ': 'g',
    'ʜ': 'h', 'ɪ': 'i', 'ᴊ': 'j', 'ᴋ': 'k', 'ʟ': 'l', 'ᴍ': 'm', 'ɴ': 'n', 'ᴏ': 'o',
    'ᴘ': 'p', 'ǫ': 'q', 'ʀ': 'r', 'ᴛ': 't', 'ᴜ': 'u'
})
SMALL_CAPS_CHARS = set(SMALL_CAPS.values())


def _make_font_dict(start_lower: int, start_upper: Optional[int] = None) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for i, ch in enumerate('abcdefghijklmnopqrstuvwxyz'):
        m[ch] = chr(start_lower + i)
    if start_upper:
        for i, ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            m[ch] = chr(start_upper + i)
    return m


FONT_MAPS: Dict[str, Dict[str, str]] = {
    'small_caps': {**SMALL_CAPS, **{k.upper(): v for k, v in SMALL_CAPS.items()}},
    'sans_bold': _make_font_dict(0x1D5EE, 0x1D5D4),
    'sans': _make_font_dict(0x1D5BA, 0x1D5A0),
    'bold': _make_font_dict(0x1D41A, 0x1D400),
    'monospace': _make_font_dict(0x1D68A, 0x1D670),
    'double_struck': _make_font_dict(0x1D552),
    'fullwidth': _make_font_dict(0xFF41, 0xFF21),
    'standard': {}
}

FONT_DISPLAY_NAMES: Dict[str, str] = {
    'small_caps': 'Small Caps (ᴀʙᴄ)',
    'sans_bold': 'Sans-Serif Bold (𝗮𝗯𝗰)',
    'sans': 'Sans-Serif (𝖺𝖻𝖼)',
    'bold': 'Mathematical Bold (𝐚𝐛𝐜)',
    'monospace': 'Monospace (𝚊𝚋𝚌)',
    'double_struck': 'Double-Struck (𝕒𝕓𝕔)',
    'fullwidth': 'Fullwidth (ａｂｃ)',
    'standard': 'Standard Discord Lowercase'
}


def apply_font_style(text: str, font_name: str) -> str:
    """Applies the specified aesthetic font style to text while preserving numbers and symbols."""
    fmap = FONT_MAPS.get(font_name, {})
    if not fmap:
        return text
    return "".join(fmap.get(ch, ch) for ch in text)


def to_small_caps(text: str) -> str:
    """Converts alphabetic string into small caps unicode characters."""
    return apply_font_style(text, 'small_caps')


def normalize_channel_name(name: str) -> str:
    """Normalizes small-caps or stylized channel name to standard ASCII lowercase."""
    step1 = "".join(REVERSE_SMALL_CAPS.get(ch, ch) for ch in name)
    nfkd = unicodedata.normalize('NFKD', step1)
    return "".join(REVERSE_SMALL_CAPS.get(ch, ch) for ch in nfkd).lower()


def identify_log_channel_type(name: str) -> Optional[str]:
    """
    Identifies the canonical log channel key from any stylized or raw channel name.
    e.g.:
      '.ʏᴜɴᴀ.ᴍᴇssᴀɢᴇ.' -> 'message'
      'yuna-nightmode' -> 'nightmode'
      '․ʏᴜɴᴀ․ɴɪɢʜᴛᴍᴏᴅᴇ․' -> 'nightmode'
      'yuna-antinuke' -> 'antinuke'
      '.ʏᴜɴᴀ.ᴀɴᴛɪɴᴜᴋᴇ.' -> 'antinuke'
      'yuna-automod' -> 'automod'
      '.ʏᴜɴᴀ.ᴀᴜᴛᴏᴍᴏᴅ.' -> 'automod'
      'security-logs' -> 'security'
    """
    norm = normalize_channel_name(name)
    # Check compound names first before individual tokens
    if "nightmode" in norm or "night-mode" in norm or "night_mode" in norm:
        return "nightmode"
    if "antinuke" in norm or ("yuna" in norm and "nuke" in norm):
        return "antinuke"
    if "automod" in norm:
        return "automod"
    if "whitelist" in norm or "white-list" in norm:
        return "whitelist"
    if "security" in norm:
        return "security"
    if "verify" in norm or "verification" in norm:
        return "verify"
    if "topz" in norm or "top" in norm:
        return "invite_topz"
    if "tracker" in norm:
        return "invite_tracker"
    if "invite" in norm and ("tracker" in norm or "track" in norm or "log" in norm or "logs" in norm) and "audit" not in norm:
        return "invite_tracker"
    if "message" in norm or "messages" in norm or "msg" in norm:
        return "message"
    if "member" in norm or "members" in norm:
        return "member"
    if "channel" in norm or "channels" in norm:
        return "channel"
    if "invite" in norm or "invites" in norm:
        return "invite"
    if "ticket" in norm or "tickets" in norm:
        return "ticket"
    if "voice" in norm:
        return "voice"
    if "role" in norm or "roles" in norm:
        return "role"
    if "file" in norm or "files" in norm:
        return "file"
    if "server" in norm or "guild" in norm:
        return "server"
    if "admin" in norm:
        return "admin"
    if "raid" in norm:
        return "raid"
    if "misuse" in norm:
        return "misuse"
    if "ban" in norm or "bans" in norm:
        return "ban"
    if "join" in norm:
        return "joins"
    if "leave" in norm:
        return "leaves"
    if "presence" in norm:
        return "presence"
    if "relationship" in norm or "rel" in norm:
        return "relationship"
    if "mod" in norm or "moderation" in norm:
        return "mod"
    if "boost" in norm:
        return "boost"
    return None


def detect_guild_channel_style(guild: discord.Guild) -> Dict[str, Any]:
    """
    Analyzes existing text channels in guild to accurately detect:
    1. Dominant font style (small_caps, sans_bold, sans, bold, monospace, double_struck, fullwidth, or standard)
    2. Dominant separator / delimiter (・, ﹒, ․, │・, ┊・, -, etc.)
    3. Surrounding framing style ('enclosed', 'pipe', or 'hyphen')
    """
    sample_channels = [
        c for c in guild.text_channels
        if not (c.category and "logs" in c.category.name.lower())
        and not identify_log_channel_type(c.name)
    ]
    if not sample_channels:
        sample_channels = list(guild.text_channels)

    channel_names = [c.name for c in sample_channels]
    cat_names = [c.name for c in guild.categories if "logs" not in c.name.lower()]

    # 1. Detect dominant font family
    font_scores: Dict[str, int] = {k: 0 for k in FONT_MAPS}
    for text in (channel_names + cat_names):
        for ch in text:
            cp = ord(ch)
            if ch in SMALL_CAPS_CHARS:
                font_scores['small_caps'] += 1
            elif (0x1D5EE <= cp <= 0x1D607) or (0x1D5D4 <= cp <= 0x1D5ED):
                font_scores['sans_bold'] += 1
            elif (0x1D5BA <= cp <= 0x1D5D3) or (0x1D5A0 <= cp <= 0x1D5B9):
                font_scores['sans'] += 1
            elif (0x1D41A <= cp <= 0x1D433) or (0x1D400 <= cp <= 0x1D419):
                font_scores['bold'] += 1
            elif (0x1D68A <= cp <= 0x1D6A3) or (0x1D670 <= cp <= 0x1D689):
                font_scores['monospace'] += 1
            elif 0x1D552 <= cp <= 0x1D56B:
                font_scores['double_struck'] += 1
            elif (0xFF41 <= cp <= 0xFF5A) or (0xFF21 <= cp <= 0xFF3A):
                font_scores['fullwidth'] += 1
            elif 'a' <= ch.lower() <= 'z':
                font_scores['standard'] += 1

    # Detect the genuinely dominant font family in the server
    detected_font = 'standard'
    best_score = font_scores.get('standard', 0)
    for font_key, score in font_scores.items():
        if font_key == 'standard':
            continue
        if score > best_score and score >= 10:
            best_score = score
            detected_font = font_key

    # 2. Detect separator and framing style
    bullet_count = sum(1 for n in channel_names if '・' in n)
    small_dot_count = sum(1 for n in channel_names if '﹒' in n)
    one_dot_count = sum(1 for n in channel_names if '․' in n or '.' in n)
    pipe_char = next((p for p in ('│', '┊', '〢', '┃') if any(p in n for n in channel_names)), None)

    if pipe_char:
        has_bullet = any(f"{pipe_char}・" in n for n in channel_names) or bullet_count > 0
        pipe_prefix = f"{pipe_char}・" if has_bullet else f"{pipe_char}-"
        sep = '・' if has_bullet else '-'
        framing = 'pipe'
    elif bullet_count > 0 and bullet_count >= small_dot_count:
        pipe_prefix = ""
        sep = '・'
        framing = 'enclosed'
    elif small_dot_count > 0:
        pipe_prefix = ""
        sep = '﹒'
        framing = 'enclosed'
    elif one_dot_count > 0:
        pipe_prefix = ""
        sep = '․'
        framing = 'enclosed'
    else:
        pipe_prefix = ""
        if detected_font != 'standard':
            sep = '・'
            framing = 'enclosed'
        else:
            sep = '-'
            framing = 'hyphen'

    return {
        "font": detected_font,
        "font_display": FONT_DISPLAY_NAMES.get(detected_font, detected_font.title()),
        "framing": framing,
        "sep": sep,
        "pipe_prefix": pipe_prefix,
        "uses_dots": sep in ('﹒', '․', '.'),
        "uses_bullet": sep == '・',
        "uses_pipe": framing == 'pipe',
        "uses_small_caps": detected_font == 'small_caps'
    }


def detect_yuna_logs_style(guild: discord.Guild, category: Optional[discord.CategoryChannel] = None) -> Dict[str, Any]:
    """
    Detects the dominant text styling and font format syncing with the server.
    Ensures Yuna Logs reflects the server's dominant font style.
    """
    return detect_guild_channel_style(guild)


OFFICIAL_LOGS_CATEGORY_NAME = "❀ YUNA・LOGS"

AESTHETIC_LOG_CHANNELS: Dict[str, str] = {
    "mod": "﹒❀﹒mod﹒audit․・",
    "ban": "﹒❀﹒ban﹒audit․・",
    "security": "﹒❀﹒security﹒intel․・",
    "antinuke": "﹒❀﹒antinuke﹒intel․・",
    "automod": "﹒❀﹒automod﹒intel․・",
    "raid": "﹒❀﹒raid﹒intel․・",
    "nightmode": "﹒❀﹒nightmode﹒intel․・",
    "whitelist": "﹒❀﹒whitelist﹒audit․・",
    "admin": "﹒❀﹒admin﹒audit․・",
    "server": "﹒❀﹒server﹒audit․・",
    "channel": "﹒❀﹒channel﹒audit․・",
    "role": "﹒❀﹒role﹒audit․・",
    "misuse": "﹒❀﹒misuse﹒intel․・",
    "message": "﹒❀﹒message﹒audit․・",
    "file": "﹒❀﹒file﹒audit․・",
    "joins": "﹒❀﹒joins﹒audit․・",
    "leaves": "﹒❀﹒leaves﹒audit․・",
    "member": "﹒❀﹒member﹒audit․・",
    "verify": "﹒❀﹒verify﹒audit․・",
    "voice": "﹒❀﹒voice﹒trace․・",
    "invite": "﹒❀﹒invite﹒audit․・",
    "invite_tracker": "﹒❀﹒invite﹒tracker․・",
    "invite-tracker": "﹒❀﹒invite﹒tracker․・",
    "invite_logs": "﹒❀﹒invite﹒tracker․・",
    "invite-logs": "﹒❀﹒invite﹒tracker․・",
    "invite_topz": "﹒❀﹒invite﹒topz․・",
    "invite-topz": "﹒❀﹒invite﹒topz․・",
    "presence": "﹒❀﹒presence﹒trace․・",
    "ticket": "﹒❀﹒ticket﹒audit․・",
    "relationship": "﹒❀﹒relationship﹒trace․・",
    "boost": "﹒❀﹒boost﹒audit․・",
}


def format_channel_name(raw_name: str, style: Optional[Dict[str, Any]] = None, prefix: str = "yuna") -> str:
    """
    Formats log channel name to the official aesthetic theme:
    e.g. '﹒❀﹒nightmode﹒intel․・', '﹒❀﹒mod﹒audit․・', '﹒❀﹒voice﹒trace․・'
    Uses U+2024 ('․') and U+30FB ('・') at the end to prevent Discord from stripping it.
    Applies server font style (e.g. small_caps, sans_bold) to channel tokens.
    """
    clean_name = raw_name.lower().replace("_", "-").strip()
    font_style = style.get("font", "standard") if isinstance(style, dict) else "standard"

    base_name = AESTHETIC_LOG_CHANNELS.get(clean_name, f"﹒❀﹒{clean_name}﹒audit․・")
    if font_style and font_style != "standard":
        parts = base_name.split("﹒")
        if len(parts) >= 3:
            styled_parts = [parts[0]]
            for part in parts[1:-1]:
                styled_parts.append(apply_font_style(part, font_style))
            last = parts[-1]
            if last.endswith("․・"):
                core_last = last[:-2]
                styled_parts.append(apply_font_style(core_last, font_style) + "․・")
            else:
                styled_parts.append(apply_font_style(last, font_style))
            return "﹒".join(styled_parts)
    return base_name



async def standardize_all_yuna_logs_channels(
    guild: discord.Guild,
    category: Optional[discord.CategoryChannel] = None,
    style: Optional[Dict[str, Any]] = None
) -> List[tuple[discord.TextChannel, str, str]]:
    """
    Standardizes every text channel under the '❀ YUNA・LOGS' category so that ALL channels share
    the EXACT same text styling, casing, font, and delimiter format.
    Automatically identifies each channel's type, cleans up any stray duplicate channels,
    and renames non-standard channel names to the category's standard style.
    """
    if not guild or not getattr(guild.me, "guild_permissions", None) or not guild.me.guild_permissions.manage_channels:
        return []

    can_manage = bool(getattr(guild.me, "guild_permissions", None) and guild.me.guild_permissions.manage_channels)

    if category is None or category.name != OFFICIAL_LOGS_CATEGORY_NAME:
        category = discord.utils.find(
            lambda c: c.name in (OFFICIAL_LOGS_CATEGORY_NAME, "🌸 YUNA・LOGS")
            or ("yuna" in c.name.lower() and "log" in c.name.lower())
            or c.name.lower() in ("❀ yuna・logs", "🌸 yuna・logs", "yuna logs", "yuna-logs", "yuna_logs"),
            guild.categories
        )

    if not category:
        return []

    # Standardize category name to official aesthetic name
    if can_manage and category.name != OFFICIAL_LOGS_CATEGORY_NAME:
        try:
            await category.edit(name=OFFICIAL_LOGS_CATEGORY_NAME, reason="Yuna Logs: Standardize category name")
        except Exception:
            pass

    if not style:
        style = detect_yuna_logs_style(guild, category)

    renamed_list: List[tuple[discord.TextChannel, str, str]] = []
    seen_types: Dict[str, discord.TextChannel] = {}

    cat_text_channels = getattr(category, "text_channels", None)
    if cat_text_channels is None and hasattr(category, "channels"):
        cat_text_channels = [c for c in category.channels if getattr(c, 'type', None) == discord.ChannelType.text or hasattr(c, 'send')]
    if not cat_text_channels:
        return []

    # Sort channels by position/creation for deterministic order
    channels = sorted(list(cat_text_channels), key=lambda c: (getattr(c, 'position', 0), getattr(c, 'created_at', None) or getattr(c, 'id', 0)))

    for ch in channels:
        raw_key = identify_log_channel_type(ch.name)
        if not raw_key:
            norm = normalize_channel_name(ch.name)
            clean = norm.replace("yuna", "").replace("audit", "").replace("intel", "").replace("trace", "").strip(".-_・﹒․│┊┃❀🌸⠀ ")
            raw_key = clean if clean else None

        if not raw_key:
            continue

        target_name = format_channel_name(raw_key, style, "Yuna")

        # Duplicate channel detection within Yuna Logs
        if raw_key in seen_types:
            existing = seen_types[raw_key]
            ch_is_yuna = getattr(ch, "topic", None) and any(
                t in ch.topic for t in ("Automated Audit Logs", "Antinuke Security Alerts")
            )
            existing_is_yuna = getattr(existing, "topic", None) and any(
                t in existing.topic for t in ("Automated Audit Logs", "Antinuke Security Alerts")
            )

            if ch_is_yuna and not existing_is_yuna:
                # 'ch' is authentic Yuna channel, ignore user duplicate 'existing'
                seen_types[raw_key] = ch
                continue
            elif existing_is_yuna and not ch_is_yuna:
                # 'existing' is authentic Yuna channel, ignore user duplicate 'ch'
                continue
            else:
                # Both are internal duplicates; keep the styled one and clean up the redundant one
                if ch.name == target_name and existing.name != target_name:
                    to_delete, primary = existing, ch
                    seen_types[raw_key] = ch
                else:
                    to_delete, primary = ch, existing

                try:
                    await to_delete.delete(reason="Yuna Logs: Cleanup duplicate logging channel")
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
                continue

        seen_types[raw_key] = ch

        # Ensure channel text styling, permission sync, and mute/active topic
        if can_manage:
            edit_fields = {}
            if ch.name != target_name:
                edit_fields["name"] = target_name
            if not getattr(ch, "permissions_synced", False):
                edit_fields["sync_permissions"] = True

            desired_topic = (
                "<a:37496alert:1550972111215009914> High-Priority Antinuke Security Alerts (Notifications Active)"
                if raw_key in ("antinuke", "security")
                else "🔕 Automated Audit Logs (Notifications Muted / Silent)"
            )
            if getattr(ch, "topic", None) != desired_topic:
                edit_fields["topic"] = desired_topic

            if edit_fields:
                try:
                    old_name = ch.name
                    edit_fields["reason"] = "Yuna Logs: Standardize channel style & permissions"
                    await ch.edit(**edit_fields)
                    if "name" in edit_fields:
                        renamed_list.append((ch, old_name, target_name))
                    await asyncio.sleep(0.35)  # Gentle spacing for Discord rate limits
                except Exception as ren_err:
                    print(f"[Yuna Logs Style Rename Warning] #{ch.name} ({ch.id}): {ren_err}", flush=True)

    return renamed_list


async def ensure_channel_in_yuna_logs(
    guild: discord.Guild,
    channel: Optional[discord.TextChannel],
    category: Optional[discord.CategoryChannel] = None
) -> Optional[discord.TextChannel]:
    """
    Ensures that the given channel is positioned under the 'Yuna Logs' category
    and that its text styling matches the category's standard format.
    """
    if not guild or not channel:
        return channel

    can_manage = getattr(guild.me, "guild_permissions", None) and guild.me.guild_permissions.manage_channels

    if category is None or category.name.lower() != "yuna logs":
        category = await get_or_create_yuna_logs_category(guild)

    if not category:
        return channel

    current_cat = getattr(channel, "category", None)
    if not current_cat or current_cat.id != category.id:
        if can_manage:
            try:
                await channel.edit(category=category, sync_permissions=True, reason="Moving security log channel under Yuna Logs category")
            except Exception as e:
                print(f"[YUNA LOGS MOVE WARNING] Could not move #{channel.name} ({channel.id}) to {category.name}: {e}", flush=True)

    # Standardize style if channel name doesn't match category's text style
    if can_manage:
        try:
            log_type = identify_log_channel_type(channel.name)
            if log_type:
                style = detect_yuna_logs_style(guild, category)
                styled_name = format_channel_name(log_type, style, "Yuna")
                if channel.name != styled_name:
                    await channel.edit(name=styled_name, reason="Yuna Logs: Standardize channel text style to match category")
        except Exception:
            pass

    return channel


async def sync_security_log_channels_to_yuna_logs(
    guild: discord.Guild,
    category: Optional[discord.CategoryChannel] = None
) -> List[discord.TextChannel]:
    """
    Identifies previously created security log channels (Nightmode, Antinuke, Automod) in the guild:
    - Resolves duplicates per feature by keeping the primary (configured DB channel or oldest).
    - Safely deletes any redundant/duplicate channels if bot has manage_channels permission.
    - Moves each primary channel under the official 'Yuna Logs' category.
    - Standardizes all channel names to match the EXACT text styling, casing, font, and delimiter format of Yuna Logs.
    - Synchronizes database configurations.
    """
    if not guild or not getattr(guild.me, "guild_permissions", None) or not guild.me.guild_permissions.manage_channels:
        return []

    # Ensure category exists and duplicate categories are resolved
    if category is None or category.name.lower() != "yuna logs":
        category = await get_or_create_yuna_logs_category(guild)

    if not category:
        return []

    style = detect_yuna_logs_style(guild, category)
    styled_nm_name = format_channel_name("nightmode", style, "Yuna")
    styled_anti_name = format_channel_name("antinuke", style, "Yuna")
    styled_am_name = format_channel_name("automod", style, "Yuna")

    text_channels = getattr(guild, "text_channels", [])
    moved_channels: List[discord.TextChannel] = []

    # ================= 1. NIGHTMODE DUPLICATE MANAGEMENT & MIGRATION =================
    try:
        nm_db_id = None
        from core.database.connection_pool import db_pool
        row = await db_pool.fetch_one('db/anti.db', "SELECT log_channel FROM nightmode_config WHERE guild_id = ?", (guild.id,))
        if row and row[0]:
            nm_db_id = int(row[0])

        nm_matches = [
            ch for ch in text_channels
            if ch.id == nm_db_id
            or ch.name == styled_nm_name
            or identify_log_channel_type(ch.name) == "nightmode"
            or ch.name.lower() in ("yuna-nightmode", "nightmode-logs", "night-mode-logs")
        ]
        # De-duplicate by ID
        nm_matches = list({ch.id: ch for ch in nm_matches}.values())

        if nm_matches:
            primary_nm = None
            if nm_db_id:
                primary_nm = discord.utils.get(nm_matches, id=nm_db_id)
            if not primary_nm:
                primary_nm = discord.utils.find(lambda c: c.name == styled_nm_name, nm_matches)
            if not primary_nm:
                primary_nm = min(nm_matches, key=lambda c: getattr(c, 'created_at', None) or c.id)

            # Delete any duplicate channels
            for dup in nm_matches:
                if dup.id != primary_nm.id:
                    try:
                        await dup.delete(reason="Yuna: Cleanup duplicate Nightmode channel")
                        await asyncio.sleep(0.3)
                    except Exception as dup_err:
                        print(f"[YUNA DUPE CLEANUP ERROR] Nightmode #{dup.name} ({dup.id}): {dup_err}", flush=True)

            # Move primary under Yuna Logs & ensure standard text styling
            edit_kwargs = {}
            if not primary_nm.category or primary_nm.category.id != category.id:
                edit_kwargs["category"] = category
            if primary_nm.name != styled_nm_name:
                edit_kwargs["name"] = styled_nm_name

            if edit_kwargs:
                try:
                    await primary_nm.edit(**edit_kwargs, reason="Moving & standardizing Nightmode log channel under Yuna Logs")
                    moved_channels.append(primary_nm)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            # Synchronize DB
            if nm_db_id != primary_nm.id:
                try:
                    async with aiosqlite.connect('db/anti.db') as db:
                        await db.execute("UPDATE nightmode_config SET log_channel = ? WHERE guild_id = ?", (primary_nm.id, guild.id))
                        await db.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"[YUNA SYNC NIGHTMODE ERROR] '{guild.name}' ({guild.id}): {e}", flush=True)

    # ================= 2. ANTINUKE DUPLICATE MANAGEMENT & MIGRATION =================
    try:
        anti_db_id = None
        from core.database.connection_pool import db_pool
        row = await db_pool.fetch_one('db/anti.db', "SELECT log_channel FROM antinuke WHERE guild_id = ?", (guild.id,))
        if row and row[0]:
            anti_db_id = int(row[0])

        anti_matches = [
            ch for ch in text_channels
            if ch.id == anti_db_id
            or ch.name == styled_anti_name
            or identify_log_channel_type(ch.name) == "antinuke"
            or ch.name.lower() in ("yuna-antinuke", "antinuke-logs", "antinuke-log", "security-logs", "yuna-security-logs")
        ]
        anti_matches = list({ch.id: ch for ch in anti_matches}.values())

        if anti_matches:
            primary_anti = None
            if anti_db_id:
                primary_anti = discord.utils.get(anti_matches, id=anti_db_id)
            if not primary_anti:
                primary_anti = discord.utils.find(lambda c: c.name == styled_anti_name, anti_matches)
            if not primary_anti:
                primary_anti = min(anti_matches, key=lambda c: getattr(c, 'created_at', None) or c.id)

            # Delete any duplicate channels
            for dup in anti_matches:
                if dup.id != primary_anti.id:
                    try:
                        await dup.delete(reason="Yuna: Cleanup duplicate Antinuke channel")
                        await asyncio.sleep(0.3)
                    except Exception as dup_err:
                        print(f"[YUNA DUPE CLEANUP ERROR] Antinuke #{dup.name} ({dup.id}): {dup_err}", flush=True)

            # Move primary under Yuna Logs & ensure standard text styling
            edit_kwargs = {}
            if not primary_anti.category or primary_anti.category.id != category.id:
                edit_kwargs["category"] = category
            if primary_anti.name != styled_anti_name:
                edit_kwargs["name"] = styled_anti_name

            if edit_kwargs:
                try:
                    await primary_anti.edit(**edit_kwargs, reason="Moving & standardizing Antinuke log channel under Yuna Logs")
                    moved_channels.append(primary_anti)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            # Synchronize DB
            if anti_db_id != primary_anti.id:
                try:
                    async with aiosqlite.connect('db/anti.db') as db:
                        await db.execute('''
                            CREATE TABLE IF NOT EXISTS antinuke (
                                guild_id INTEGER PRIMARY KEY,
                                status BOOLEAN DEFAULT 0,
                                log_channel INTEGER
                            )
                        ''')
                        await db.execute("UPDATE antinuke SET log_channel = ? WHERE guild_id = ?", (primary_anti.id, guild.id))
                        await db.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"[YUNA SYNC ANTINUKE ERROR] '{guild.name}' ({guild.id}): {e}", flush=True)

    # ================= 3. AUTOMOD DUPLICATE MANAGEMENT & MIGRATION =================
    try:
        am_db_id = None
        from core.database.connection_pool import db_pool
        row = await db_pool.fetch_one('db/automod.db', "SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
        if row and row[0]:
            am_db_id = int(row[0])

        am_matches = [
            ch for ch in text_channels
            if ch.id == am_db_id
            or ch.name == styled_am_name
            or identify_log_channel_type(ch.name) == "automod"
            or ch.name.lower() in ("yuna-automod", "automod-logs", "automod")
        ]
        am_matches = list({ch.id: ch for ch in am_matches}.values())

        if am_matches:
            primary_am = None
            if am_db_id:
                primary_am = discord.utils.get(am_matches, id=am_db_id)
            if not primary_am:
                primary_am = discord.utils.find(lambda c: c.name == styled_am_name, am_matches)
            if not primary_am:
                primary_am = min(am_matches, key=lambda c: getattr(c, 'created_at', None) or c.id)

            # Delete any duplicate channels
            for dup in am_matches:
                if dup.id != primary_am.id:
                    try:
                        await dup.delete(reason="Yuna: Cleanup duplicate AutoMod channel")
                        await asyncio.sleep(0.3)
                    except Exception as dup_err:
                        print(f"[YUNA DUPE CLEANUP ERROR] AutoMod #{dup.name} ({dup.id}): {dup_err}", flush=True)

            # Move primary under Yuna Logs & ensure standard text styling
            edit_kwargs = {}
            if not primary_am.category or primary_am.category.id != category.id:
                edit_kwargs["category"] = category
            if primary_am.name != styled_am_name:
                edit_kwargs["name"] = styled_am_name

            if edit_kwargs:
                try:
                    await primary_am.edit(**edit_kwargs, reason="Moving & standardizing AutoMod log channel under Yuna Logs")
                    moved_channels.append(primary_am)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            # Synchronize DB
            if am_db_id != primary_am.id:
                try:
                    async with aiosqlite.connect('db/automod.db') as db:
                        await db.execute("CREATE TABLE IF NOT EXISTS automod_logging (guild_id INTEGER PRIMARY KEY, log_channel INTEGER)")
                        await db.execute("INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?, ?)", (guild.id, primary_am.id))
                        await db.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"[YUNA SYNC AUTOMOD ERROR] '{guild.name}' ({guild.id}): {e}", flush=True)

    # ================= 4. UNIFY ALL EXISTING CHANNELS UNDER YUNA LOGS =================
    try:
        await standardize_all_yuna_logs_channels(guild, category=category, style=style)
    except Exception as std_err:
        print(f"[YUNA LOGS UNIFY ERROR] '{guild.name}' ({guild.id}): {std_err}", flush=True)

    return moved_channels


async def sync_all_security_log_channels(bot: commands.Bot) -> None:
    """
    DEPRECATED / DISABLED: Automatic global migration across all guilds is permanently disabled
    to prevent unprompted channel modifications. Configuration only occurs per-guild via '/logs setup'.
    """
    return


async def get_or_create_antinuke_log_channel(guild):
    """
    Checks for existing security log channels (in DB or matching names like yuna-antinuke, antinuke-logs, security-logs).
    - If an existing channel is found, reuses it and ensures it is under 'Yuna Logs' category with matching standard style.
    - If duplicate log channels exist (>1 channel), automatically deletes the duplicates and keeps the primary channel.
    - If no log channel exists anywhere, creates a new private text channel matching Yuna Logs style.
    """
    if not guild:
        return None, None

    import aiosqlite

    can_manage = getattr(guild.me, "guild_permissions", None) and guild.me.guild_permissions.manage_channels

    category = await get_or_create_yuna_logs_category(guild)
    style = detect_yuna_logs_style(guild, category)
    styled_name = format_channel_name("antinuke", style, "Yuna")

    # 1. Check database for saved log_channel
    saved_channel = None
    try:
        async with aiosqlite.connect('db/anti.db') as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS antinuke (
                    guild_id INTEGER PRIMARY KEY,
                    status BOOLEAN DEFAULT 0,
                    log_channel INTEGER
                )
            ''')
            async with db.execute("SELECT log_channel FROM antinuke WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    saved_channel = guild.get_channel(row[0])
                    if not saved_channel:
                        try:
                            saved_channel = await guild.fetch_channel(row[0])
                        except Exception:
                            saved_channel = None
    except Exception:
        pass

    def _norm_ch(n: str) -> str:
        return str(n or "").lower().replace("-", "").replace(" ", "").replace(".", "").replace("·", "").replace("․", "").replace("・", "").replace("⚛", "").replace("❀", "").replace("﹒", "").strip()

    valid_names = ("yuna-antinuke", "antinuke-logs", "antinuke-log", "yuna-logs", "security-logs", "yuna-security-logs")

    def _is_antinuke_log_channel(ch_obj) -> bool:
        if not ch_obj or not isinstance(ch_obj, discord.TextChannel):
            return False
        if saved_channel and ch_obj.id == saved_channel.id:
            return True
        cname = getattr(ch_obj, "name", "")
        if cname == styled_name or cname.lower() in valid_names:
            return True
        if identify_log_channel_type(cname) == "antinuke":
            return True
        norm_c = _norm_ch(cname)
        norm_s = _norm_ch(styled_name)
        if norm_c and (norm_c == norm_s or "antinuke" in norm_c):
            return True
        return False

    matching_channels = [ch for ch in getattr(guild, "text_channels", []) if _is_antinuke_log_channel(ch)]
    matching_channels = list({ch.id: ch for ch in matching_channels}.values())

    primary_channel = None
    if saved_channel and saved_channel in matching_channels:
        primary_channel = saved_channel
    elif matching_channels:
        # Prefer oldest channel to preserve existing audit logs and history
        primary_channel = min(matching_channels, key=lambda c: getattr(c, 'created_at', None) or c.id)

    if primary_channel:
        # Ensure under Yuna Logs category & styled name
        await ensure_channel_in_yuna_logs(guild, primary_channel, category=category)
        if primary_channel.name != styled_name and can_manage:
            try:
                await primary_channel.edit(name=styled_name, reason="Yuna Antinuke: Standardize channel text style")
            except Exception:
                pass

        # Clean up any other duplicate channels matching antinuke names
        if can_manage:
            for ch in matching_channels:
                if ch.id != primary_channel.id:
                    try:
                        await ch.delete(reason="Yuna Antinuke: Cleanup duplicate logging channel")
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass

        # Update DB if needed
        try:
            async with aiosqlite.connect('db/anti.db') as db:
                await db.execute("UPDATE antinuke SET log_channel = ? WHERE guild_id = ?", (primary_channel.id, guild.id))
                await db.commit()
        except Exception:
            pass

        return primary_channel, None

    # 3. Create new private logging channel ONLY if no existing channel exists
    if hasattr(guild, "fetch_channels"):
        try:
            live_channels = await guild.fetch_channels()
            fresh_matches = [ch for ch in live_channels if _is_antinuke_log_channel(ch)]
            if fresh_matches:
                primary_channel = min(fresh_matches, key=lambda c: getattr(c, 'created_at', None) or c.id)
                await ensure_channel_in_yuna_logs(guild, primary_channel, category=category)
                try:
                    async with aiosqlite.connect('db/anti.db') as db:
                        await db.execute("UPDATE antinuke SET log_channel = ? WHERE guild_id = ?", (primary_channel.id, guild.id))
                        await db.commit()
                except Exception:
                    pass
                return primary_channel, None
        except Exception:
            pass

    if not category:
        category = await get_or_create_yuna_logs_category(guild)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            use_external_emojis=True
        )
    }
    try:
        log_channel = await guild.create_text_channel(
            styled_name,
            category=category,
            overwrites=overwrites,
            reason="Antinuke Logging Channel Creation"
        )
        try:
            async with aiosqlite.connect('db/anti.db') as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS antinuke (
                        guild_id INTEGER PRIMARY KEY,
                        status BOOLEAN DEFAULT 0,
                        log_channel INTEGER
                    )
                ''')
                await db.execute("INSERT OR REPLACE INTO antinuke (guild_id, log_channel) VALUES (?, ?)", (guild.id, log_channel.id))
                await db.commit()
        except Exception:
            pass
        return log_channel, None
    except Exception:
        return None, None


_antinuke_log_channel_cache: Dict[int, tuple] = {}
_ANTINUKE_LOG_CHANNEL_TTL = 60.0

async def send_antinuke_log(guild, event_name: str, executor, action_taken: str, details: str = None, target = None, detection_time=None):
    """
    Fetches the configured antinuke log channel for the guild and dispatches an antinuke log embed
    through the rate-limit immune ChannelLogDispatcher. Also records into db/audit_logs.db for dashboard view.
    """
    if not guild:
        return

    display_event_name = _humanize_antinuke_event(event_name)

    # Always persist to dashboard audit log database (regardless of Discord channel configuration)
    try:
        import asyncio
        from core.dashboard_server import store_antinuke_event_log
        asyncio.create_task(store_antinuke_event_log(guild.id, display_event_name, executor, action_taken, _clean_security_text(details), target))
    except Exception:
        pass

    import time
    now = time.time()
    cached = _antinuke_log_channel_cache.get(guild.id)
    if cached and (now - cached[2]) < _ANTINUKE_LOG_CHANNEL_TTL:
        log_channel_id = cached[0]
        log_webhook_url = cached[1]
    else:
        log_channel_id = None
        log_webhook_url = None
        try:
            from core.database.connection_pool import db_pool
            row = await db_pool.fetch_one('db/anti.db', "SELECT log_channel, log_webhook FROM antinuke WHERE guild_id = ?", (guild.id,))
            if row:
                log_channel_id = row[0]
                if len(row) > 1:
                    log_webhook_url = row[1]
        except Exception:
            pass
        _antinuke_log_channel_cache[guild.id] = (log_channel_id, log_webhook_url, now)

    log_channel = None
    if log_channel_id:
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            try:
                log_channel = await guild.fetch_channel(log_channel_id)
            except Exception:
                log_channel = None

    if not log_channel and not log_webhook_url:
        # Fallback to searching matching channels
        matching_channels = [
            ch for ch in guild.text_channels 
            if ch.name.lower() in ("yuna-antinuke", "antinuke-logs", "antinuke-log")
        ]
        if matching_channels:
            log_channel = matching_channels[0]

    if not log_channel and not log_webhook_url:
        return

    try:
        embed = build_olympus_style_antinuke_embed(
            guild=guild,
            event_type=event_name,
            executor=executor,
            punishment=action_taken,
            is_authorized=bool("Authorized" in action_taken or "Allowed" in action_taken),
            details=details,
            target=target,
            detection_time=detection_time
        )

        sent_via_webhook = False
        if log_webhook_url:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    wh = discord.Webhook.from_url(log_webhook_url, session=session)
                    bot_name = guild.me.display_name if guild.me else "Yuna"
                    bot_avatar = guild.me.display_avatar.url if (guild.me and guild.me.display_avatar) else None
                    await wh.send(embed=embed, username=f"{bot_name} Sentinel", avatar_url=bot_avatar)
                    sent_via_webhook = True
            except Exception:
                sent_via_webhook = False

        if not sent_via_webhook and log_channel:
            from core.services.log_dispatcher import log_dispatcher
            log_dispatcher.enqueue_log(log_channel, embed)
    except Exception:
        pass

    try:
        from services.logger_v2 import LoggerServiceV2
        asyncio.create_task(LoggerServiceV2.send_v2_log(guild, "antinuke", embed=embed))
    except Exception:
        pass

    # Concurrently dispatch security report DM to server admins & owner
    try:
        is_auth = bool("Authorized" in action_taken or "Allowed" in action_taken)
        asyncio.create_task(send_antinuke_dm_report(
            guild=guild,
            event_type=event_name,
            executor=executor,
            target=target,
            is_authorized=is_auth,
            punishment=action_taken,
            reason=details or event_name,
            explanation=f"Anti-Nuke Protection triggered: {action_taken} ({details or 'Security Protocol Active'}).",
            detection_time=detection_time,
        ))
    except Exception:
        pass


_RECENT_DM_REPORTS: Dict[tuple, float] = {}

_ANTINUKE_ACTION_LABELS = {
    "chcr": "Channel created",
    "chdl": "Channel deleted",
    "chup": "Channel updated",
    "rlcr": "Role created",
    "rldl": "Role deleted",
    "rlup": "Role updated",
    "kick": "Member kick",
    "ban": "Member ban",
    "botadd": "Bot added",
    "prune": "Member prune",
    "memup": "Member role changes",
    "serverup": "Server settings changed",
    "mngweb": "Webhook changes",
}


def _humanize_antinuke_event(event_type) -> str:
    """Turn internal anti-nuke event strings and audit action codes into readable labels."""
    raw = str(event_type or "Security event").strip()
    code_match = re.search(r"\b(CHCR|CHDL|CHUP|RLCR|RLDL|RLUP|KICK|BAN|BOTADD|PRUNE|MEMUP|SERVERUP|MNGWEB)\b", raw, re.I)
    if code_match:
        label = _ANTINUKE_ACTION_LABELS.get(code_match.group(1).lower(), "Security event")
        if "stream" in raw.lower() or "unauthor" in raw.lower():
            return f"Unauthorized {label[0].lower() + label[1:]} detected"
        return label

    cleaned = re.sub(r"\s*\([^)]+\)\s*", " ", raw)
    cleaned = re.sub(r"\bAnti[- ]Nuke\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bAnti\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_[]")
    aliases = {
        "webhook update": "Webhook updated",
        "webhook create": "Webhook created",
        "webhook delete": "Webhook deleted",
        "channel update": "Channel updated",
        "channel create": "Channel created",
        "channel delete": "Channel deleted",
        "role update": "Role updated",
        "role create": "Role created",
        "role delete": "Role deleted",
        "guild update": "Server settings changed",
        "member role update": "Member roles changed",
    }
    return aliases.get(cleaned.lower(), cleaned[:1].upper() + cleaned[1:] if cleaned else "Security event")


def _clean_security_text(value) -> str:
    """Remove Python object reprs from alert text while retaining useful type and ID details."""
    text = str(value or "").strip()
    text = re.sub(
        r"<Object\s+id=(\d+)\s+type=<class\s+'([^']+)'\s*>>",
        lambda match: f"{match.group(2).rsplit('.', 1)[-1].replace('_', ' ')} (ID: {match.group(1)})",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"<(Webhook|Role|TextChannel|VoiceChannel|StageChannel|ForumChannel|Member|User|Thread)\s+id=(\d+)[^>]*>",
        lambda match: f"{match.group(1)} (ID: {match.group(2)})",
        text,
        flags=re.I,
    )
    return text[:900]


def _target_type_name(target, event_label: str) -> str:
    if target is None:
        return "Unknown target"
    class_name = type(target).__name__.lower()
    if "webhook" in class_name or "webhook" in event_label.lower():
        return "Webhook"
    if "role" in class_name:
        return "Role"
    if "channel" in class_name or "thread" in class_name or "channel" in event_label.lower():
        return "Channel"
    if "member" in class_name or "user" in class_name:
        return "Member"
    if "guild" in class_name or "server" in event_label.lower():
        return "Server"
    if class_name == "object":
        return "Discord object"
    return class_name.replace("_", " ").replace("async ", "").title() or "Unknown target"


def _format_alert_actor(actor) -> str:
    actor_id = getattr(actor, "id", None)
    name = getattr(actor, "display_name", None) or getattr(actor, "global_name", None) or getattr(actor, "name", None)
    if not name and actor_id:
        name = f"<@{actor_id}>"
    if not name:
        name = "Unknown executor"
    return f"**{_clean_security_text(name)}**\nID: `{actor_id}`" if actor_id else f"**{_clean_security_text(name)}**"


def _format_alert_target(target, event_label: str) -> str:
    if target is None:
        return "Unknown target\nID: `Unavailable`"
    target_id = getattr(target, "id", None)
    target_type = _target_type_name(target, event_label)
    name = getattr(target, "display_name", None) or getattr(target, "name", None)
    if isinstance(target, str):
        # Handle a legacy Object repr safely, without rendering the Python representation.
        match = re.search(r"<Object\s+id=(\d+)\s+type=<class\s+'([^']+)'", target)
        if match:
            target_id = target_id or match.group(1)
            class_name = match.group(2).rsplit(".", 1)[-1]
            target_type = "Webhook" if "webhook" in class_name.lower() else class_name.replace("_", " ").title()
        else:
            name = _clean_security_text(target)
    identity = f"Type: {target_type} · ID: `{target_id or 'Unavailable'}`"
    return f"**{_clean_security_text(name)}**\n{identity}" if name else identity


def _format_olympus_event_label(event_type: str) -> str:
    """Format event into clean 'Unauthorized <Action>' label matching Olympus style."""
    raw = str(event_type or "").lower().strip()
    if "chcr" in raw or "channel create" in raw:
        return "Unauthorized Channel Create"
    if "chdl" in raw or "channel delete" in raw:
        return "Unauthorized Channel Delete"
    if "chup" in raw or "channel update" in raw:
        return "Unauthorized Channel Update"
    if "rlcr" in raw or "role create" in raw:
        return "Unauthorized Role Create"
    if "rldl" in raw or "role delete" in raw:
        return "Unauthorized Role Delete"
    if "rlup" in raw or "role update" in raw:
        return "Unauthorized Role Update"
    if "botadd" in raw or "bot add" in raw:
        return "Unauthorized Bot Add"
    if "kick" in raw:
        return "Unauthorized Member Kick"
    if "ban" in raw:
        return "Unauthorized Member Ban"
    if "webhook" in raw:
        return "Unauthorized Webhook Action"
    if "prune" in raw:
        return "Unauthorized Member Prune"
    if "memup" in raw or "member role" in raw:
        return "Unauthorized Member Role Update"
    if "guild" in raw or "server" in raw:
        return "Unauthorized Server Update"
    if "everyone" in raw:
        return "Unauthorized Everyone Mention"
    if "integration" in raw:
        return "Unauthorized Integration Update"
    return "Unauthorized Security Action"


def build_olympus_style_antinuke_embed(
    guild: discord.Guild,
    event_type: str,
    executor,
    punishment: str = "Banned",
    is_authorized: bool = False,
    details: str = None,
    target = None,
    detection_time = None
) -> discord.Embed:
    detected_at = detection_time or discord.utils.utcnow()
    if not getattr(detected_at, "tzinfo", None):
        detected_at = detected_at.replace(tzinfo=discord.utils.utcnow().tzinfo)

    event_display = _format_olympus_event_label(event_type)

    # Offender / Target formatting
    exec_id = getattr(executor, "id", None)
    if exec_id:
        target_mention = f"<@{exec_id}>"
        target_id_str = str(exec_id)
    else:
        target_name = getattr(executor, "name", str(executor or "Unknown User"))
        target_mention = f"@{target_name}"
        target_id_str = "Unknown"

    punish_str = str(punishment or "").lower()
    is_failed = "failed" in punish_str or "could not" in punish_str or "hierarchy" in punish_str

    if is_authorized or "author" in punish_str or "allow" in punish_str:
        embed_color = 0x57F287  # Green
        action_name = "Action"
        action_val = f"Action Status : ℹ️ | Authorized Action Allowed"
        desc_lines = [
            f"• Authorized Action: {target_mention} performed {event_display.replace('Unauthorized ', '')}",
            "• If User is trusted, please whitelist them to avoid future punishments."
        ]
    elif is_failed:
        embed_color = 0xED4245  # Red
        action_name = "Action"
        action_val = f"Ban Status : ❌ | Could Not Ban {target_mention} (Role Hierarchy)"
        desc_lines = [
            f"• Detected {target_mention} performing {event_display}",
            "• If User is trusted, please whitelist them to avoid future punishments."
        ]
    elif "kick" in punish_str:
        embed_color = 0xFF0033  # Vivid Red
        action_name = "Action"
        action_val = f"Kick Status : ✅ | {target_mention} Successfully Kicked"
        desc_lines = [
            f"• Punished {target_mention} For {event_display}",
            "• If User is trusted, please whitelist them to avoid future punishments."
        ]
    elif "quarantine" in punish_str or "strip" in punish_str:
        embed_color = 0xFF0033
        action_name = "Action"
        action_val = f"Quarantine Status : ✅ | {target_mention} Stripped Of Roles"
        desc_lines = [
            f"• Punished {target_mention} For {event_display}",
            "• If User is trusted, please whitelist them to avoid future punishments."
        ]
    else:
        # Default: Successfully Banned
        embed_color = 0xFF0033  # Vivid Red
        action_name = "Action"
        action_val = f"Ban Status : ✅ | {target_mention} Successfully Banned"
        desc_lines = [
            f"• Punished {target_mention} For {event_display}",
            "• If User is trusted, please whitelist them to avoid future punishments."
        ]

    embed = discord.Embed(
        title="🛡️ Anti Nuke",
        description="\n".join(desc_lines),
        color=embed_color,
        timestamp=detected_at
    )

    bot_avatar = None
    if getattr(guild, "me", None):
        me_avatar = getattr(guild.me, "display_avatar", None) or getattr(guild.me, "avatar", None)
        if me_avatar:
            bot_avatar = getattr(me_avatar, "url", None) or str(me_avatar)

    embed.set_author(name="Yuna Development", icon_url=bot_avatar)
    embed.add_field(name=action_name, value=action_val, inline=False)

    # Moderator field (the bot)
    bot_mention = guild.me.mention if getattr(guild, "me", None) else "@YUNA"
    bot_id_val = guild.me.id if getattr(guild, "me", None) else "1525256351171739678"
    embed.add_field(name="Moderator", value=f"{bot_mention}\n(ID: {bot_id_val})", inline=True)

    # Target field (the offender)
    embed.add_field(name="Target", value=f"{target_mention}\n(ID: {target_id_str})", inline=True)

    # Thumbnail (bot shield/avatar)
    if bot_avatar:
        embed.set_thumbnail(url=bot_avatar)
    elif getattr(guild, "icon", None):
        embed.set_thumbnail(url=guild.icon.url)

    # Footer: {guild.name} {guild.id} • Today at HH:MM (rendered by Discord timestamp)
    embed.set_footer(text=f"{guild.name} {guild.id}")
    return embed


def _classify_antinuke_outcome(is_authorized: bool, punishment) -> tuple[str, int, str]:
    action = _clean_security_text(punishment) or "No action details available"
    if is_authorized:
        return "AUTHORIZED", 0x5865F2, "✅"
    lowered = action.lower()
    restorative_terms = ("unbanned target", "restored", "cleaned", "reverted", "removed", "auto-delete", "stripped")
    if "failed" in lowered or ("attempted ban" in lowered and not any(term in lowered for term in restorative_terms)):
        return "FAILED", 0xED4245, "⚠️"
    if "ban" in lowered or any(term in lowered for term in restorative_terms) or "blocked" in lowered:
        return "BLOCKED", 0xED4245, "🛡️"
    return "ACTION TAKEN", 0xF0A33A, "🛡️"


def _humanize_antinuke_action(punishment) -> str:
    action = _clean_security_text(punishment) or "No action details available"
    lowered = action.lower()
    if "attempted ban" in lowered and "unbanned target" in lowered:
        return "Restored the affected member; the offender ban failed"
    if "instant banned offender" in lowered and "unbanned target" in lowered:
        return "Banned the offender and restored the affected member"
    if "instant banned offender" in lowered and "cleaned webhooks" in lowered:
        return "Banned the offender and removed unauthorized webhooks"
    if "instant banned offender" in lowered:
        return "Banned the offending account"
    if "ban failed" in lowered or "attempted ban" in lowered:
        if "higher role" in lowered:
            return "Ban failed because Yuna’s role is below the initiator’s role"
        return "Yuna could not ban the offending account"
    return action

async def send_antinuke_dm_report(
    guild: discord.Guild,
    event_type: str,
    executor: Any,
    target: Any = None,
    is_authorized: bool = True,
    punishment: str = "None",
    reason: str = "Integration Event (Authorised)",
    explanation: str = "This action was authorised — the executor is whitelisted or has permission to perform this action.",
    detection_time=None,
):
    """
    Dispatches a high-security DM alert to the server owner, extra owner, and server administrators
    matching the Anti-Nuke DM Security Report format with an animated ticking checkmark emoji (<a:tick:1558726958802800660>).
    """
    if not guild:
        return

    # Check guild DM notification setting
    try:
        from utils.settings_manager import get_guild_setting
        if not get_guild_setting(guild.id, "dm_notifications", True):
            return
    except Exception:
        pass

    # Deduplicate alerts fired within 15 seconds for the same action
    import time
    now_ts = time.time()
    exec_id = getattr(executor, 'id', None)
    target_id = getattr(target, 'id', None)
    clean_event = str(event_type).lower().strip().replace("anti ", "").replace(" (unauthorized)", "").replace("member ", "")
    dedup_key = (guild.id, clean_event, exec_id, target_id)

    # Prune old cache entries
    for k in list(_RECENT_DM_REPORTS.keys()):
        if now_ts - _RECENT_DM_REPORTS[k] > 15.0:
            _RECENT_DM_REPORTS.pop(k, None)

    if dedup_key in _RECENT_DM_REPORTS:
        return
    _RECENT_DM_REPORTS[dedup_key] = now_ts


    recipients = []
    seen_ids = set()

    def add_recipient(user):
        if user and not getattr(user, 'bot', False) and user.id not in seen_ids:
            # Don't DM the executor about their own action unless they are the server owner
            if exec_id and user.id == exec_id and user.id != getattr(guild, 'owner_id', None):
                return
            seen_ids.add(user.id)
            recipients.append(user)

    # 1. Guild Owner
    owner = getattr(guild, "owner", None)
    if not owner and hasattr(guild, "owner_id") and guild.owner_id:
        owner = guild.get_member(guild.owner_id)
        if not owner:
            try:
                owner = await guild.fetch_member(guild.owner_id)
            except Exception:
                pass
        if not owner:
            try:
                from core import BotBase
                bot = BotBase.get_instance()
                if bot:
                    owner = bot.get_user(guild.owner_id) or await bot.fetch_user(guild.owner_id)
            except Exception:
                pass
    if owner:
        add_recipient(owner)

    # 2. Extra Owner(s)
    try:
        from core.cache.security_cache import security_cache
        extra_owner_id = security_cache.get_extra_owner(guild.id)
        if extra_owner_id and str(extra_owner_id).isdigit():
            e_id = int(extra_owner_id)
            eo = guild.get_member(e_id)
            if not eo:
                try:
                    from core import BotBase
                    bot = BotBase.get_instance()
                    if bot:
                        eo = bot.get_user(e_id) or await bot.fetch_user(e_id)
                except Exception:
                    pass
            if eo:
                add_recipient(eo)
    except Exception:
        pass

    # 3. Server Admins (Users with Administrator permission)
    try:
        if hasattr(guild, "chunked") and not guild.chunked and hasattr(guild, "chunk"):
            try:
                await guild.chunk()
            except Exception:
                pass

        for m in guild.members:
            if not m.bot and m.guild_permissions.administrator:
                add_recipient(m)

        for role in guild.roles:
            if role.permissions.administrator:
                for m in role.members:
                    if not m.bot:
                        add_recipient(m)
    except Exception:
        pass

    if not recipients:
        return

    try:
        embed = build_olympus_style_antinuke_embed(
            guild=guild,
            event_type=event_type,
            executor=executor,
            punishment=punishment,
            is_authorized=is_authorized,
            details=reason,
            target=target,
            detection_time=detection_time
        )

        # Dispatch to all server admins (capped at 10 to avoid Discord API rate-limiting)
        for admin in recipients[:10]:
            try:
                await admin.send(embed=embed)
                await asyncio.sleep(0.2)  # Gentle spacing for Discord DM rate limits
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass
            except Exception as e:
                print(f"[DM SECURITY REPORT WARNING] Could not DM admin {admin.id}: {e}")
    except Exception as e:
        print(f"[DM SECURITY REPORT WARNING] {e}")


def check_bot_hierarchy_and_admin(guild: discord.Guild) -> tuple[bool, bool, list[discord.Role]]:
    """
    Checks if Yuna has Administrator permission and if Yuna's highest role is on top.
    Returns (has_admin: bool, is_on_top: bool, roles_above: List[discord.Role]).
    """
    if not guild or not guild.me:
        return False, False, []

    has_admin = bool(getattr(guild.me.guild_permissions, 'administrator', False))
    my_top_role = getattr(guild.me, 'top_role', None)
    my_top_pos = getattr(my_top_role, 'position', 0) if my_top_role else 0
    
    # Roles above Yuna, excluding managed bot roles and @everyone
    roles_above = [
        r for r in guild.roles
        if r != getattr(guild, 'default_role', None)
        and not getattr(r, 'managed', False)
        and getattr(r, 'position', 0) > my_top_pos
    ]
    
    is_on_top = (len(roles_above) == 0)
    return has_admin, is_on_top, roles_above


def build_permission_and_hierarchy_warning(guild: discord.Guild) -> Optional[discord.Embed]:
    """
    Constructs a prominent warning embed if Yuna lacks Administrator or if its role is not on top.
    """
    if not guild or not guild.me:
        return None

    has_admin, is_on_top, roles_above = check_bot_hierarchy_and_admin(guild)
    if has_admin and is_on_top:
        return None

    embed = discord.Embed(
        title="⚠️ Important: Bot Permissions & Role Hierarchy Note",
        color=0xFEE75C,
        timestamp=discord.utils.utcnow()
    )

    warnings = []
    if not has_admin:
        warnings.append(
            "• ❌ **Missing Administrator Role / Permission**\n"
            "  Yuna currently lacks the **Administrator** permission. Without Administrator, Anti-Nuke, "
            "Auto-Recovery, and Anti-Raid systems cannot ban rogue admins or restore channels/roles."
        )

    if not is_on_top:
        sample_roles = ", ".join(f"`{r.name}`" for r in roles_above[:4])
        more = f" and {len(roles_above) - 4} more" if len(roles_above) > 4 else ""
        warnings.append(
            f"• ⚠️ **Bot Role is NOT on Top**\n"
            f"  Yuna's highest role (**{guild.me.top_role.name}**) is below {len(roles_above)} role(s): {sample_roles}{more}.\n"
            f"  *Discord's role hierarchy strictly forbids bots from banning, kicking, or managing anyone whose highest role is above the bot!*\n"
            f"  **Fix:** Open **Server Settings → Roles**, click and drag **{guild.me.top_role.name}** to the **very top** (just below Server Owner)."
        )

    embed.description = "\n\n".join(warnings)
    embed.set_footer(text="Yuna Security Shield • Server Health Note", icon_url=guild.me.display_avatar.url if guild.me else None)
    return embed


def parse_duration_string(val: str):
    """
    Parses duration strings like '60s', '5m', '15m', '1h', '1d', '7d', '10 mins', '1 hour'
    Returns a tuple (timedelta, formatted_label) or None if invalid.
    """
    import re
    from datetime import timedelta
    if not val:
        return None
    val = val.strip().lower()

    pattern = re.compile(r'(\d+)\s*([a-z]+)?')
    matches = pattern.findall(val)
    if not matches:
        return None

    total_seconds = 0
    formatted_parts = []

    unit_map = {
        's': ('seconds', 1, 's'),
        'sec': ('seconds', 1, 's'),
        'secs': ('seconds', 1, 's'),
        'second': ('seconds', 1, 's'),
        'seconds': ('seconds', 1, 's'),
        'm': ('minutes', 60, 'm'),
        'min': ('minutes', 60, 'm'),
        'mins': ('minutes', 60, 'm'),
        'minute': ('minutes', 60, 'm'),
        'minutes': ('minutes', 60, 'm'),
        'h': ('hours', 3600, 'h'),
        'hr': ('hours', 3600, 'h'),
        'hrs': ('hours', 3600, 'h'),
        'hour': ('hours', 3600, 'h'),
        'hours': ('hours', 3600, 'h'),
        'd': ('days', 86400, 'd'),
        'day': ('days', 86400, 'd'),
        'days': ('days', 86400, 'd'),
        'w': ('weeks', 604800, 'w'),
        'week': ('weeks', 604800, 'w'),
        'weeks': ('weeks', 604800, 'w'),
    }

    for num_str, unit_str in matches:
        num = int(num_str)
        unit_str = unit_str.strip() if unit_str else 'm'
        if unit_str in unit_map:
            name, mult, short = unit_map[unit_str]
            total_seconds += num * mult
            formatted_parts.append(f"{num}{short}")
        else:
            return None

    if total_seconds <= 0:
        return None

    # Discord max timeout duration is 28 days (2419200 seconds)
    if total_seconds > 2419200:
        total_seconds = 2419200
        formatted_label = "28d"
    else:
        formatted_label = " ".join(formatted_parts)

    return timedelta(seconds=total_seconds), formatted_label


def slow_delete_message(message: Optional[discord.Message], delay: float = 1.0) -> None:
    """Safely and slowly deletes a message in the background with rate limit backoff.
    Prevents Discord HTTP 429 rate limit spikes during chat/VC cleanup.
    """
    if not message:
        return
    try:
        from core.discord.request_manager import request_manager
        request_manager.slow_delete(message, delay=delay)
    except Exception:
        async def _fallback_delete():
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                await message.delete()
            except Exception:
                pass
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        loop.create_task(_fallback_delete())
