# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                  ║
# ║   ░█▄░█░█▀▀░█▀▄░█▀▄   ░█░█   ░█░░░▀█▀░█░█░█▀▀                 ║
# ║   ░█░▀█░█▀▀░█▀▄░█░█   ░▄▀▄   ░█░░░░█░░▀▄▀░█▀▀                 ║
# ║   ░▀░░▀░▀▀▀░▀░▀░▀▀░   ░▀░▀   ░▀▀▀░▀█▀░░▀░░▀▀▀                 ║
# ║                                                                  ║
# ║            © 2026 Nerd X Live — All Rights Reserved             ║
# ║   github   ──  https://github.com/nithishkumar717/zyuna         ║
# ║                                                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio
import math
import time
import os
import aiosqlite
import discord
from discord.ext import commands
from typing import Any, Dict, List, Optional, Tuple

from utils.Tools import ignore_check, blacklist_check
from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER, OWNER_IDS
from core.database.connection_pool import db_pool


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


class PingLoadingView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        container = discord.ui.Container(
            discord.ui.TextDisplay("**Checking Latency...**"),
            discord.ui.Separator(visible=True),
            discord.ui.TextDisplay("Calculating response times, please wait."),
        )
        self.add_item(container)


class PingTelemetryView(discord.ui.LayoutView):
    def __init__(self, cog, ctx, metrics):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = ctx.author.id
        self.requester = ctx.author
        self.message = None
        self.cooldown = commands.CooldownMapping.from_cooldown(
            1, 2.5, commands.BucketType.user
        )

        self.container = discord.ui.Container()
        self.header_display = discord.ui.TextDisplay("**Ultra-Low Latency**")
        self.top_sep = discord.ui.Separator(visible=True)
        self.body_display = discord.ui.TextDisplay(cog._format_ping_metrics(metrics))
        self.bottom_sep = discord.ui.Separator(visible=True)
        self.refresh_btn = discord.ui.Button(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
            custom_id=f"zyuna_ping_refresh_{self.author_id}",
        )
        self.refresh_btn.callback = self.refresh_callback
        self.action_row = discord.ui.ActionRow(self.refresh_btn)
        self.footer_sep = discord.ui.Separator(visible=True)
        self.footer_display = discord.ui.TextDisplay(self._footer_text())

        for item in (
            self.header_display,
            self.top_sep,
            self.body_display,
            self.bottom_sep,
            self.action_row,
            self.footer_sep,
            self.footer_display,
        ):
            self.container.add_item(item)
        self.add_item(self.container)

    def _footer_text(self):
        requester_name = getattr(
            self.requester, "display_name", str(self.requester)
        )
        return f"-# Requested by {requester_name} • Last refreshed <t:{int(time.time())}:R>"

    async def refresh_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Uh oh! That message doesn't belong to you. You must run this command to interact with it.",
                ephemeral=True,
            )
            return

        bucket = self.cooldown.get_bucket(interaction.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            await interaction.response.send_message(
                f"Please try again after {retry_after:.1f}s", ephemeral=True
            )
            return

        await interaction.response.defer()
        metrics = await self.cog._collect_ping_metrics(interaction.guild)
        self.body_display.content = self.cog._format_ping_metrics(metrics)
        self.footer_display.content = self._footer_text()

        try:
            await interaction.edit_original_response(view=self)
        except Exception:
            if interaction.message:
                await interaction.message.edit(view=self)
            elif self.message:
                await self.message.edit(view=self)

    async def on_timeout(self):
        self.refresh_btn.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class PingFallbackView(discord.ui.View):
    """Standard Discord Button View fallback for servers without LayoutView."""
    def __init__(self, cog, ctx, metrics):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = ctx.author.id
        self.requester = ctx.author
        self.message = None
        self.cooldown = commands.CooldownMapping.from_cooldown(
            1, 2.5, commands.BucketType.user
        )

    @discord.ui.button(label="Refresh", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ This interaction is not for you.", ephemeral=True)
        bucket = self.cooldown.get_bucket(interaction.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return await interaction.response.send_message(f"Please wait {retry_after:.1f}s before refreshing again.", ephemeral=True)

        await interaction.response.defer()
        metrics = await self.cog._collect_ping_metrics(interaction.guild)
        embed = self.cog._build_ping_embed(metrics, self.requester)
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=self)


class Ping(commands.Cog):
    """Network, Gateway and Database Telemetry."""

    def __init__(self, bot):
        self.bot = bot
        self.started_at = getattr(bot, "start_time", None) or time.time()

    async def _probe_api_latency(self):
        started = time.perf_counter()
        try:
            route = discord.http.Route("GET", "/gateway")
            await self.bot.http.request(route)
            return max(0.01, round((time.perf_counter() - started) * 1000, 2))
        except Exception:
            return "N/A"

    async def _probe_sqlite_latency(self):
        try:
            started = time.perf_counter()
            async with aiosqlite.connect("db/anti.db", timeout=2) as db:
                await db.execute("SELECT 1")
            return max(0.01, round((time.perf_counter() - started) * 1000, 2))
        except Exception:
            return "N/A"

    async def _collect_ping_metrics(self, guild):
        shard_id = getattr(guild, "shard_id", 0) if guild else 0
        shard = self.bot.get_shard(shard_id) if hasattr(self.bot, "get_shard") else None
        raw_ws = getattr(shard, "latency", None) if shard else None
        if raw_ws is None:
            raw_ws = getattr(self.bot, "latency", None)
        if not isinstance(raw_ws, (int, float)) or not math.isfinite(raw_ws):
            gateway_ms = "N/A"
        else:
            gateway_ms = max(0.01, round(raw_ws * 1000, 2))

        api_ms, sqlite_ms = await asyncio.gather(
            self._probe_api_latency(), self._probe_sqlite_latency()
        )
        if api_ms == "N/A":
            api_ms = gateway_ms

        uptime_seconds = max(0, int(time.time() - self.started_at))
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days:
            uptime = f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours:
            uptime = f"{hours}h {minutes}m {seconds}s"
        elif minutes:
            uptime = f"{minutes}m {seconds}s"
        else:
            uptime = f"{seconds}s"

        shard_count = getattr(self.bot, "shard_count", 1) or 1
        return {
            "gateway": gateway_ms,
            "api": api_ms,
            "sqlite": sqlite_ms,
            "uptime": uptime,
            "shard": f"#{shard_id + 1}/{shard_count}",
        }

    @staticmethod
    def _format_ping_metrics(metrics):
        def format_ms(value):
            if value is None or str(value).strip().upper() in ("N/A", "NONE"):
                return "N/A"
            if isinstance(value, str) and value.strip().lower().endswith("ms"):
                value = value.strip()[:-2]
            try:
                return f"{round(float(value))}ms"
            except (TypeError, ValueError):
                return str(value)

        return "\n".join(
            (
                f"**Gateway:** `{format_ms(metrics['gateway'])}`",
                f"**API:** `{format_ms(metrics['api'])}`",
                f"**SQLite:** `{format_ms(metrics['sqlite'])}`",
                f"**System Uptime:** `{metrics['uptime']}`",
            )
        )

    def _build_ping_embed(self, metrics, requester):
        embed = discord.Embed(
            title="⚡ Ultra-Low Latency Telemetry",
            description=self._format_ping_metrics(metrics),
            color=0x2b2d31,
        )
        req_name = getattr(requester, "display_name", str(requester)) if requester else "Unknown"
        embed.set_footer(text=f"Requested by {req_name} • Active Shard {metrics.get('shard', '#1/1')}")
        return embed

    async def _execute_ping_telemetry(self, ctx):
        # Try CV2 LayoutView (Zyuna design) first; fallback to clean embed if not supported
        try:
            message = await ctx.send(view=PingLoadingView())
            metrics = await self._collect_ping_metrics(ctx.guild)
            view = PingTelemetryView(self, ctx, metrics)
            view.message = message
            try:
                await message.edit(view=view)
            except Exception:
                if ctx.interaction:
                    await ctx.interaction.edit_original_response(view=view)
        except Exception:
            # Fallback to standard Embed + Button View
            metrics = await self._collect_ping_metrics(ctx.guild)
            embed = self._build_ping_embed(metrics, ctx.author)
            fallback_view = PingFallbackView(self, ctx, metrics)
            msg = await ctx.send(embed=embed, view=fallback_view)
            fallback_view.message = msg

    @commands.hybrid_command(
        name="ping",
        aliases=["pong"],
        description="Displays detailed network and database telemetry for Yuna Prime.",
        help="Checks the bot's WebSocket, API, and Database latencies.",
        with_app_command=True,
    )
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def ping(self, ctx):
        await self._execute_ping_telemetry(ctx)

    @commands.hybrid_command(
        name="latency",
        aliases=["lcy"],
        description="Displays detailed network and database telemetry.",
        help="Checks the bot latency, database status, and uptime.",
        with_app_command=True,
    )
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def latency(self, ctx):
        await self._execute_ping_telemetry(ctx)

    @commands.command(
        name="pingall",
        help="Displays full system and telemetry diagnostics (Bot Owner only).",
        hidden=True,
    )
    @ignore_check()
    @blacklist_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def pingall(self, ctx: commands.Context):
        """Bot Owner only: Displays detailed telemetry breakdown."""
        is_owner = False
        try:
            uid = int(ctx.author.id)
            is_owner = (uid in GLOBAL_OWNER_IDS) or (uid == PRIMARY_BOT_OWNER) or (uid in OWNER_IDS) or (await self.bot.is_owner(ctx.author))
        except Exception:
            is_owner = (int(ctx.author.id) in GLOBAL_OWNER_IDS) or (int(ctx.author.id) == PRIMARY_BOT_OWNER)

        if not is_owner:
            return  # Silently ignore for non-owners

        await self._execute_ping_telemetry(ctx)


async def setup(bot):
    await bot.add_cog(Ping(bot))
