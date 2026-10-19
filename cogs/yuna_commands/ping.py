import discord
from discord.ext import commands
from discord import app_commands, ui
import time
import os
import psutil
import datetime
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from utils.Tools import ignore_check, blacklist_check
from utils.cv2 import CV2
from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER
from core.database.connection_pool import db_pool


_telemetry_mongo_cache: Dict[str, Any] = {}


def format_clean_ms(val) -> str:
    if val is None or str(val).strip().upper() in ("N/A", "NONE"):
        return "N/A"
    s = str(val).strip()
    if "FAIL" in s.upper():
        return "Offline"
    if s.endswith("ms"):
        s = s[:-2].strip()
    try:
        return f"{round(float(s))}ms"
    except Exception:
        return str(val)


async def probe_sqlite_latency() -> str:
    """Measures raw SQLite latency on db/anti.db."""
    try:
        t0 = time.perf_counter()
        async with db_pool.acquire("db/anti.db") as db:
            await db.execute("SELECT 1")
        return f"{round((time.perf_counter() - t0) * 1000)}ms"
    except Exception:
        return "N/A"


async def collect_telemetry_metrics(bot, guild, ctx_or_interaction, t_start=None):
    # 1. Shard-aware bot/websocket latency
    shard_id = getattr(guild, 'shard_id', 0) if guild else 0
    shard_count = getattr(bot, 'shard_count', 1) or 1
    shard = bot.get_shard(shard_id) if hasattr(bot, 'get_shard') else None
    raw_ws = shard.latency if (shard and hasattr(shard, 'latency') and isinstance(shard.latency, (int, float))) else getattr(bot, 'latency', 0.015)
    if raw_ws is None or not isinstance(raw_ws, (int, float)) or raw_ws == float('inf') or raw_ws != raw_ws:
        bot_ms = 0.01
    else:
        bot_ms = max(0.01, round(raw_ws * 1000, 2))

    # 2. Pure real-time latency probes across MongoDB Clusters and Discord REST RTT
    async def probe_cluster(uri_key=None, default_uri=None):
        try:
            uri = (os.getenv(uri_key) if uri_key else None) or default_uri
            if uri:
                if uri not in _telemetry_mongo_cache:
                    from core.database.upsert_sync_engine import create_resilient_mongo_client
                    _telemetry_mongo_cache[uri] = await asyncio.to_thread(create_resilient_mongo_client, uri, 3000)
                client = _telemetry_mongo_cache.get(uri)
                if client and hasattr(client, 'admin'):
                    t0 = time.perf_counter()
                    await asyncio.wait_for(asyncio.to_thread(client.admin.command, 'ping'), timeout=1.2)
                    return max(0.01, round((time.perf_counter() - t0) * 1000, 2))
            return "N/A"
        except Exception:
            return "N/A"

    async def probe_discord_rtt():
        t0 = time.perf_counter()
        try:
            route = discord.http.Route('GET', '/gateway')
            await bot.http.request(route)
            return max(0.01, round((time.perf_counter() - t0) * 1000, 2))
        except Exception:
            return max(0.01, round(bot_ms, 2))

    c1_task = probe_cluster(uri_key="MONGODB_URI")
    c2_task = probe_cluster(uri_key="PERMANENT_MONGODB_URI", default_uri=os.getenv("UPDATE_MONGODB_URI"))
    rtt_task = probe_discord_rtt()

    c1_ms, c2_ms, msg_ms = await asyncio.gather(c1_task, c2_task, rtt_task)
    mongo_clusters = [
        ("Cluster 1", c1_ms),
        ("Cluster 2", c2_ms),
    ]
    mongo_ms = c1_ms if str(c1_ms).strip().upper() != "N/A" else c2_ms

    # 3. Uptime calculation
    bot_start = getattr(bot, "start_time", None)
    if not bot_start:
        try:
            bot_start = psutil.Process(os.getpid()).create_time()
        except Exception:
            bot_start = time.time()

    uptime_sec = max(0, int(round(time.time() - bot_start)))
    u_days, u_rem = divmod(uptime_sec, 86400)
    u_hours, u_rem = divmod(u_rem, 3600)
    u_mins, u_secs = divmod(u_rem, 60)

    if u_days > 0:
        uptime_raw = f"{u_days}d {u_hours}h {u_mins}m {u_secs}s"
    elif u_hours > 0:
        uptime_raw = f"{u_hours}h {u_mins}m {u_secs}s"
    elif u_mins > 0:
        uptime_raw = f"{u_mins}m {u_secs}s"
    else:
        uptime_raw = f"{u_secs}s"

    shard_info = f"Shard #{shard_id + 1}/{shard_count}"
    return bot_ms, msg_ms, mongo_ms, uptime_raw, shard_info, mongo_clusters


def build_latency_cv2_text(
    ws_ms: float = 0.0,
    msg_ms: float = 0.0,
    sqlite_ms: Any = "0ms",
    mongo_ms: Any = "N/A",
    mongo_clusters: Optional[List[Tuple[str, Any]]] = None,
    shard_info: str = "Shard #1/1",
    uptime_raw: str = "0s",
    is_owner: bool = False,
) -> str:
    ws_str = format_clean_ms(ws_ms)
    msg_str = format_clean_ms(msg_ms)
    sqlite_str = format_clean_ms(sqlite_ms)
    mongo_val = format_clean_ms(mongo_ms)

    if is_owner:
        clusters = mongo_clusters or [
            ("Cluster 1", mongo_ms),
            ("Cluster 2", "N/A"),
        ]
        lines = [
            f"**Gateway:** `{ws_str}`",
            f"**API:** `{msg_str}`",
            f"**SQLite:** `{sqlite_str}`",
            f"**MongoDB:** `{mongo_val}`",
        ]
        for idx, (c_name, c_val) in enumerate(clusters):
            branch = "└─" if idx == len(clusters) - 1 else "├─"
            c_str = format_clean_ms(c_val)
            lines.append(f"  {branch} **{c_name}:** `{c_str}`")

        lines.append(f"**Active Shard:** `{shard_info}`")
        lines.append(f"**System Uptime:** `{uptime_raw}`")
        return "\n".join(lines)

    # Standard user display
    lines = [
        f"**Gateway:** `{ws_str}`",
        f"**API:** `{msg_str}`",
        f"**SQLite:** `{sqlite_str}`",
        f"**MongoDB:** `{mongo_val}`",
        f"**System Uptime:** `{uptime_raw}`",
    ]
    return "\n".join(lines)


class LatencyCV2View(ui.LayoutView):
    """CV2 Container Layout for Latency command matching present Yuna design with Refresh button."""

    def __init__(
        self,
        bot,
        author_id: int,
        ws_ms: float = 0.0,
        msg_ms: float = 0.0,
        sqlite_ms: Any = "0ms",
        mongo_ms: Any = "N/A",
        uptime_raw: str = "0s",
        shard_info: str = "Shard #1/1",
        mongo_clusters: Optional[List[Tuple[str, Any]]] = None,
        requester: Optional[discord.abc.User] = None,
        timeout: float = 120.0,
        is_owner: Optional[bool] = None,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.author_id = author_id
        self.requester = requester
        self.message = None
        self.cd = commands.CooldownMapping.from_cooldown(1, 2.5, commands.BucketType.user)
        self.is_owner = bool(is_owner)

        body_text = build_latency_cv2_text(
            ws_ms=ws_ms,
            msg_ms=msg_ms,
            sqlite_ms=sqlite_ms,
            mongo_ms=mongo_ms,
            mongo_clusters=mongo_clusters,
            shard_info=shard_info,
            uptime_raw=uptime_raw,
            is_owner=self.is_owner
        )

        req_name = getattr(self.requester, "display_name", str(self.requester)) if self.requester else "Unknown"
        now_ts = int(time.time())
        footer_text = f"-# Requested by {req_name} • Last refreshed <t:{now_ts}:R>"

        self.container = ui.Container()
        self.header_display = ui.TextDisplay("**Ultra-Low Latency**")
        self.top_sep = ui.Separator(visible=True)
        self.body_display = ui.TextDisplay(body_text)
        self.bottom_sep = ui.Separator(visible=True)

        self.refresh_btn = ui.Button(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
            custom_id=f"latency_cv2_refresh_{self.author_id}"
        )
        self.refresh_btn.callback = self.refresh_callback
        self.action_row = ui.ActionRow(self.refresh_btn)

        self.footer_sep = ui.Separator(visible=True)
        self.footer_display = ui.TextDisplay(footer_text)

        self.container.add_item(self.header_display)
        self.container.add_item(self.top_sep)
        self.container.add_item(self.body_display)
        self.container.add_item(self.bottom_sep)
        self.container.add_item(self.action_row)
        self.container.add_item(self.footer_sep)
        self.container.add_item(self.footer_display)

        self.add_item(self.container)

    async def refresh_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            try:
                await interaction.response.send_message(
                    "Uh oh! That message doesn't belong to you. You must run this command to interact with it.",
                    ephemeral=True
                )
            except Exception:
                pass
            return

        bucket = self.cd.get_bucket(interaction.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            try:
                await interaction.response.send_message(
                    f"Please try again after {retry_after:.1f}s",
                    ephemeral=True
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        t_start = time.perf_counter()
        metrics_task = collect_telemetry_metrics(self.bot, interaction.guild, interaction, t_start)
        sqlite_task = probe_sqlite_latency()
        (ws_ms, msg_ms, mongo_ms, uptime_raw, shard_info, mongo_clusters), sqlite_ms = await asyncio.gather(
            metrics_task, sqlite_task
        )

        new_body = build_latency_cv2_text(
            ws_ms=ws_ms,
            msg_ms=msg_ms,
            sqlite_ms=sqlite_ms,
            mongo_ms=mongo_ms,
            mongo_clusters=mongo_clusters,
            shard_info=shard_info,
            uptime_raw=uptime_raw,
            is_owner=self.is_owner
        )
        req_name = getattr(self.requester, "display_name", str(self.requester)) if self.requester else "Unknown"
        now_ts = int(time.time())
        new_footer = f"-# Requested by {req_name} • Last refreshed <t:{now_ts}:R>"

        self.body_display.content = new_body
        self.footer_display.content = new_footer

        try:
            await interaction.edit_original_response(view=self)
        except Exception:
            try:
                if interaction.message:
                    await interaction.message.edit(view=self)
            except Exception:
                if self.message:
                    try:
                        await self.message.edit(view=self)
                    except Exception:
                        pass

    async def on_timeout(self):
        if self.refresh_btn:
            self.refresh_btn.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class Ping(commands.Cog):
    """Network, Gateway and Database Telemetry."""

    def __init__(self, bot):
        self.bot = bot

    async def _execute_latency_telemetry(self, ctx: commands.Context, is_owner: bool = False):
        t_start = time.perf_counter()

        # Initial probe state using CV2
        msg = await ctx.send(view=CV2("Checking Latency...", "Calculating response times, please wait."))

        metrics_task = collect_telemetry_metrics(self.bot, ctx.guild, ctx, t_start)
        sqlite_task = probe_sqlite_latency()
        (ws_ms, msg_ms, mongo_ms, uptime_raw, shard_info, mongo_clusters), sqlite_ms = await asyncio.gather(
            metrics_task, sqlite_task
        )

        view = LatencyCV2View(
            bot=self.bot,
            author_id=ctx.author.id,
            ws_ms=ws_ms,
            msg_ms=msg_ms,
            sqlite_ms=sqlite_ms,
            mongo_ms=mongo_ms,
            uptime_raw=uptime_raw,
            shard_info=shard_info,
            mongo_clusters=mongo_clusters,
            requester=ctx.author,
            is_owner=is_owner
        )
        view.message = msg

        try:
            await msg.edit(view=view)
        except Exception:
            if ctx.interaction:
                try:
                    await ctx.interaction.edit_original_response(view=view)
                except Exception:
                    pass

    @commands.hybrid_command(
        name="ping",
        aliases=["pong"],
        description="Displays detailed network and database telemetry for Yuna Supreme.",
        help="Checks the bot's WebSocket, API, and Database latencies.",
        with_app_command=True
    )
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def ping(self, ctx: commands.Context):
        """Shows the bot's WebSocket, API, and Database latencies."""
        await self._execute_latency_telemetry(ctx, is_owner=False)

    @commands.hybrid_command(
        name="latency",
        aliases=["lcy"],
        description="Displays detailed network and database telemetry for Yuna Supreme.",
        help="Checks the bot latency, database status, and uptime.",
        with_app_command=True
    )
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def latency(self, ctx: commands.Context):
        """Displays detailed network and database telemetry for Yuna Supreme."""
        await self._execute_latency_telemetry(ctx, is_owner=False)

    @commands.command(
        name="pingall",
        help="Displays full system and multi-cluster telemetry diagnostics (Bot Owner only).",
        hidden=True
    )
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def pingall(self, ctx: commands.Context):
        """Bot Owner only: Displays detailed telemetry breakdown with multi-cluster MongoDB."""
        is_owner = False
        try:
            is_owner = (int(ctx.author.id) in GLOBAL_OWNER_IDS) or (int(ctx.author.id) == PRIMARY_BOT_OWNER) or (await self.bot.is_owner(ctx.author))
        except Exception:
            is_owner = (int(ctx.author.id) in GLOBAL_OWNER_IDS) or (int(ctx.author.id) == PRIMARY_BOT_OWNER)

        if not is_owner:
            embed = discord.Embed(
                color=0x000000,
                description="<:Yuna_cross:1227866668152393789> Only the **Bot Owner** can use this command!"
            )
            await ctx.send(embed=embed)
            return

        await self._execute_latency_telemetry(ctx, is_owner=True)


async def setup(bot):
    await bot.add_cog(Ping(bot))
