"""
YUNA Central Time & Timezone Utilities.
Provides unified, robust, and timezone-aware handling for Indian Standard Time (IST)
and UTC, preventing Python 3.12 datetime deprecation warnings and SQLite midnight offsets.
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import logging
import sys
import builtins
import re

# 1. Official Timezones
IST = timezone(timedelta(hours=5, minutes=30), name="IST")
UTC = timezone.utc

__all__ = [
    "IST", "UTC", "now_ist", "now_utc", "utcnow", "to_ist", "format_ist_date",
    "format_ist_time", "format_ist_full", "today_ist_str", "get_epoch",
    "discord_timestamp", "ist_converter", "YunaLogFormatter", "setup_ist_logging",
    "install_ist_print_hook", "set_global_bot", "register_guild",
    "register_guilds_from_bot", "get_guild_name", "enrich_log_with_guild_name"
]


def now_ist() -> datetime:
    """Returns the current timezone-aware datetime in Indian Standard Time (IST, UTC+05:30)."""
    return datetime.now(IST)


def now_utc() -> datetime:
    """Returns the current timezone-aware datetime in UTC (replaces deprecated datetime.utcnow())."""
    return datetime.now(UTC)


def utcnow() -> datetime:
    """Convenience alias for now_utc()."""
    return now_utc()


def today_ist_str() -> str:
    """Returns today's date in IST as 'YYYY-MM-DD'."""
    return format_ist_date()


def to_ist(dt: Optional[datetime] = None) -> datetime:
    """Converts any datetime (UTC or aware) into IST. If naive, assumes UTC."""
    if dt is None:
        return now_ist()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)


def format_ist_date(dt: Optional[datetime] = None) -> str:
    """Returns formatted IST date string: 'YYYY-MM-DD' (e.g. '2026-09-13')."""
    target = to_ist(dt)
    return target.strftime("%Y-%m-%d")


def format_ist_time(dt: Optional[datetime] = None, include_seconds: bool = True) -> str:
    """Returns formatted IST time string: 'HH:MM:SS AM/PM IST' (12-hour AM/PM)."""
    target = to_ist(dt)
    fmt = "%I:%M:%S %p IST" if include_seconds else "%I:%M %p IST"
    return target.strftime(fmt)


def format_ist_full(dt: Optional[datetime] = None) -> str:
    """Returns human-friendly full IST date & time: '13 September 2026, 02:45 PM IST'."""
    target = to_ist(dt)
    return target.strftime("%d %B %Y, %I:%M %p IST")


def get_epoch(dt: Optional[datetime] = None) -> int:
    """Returns the integer Unix epoch timestamp for any datetime."""
    if dt is None:
        return int(now_utc().timestamp())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())


def discord_timestamp(dt: Optional[datetime] = None, style: str = "F") -> str:
    """Returns a Discord markdown dynamic timestamp: '<t:epoch:style>'.
    Styles:
        't': Short Time (e.g. 2:45 PM)
        'T': Long Time (e.g. 2:45:00 PM)
        'd': Short Date (e.g. 13/09/2026)
        'D': Long Date (e.g. 13 September 2026)
        'f': Short Date/Time (e.g. 13 September 2026 2:45 PM)
        'F': Long Date/Time (e.g. Sunday, 13 September 2026 2:45 PM)
        'R': Relative Time (e.g. in 2 hours / 5 minutes ago)
    """
    epoch = get_epoch(dt)
    return f"<t:{epoch}:{style}>"


# ==========================================
# 📋 IST LOGGING CONVERTER & FORMATTER
# ==========================================

def ist_converter(seconds: Optional[float] = None):
    """Converts unix timestamp seconds into a time.struct_time in IST (UTC+05:30)."""
    if seconds is None:
        dt = datetime.now(IST)
    else:
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone(IST)
    return dt.timetuple()


# ==========================================
# 🏰 CENTRAL GUILD REGISTRY & ENRICHMENT
# ==========================================

_GLOBAL_BOT = None
_GUILD_REGISTRY: dict[int, str] = {}


def set_global_bot(bot):
    """Registers the running bot instance globally to resolve live guild names."""
    global _GLOBAL_BOT
    _GLOBAL_BOT = bot
    register_guilds_from_bot(bot)


def register_guild(guild_id: Union[int, str], guild_name: str):
    """Registers or updates a single guild ID -> server name mapping in RAM."""
    if guild_id and guild_name:
        try:
            _GUILD_REGISTRY[int(guild_id)] = str(guild_name)
        except Exception:
            pass


def register_guilds_from_bot(bot):
    """Extracts all connected guild names into the global in-memory registry."""
    if not bot:
        return
    try:
        for g in getattr(bot, "guilds", []):
            if hasattr(g, "id") and hasattr(g, "name"):
                _GUILD_REGISTRY[int(g.id)] = str(g.name)
    except Exception:
        pass


def get_guild_name(guild_id: Union[int, str]) -> Optional[str]:
    """Resolves a guild ID to its server name from live bot cache or local registry."""
    try:
        gid = int(guild_id)
        if _GLOBAL_BOT and hasattr(_GLOBAL_BOT, "get_guild"):
            g = _GLOBAL_BOT.get_guild(gid)
            if g and g.name:
                _GUILD_REGISTRY[gid] = g.name
                return g.name
        return _GUILD_REGISTRY.get(gid)
    except Exception:
        return None


def enrich_log_with_guild_name(text: str) -> str:
    """
    Scans a log string for guild IDs and ensures the server name is printed alongside:
    - 'Guild <id>' -> 'Guild \'<name>\' (<id>)'
    - 'guild <id>' -> 'guild \'<name>\' (<id>)'
    - '[TAG] <id>:' -> '[TAG] \'<name>\' (<id>):'
    - 'in/for/from guild <id>' -> 'in/for/from guild \'<name>\' (<id>)'
    If the server name is already present near the ID, the string is preserved as-is.
    """
    if not isinstance(text, str):
        return text

    def _repl_guild(m):
        prefix = m.group(1)
        gid_str = m.group(2)
        g_name = get_guild_name(gid_str)
        if g_name and g_name not in text:
            return f"{prefix}'{g_name}' ({gid_str})"
        return m.group(0)

    # 1. Match 'guild', 'Guild', 'guild_id', 'guild:' followed by snowflake
    res = re.sub(r'(\b[Gg]uild(?:[ _]id)?\s*[:=]?\s*)(\d{17,20})\b', _repl_guild, text)

    # 2. Match bracket prefix: '[TAG] <guild_id>'
    def _repl_bracket(m):
        prefix = m.group(1)
        gid_str = m.group(2)
        g_name = get_guild_name(gid_str)
        if g_name and g_name not in text:
            return f"{prefix}'{g_name}' ({gid_str})"
        return m.group(0)

    res = re.sub(r'(\[[^\]]+\]\s*)(\d{17,20})\b', _repl_bracket, res)

    # 3. Match 'in/for/from guild <id>'
    def _repl_prep(m):
        prefix = m.group(1)
        gid_str = m.group(2)
        g_name = get_guild_name(gid_str)
        if g_name and g_name not in text:
            return f"{prefix}'{g_name}' ({gid_str})"
        return m.group(0)

    res = re.sub(r'(\b(?:in|for|from)\s+guild\s+)((?:\'|\")?[^\'\"\(]+(?:\'|\")?\s*)?(\d{17,20})\b', _repl_prep, res)
    return res


class YunaLogFormatter(logging.Formatter):
    """Discord/Standard logging formatter that displays timestamps in 12-hour format with an explicit 'IST' label."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("datefmt", "%Y-%m-%d %I:%M:%S %p")
        super().__init__(*args, **kwargs)
        self.datefmt = "%Y-%m-%d %I:%M:%S %p"
        try:
            import discord.utils
            if hasattr(discord.utils, "_ColourFormatter"):
                self._colour_formatter = discord.utils._ColourFormatter()
                for level, fmt_obj in self._colour_formatter.FORMATS.items():
                    fmt_obj.datefmt = "%Y-%m-%d %I:%M:%S %p"
                    if "%(asctime)s IST" not in fmt_obj._style._fmt:
                        fmt_obj._style._fmt = fmt_obj._style._fmt.replace(
                            "%(asctime)s", "%(asctime)s IST"
                        )
            else:
                self._colour_formatter = None
        except Exception:
            self._colour_formatter = None

    def format(self, record):
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = enrich_log_with_guild_name(record.msg)
        if self._colour_formatter:
            return self._colour_formatter.format(record)
        return super().format(record)


_orig_print = builtins.print
_ANSI_STRIP = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
_TS_REGEX = re.compile(r'^\[?\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)?(\s*IST)?\]?|^\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}:\d{2}', re.IGNORECASE)


def install_ist_print_hook():
    """Enhances builtins.print to automatically prefix un-timestamped log messages with 12-hour AM/PM IST time and enrich guild IDs with server names."""
    if getattr(builtins.print, "_yuna_hooked", False):
        return

    def yuna_print(*args, **kwargs):
        file = kwargs.get("file", None)
        if (file is None or file in (sys.stdout, sys.stderr)) and args:
            new_args = []
            for a in args:
                if isinstance(a, str):
                    new_args.append(enrich_log_with_guild_name(a))
                else:
                    new_args.append(a)
            args = tuple(new_args)

            first_arg = str(args[0])
            clean = _ANSI_STRIP.sub('', first_arg).strip()
            # Only prefix if not a separator/empty and doesn't already have an IST or timestamp prefix
            if clean and not (set(clean) <= {'*', '-', '=', '#', '_', ' '}) and not _TS_REGEX.match(clean):
                ts_prefix = f"\x1b[38;5;197m[\x1b[0m{format_ist_time()}\x1b[38;5;197m]\x1b[0m -> "
                args = (ts_prefix + first_arg,) + args[1:]
        return _orig_print(*args, **kwargs)

    yuna_print._yuna_hooked = True
    builtins.print = yuna_print


def setup_ist_logging():
    """Globally configures Python standard logging, print(), and Loguru to print all logs in IST (12-hour AM/PM)."""
    # 1. Standard library logging converter (used by discord.py, pymongo, aiohttp, etc.)
    logging.Formatter.converter = staticmethod(ist_converter)

    # 2. Configure root logger with 12-hour AM/PM IST format if not already configured
    try:
        logging.basicConfig(
            level=logging.INFO,
            format="\x1b[38;5;197m[\x1b[0m%(asctime)s\x1b[38;5;197m]\x1b[0m -> \x1b[38;5;197m%(message)s\x1b[0m",
            datefmt="%I:%M:%S %p IST",
        )
        for handler in logging.root.handlers:
            if handler.formatter:
                handler.formatter.datefmt = "%I:%M:%S %p IST"
    except Exception:
        pass

    # 3. Loguru (used by core.logging)
    try:
        from loguru import logger
        logger.configure(patcher=lambda r: r.update(time=r["time"].astimezone(IST)))
    except ImportError:
        pass

    # 4. Global print hook for all logs in 12-hour AM/PM IST
    install_ist_print_hook()


# Auto-configure standard logging converter globally on import
logging.Formatter.converter = staticmethod(ist_converter)
install_ist_print_hook()
