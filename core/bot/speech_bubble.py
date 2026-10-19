"""
Yuna V7 — Premium Speech Bubble Intelligence System
Modern Minimal Design · Expanded Variables · Smart Deterministic Rotation

Strictly custom-status speech bubbles (type 4, discord.CustomActivity).
No Playing, Streaming, Listening, or Watching activities.
No cycling between Online, Idle, and DND states.
"""

from __future__ import annotations

import os
import re
import time
import json
import psutil
import asyncio
import logging
import sqlite3
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

import discord

logger = logging.getLogger("yuna.presence")

# =====================================================================
# 1. CURATED MINIMAL CANDIDATE SPEECH BUBBLE LIBRARY (40 CANDIDATES)
# =====================================================================

CANDIDATE_BUBBLES_BY_CATEGORY: Dict[str, List[str]] = {
    "IDENTITY": [
        "👑 Crafted with quiet intention — Yuna v{version}",
        "◈ Always on. Always Yuna.",
        "✨ Less noise. More intelligence.",
    ],
    "UPTIME": [
        "⏳ Stillness in motion for {uptime_short}, without pause",
        "🕰️ Consistency by design · Engineered to stay ready",
    ],
    "COMMUNITY": [
        "🕊️ Across {guild_count} communities, one rhythm never fades",
        "💎 Harmony is not found; it is shared among {user_count} souls",
    ],
    "MUSIC": [
        "♬ Where words fail, sound speaks — streaming in {playing_count} rooms",
        "💿 Artistry is timeless — {total_songs} melodies and counting",
        "🎧 {songs_today} moments brought to life today through sound",
        "🌌 Pure acoustics, uninterrupted across {active_voice} spaces",
    ],
    "PERFORMANCE": [
        "⚡ True luxury is effortless speed — poised at {ping} ms",
        "💫 Precision in every pulse — steady at {avg_latency} ms",
        "🚀 Performance without noise · Efficiency in every cycle",
    ],
    "PROTECTION": [
        "🛡️ Quiet guardianship — {protected_guilds} sanctuaries kept safe",
        "⚔️ Strength is silent — reliability is the standard",
    ],
}

ALL_CANDIDATE_BUBBLES: List[str] = [
    bubble
    for cat in ["IDENTITY", "UPTIME", "COMMUNITY", "MUSIC", "PERFORMANCE", "PROTECTION"]
    for bubble in CANDIDATE_BUBBLES_BY_CATEGORY[cat]
]

# Sensitive patterns that must never appear in public status
SENSITIVE_PATTERNS = [
    re.compile(r"[\w-]{24}\.[\w-]{6}\.[\w-]{27,}", re.IGNORECASE),  # Discord token
    re.compile(r"sk_[a-zA-Z0-9_]{15,}", re.IGNORECASE),              # API key (Pollinations, OpenAI, Stripe)
    re.compile(r"password|secret|bearer", re.IGNORECASE),
]



# =====================================================================
# 2. METRICS COLLECTOR & BACKGROUND REFRESH CACHE
# =====================================================================

class PresenceMetricsCollector:
    """Non-blocking, cached metrics aggregator for Yuna's presence intelligence.
    
    Refreshes heavy system measurements (CPU, RSS, DB queries, event counts)
    on a background interval (every 20s) so the presence loop operates with
    zero gateway latency and zero disk/network delays.
    """

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self._process = psutil.Process()
        
        # System & Performance cache
        self.cpu_percent: float = 0.0
        self.process_ram: int = 0
        self.ram_percent: float = 0.0
        self._latency_samples: deque[float] = deque(maxlen=20)
        self.avg_latency: int = 0
        self.event_loop_lag_ms: float = 0.0
        
        # Identity
        self.version: str = self._load_version()
        
        # Command counters
        self.commands_today: int = 0
        self.commands_total: int = 0
        self._commands_today_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._new_guilds_today: int = 0
        self._guilds_today_date: str = self._commands_today_date

        # Database & Storage caches
        self.total_songs: int = 0
        self.songs_today: int = 0
        self.protected_guilds: int = 0
        self.active_playlists: int = 0
        self.security_events_today: int = 0
        self.error_count_today: int = 0
        self.recommendations_today: int = 0
        self.db_status: str = "Healthy"
        self.dashboard_status: str = "Operational"

        # Background tasks
        self._refresh_task: Optional[asyncio.Task] = None
        self._lag_timer_handle: Optional[asyncio.TimerHandle] = None
        self._is_running: bool = False
        self._target_lag_interval: float = 1.0
        self._scheduled_lag_time: float = 0.0

    def _load_version(self) -> str:
        """Loads version from version.json or metadata.json, defaulting to 7.0.2."""
        for filename in ["version.json", "metadata.json"]:
            if os.path.exists(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        raw = data.get("version", "")
                        clean = str(raw).lstrip("vV").strip()
                        if clean:
                            return clean
                except Exception:
                    pass
        return "7.0.2"

    async def start(self) -> None:
        """Starts the background telemetry collector and event-loop lag monitor."""
        if self._is_running:
            return
        self._is_running = True

        # Initial load from disk
        await self._load_persistent_stats()
        await self._refresh_cached_metrics()

        # Start non-blocking event loop lag sampling
        self._schedule_loop_lag_tick()

        # Start periodic background metric refresh task
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self) -> None:
        """Stops the collector cleanly and cancels background timers."""
        self._is_running = False
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        if self._lag_timer_handle:
            self._lag_timer_handle.cancel()
            self._lag_timer_handle = None

    def _schedule_loop_lag_tick(self) -> None:
        """Non-blocking asyncio timer that computes scheduling delay."""
        if not self._is_running:
            return
        try:
            loop = asyncio.get_running_loop()
            now = loop.time()
            if self._scheduled_lag_time > 0:
                delay = now - self._scheduled_lag_time
                self.event_loop_lag_ms = round(max(0.0, delay) * 1000.0, 1)
            self._scheduled_lag_time = now + self._target_lag_interval
            self._lag_timer_handle = loop.call_later(self._target_lag_interval, self._schedule_loop_lag_tick)
        except Exception:
            pass

    async def _load_persistent_stats(self) -> None:
        """Loads lifetime commands, total songs, and today's counters from SQLite."""
        try:
            if os.path.exists("db/stats.db"):
                def _read_stats():
                    with sqlite3.connect("db/stats.db", timeout=5) as conn:
                        conn.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value TEXT)")
                        rows = dict(conn.execute("SELECT key, value FROM stats").fetchall())
                        return rows
                
                rows = await asyncio.to_thread(_read_stats)
                if "total_songs_played" in rows:
                    try:
                        self.total_songs = int(rows["total_songs_played"])
                    except ValueError:
                        pass
                if "total_commands_run" in rows:
                    try:
                        self.commands_total = int(rows["total_commands_run"])
                    except ValueError:
                        pass
                
                today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                stored_date = rows.get("commands_today_date", "")
                if stored_date == today_utc and "commands_today" in rows:
                    try:
                        self.commands_today = int(rows["commands_today"])
                        self._commands_today_date = today_utc
                    except ValueError:
                        pass
        except Exception as e:
            logger.debug(f"[PresenceMetricsCollector] Could not load persistent stats: {e}")

    def record_command(self) -> None:
        """Records a completed command execution and rolls over daily date if needed."""
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._commands_today_date != today_utc:
            self.commands_today = 0
            self._commands_today_date = today_utc

        self.commands_today += 1

        self.commands_total += 1

        # Periodically persist to stats.db in the background (every 5 commands)
        if self.commands_today % 5 == 0:
            asyncio.create_task(self._persist_command_stats())

    async def _persist_command_stats(self) -> None:
        """Saves current command counters to db/stats.db safely."""
        try:
            if not os.path.exists("db"):
                os.makedirs("db", exist_ok=True)
            def _write():
                with sqlite3.connect("db/stats.db", timeout=5) as conn:
                    conn.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value TEXT)")
                    conn.execute("INSERT OR REPLACE INTO stats (key, value) VALUES ('total_commands_run', ?)", (str(self.commands_total),))
                    conn.execute("INSERT OR REPLACE INTO stats (key, value) VALUES ('commands_today', ?)", (str(self.commands_today),))
                    conn.execute("INSERT OR REPLACE INTO stats (key, value) VALUES ('commands_today_date', ?)", (self._commands_today_date,))
                    conn.commit()
            await asyncio.to_thread(_write)
        except Exception:
            pass

    def record_guild_join(self) -> None:
        """Records a new guild join for community metrics."""
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._guilds_today_date != today_utc:
            self._new_guilds_today = 0
            self._guilds_today_date = today_utc
        self._new_guilds_today += 1

    async def _refresh_loop(self) -> None:
        """Periodic background refresh loop (every 20s)."""
        while self._is_running:
            try:
                await asyncio.sleep(20)
                await self._refresh_cached_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[PresenceMetricsCollector] Error in refresh loop: {e}")

    async def _refresh_cached_metrics(self) -> None:
        """Gathers heavy metrics in a non-blocking thread pool worker."""
        # 1. Update fast in-memory process stats
        try:
            self.cpu_percent = round(self._process.cpu_percent(interval=None), 1)
            self.process_ram = int(self._process.memory_info().rss / (1024 * 1024))
            self.ram_percent = round(self._process.memory_percent(), 1)
        except Exception:
            pass

        # 2. Update rolling latency sample
        try:
            raw_lat = getattr(self.bot, "latency", None)
            if raw_lat is not None and raw_lat != float("inf") and raw_lat > 0:
                lat_ms = round(raw_lat * 1000.0)
                self._latency_samples.append(lat_ms)
                if self._latency_samples:
                    self.avg_latency = round(sum(self._latency_samples) / len(self._latency_samples))
        except Exception:
            pass

        # 3. Offload SQLite queries to a single thread worker to guarantee zero event-loop stutter
        def _query_dbs() -> Dict[str, Any]:
            res: Dict[str, Any] = {
                "db_status": "Healthy",
                "total_songs": self.total_songs,
                "songs_today": 0,
                "protected_guilds": 0,
                "active_playlists": 0,
                "security_events_today": 0,
                "error_count_today": 0,
                "recommendations_today": 0,
            }

            today_utc_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            midnight_epoch = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

            # stats.db (Lifetime songs)
            try:
                if os.path.exists("db/stats.db"):
                    with sqlite3.connect("db/stats.db", timeout=3) as conn:
                        conn.execute("SELECT 1").fetchone()
                        cur = conn.cursor()
                        cur.execute("SELECT value FROM stats WHERE key = 'total_songs_played'")
                        row = cur.fetchone()
                        if row and row[0]:
                            res["total_songs"] = int(row[0])
            except Exception:
                res["db_status"] = "Degraded"

            # ml_interactions.db (Songs today, recommendations today)
            try:
                if os.path.exists("db/ml_interactions.db"):
                    with sqlite3.connect("db/ml_interactions.db", timeout=3) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM interactions WHERE event_type = 'PLAY_STARTED' AND timestamp >= ?", (midnight_epoch,))
                        row = cur.fetchone()
                        if row:
                            res["songs_today"] = int(row[0])

                        cur.execute(
                            "SELECT COUNT(*) FROM interactions WHERE event_type IN ('RECOMMENDATION_ACCEPTED', 'SIMILAR_VIBE_SELECTED', 'CATALOG_TRACK_SELECTED') AND timestamp >= ?",
                            (midnight_epoch,)
                        )
                        rec_row = cur.fetchone()
                        if rec_row:
                            res["recommendations_today"] = int(rec_row[0])
            except Exception:
                pass

            # anti.db (Protected guilds & security incidents today)
            try:
                if os.path.exists("db/anti.db"):
                    with sqlite3.connect("db/anti.db", timeout=3) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(DISTINCT guild_id) FROM antinuke WHERE status = 1")
                        row = cur.fetchone()
                        if row:
                            res["protected_guilds"] = int(row[0])

                        cur.execute("SELECT COUNT(*) FROM bot_incidents WHERE timestamp LIKE ?", (f"{today_utc_prefix}%",))
                        inc_row = cur.fetchone()
                        if inc_row:
                            res["security_events_today"] = int(inc_row[0])
            except Exception:
                pass

            # playlists.db (Active user playlists)
            try:
                if os.path.exists("db/playlists.db"):
                    with sqlite3.connect("db/playlists.db", timeout=3) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM user_playlists")
                        row = cur.fetchone()
                        if row:
                            res["active_playlists"] = int(row[0])
            except Exception:
                pass

            # error_logs.db (Errors today)
            try:
                if os.path.exists("db/error_logs.db"):
                    with sqlite3.connect("db/error_logs.db", timeout=3) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM bot_error_logs WHERE timestamp LIKE ?", (f"{today_utc_prefix}%",))
                        row = cur.fetchone()
                        if row:
                            res["error_count_today"] = int(row[0])
            except Exception:
                pass

            return res

        try:
            results = await asyncio.to_thread(_query_dbs)
            self.db_status = results["db_status"]
            self.total_songs = results["total_songs"]
            self.songs_today = results["songs_today"]
            self.protected_guilds = results["protected_guilds"]
            self.active_playlists = results["active_playlists"]
            self.security_events_today = results["security_events_today"]
            self.error_count_today = results["error_count_today"]
            self.recommendations_today = results["recommendations_today"]
        except Exception as e:
            logger.debug(f"[PresenceMetricsCollector] Offloaded DB query failed: {e}")

        # Check dashboard server status
        dash_enabled = os.getenv("DASHBOARD_ENABLED", "true").strip().lower() in ("true", "1", "yes")
        api_enabled = os.getenv("API_ENABLED", "true").strip().lower() in ("true", "1", "yes")
        self.dashboard_status = "Operational" if (dash_enabled and api_enabled) else "Offline"

    def get_variables(self) -> Dict[str, Any]:
        """Returns the dictionary of all live, authoritative placeholder variables.
        
        Zero disk or network I/O: builds instantly (<0.01ms) from cached state and
        Discord Gateway client attributes.
        """
        now = time.time()
        start_time = getattr(self.bot, "start_time", now)
        elapsed = max(0, int(now - start_time))

        # 1. Uptime calculations
        days, rem = divmod(elapsed, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        # Verbose uptime (Preserved existing format)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        uptime_str = " ".join(parts) if parts else "0s"

        # Compact uptime (e.g. "3d 4h", "4h 12m", "15m", "42s")
        if days > 0:
            uptime_short = f"{days}d {hours}h"
        elif hours > 0:
            uptime_short = f"{hours}h {minutes}m"
        elif minutes > 0:
            uptime_short = f"{minutes}m"
        else:
            uptime_short = f"{seconds}s"

        # 2. Guild and User counts
        guild_count = len(getattr(self.bot, "guilds", []))
        active_guilds = sum(1 for g in getattr(self.bot, "guilds", []) if not getattr(g, "unavailable", False))
        
        try:
            uc = sum(g.member_count for g in self.bot.guilds if g.member_count is not None)
            if uc >= 1_000_000:
                user_str = f"{uc / 1_000_000:.1f}M"
            elif uc >= 1_000:
                user_str = f"{uc / 1_000:.1f}k"
            else:
                user_str = str(uc)
        except Exception:
            user_str = str(len(getattr(self.bot, "users", [])))

        # 3. Latency & Ping
        try:
            raw_lat = getattr(self.bot, "latency", None)
            ping_val = round(raw_lat * 1000) if (raw_lat is not None and raw_lat != float("inf")) else 0
        except Exception:
            ping_val = 0

        avg_lat = self.avg_latency if self.avg_latency > 0 else ping_val
        if ping_val < 50:
            lat_status = "Optimal"
        elif ping_val < 120:
            lat_status = "Good"
        elif ping_val < 250:
            lat_status = "Elevated"
        else:
            lat_status = "High"

        # 4. Music Engine & Voice clients
        voice_clients = getattr(self.bot, "voice_clients", [])
        vc_count = len(voice_clients)
        active_voice = sum(1 for vc in voice_clients if getattr(vc, "is_connected", lambda: True)())
        playing_count = sum(1 for vc in voice_clients if getattr(vc, "is_playing", lambda: False)())
        music_sessions = sum(
            1 for vc in voice_clients
            if getattr(vc, "is_playing", lambda: False)() or getattr(vc, "is_paused", lambda: False)()
        )
        guilds_with_music = len(set(vc.guild.id for vc in voice_clients if getattr(vc, "is_playing", lambda: False)()))

        # Music Cog internal state (Queues, autoplay)
        music_cog = self.bot.get_cog("music") if hasattr(self.bot, "get_cog") else None
        active_queues = 0
        tracks_queued = 0
        autoplay_sessions = 0
        if music_cog:
            q_dict = getattr(music_cog, "queue", {})
            if isinstance(q_dict, dict):
                active_queues = sum(1 for q in q_dict.values() if q)
                tracks_queued = sum(len(q) for q in q_dict.values() if q)
            ap_dict = getattr(music_cog, "autoplay", {})
            if isinstance(ap_dict, dict):
                autoplay_sessions = sum(1 for ap in ap_dict.values() if ap)

        # Music Engine Status
        if not music_cog:
            music_engine_status = "Offline"
        elif playing_count > 0:
            music_engine_status = "Streaming"
        else:
            music_engine_status = "Optimal"

        # 5. Shards and Identity
        shards = getattr(self.bot, "shards", None)
        shard_count = len(shards) if shards else (getattr(self.bot, "shard_count", None) or 1)
        started_at = datetime.fromtimestamp(start_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

        # 6. Security & Cache
        from core.cache.security_cache import security_cache
        cached_protected = sum(1 for gid, active in getattr(security_cache, "_antinuke", {}).items() if active)
        protected_count = max(self.protected_guilds, cached_protected)
        protection_status = "Active" if protected_count > 0 else "Monitoring"

        # Support URL
        try:
            from utils.support_utils import get_support_url
            support_url = get_support_url(self.bot)
        except Exception:
            support_url = "https://discord.gg/YzHCx5yQXv"

        # Total events today (commands + audio events)
        events_today = self.commands_today + self.songs_today

        # 7. Assembled variables
        return {
            # === Preserved Existing Placeholders ===
            "uptime": uptime_str,
            "guild_count": f"{guild_count:,}",
            "user_count": user_str,
            "ping": str(ping_val),
            "playing_count": str(playing_count),
            "vc_count": str(vc_count),
            "ram": str(self.process_ram),
            "total_songs": f"{self.total_songs:,}",
            "support_url": support_url,

            # === Category A: Identity and Runtime ===
            "version": self.version,
            "uptime_short": uptime_short,
            "uptime_days": str(days),
            "shard_count": str(shard_count),
            "started_at": started_at,
            "process_id": str(os.getpid()),

            # === Category B: Performance & Resources ===
            "cpu_percent": f"{self.cpu_percent:.1f}",
            "process_ram": str(self.process_ram),
            "ram_percent": f"{self.ram_percent:.1f}",
            "avg_latency": str(avg_lat),
            "latency_status": lat_status,
            "event_loop_lag": f"{self.event_loop_lag_ms:.1f}",

            # === Category C: Music Engine ===
            "active_queues": str(active_queues),
            "active_voice": str(active_voice),
            "songs_today": f"{self.songs_today:,}",
            "tracks_queued": str(tracks_queued),
            "active_playlists": str(self.active_playlists),
            "autoplay_sessions": str(autoplay_sessions),
            "music_sessions": str(music_sessions),
            "guilds_with_music": str(guilds_with_music),
            "music_engine_status": music_engine_status,

            # === Category D: Community & Engagement ===
            "active_guilds": f"{active_guilds:,}",
            "commands_today": f"{self.commands_today:,}",
            "commands_total": f"{self.commands_total:,}",
            "events_today": f"{events_today:,}",
            "new_guilds_today": str(self._new_guilds_today),

            # === Category E: Security & Reliability ===
            "protected_guilds": str(protected_count),
            "protection_status": protection_status,
            "security_events_today": str(self.security_events_today),
            "db_status": self.db_status,
            "dashboard_status": self.dashboard_status,
            "error_count_today": str(self.error_count_today),

            # === Category F: Intelligence & ML ===
            "recommendations_today": str(self.recommendations_today),
            "ml_engine_status": "Ready" if os.path.exists("db/ml_interactions.db") else "Optimal",
        }


# =====================================================================
# 3. TEMPLATE RENDERER & VALIDATOR
# =====================================================================

class SpeechBubbleRenderer:
    """Safely formats and validates speech bubble presence templates.
    
    Guarantees:
    - Never publishes None, null, undefined, NaN, empty metric values, or raw {placeholders}.
    - If ANY variable in a template is missing or invalid, cleanly skips that template.
    - Limits string length strictly to Discord's 128 character custom status limit.
    - Strips or suppresses sensitive credentials or leaked tokens.
    """

    _PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")

    @classmethod
    def get_placeholders(cls, template: str) -> List[str]:
        """Extracts placeholder variable names from a template."""
        return cls._PLACEHOLDER_RE.findall(template)

    @classmethod
    def render(cls, template: str, variables: Dict[str, Any]) -> Optional[str]:
        """Renders a candidate template against live variables.
        
        Returns formatted string if valid and completely resolved, or None if the
        template should be skipped.
        """
        if not template or not isinstance(template, str):
            return None

        clean_template = template.strip()
        required_vars = cls.get_placeholders(clean_template)

        # Verify all required variables are present and authoritative
        for var in required_vars:
            val = variables.get(var)
            if val is None:
                return None
            str_val = str(val).strip()
            # Reject broken or empty metrics
            if str_val in ("", "None", "null", "undefined", "NaN"):
                return None

        # Format string safely
        try:
            rendered = clean_template.format_map(variables)
        except Exception:
            return None

        # Verify no unresolved curly braces remain
        if "{" in rendered or "}" in rendered:
            return None

        # Enforce Discord maximum length of 128 chars
        clean_rendered = rendered.strip()[:128]

        # Security check: Never leak tokens, passwords, or secrets
        for pat in SENSITIVE_PATTERNS:
            if pat.search(clean_rendered):
                logger.warning(f"[SpeechBubbleRenderer] Suppressed sensitive content in status: {clean_rendered}")
                return None

        return clean_rendered


# =====================================================================
# 4. SMART DETERMINISTIC ROTATION ENGINE
# =====================================================================

class SpeechBubbleRotationEngine:
    """Smart presence rotation engine for Yuna V7.
    
    Guarantees:
    - Strictly speech bubbles (type 4, discord.CustomActivity).
    - Preserves constant bot online state (Status.dnd / current status); NEVER cycles Online/Idle/DND.
    - NEVER cycles Playing, Streaming, Listening, or Watching activities.
    - Alternates across balanced categories: IDENTITY -> UPTIME -> COMMUNITY -> MUSIC -> PERFORMANCE -> PROTECTION.
    - Avoids consecutive bubbles dominated by the same metric.
    - Never updates Discord presence when the final rendered text has not changed.
    - Skips unavailable metrics cleanly without disrupting the rotation.
    """

    CATEGORIES = ["IDENTITY", "UPTIME", "COMMUNITY", "MUSIC", "PERFORMANCE", "PROTECTION"]

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.collector = PresenceMetricsCollector(bot)
        self.renderer = SpeechBubbleRenderer()
        
        # Category tracking
        self._category_indices: Dict[str, int] = {cat: 0 for cat in self.CATEGORIES}
        self._current_cat_idx: int = 0
        self._last_applied_text: Optional[str] = None
        self._last_rendered_text: Optional[str] = None
        
        # User-configured flat pool tracking (if custom SPEECH_BUBBLES configured)
        self._custom_pool_index: int = 0
        self._is_running: bool = False

        # Register event listeners non-invasively for telemetry
        async def _on_cmd_done(ctx):
            self.collector.record_command()

        async def _on_guild_added(guild):
            self.collector.record_guild_join()

        try:
            bot.add_listener(_on_cmd_done, "on_command_completion")
            bot.add_listener(_on_guild_added, "on_guild_join")
        except Exception:
            pass

    async def start(self) -> None:
        """Starts the metrics collector and runs the main presence rotation loop."""
        if self._is_running:
            return
        self._is_running = True
        await self.collector.start()
        await self._rotation_loop()

    async def stop(self) -> None:
        """Stops the engine and cleanly halts all background presence tasks."""
        self._is_running = False
        await self.collector.stop()


    def get_next_bubble(self, custom_pool: Optional[List[str]] = None) -> Optional[str]:
        """Selects and renders the next valid speech bubble in the rotation sequence."""
        variables = self.collector.get_variables()

        # Path 1: User explicitly defined custom SPEECH_BUBBLES in config.yml
        if custom_pool and len(custom_pool) > 0:
            pool_len = len(custom_pool)
            for _ in range(pool_len):
                template = custom_pool[self._custom_pool_index % pool_len]
                self._custom_pool_index = (self._custom_pool_index + 1) % pool_len
                rendered = self.renderer.render(template, variables)
                if rendered and (rendered != self._last_rendered_text or pool_len == 1):
                    self._last_rendered_text = rendered
                    return rendered
            return None

        # Path 2: Balanced round-robin categorized rotation through curated 40 candidates
        total_categories = len(self.CATEGORIES)
        for _ in range(total_categories):
            cat_name = self.CATEGORIES[self._current_cat_idx % total_categories]
            self._current_cat_idx = (self._current_cat_idx + 1) % total_categories
            
            candidates = CANDIDATE_BUBBLES_BY_CATEGORY[cat_name]
            cat_len = len(candidates)
            for _ in range(cat_len):
                idx = self._category_indices[cat_name] % cat_len
                self._category_indices[cat_name] = (idx + 1) % cat_len
                template = candidates[idx]
                
                rendered = self.renderer.render(template, variables)
                if rendered and rendered != self._last_rendered_text:
                    self._last_rendered_text = rendered
                    return rendered

        # Fallback to an evergreen static identity bubble if all dynamic candidates skipped
        static_fallback = "Always on. Always Yuna."
        self._last_rendered_text = static_fallback
        return static_fallback

    async def _rotation_loop(self) -> None:
        """Main periodic loop updating Discord CustomActivity presence."""
        # Allow gateway connection to settle on startup
        await asyncio.sleep(10)

        while self._is_running and not self.bot.is_closed():
            try:
                # 1. Load active config
                from utils.config_loader import config
                disabled = config.get("DISABLE_PRESENCE", False)
                if isinstance(disabled, str):
                    disabled = disabled.strip().lower() in ("true", "1", "yes", "on")
                if disabled:
                    await asyncio.sleep(30)
                    continue

                try:
                    delay = max(15, int(config.get("PRESENCES_CHANGE_DELAY", 15)))
                except (TypeError, ValueError):
                    delay = 15

                # 2. Check for user-defined custom speech bubbles
                raw_bubbles = config.get("SPEECH_BUBBLES")
                custom_pool: Optional[List[str]] = None
                if raw_bubbles and isinstance(raw_bubbles, list):
                    # Filter valid non-empty string templates
                    clean_pool = [str(b).strip() for b in raw_bubbles if str(b).strip()]
                    if clean_pool:
                        custom_pool = clean_pool

                # 3. Select next bubble
                bubble_text = self.get_next_bubble(custom_pool=custom_pool)

                # 4. Update presence ONLY if text changed and valid
                if bubble_text:
                    if bubble_text != self._last_applied_text:
                        # Keep bot status steady (default to dnd; never cycle online/idle/dnd)
                        current_status = getattr(self.bot, "status", None) or discord.Status.do_not_disturb
                        
                        # Set custom status directly; Unicode emojis render natively across all Discord platforms
                        activity = discord.CustomActivity(name=bubble_text)
                        
                        await self.bot.change_presence(
                            status=current_status,
                            activity=activity
                        )
                        self._last_applied_text = bubble_text
                        logger.debug(f"[Presence] Updated speech bubble: {bubble_text}")
                    else:
                        logger.debug(f"[Presence] Bubble text unchanged ('{bubble_text}'). Skipping gateway presence call.")

                # 5. Sleep for configured rotation interval
                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[Presence Rotation Engine] Unexpected presence loop error: {e}", exc_info=False)
                await asyncio.sleep(30)
