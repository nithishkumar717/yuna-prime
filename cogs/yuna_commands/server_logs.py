"""
Yuna Auto-Logging System V2 - Server Logs Cog
Provides `/logs setup` slash & prefix hybrid command, auto-detects server channel text styles,
auto-provisions dedicated event channels under the 'Yuna Logs' category,
and dispatches real-time event logs via Discord Webhook.
"""

from __future__ import annotations
import os
import re
import time
import json
import asyncio
import datetime
import unicodedata
from typing import Optional, Dict, Any, List

import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

from services.logger_v2 import LoggerServiceV2
from utils.settings_manager import set_guild_setting, get_guild_setting
from utils.log_cooldown import log_setup_cooldown

DB_PATH = "db/audit_logs.db"
DISCORD_INVITE_RE = re.compile(
    r"(?:https?://)?(?:discord\.gg|discord(?:app)?\.com/invite)/([A-Za-z0-9-]+)",
    re.IGNORECASE,
)

# The complete logging categories (including dedicated invite surveillance channels)
LOG_CHANNELS = [
    'message', 'mod', 'verify', 'whitelist', 'security',
    'server', 'role', 'file', 'voice', 'member', 'channel',
    'invite', 'invite_tracker', 'invite_topz', 'ticket', 'admin', 'raid', 'misuse', 'antinuke',
    'nightmode', 'automod', 'ban', 'joins', 'leaves', 'presence',
    'relationship', 'boost'
]

DASHBOARD_CONFIG_KEYS = {
    "categories",
    "serverLogsChannel",
    "modLogsChannel",
    "perEventEnabled",
    "eventsConfig",
    "disabledEvents",
    "channelMappings",
    "ignoredChannels",
    "ignoredCategories",
    "ignoredRoles",
    "displayOldRoles",
    "displayIds",
    "moderationActions",
}


class MemberJoinAuditV2View(discord.ui.LayoutView):
    """Minimal gold-accented Components V2 panel for member arrival events."""

    def __init__(self, member: discord.Member, details: Dict[str, str]):
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_color=0xD6B15E)
        display_name = str(getattr(member, "display_name", member.name)).replace("`", "ˋ")
        username = str(member.name).replace("`", "ˋ")

        container.add_item(discord.ui.TextDisplay("## ✦ Member Arrival\n-# YUNA • JOIN AUDIT"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            f"### {display_name}\n`@{username}` · ID `{member.id}`"
        ))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            "**ACCOUNT**\n"
            f"> Created · {details.get('Account Created', 'Unknown')}\n"
            f"> Age · {details.get('Account Age', 'Unknown')}\n"
            f"> Type · {details.get('Account Type', 'Unknown')}\n\n"
            "**SERVER**\n"
            f"> Joined · {details.get('Joined Server', 'Unknown')}\n"
            f"> Member count · {details.get('Member Count', 'Unknown')}"
        ))
        container.add_item(discord.ui.Separator())
        invite_label = "ADDED BY" if member.bot else "INVITED BY"
        invite_value = details.get("Added By") if member.bot else details.get("Invited By")
        invite_value = invite_value or "Unknown"
        code_value = details.get("Invite Code", "Unknown")
        container.add_item(discord.ui.TextDisplay(
            f"**{invite_label}**\n"
            f"> {invite_value}\n"
            f"> Invite code · {code_value}"
        ))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("-# YUNA • AUTOMATED MEMBER AUDIT"))
        self.add_item(container)


def _remap_saved_dashboard_channels(saved_config: Dict[str, Any], new_channel_map: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve dashboard options and refresh references to setup channels."""
    dashboard_config = {
        key: json.loads(json.dumps(value))
        for key, value in saved_config.items()
        if key in DASHBOARD_CONFIG_KEYS
    }
    old_channel_keys = {
        str(entry.get("channel_id")): key
        for key, entry in saved_config.items()
        if isinstance(entry, dict) and entry.get("channel_id")
    }

    def remap(value: Any) -> Any:
        old_key = old_channel_keys.get(str(value))
        new_entry = new_channel_map.get(old_key) if old_key else None
        new_id = new_entry.get("channel_id") if isinstance(new_entry, dict) else None
        return str(new_id) if new_id else value

    for field in ("serverLogsChannel", "modLogsChannel"):
        if field in dashboard_config:
            dashboard_config[field] = remap(dashboard_config[field])

    events_config = dashboard_config.get("eventsConfig")
    if isinstance(events_config, dict):
        dashboard_config["eventsConfig"] = {
            key: remap(value) for key, value in events_config.items()
        }

    categories = dashboard_config.get("categories")
    if isinstance(categories, list):
        for category_config in categories:
            if isinstance(category_config, dict) and "channel" in category_config:
                category_config["channel"] = remap(category_config["channel"])

    return dashboard_config

from utils.Tools import (
    SMALL_CAPS,
    REVERSE_SMALL_CAPS,
    SMALL_CAPS_CHARS,
    FONT_MAPS,
    FONT_DISPLAY_NAMES,
    apply_font_style,
    to_small_caps,
    normalize_channel_name,
    identify_log_channel_type,
    detect_guild_channel_style,
    detect_yuna_logs_style,
    format_channel_name,
    standardize_all_yuna_logs_channels,
    OFFICIAL_LOGS_CATEGORY_NAME,
    AESTHETIC_LOG_CHANNELS
)


class LogsSetupConfirmationView(discord.ui.LayoutView):
    """Components V2 prompt for automatic or dashboard-based log setup."""

    def __init__(self, cog: "ServerLogs", ctx: commands.Context, target: Optional[str]):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.requester_id = ctx.author.id
        self.target = target
        self.message = None
        self._build_card(
            "Choose how you want to configure logging.\n\n"
            "**Automatic setup** — Create or reuse Yuna’s log category and channels, then route "
            "Yuna log events to their matching channels.\n\n"
            "**Manual setup** — Create or choose your own channels, then map events in "
            "**Dashboard → Logs → Server Logs**.\n\n"
            "Select an option to continue.",
            show_choices=True,
        )

    def _build_card(self, body: str, *, show_choices: bool = False, dashboard_url: Optional[str] = None):
        self.clear_items()
        container = discord.ui.Container(accent_color=0xD6B15E)
        container.add_item(discord.ui.TextDisplay("## Yuna Server Logs Setup"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(body))

        if show_choices:
            row = discord.ui.ActionRow()
            auto_button = discord.ui.Button(
                label="Continue with Auto Setup",
                style=discord.ButtonStyle.primary,
            )
            auto_button.callback = self.create_channels
            manual_button = discord.ui.Button(
                label="Configure Manually",
                style=discord.ButtonStyle.secondary,
            )
            manual_button.callback = self.configure_manually
            row.add_item(auto_button)
            row.add_item(manual_button)
            container.add_item(discord.ui.Separator())
            container.add_item(row)
        elif dashboard_url:
            row = discord.ui.ActionRow()
            row.add_item(discord.ui.Button(
                label="Open Server Logs Dashboard",
                style=discord.ButtonStyle.link,
                url=dashboard_url,
            ))
            container.add_item(discord.ui.Separator())
            container.add_item(row)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the administrator who started this setup can choose an option.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        self._build_card("This setup prompt expired. Run `/logs setup` again to choose an option.")
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.HTTPException, discord.NotFound):
                pass

    async def create_channels(self, interaction: discord.Interaction):
        # Prevent Discord HTTP 429 Channel Edit Rate Limits
        acquired, remaining, count, _ = await log_setup_cooldown.acquire(self.ctx.guild.id)
        if not acquired:
            embed = log_setup_cooldown.build_cooldown_embed(self.ctx.guild, remaining, count)
            self.clear_items()
            return await interaction.response.edit_message(content=None, embed=embed, view=None)

        self._build_card("**Automatic setup selected.** Yuna is preparing the log channels and routes now.")
        await interaction.response.edit_message(view=self)
        await self.cog._provision_logs_setup(self.ctx, self.target)

    async def configure_manually(self, interaction: discord.Interaction):
        guild_id = self.ctx.guild.id
        dashboard_root = (
            os.getenv("FRONTEND_URL")
            or "https://yuna.dpdns.org"
        ).rstrip("/")
        dashboard_url = f"{dashboard_root}/dashboard?guild_id={guild_id}&view=logging"
        self._build_card(
            "**Manual setup selected.** Create or choose your text channels, then map the events "
            "and save in **Dashboard → Logs → Server Logs**. Yuna will use those channel mappings; "
            "this choice does not create channels.\n\n"
            "Use the button below to open this server’s logging settings.",
            dashboard_url=dashboard_url,
        )
        await interaction.response.edit_message(view=self)


class ServerLogs(commands.Cog):
    """Yuna Auto-Logging System V2 - Server logging and channel management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Ensures WhitelistPanelV2View and WhitelistNoticeV2View persistent views are registered when ServerLogs cog loads."""
        try:
            await self._init_db()
            from services.whitelist_panel import WhitelistPanelV2View, WhitelistNoticeV2View
            self.bot.add_view(WhitelistPanelV2View())
            self.bot.add_view(WhitelistNoticeV2View())
            print("[ServerLogs] Persistent WhitelistPanelV2View and WhitelistNoticeV2View routers registered successfully.", flush=True)
        except Exception as e:
            print(f"[ServerLogs] Whitelist persistent views registration error: {e}", flush=True)

    async def _init_db(self):
        """Ensures server_logs_config exists in db/audit_logs.db."""
        os.makedirs("db", exist_ok=True)
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS server_logs_config (
                    guild_id INTEGER PRIMARY KEY,
                    webhook_url TEXT,
                    webhook_forward_url TEXT DEFAULT '',
                    webhook_forward_enabled INTEGER DEFAULT 1,
                    webhook_enabled INTEGER DEFAULT 1,
                    retention TEXT DEFAULT '90 Days',
                    categories_json TEXT,
                    updated_at TEXT
                )
            """)
            async with db.execute("PRAGMA table_info(server_logs_config)") as cursor:
                columns = {row[1] for row in await cursor.fetchall()}
            if "webhook_forward_url" not in columns:
                await db.execute("ALTER TABLE server_logs_config ADD COLUMN webhook_forward_url TEXT DEFAULT ''")
            if "webhook_forward_enabled" not in columns:
                await db.execute("ALTER TABLE server_logs_config ADD COLUMN webhook_forward_enabled INTEGER DEFAULT 1")
                await db.execute("UPDATE server_logs_config SET webhook_forward_enabled = COALESCE(webhook_enabled, 1)")
            async with db.execute(
                "SELECT guild_id, webhook_url, categories_json FROM server_logs_config "
                "WHERE COALESCE(webhook_forward_url, '') = '' AND COALESCE(webhook_url, '') != ''"
            ) as cursor:
                legacy_rows = await cursor.fetchall()
            for guild_id, legacy_url, categories_json in legacy_rows:
                setup_webhooks = set()
                try:
                    payload = json.loads(categories_json or "{}")
                    if isinstance(payload, dict):
                        setup_webhooks = {
                            str(entry.get("webhook_url") or "").strip()
                            for entry in payload.values()
                            if isinstance(entry, dict)
                        }
                except (TypeError, ValueError):
                    pass
                # `/logs setup` owns its per-channel webhook URLs in categories_json.
                # Keep a legacy URL as dashboard forwarding only when it is not one
                # of those channel webhooks.
                if legacy_url and legacy_url.strip() not in setup_webhooks:
                    await db.execute(
                        "UPDATE server_logs_config SET webhook_forward_url = ? WHERE guild_id = ?",
                        (legacy_url.strip(), guild_id),
                    )
            await db.commit()

    @commands.hybrid_group(name="logs", description="Configure Yuna Auto-Logging System")
    @commands.has_permissions(administrator=True)
    async def logs_group(self, ctx: commands.Context):
        """Base logs command displaying available options."""
        embed = discord.Embed(
            title="🛰️ Yuna Auto-Logging System V2",
            description=(
                "Configure Yuna's server event logging and choose where each event appears.\n\n"
                "**Commands:**\n"
                f"• `{ctx.prefix}logs setup` or `/logs setup` — Choose automatic channel setup or map your own channels in the dashboard.\n"
                f"• `{ctx.prefix}logs status` or `/logs status` — View active logging channels and webhook statuses.\n\n"
                "Use **Dashboard → Logs → Server Logs** to route events, disable event types, and set local cache retention. "
                "Use **Dashboard → Logs → Audit Logs** to search, filter, page through, and export audit history."
            ),
            color=0x2B2D31
        )
        author_icon = getattr(getattr(ctx.author, "display_avatar", None), "url", None)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=author_icon)
        await ctx.reply(embed=embed)

    @logs_group.command(name="setup", description="Choose automatic or manual server log setup")
    @app_commands.describe(target="Optional: use whitelist to set up only the Whitelist Control Panel")
    @commands.has_permissions(administrator=True)
    async def logs_setup(self, ctx: commands.Context, *, target: Optional[str] = None):
        """Ask whether to create the log channels or configure them manually."""
        guild = ctx.guild
        if not guild:
            return await ctx.reply("This command can only be used in a server.")

        # Rate-limit cooldown protection against Discord HTTP 429 channel edits
        is_cd, remaining, count = await log_setup_cooldown.check(guild.id)
        if is_cd:
            embed = log_setup_cooldown.build_cooldown_embed(guild, remaining, count)
            if ctx.interaction:
                return await ctx.send(embed=embed, ephemeral=True)
            return await ctx.reply(embed=embed, mention_author=False)

        if target and any(key in target.lower() for key in ("white", "wl", "ui")):
            acquired, remaining, count, _ = await log_setup_cooldown.acquire(guild.id)
            if not acquired:
                embed = log_setup_cooldown.build_cooldown_embed(guild, remaining, count)
                if ctx.interaction:
                    return await ctx.send(embed=embed, ephemeral=True)
                return await ctx.reply(embed=embed, mention_author=False)
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.defer(ephemeral=False)
            return await self._provision_logs_setup(ctx, target)

        view = LogsSetupConfirmationView(self, ctx, target)
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
            view.message = await ctx.send(view=view, ephemeral=True)
        else:
            view.message = await ctx.reply(view=view, mention_author=False)

    async def _provision_logs_setup(self, ctx: commands.Context, target: Optional[str] = None):
        """Create or reuse Yuna logging channels and configure their delivery."""
        guild = ctx.guild
        if not guild:
            return await ctx.reply("❌ This command can only be executed in a server.")

        # Verify bot permissions
        bot_member = guild.me
        if not bot_member.guild_permissions.manage_channels:
            return await ctx.reply("❌ Bot requires `Manage Channels` permission to set up logging channels.")
        if not bot_member.guild_permissions.manage_webhooks:
            return await ctx.reply("❌ Bot requires `Manage Webhooks` permission to initialize logging webhooks.")

        await self._init_db()

        # 1. Detect server styling
        server_style = detect_yuna_logs_style(guild)

        # Handle specific Whitelist UI setup if requested
        if target and any(k in target.lower() for k in ("white", "wl", "ui")):
            from services.whitelist_panel import WhitelistPanelService
            wl_channel = await WhitelistPanelService.get_whitelist_channel(guild)
            if not wl_channel:
                category = discord.utils.find(lambda c: "yuna" in c.name.lower() and "log" in c.name.lower(), guild.categories)
                if not category:
                    category = await guild.create_category(
                        name=OFFICIAL_LOGS_CATEGORY_NAME,
                        overwrites={
                            guild.default_role: discord.PermissionOverwrite(
                                view_channel=False,
                                send_messages=False,
                                send_messages_in_threads=False,
                                create_public_threads=False,
                                create_private_threads=False,
                                add_reactions=False,
                                read_message_history=False,
                                use_application_commands=False
                            ),
                            bot_member: discord.PermissionOverwrite(
                                view_channel=True,
                                send_messages=True,
                                send_messages_in_threads=True,
                                embed_links=True,
                                attach_files=True,
                                read_message_history=True,
                                manage_webhooks=True,
                                manage_channels=True,
                                manage_messages=True
                            )
                        }
                    )
                styled_name = format_channel_name("whitelist", server_style, "Yuna")
                wl_channel = await guild.create_text_channel(
                    name=styled_name,
                    category=category,
                    topic="🔕 Automated Audit Logs (Notifications Muted / Silent)",
                    overwrites={
                        guild.default_role: discord.PermissionOverwrite(
                            view_channel=False,
                            send_messages=False,
                            send_messages_in_threads=False,
                            create_public_threads=False,
                            create_private_threads=False,
                            add_reactions=False,
                            read_message_history=False,
                            use_application_commands=False
                        ),
                        bot_member: discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            send_messages_in_threads=True,
                            embed_links=True,
                            attach_files=True,
                            read_message_history=True,
                            manage_webhooks=True,
                            manage_channels=True,
                            manage_messages=True
                        )
                    }
                )

            wl_msg = await WhitelistPanelService.setup_panel(guild, wl_channel)
            embed = discord.Embed(
                title="<a:tick:1558726958802800660> Whitelist UI Connected",
                description=(
                    f"• **Channel:** {wl_channel.mention} (`#{wl_channel.name}`)\n"
                    f"• **Interactive State:** 🟢 **Connected**\n"
                    f"• **Persistent Mode:** Active (Survives bot restarts)\n\n"
                    f"Staff can now click the interactive buttons in {wl_channel.mention} to whitelist users, security bots, and roles directly!"
                ),
                color=0x57F287,
                timestamp=discord.utils.utcnow()
            )
            bot_icon = getattr(getattr(guild.me, "display_avatar", None), "url", None)
            embed.set_footer(text=f"Guild ID: {guild.id} | Yuna Logging System", icon_url=bot_icon)
            return await ctx.send(embed=embed)

        # 2. Find or create 'Yuna Logs' Category
        # STRICT ISOLATION: Only match categories explicitly identified as Yuna Logs
        def is_yuna_logs_category(cat) -> bool:
            if not cat or not getattr(cat, "name", None):
                return False
            name = cat.name.lower()
            return ("yuna" in name and "log" in name) or name in ("yuna logs", "yuna-logs", "yuna_logs", "❀ yuna・logs", "🌸 yuna・logs")

        # Check if we have a saved category_id or channel map in DB for this guild
        saved_cat_id = None
        saved_channels_map = {}
        try:
            async with aiosqlite.connect(DB_PATH, timeout=5.0) as db:
                async with db.execute("SELECT categories_json FROM server_logs_config WHERE guild_id = ?", (guild.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        cfg_data = json.loads(row[0])
                        if isinstance(cfg_data, dict):
                            saved_channels_map = cfg_data
                            saved_cat_id = cfg_data.get("_category_id")
        except Exception:
            pass

        category = None
        # Priority 0: Exact category ID previously created/saved by Yuna in this guild
        if saved_cat_id:
            cand_cat = guild.get_channel(int(saved_cat_id))
            if cand_cat and isinstance(cand_cat, discord.CategoryChannel) and is_yuna_logs_category(cand_cat):
                category = cand_cat

        # Priority 1: Category explicitly recognized as Yuna Logs with channels
        if not category:
            for c in guild.categories:
                if is_yuna_logs_category(c) and len(c.text_channels) > 0:
                    category = c
                    break

        # Priority 2: Empty category explicitly recognized as Yuna Logs
        if not category:
            for c in guild.categories:
                if is_yuna_logs_category(c):
                    category = c
                    break

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
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                send_messages_in_threads=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
                manage_webhooks=True,
                manage_channels=True,
                manage_messages=True
            )
        }

        if not category:
            try:
                category = await guild.create_category(
                    name=OFFICIAL_LOGS_CATEGORY_NAME,
                    overwrites=overwrites,
                    reason="Yuna Logs V2 Auto-Logging Setup"
                )
            except Exception as e:
                return await ctx.send(f"❌ Failed to create category: {e}")
        else:
            # Enforce standardized category name and secure private permissions
            try:
                cat_kwargs = {"overwrites": overwrites, "reason": "Yuna Logs V2: Enforce secure category permissions"}
                if category.name not in (OFFICIAL_LOGS_CATEGORY_NAME, "❀ YUNA・LOGS"):
                    cat_kwargs["name"] = OFFICIAL_LOGS_CATEGORY_NAME
                await category.edit(**cat_kwargs)
            except Exception as cat_err:
                print(f"[Logs Setup] Failed to update category {category.name}: {cat_err}")

        # Clean up only empty duplicate YUNA logs categories left from prior setups (never touch other categories)
        for c in guild.categories:
            if c.id != category.id and is_yuna_logs_category(c) and len(c.text_channels) == 0:
                try:
                    await c.delete(reason="Yuna Logs: Remove empty duplicate Yuna logs category")
                except Exception:
                    pass

        # Ensure any existing Nightmode, Antinuke, or Automod channels are moved under Yuna Logs
        try:
            from utils.Tools import sync_security_log_channels_to_yuna_logs
            await sync_security_log_channels_to_yuna_logs(guild, category=category)
        except Exception as sync_sec_err:
            print(f"[Logs Setup] Failed to sync security log channels to Yuna Logs: {sync_sec_err}")

        # Detect category style directly from the resolved category
        server_style = detect_yuna_logs_style(guild, category)

        # Fetch bot avatar bytes for webhook branding
        bot_avatar_bytes = None
        try:
            if self.bot.user and self.bot.user.display_avatar:
                bot_avatar_bytes = await self.bot.user.display_avatar.read()
        except Exception:
            pass

        reused_count = 0
        renamed_count = 0
        created_count = 0
        webhook_count = 0
        categories_map: Dict[str, Dict[str, Any]] = {}
        primary_webhook_url = ""
        claimed_channel_ids = set()

        # 3. Provision or link each of the 24 logging channels
        for raw_name in LOG_CHANNELS:
            styled_name = format_channel_name(raw_name, server_style, "Yuna")
            channel = None

            # 0th pass: Authenticate via Yuna's saved DB channel ID (Guaranteed authentic Yuna channel)
            if raw_name in saved_channels_map and isinstance(saved_channels_map[raw_name], dict) and saved_channels_map[raw_name].get("channel_id"):
                saved_cid = saved_channels_map[raw_name]["channel_id"]
                cand = discord.utils.get(category.text_channels, id=int(saved_cid))
                if cand and cand.id not in claimed_channel_ids:
                    channel = cand

            # 1st pass: Exact match on styled name among unclaimed text channels in category
            if not channel:
                for ch in category.text_channels:
                    if ch.id not in claimed_channel_ids and ch.name == styled_name:
                        channel = ch
                        break

            # 2nd pass: Keyword/token pattern match among unclaimed text channels in category
            if not channel:
                if raw_name == 'joins':
                    pat = r'(^|[^a-z0-9])joins?([^a-z0-9]|$)'
                elif raw_name == 'leaves':
                    pat = r'(^|[^a-z0-9])(leave|leaves)([^a-z0-9]|$)'
                else:
                    pat = rf'(^|[^a-z0-9]){re.escape(raw_name)}([^a-z0-9]|$)'

                candidates = []
                for ch in category.text_channels:
                    if ch.id in claimed_channel_ids:
                        continue
                    ch_norm = normalize_channel_name(ch.name)
                    if re.search(pat, ch_norm):
                        candidates.append(ch)

                if candidates:
                    # PROVENANCE VERIFICATION: Prioritize genuine channel created by Yuna (has Yuna topic)
                    # and ignore user-created duplicate channels
                    yuna_cands = [
                        c for c in candidates
                        if getattr(c, "topic", None) and any(
                            t in c.topic for t in ("Automated Audit Logs", "Antinuke Security Alerts")
                        )
                    ]
                    channel = yuna_cands[0] if yuna_cands else candidates[0]


            if raw_name in ("antinuke", "security"):
                desired_topic = "<a:37496alert:1550972111215009914> High-Priority Antinuke Security Alerts (Notifications Active)"
            elif raw_name in ("invite_tracker", "invite_logs"):
                desired_topic = "🔕 Automated Invite Tracker (Live Arrival Attribution)"
            elif raw_name == "invite_topz":
                desired_topic = "🏆 Live Top Inviters Leaderboard • Yuna Invite Tracker"
            else:
                desired_topic = "🔕 Automated Audit Logs (Notifications Muted / Silent)"

            if channel:
                claimed_channel_ids.add(channel.id)
                reused_count += 1
                
                edit_fields = {}
                if channel.name != styled_name:
                    edit_fields["name"] = styled_name
                if not getattr(channel, "permissions_synced", False) and raw_name != "invite_topz":
                    edit_fields["sync_permissions"] = True
                if getattr(channel, "topic", None) != desired_topic:
                    edit_fields["topic"] = desired_topic

                if edit_fields:
                    try:
                        edit_fields["reason"] = "Yuna Logs V2: Standardize channel & permissions"
                        await channel.edit(**edit_fields)
                        if "name" in edit_fields:
                            renamed_count += 1
                        await asyncio.sleep(0.3)  # Gentle spacing for Discord rate limits
                    except Exception as ren_err:
                        print(f"[Logs Setup] Failed to update channel {channel.name}: {ren_err}")
            else:
                try:
                    create_kwargs = {
                        "name": styled_name,
                        "category": category,
                        "topic": desired_topic,
                        "reason": f"Yuna Logs V2: Channel for {raw_name}"
                    }
                    if raw_name == "invite_topz":
                        topz_overwrites = dict(category.overwrites)
                        topz_overwrites[guild.default_role] = discord.PermissionOverwrite(
                            view_channel=False,
                            send_messages=False,
                            add_reactions=False,
                            read_message_history=True
                        )
                        create_kwargs["overwrites"] = topz_overwrites

                    channel = await guild.create_text_channel(**create_kwargs)
                    claimed_channel_ids.add(channel.id)
                    created_count += 1
                    await asyncio.sleep(0.3)  # Gentle spacing for Discord rate limits
                except Exception as ch_err:
                    print(f"[Logs Setup] Failed to create channel {raw_name}: {ch_err}")
                    continue

            # Sync security database configurations for dedicated security channels
            if channel:
                if raw_name == 'nightmode':
                    try:
                        async with aiosqlite.connect('db/anti.db', timeout=10.0) as anti_db:
                            await anti_db.execute(
                                "UPDATE nightmode_config SET log_channel = ? WHERE guild_id = ?",
                                (channel.id, guild.id)
                            )
                            await anti_db.commit()
                    except Exception:
                        pass
                elif raw_name == 'antinuke':
                    try:
                        async with aiosqlite.connect('db/anti.db', timeout=10.0) as anti_db:
                            await anti_db.execute(
                                "UPDATE antinuke SET log_channel = ? WHERE guild_id = ?",
                                (channel.id, guild.id)
                            )
                            await anti_db.commit()
                    except Exception:
                        pass
                elif raw_name == 'automod':
                    try:
                        async with aiosqlite.connect('db/automod.db', timeout=10.0) as am_db:
                            await am_db.execute("CREATE TABLE IF NOT EXISTS automod_logging (guild_id INTEGER PRIMARY KEY, log_channel INTEGER)")
                            await am_db.execute("INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?, ?)", (guild.id, channel.id))
                            await am_db.commit()
                    except Exception:
                        pass
                elif raw_name in ('invite_tracker', 'invite_logs'):
                    try:
                        async with aiosqlite.connect('db/invites.db', timeout=10.0) as inv_db:
                            await inv_db.execute(
                                "INSERT INTO invite_config (guild_id, enabled, log_channel) VALUES (?, 1, ?) "
                                "ON CONFLICT(guild_id) DO UPDATE SET log_channel = excluded.log_channel, enabled = 1",
                                (guild.id, channel.id)
                            )
                            await inv_db.commit()
                    except Exception:
                        pass
                elif raw_name == 'invite_topz':
                    try:
                        async with aiosqlite.connect('db/invites.db', timeout=10.0) as inv_db:
                            await inv_db.execute(
                                "INSERT INTO invite_config (guild_id, enabled, topz_channel) VALUES (?, 1, ?) "
                                "ON CONFLICT(guild_id) DO UPDATE SET topz_channel = excluded.topz_channel, enabled = 1",
                                (guild.id, channel.id)
                            )
                            await inv_db.commit()
                        it_cog = self.bot.get_cog("InviteTracker")
                        if it_cog and hasattr(it_cog, "update_topz_leaderboard"):
                            asyncio.create_task(it_cog.update_topz_leaderboard(guild, channel))
                    except Exception:
                        pass

            # Fetch or create Webhook strictly for Yuna on this channel
            webhook_url = ""
            if channel:
                try:
                    webhooks = await channel.webhooks()
                    wh = discord.utils.find(lambda w: w.name == "Yuna Logs Webhook" or (w.user and w.user.id == guild.me.id), webhooks)
                    if not wh:
                        wh = await channel.create_webhook(
                            name="Yuna Logs Webhook",
                            avatar=bot_avatar_bytes,
                            reason="Yuna Logs V2 Channel Webhook"
                        )
                    if wh:
                        webhook_url = wh.url
                        webhook_count += 1
                        if not primary_webhook_url:
                            primary_webhook_url = wh.url
                except Exception as wh_err:
                    print(f"[Logs Setup Webhook Warning - {channel.name}]: {wh_err}")

            categories_map[raw_name] = {
                "channel_id": channel.id if channel else None,
                "channel_name": channel.name if channel else raw_name,
                "webhook_url": webhook_url
            }

        # 4. Save to db/audit_logs.db
        categories_map["_category_id"] = category.id
        categories_map.update(_remap_saved_dashboard_channels(saved_channels_map, categories_map))
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA busy_timeout=30000;")
            async with db.execute(
                "SELECT categories_json, webhook_forward_url, webhook_forward_enabled, retention FROM server_logs_config WHERE guild_id = ?",
                (guild.id,),
            ) as cursor:
                previous_row = await cursor.fetchone()
            if previous_row and previous_row[0]:
                try:
                    previous_config = json.loads(previous_row[0])
                    if isinstance(previous_config, dict):
                        for config_key in (
                            "categories", "serverLogsChannel", "modLogsChannel", "perEventEnabled",
                            "eventsConfig", "disabledEvents", "channelMappings", "ignoredChannels",
                            "ignoredCategories", "ignoredRoles", "displayOldRoles", "displayIds",
                            "moderationActions",
                        ):
                            if config_key in previous_config and config_key not in categories_map:
                                categories_map[config_key] = previous_config[config_key]
                except (TypeError, ValueError):
                    pass
            categories_json = json.dumps(categories_map)
            await db.execute("""
                INSERT INTO server_logs_config (guild_id, webhook_url, webhook_enabled, retention, categories_json, updated_at)
                VALUES (?, ?, 1, '90 Days', ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    webhook_url = excluded.webhook_url,
                    webhook_enabled = 1,
                    categories_json = excluded.categories_json,
                    updated_at = excluded.updated_at
            """, (guild.id, primary_webhook_url, categories_json, now_iso))
            await db.commit()

        set_guild_setting(guild.id, "server_logs_webhook", primary_webhook_url)
        set_guild_setting(guild.id, "server_logs_webhook_enabled", True)
        server_logs_channel = categories_map.get("serverLogsChannel")
        if "serverLogsChannel" not in categories_map:
            server_logs_channel = categories_map.get("server", {}).get("channel_id")
        mod_logs_channel = categories_map.get("modLogsChannel")
        if "modLogsChannel" not in categories_map:
            mod_logs_channel = categories_map.get("mod", {}).get("channel_id")
        set_guild_setting(guild.id, "server_logs_channel", server_logs_channel or None)
        set_guild_setting(guild.id, "mod_logs_channel", mod_logs_channel or None)
        LoggerServiceV2.update_guild_cache(guild.id, {
            **categories_map,
            "_customWebhookUrl": (previous_row[1] or "") if previous_row else "",
            "_customWebhookEnabled": bool(previous_row[2]) if previous_row else True,
            "_logRetention": (previous_row[3] or "90 Days") if previous_row else "90 Days",
        })

        # 5. Standardize all channels under Yuna Logs to guarantee 100% unified text style
        try:
            await standardize_all_yuna_logs_channels(guild, category=category, style=server_style)
        except Exception as std_err:
            print(f"[Logs Setup Standardize Warning]: {std_err}")

        # Auto-send / update the interactive Whitelist Control Panel in ․yuna․whitelist․
        whitelist_entry = categories_map.get("whitelist")
        wl_status_str = "Not Setup"
        if whitelist_entry and whitelist_entry.get("channel_id"):
            wl_channel = guild.get_channel(int(whitelist_entry["channel_id"]))
            if wl_channel:
                try:
                    from services.whitelist_panel import WhitelistPanelService
                    wl_msg = await WhitelistPanelService.setup_panel(guild, wl_channel)
                    wl_status_str = f"🟢 Connected ({wl_channel.mention})"
                except Exception as wl_pnl_err:
                    print(f"[Logs Setup] Whitelist panel auto-send warning: {wl_pnl_err}")
                    wl_status_str = f"⚠️ Setup Warning ({wl_channel.mention})"

        # Auto-ensure dedicated Invite Logs and Invite Topz channels under YUNA LOGS
        invite_status_str = "Not Setup"
        try:
            it_cog = self.bot.get_cog("InviteTracker")
            if it_cog and hasattr(it_cog, "ensure_yuna_logs_invite_channels"):
                inv_res = await it_cog.ensure_yuna_logs_invite_channels(guild, category=category)
                if inv_res and inv_res.get("logs") and inv_res.get("topz"):
                    invite_status_str = f"🟢 Connected ({inv_res['logs'].mention} & {inv_res['topz'].mention})"
                elif inv_res and inv_res.get("logs"):
                    invite_status_str = f"🟢 Connected ({inv_res['logs'].mention})"
        except Exception as inv_err:
            print(f"[Logs Setup] Invite channels setup warning: {inv_err}")

        font_display = server_style.get("font_display", "Standard")
        sample_name = format_channel_name("message", server_style, "Yuna")

        desc_lines = [
            f"• **Category:** `{category.name}`",
            f"• **Font & Text Style:** `{font_display}` *(Synced with Server)*",
            f"• **Channel Format:** `#{sample_name}`",
            f"• **Whitelist UI:** {wl_status_str}",
            f"• **Invite Surveillance:** {invite_status_str}",
            f"• **Permissions:** 🔒 Private (Hidden from @everyone, synced)",
            f"• **Notification Mode:** 🔕 Muted (`@silent` active for all routine logs)",
            f"• **Security Alerts:** 🔔 Normal / Loud (`antinuke` & `security` alert staff)",
            f"• **Reused Channels:** `{reused_count}`" + (f" *({renamed_count} renamed to server style)*" if renamed_count > 0 else ""),
            f"• **Newly Created Channels:** `{created_count}`",
            f"• **Log Destinations Ready:** `{webhook_count}/{len(LOG_CHANNELS)}`",
            "",
            "All enabled events now route to their configured Yuna log channels."
        ]
        embed = discord.Embed(
            title="<a:tick:1558726958802800660> Yuna Server Logs Ready",
            description="\n".join(desc_lines),
            color=0x57F287,
            timestamp=discord.utils.utcnow()
        )
        bot_icon = getattr(getattr(guild.me, "display_avatar", None), "url", None)
        embed.set_footer(text=f"Guild ID: {guild.id} | Yuna Logging System", icon_url=bot_icon)
        await ctx.send(embed=embed)

    @logs_group.command(name="whitelist", description="Set up or reconnect the Whitelist Control Panel UI")
    @commands.has_permissions(administrator=True)
    async def logs_whitelist_cmd(self, ctx: commands.Context):
        """Specifically deploys, connects, or reconnects the Whitelist UI control panel."""
        await self.logs_setup(ctx, target="whitelist")

    @logs_group.command(name="status", description="Check current status of Yuna Logs setup")
    @commands.has_permissions(administrator=True)
    async def logs_status(self, ctx: commands.Context):
        """Displays status of the logging channels and webhook configurations."""
        guild = ctx.guild
        if not guild:
            return

        category = discord.utils.find(
            lambda c: isinstance(c, discord.CategoryChannel) and ("yuna" in c.name.lower() and "log" in c.name.lower() or c.name in ("Yuna Logs", "❀ YUNA・LOGS", OFFICIAL_LOGS_CATEGORY_NAME)),
            guild.categories
        )

        if not category:
            return await ctx.reply("❌ No Yuna Logs category found. Run `/logs setup` to configure.")

        server_style = detect_yuna_logs_style(guild, category)
        font_display = server_style.get("font_display", "Standard")
        sample_name = format_channel_name("message", server_style, "Yuna")

        from services.whitelist_panel import WhitelistPanelService
        wl_channel = await WhitelistPanelService.get_whitelist_channel(guild)
        wl_status = f"🟢 Connected ({wl_channel.mention})" if wl_channel else "🔴 Not Setup"

        inv_logs_ch = discord.utils.find(lambda c: c.name in ("﹒❀﹒invite﹒tracker․・", "📩・𝗜𝗡𝗩𝗜𝗧𝗘﹒𝗧𝗥𝗔𝗖𝗞𝗘𝗥", "﹒❀﹒invite﹒logs․・", "📩・𝗜𝗡𝗩𝗜𝗧𝗘﹒𝗟𝗢𝗚𝗦") or ("invite" in c.name.lower() and ("tracker" in c.name.lower() or "track" in c.name.lower() or "log" in c.name.lower())), category.text_channels) if category else None
        inv_topz_ch = discord.utils.find(lambda c: c.name in ("﹒❀﹒invite﹒topz․・", "🏆・𝗜𝗡𝗩𝗜𝗧𝗘﹒𝗧𝗢𝗣𝗭") or ("invite" in c.name.lower() and "top" in c.name.lower()), category.text_channels) if category else None
        inv_status = f"🟢 Connected ({inv_logs_ch.mention} & {inv_topz_ch.mention})" if (inv_logs_ch and inv_topz_ch) else (f"🟢 Connected ({inv_logs_ch.mention})" if inv_logs_ch else "🔴 Not Setup")

        configured_channels = len(category.text_channels)
        embed = discord.Embed(
            title="📊 Yuna Logs Status",
            description=(
                f"• **Category:** `{category.name}`\n"
                f"• **Font & Text Style:** `{font_display}` *(Synced with Server)*\n"
                f"• **Channel Format:** `#{sample_name}`\n"
                f"• **Whitelist UI:** {wl_status}\n"
                f"• **Invite Surveillance:** {inv_status}\n"
                f"• **Channels Linked:** `{configured_channels}/{len(LOG_CHANNELS)}`\n"
                f"• **Permissions:** 🔒 Private (Hidden from @everyone, synced)\n"
                f"• **Notification Mode:** 🔕 Muted (`@silent` active for all routine logs)\n"
                f"• **Security Alerts:** 🔔 Normal / Loud (`antinuke` & `security` alert staff)\n\n"
                "To refresh or add missing channels, run `/logs setup`."
            ),
            color=0x2B2D31,
            timestamp=discord.utils.utcnow()
        )
        bot_icon = getattr(getattr(guild.me, "display_avatar", None), "url", None)
        embed.set_footer(text=f"Guild ID: {guild.id}", icon_url=bot_icon)
        await ctx.reply(embed=embed)

    # =========================================================================
    # EVENT LISTENERS FOR AUTO-LOGGING
    # =========================================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Logs Discord invites posted by members when that dashboard event is enabled."""
        if not message.guild or message.author.bot or not message.content:
            return
        invite_match = DISCORD_INVITE_RE.search(message.content)
        if not invite_match:
            return
        await LoggerServiceV2.send_v2_log(
            guild=message.guild,
            channel_key="invite",
            event_key="invite_posted",
            source_channel=message.channel,
            title="Invite Posted",
            description=f"🔗 {message.author.mention} posted a Discord invite in {message.channel.mention}: {invite_match.group(0)}",
            color=0x5865F2,
            user=message.author,
        )

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        """Logs bulk message purges once per Discord bulk-delete event."""
        if not messages:
            return
        channel = messages[0].channel
        guild = getattr(channel, "guild", None)
        if not guild:
            return
        executor = await LoggerServiceV2.get_executor(
            guild, discord.AuditLogAction.message_bulk_delete
        )
        await LoggerServiceV2.send_v2_log(
            guild=guild,
            channel_key="message",
            event_key="bulk_delete",
            source_channel=channel,
            title="Bulk Messages Deleted",
            description=f"🧹 {len(messages)} messages were deleted in {channel.mention}.",
            color=0xED4245,
            executor=executor,
            fields=[{"name": "Messages Deleted", "value": str(len(messages)), "inline": True}],
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Logs member join events to 'joins' channel."""
        now = discord.utils.utcnow()
        created_at = member.created_at
        joined_at = getattr(member, "joined_at", None) or now
        account_age_seconds = max(0, int((now - created_at).total_seconds()))
        age_days, age_remainder = divmod(account_age_seconds, 86400)
        age_hours, age_remainder = divmod(age_remainder, 3600)
        age_minutes = age_remainder // 60
        if age_days:
            account_age = f"{age_days}d {age_hours}h"
        elif age_hours:
            account_age = f"{age_hours}h {age_minutes}m"
        else:
            account_age = f"{max(1, age_minutes)}m"

        if account_age_seconds < 3 * 86400:
            account_age += " • NEW ACCOUNT (< 3 days)"

        member_count = getattr(member.guild, "member_count", None)
        join_fields = [
            {"name": "User ID", "value": str(member.id), "inline": True},
            {
                "name": "Account Created",
                "value": created_at.strftime("%b %d, %Y at %I:%M:%S %p UTC"),
                "inline": True,
            },
            {"name": "Account Age", "value": account_age, "inline": True},
            {
                "name": "Joined Server",
                "value": joined_at.strftime("%b %d, %Y at %I:%M:%S %p UTC"),
                "inline": True,
            },
            {"name": "Account Type", "value": "Bot" if member.bot else "Human", "inline": True},
        ]
        if member_count is not None:
            join_fields.append({"name": "Member Count", "value": f"#{member_count}", "inline": True})

        inviter = None
        invite_code = None
        added_by = None
        if member.bot:
            added_by = await LoggerServiceV2.get_executor(
                member.guild, discord.AuditLogAction.bot_add, member.id
            )
            join_fields.append({
                "name": "Added By",
                "value": f"{added_by} (ID: {added_by.id})" if added_by else "Unknown (View Audit Log permission required)",
                "inline": True,
            })
            join_fields.append({"name": "Invite Code", "value": "Not applicable to bot additions", "inline": True})
        else:
            invite_tracker = self.bot.get_cog("InviteTracker")
            inviter = None
            invite_code = None
            if invite_tracker:
                try:
                    inviter, invite_code = await invite_tracker.resolve_join_invite(member)
                except Exception:
                    pass

            is_vanity = False
            clean_code = str(invite_code) if invite_code else None
            if clean_code and clean_code.startswith("VANITY:"):
                is_vanity = True
                clean_code = clean_code.split("VANITY:", 1)[1]
            elif clean_code and getattr(member.guild, "vanity_url_code", None) == clean_code:
                is_vanity = True

            if clean_code == "NO_PERMS":
                inviter_display = "Unavailable (Missing 'Manage Server')"
                code_display = "Permission Required"
            elif is_vanity:
                inviter_display = "Vanity URL"
                code_display = f"discord.gg/{clean_code}"
            elif inviter:
                inviter_name = getattr(inviter, "display_name", getattr(inviter, "name", str(inviter)))
                inviter_display = f"{inviter.mention} ({inviter_name} · ID: `{inviter.id}`)"
                code_display = f"discord.gg/{clean_code}" if clean_code else "Unknown"
            elif clean_code:
                inviter_display = "Unknown"
                code_display = f"discord.gg/{clean_code}"
            else:
                if getattr(member.guild, "vanity_url_code", None):
                    inviter_display = "Vanity URL / Unknown"
                    code_display = f"discord.gg/{member.guild.vanity_url_code}"
                else:
                    inviter_display = "Unknown (Discovery / Direct)"
                    code_display = "None"

            join_fields.extend([
                {"name": "Invited By", "value": inviter_display, "inline": True},
                {"name": "Invite Code", "value": code_display, "inline": True},
            ])

        join_details = {field["name"]: str(field["value"]) for field in join_fields}
        join_view = MemberJoinAuditV2View(member, join_details)

        await LoggerServiceV2.send_v2_log(
            guild=member.guild,
            channel_key="security" if member.bot else "joins",
            event_key="bot_add" if member.bot else "joins",
            title="Bot Added" if member.bot else "Member Joined",
            description=f"📥 {member.mention} **({member})** joined the server.",
            color=0x57F287,
            user=member,
            executor=added_by,
            fields=join_fields,
            view=join_view,
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Logs member departures to 'leaves' channel with verified departure reasons."""
        if not member.guild:
            return

        dep_type, executor, dep_reason = await LoggerServiceV2.resolve_member_departure(
            member.guild, member
        )

        if dep_type == "kicked":
            mod_str = executor.mention if executor else "a moderator"
            description = f"**{member}** was kicked by {mod_str}."
        elif dep_type == "banned":
            mod_str = executor.mention if executor else "a moderator"
            description = f"**{member}** was banned by {mod_str}."
        else:
            description = f"**{member}** left the server."

        fields = [
            {"name": "Departure Reason", "value": dep_reason, "inline": False},
            {"name": "User ID", "value": f"`{member.id}`", "inline": True},
        ]

        await LoggerServiceV2.send_v2_log(
            guild=member.guild,
            channel_key="leaves",
            event_key="leaves",
            title="Member Left",
            description=description,
            color=0xED4245,
            user=member,
            executor=executor,
            fields=fields,
        )

        # If member was kicked, also mirror to mod log channel if configured and distinct from leaves
        if dep_type == "kicked":
            try:
                leaves_res = await LoggerServiceV2.resolve_target_channel(
                    member.guild, "leaves", "leaves"
                )
                leaves_ch = leaves_res[0] if leaves_res else None
                mod_res = await LoggerServiceV2.resolve_target_channel(
                    member.guild, "mod", "kick", moderation_action="kick"
                )
                mod_ch = mod_res[0] if mod_res else None

                if mod_ch and (not leaves_ch or mod_ch.id != leaves_ch.id):
                    mod_fields = [
                        {"name": "Reason", "value": dep_reason, "inline": False},
                        {"name": "User ID", "value": f"`{member.id}`", "inline": True},
                    ]
                    await LoggerServiceV2.send_v2_log(
                        guild=member.guild,
                        channel_key="mod",
                        event_key="kick",
                        moderation_action="kick",
                        title="Member Kicked",
                        description=f"**{member}** was kicked by {executor.mention if executor else 'a moderator'}.",
                        color=0xED4245,
                        user=member,
                        executor=executor,
                        fields=mod_fields,
                    )
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Logs message deletions to 'message' channel."""
        if not message.guild or message.author.bot:
            return

        executor = None
        for attempt in range(3):
            executor = await LoggerServiceV2.get_executor(
                message.guild, discord.AuditLogAction.message_delete, message.author.id
            )
            if executor:
                break
            if attempt < 2:
                await asyncio.sleep(0.25)
        try:
            from core.dashboard_server import store_deleted_message_audit
            await store_deleted_message_audit(message, executor)
        except Exception as exc:
            print(f"[MESSAGE DELETE AUDIT ERROR] {exc}")
        content = message.content[:1000] if message.content else "*[No Text / Attachment]*"
        await LoggerServiceV2.send_v2_log(
            guild=message.guild,
            channel_key="message",
            event_key="message_delete",
            source_channel=message.channel,
            title="Message Deleted",
            description=f"🗑️ Message by {message.author.mention} deleted in {message.channel.mention}.",
            color=0xED4245,
            user=message.author,
            executor=executor,
            fields=[
                {"name": "Content", "value": f"```{content}```", "inline": False},
                {"name": "Deleted By", "value": executor.mention if executor else "Self / Unknown", "inline": True}
            ]
        )

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, channel: discord.abc.GuildChannel, last_pin_at):
        """Logs pin-list changes; Discord does not identify the individual pin action here."""
        guild = getattr(channel, "guild", None)
        if not guild:
            return
        channel_label = getattr(channel, "mention", f"#{getattr(channel, 'name', 'channel')}")
        pin_time = last_pin_at.strftime("%Y-%m-%d %H:%M UTC") if last_pin_at else "No pinned messages remain"
        await LoggerServiceV2.send_v2_log(
            guild=guild,
            channel_key="message",
            event_key="pins_update",
            source_channel=channel,
            title="Channel Pins Updated",
            description=f"Pinned messages changed in {channel_label}.",
            color=0xFEE75C,
            fields=[{"name": "Latest Pin", "value": pin_time, "inline": True}],
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Logs message edits to 'message' channel."""
        if not before.guild or before.author.bot or before.content == after.content:
            return

        await LoggerServiceV2.send_v2_log(
            guild=before.guild,
            channel_key="message",
            event_key="message_edit",
            source_channel=before.channel,
            title="Message Edited",
            description=f"✏️ Message by {before.author.mention} edited in {before.channel.mention}. [Jump to Message]({after.jump_url})",
            color=0xFEE75C,
            user=before.author,
            fields=[
                {"name": "🔴 Before", "value": f"```{before.content[:500] or 'Empty'}```", "inline": False},
                {"name": "🟢 After", "value": f"```{after.content[:500] or 'Empty'}```", "inline": False}
            ]
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        """Logs member bans to 'ban' channel."""
        executor = await LoggerServiceV2.get_executor(guild, discord.AuditLogAction.ban, user.id)
        await LoggerServiceV2.send_v2_log(
            guild=guild,
            channel_key="ban",
            event_key="ban",
            moderation_action="ban",
            title="User Banned",
            description=f"🔨 **{user}** was banned from the server.",
            color=0x95A5A6,
            user=user,
            executor=executor,
            fields=[{"name": "User ID", "value": f"`{user.id}`", "inline": True}]
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Logs voice state changes to 'voice' channel."""
        if before.channel is None and after.channel is not None:
            await LoggerServiceV2.send_v2_log(
                guild=member.guild,
                channel_key="voice",
                event_key="voice_join",
                source_channel=after.channel,
                title="Voice Joined",
                description=f"🔊 {member.mention} joined {after.channel.mention}.",
                color=0x57F287,
                user=member
            )
        elif before.channel is not None and after.channel is None:
            await LoggerServiceV2.send_v2_log(
                guild=member.guild,
                channel_key="voice",
                event_key="voice_leave",
                source_channel=before.channel,
                title="Voice Left",
                description=f"🔇 {member.mention} left {before.channel.mention}.",
                color=0xED4245,
                user=member
            )
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            await LoggerServiceV2.send_v2_log(
                guild=member.guild,
                channel_key="voice",
                event_key="voice_move",
                source_channel=after.channel,
                title="Voice Moved",
                description=f"🔄 {member.mention} moved from {before.channel.mention} <a:arrow:1557834336571494480> {after.channel.mention}.",
                color=0x5865F2,
                user=member
            )

        source_voice_channel = after.channel or before.channel
        if before.mute != after.mute and source_voice_channel:
            executor = await LoggerServiceV2.get_executor(
                member.guild, discord.AuditLogAction.member_update, member.id
            )
            await LoggerServiceV2.send_v2_log(
                guild=member.guild,
                channel_key="voice",
                event_key="voice_mute",
                source_channel=source_voice_channel,
                title="Voice Server Mute Changed",
                description=f"🎙️ {member.mention} was {'server-muted' if after.mute else 'unmuted'} in {source_voice_channel.mention}.",
                color=0xED4245 if after.mute else 0x57F287,
                user=member,
                executor=executor,
            )
        if before.deaf != after.deaf and source_voice_channel:
            executor = await LoggerServiceV2.get_executor(
                member.guild, discord.AuditLogAction.member_update, member.id
            )
            await LoggerServiceV2.send_v2_log(
                guild=member.guild,
                channel_key="voice",
                event_key="voice_deafen",
                source_channel=source_voice_channel,
                title="Voice Server Deafen Changed",
                description=f"🎧 {member.mention} was {'server-deafened' if after.deaf else 'undeafened'} in {source_voice_channel.mention}.",
                color=0xED4245 if after.deaf else 0x57F287,
                user=member,
                executor=executor,
            )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Logs role creation to 'role' channel."""
        executor = await LoggerServiceV2.get_executor(role.guild, discord.AuditLogAction.role_create, role.id)
        await LoggerServiceV2.send_v2_log(
            guild=role.guild,
            channel_key="role",
            event_key="role_create",
            title="Role Created",
            description=f"🛠️ Role **{role.name}** (`{role.id}`) was created.",
            color=0x5865F2,
            executor=executor
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Logs role deletion to 'role' channel."""
        executor = await LoggerServiceV2.get_executor(role.guild, discord.AuditLogAction.role_delete, role.id)
        await LoggerServiceV2.send_v2_log(
            guild=role.guild,
            channel_key="role",
            event_key="role_delete",
            title="Role Deleted",
            description=f"🗑️ Role **{role.name}** (`{role.id}`) was deleted.",
            color=0xED4245,
            executor=executor
        )

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Logs role property edits using the dashboard's role-update route."""
        changes = []
        if before.name != after.name:
            changes.append(f"Name: `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"Color: `{before.color}` → `{after.color}`")
        if before.hoist != after.hoist:
            changes.append(f"Displayed separately: `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            changes.append(f"Mentionable: `{before.mentionable}` → `{after.mentionable}`")
        if before.permissions != after.permissions:
            changes.append("Permissions updated")
        if not changes:
            return
        executor = await LoggerServiceV2.get_executor(
            after.guild, discord.AuditLogAction.role_update, after.id
        )
        await LoggerServiceV2.send_v2_log(
            guild=after.guild,
            channel_key="role",
            event_key="role_update",
            title="Role Updated",
            description=f"🛠️ **{after.name}** was updated.\n" + "\n".join(changes),
            color=0x5865F2,
            executor=executor,
        )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Logs channel creation to 'channel' channel."""
        if not channel.guild:
            return
        executor = await LoggerServiceV2.get_executor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        await LoggerServiceV2.send_v2_log(
            guild=channel.guild,
            channel_key="channel",
            event_key="channel_create",
            source_channel=channel,
            title="Channel Created",
            description=f"📁 Channel **{channel.name}** (`{channel.id}`) was created.",
            color=0x5865F2,
            executor=executor
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Logs channel deletion to 'channel' channel."""
        if not channel.guild:
            return
        executor = await LoggerServiceV2.get_executor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        await LoggerServiceV2.send_v2_log(
            guild=channel.guild,
            channel_key="channel",
            event_key="channel_delete",
            source_channel=channel,
            title="Channel Deleted",
            description=f"🗑️ Channel **{channel.name}** (`{channel.id}`) was deleted.",
            color=0xED4245,
            executor=executor
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ):
        """Logs channel edits and permission overwrite changes separately."""
        guild = getattr(after, "guild", None)
        if not guild:
            return
        executor = await LoggerServiceV2.get_executor(
            guild, discord.AuditLogAction.channel_update, after.id
        )

        changes = []
        for attribute, label in (("name", "Name"), ("topic", "Topic"), ("slowmode_delay", "Slowmode")):
            old_value = getattr(before, attribute, None)
            new_value = getattr(after, attribute, None)
            if old_value != new_value:
                changes.append(f"{label}: `{old_value or 'None'}` → `{new_value or 'None'}`")
        if changes:
            await LoggerServiceV2.send_v2_log(
                guild=guild,
                channel_key="channel",
                event_key="channel_update",
                source_channel=after,
                title="Channel Updated",
                description=f"📁 **{after.name}** was updated.\n" + "\n".join(changes),
                color=0x5865F2,
                executor=executor,
            )

        old_overwrites = {
            target.id: (target, overwrite)
            for target, overwrite in getattr(before, "overwrites", {}).items()
        }
        new_overwrites = {
            target.id: (target, overwrite)
            for target, overwrite in getattr(after, "overwrites", {}).items()
        }
        added_ids = new_overwrites.keys() - old_overwrites.keys()
        removed_ids = old_overwrites.keys() - new_overwrites.keys()
        changed_ids = {
            target_id
            for target_id in old_overwrites.keys() & new_overwrites.keys()
            if old_overwrites[target_id][1] != new_overwrites[target_id][1]
        }
        permission_event = (
            "channel_perm_create" if added_ids else
            "channel_perm_delete" if removed_ids else
            "channel_perm_update" if changed_ids else None
        )
        if permission_event:
            changed_target_ids = added_ids or removed_ids or changed_ids
            changed_targets = []
            for target_id in changed_target_ids:
                target = (new_overwrites.get(target_id) or old_overwrites[target_id])[0]
                changed_targets.append(getattr(target, "mention", str(target)))
            channel_name = getattr(after, "mention", f"#{after.name}")
            await LoggerServiceV2.send_v2_log(
                guild=guild,
                channel_key="channel",
                event_key=permission_event,
                source_channel=after,
                title="Channel Permissions Updated",
                description=f"🔐 Permissions changed in {channel_name}: {', '.join(changed_targets)}",
                color=0xFEE75C,
                executor=executor,
            )


    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User | discord.Member):
        """Logs member unbans to 'ban' channel."""
        executor = await LoggerServiceV2.get_executor(guild, discord.AuditLogAction.unban, user.id)
        await LoggerServiceV2.send_v2_log(
            guild=guild,
            channel_key="ban",
            event_key="unban",
            moderation_action="unban",
            title="User Unbanned",
            description=f"🔓 **{user}** was unbanned from the server.",
            color=0x57F287,
            user=user,
            executor=executor,
            fields=[{"name": "User ID", "value": f"`{user.id}`", "inline": True}]
        )

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Logs server property updates to 'server' channel."""
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` <a:arrow:1557834336571494480> `{after.name}`")
        if before.icon != after.icon:
            changes.append("**Icon:** Updated server icon")
        if before.description != after.description:
            changes.append("**Description:** Updated server description")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification:** `{before.verification_level}` <a:arrow:1557834336571494480> `{after.verification_level}`")
        if before.premium_tier != after.premium_tier:
            changes.append(f"**Boost Level:** `Level {before.premium_tier}` <a:arrow:1557834336571494480> `Level {after.premium_tier}`")
            await LoggerServiceV2.send_v2_log(
                guild=after,
                channel_key="boost",
                title="Server Boost Tier Changed! 🚀",
                description=f"🎉 **{after.name}** reached **Level {after.premium_tier}** (previously Level {before.premium_tier})!",
                color=0xF47FFF,
                fields=[
                    {"name": "Total Boosts", "value": f"`{after.premium_subscription_count}`", "inline": True}
                ]
            )
        if not changes:
            return

        executor = await LoggerServiceV2.get_executor(after, discord.AuditLogAction.guild_update)
        await LoggerServiceV2.send_v2_log(
            guild=after,
            channel_key="server",
            event_key="server_update",
            title="Server Updated",
            description="\n".join(changes),
            color=0x5865F2,
            executor=executor
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Logs member nickname, role, and server boost changes to 'member' & 'boost' channels."""
        guild = after.guild

        if before.is_timed_out() != after.is_timed_out():
            is_timed_out = after.is_timed_out()
            executor = await LoggerServiceV2.get_executor(
                guild, discord.AuditLogAction.member_update, after.id
            )
            timeout_end = getattr(after, "timed_out_until", None)
            description = (
                f"⏳ {after.mention} was timed out until <t:{int(timeout_end.timestamp())}:F>."
                if is_timed_out and timeout_end
                else f"✅ Timeout removed for {after.mention}."
            )
            await LoggerServiceV2.send_v2_log(
                guild=guild,
                channel_key="mod",
                event_key="timeout",
                moderation_action="timeout" if is_timed_out else "untimeout",
                title="Member Timed Out" if is_timed_out else "Member Timeout Removed",
                description=description,
                color=0xED4245 if is_timed_out else 0x57F287,
                user=after,
                executor=executor,
            )

        # Server Boost Start / Stop Event
        if before.premium_since is None and after.premium_since is not None:
            boost_count = getattr(guild, "premium_subscription_count", 0)
            tier = getattr(guild, "premium_tier", 0)
            await LoggerServiceV2.send_v2_log(
                guild=guild,
                channel_key="boost",
                title="Server Boosted! 🚀",
                description=f"🎉 {after.mention} **({after})** just boosted the server!",
                color=0xF47FFF,
                user=after,
                fields=[
                    {"name": "Total Boosts", "value": f"`{boost_count}`", "inline": True},
                    {"name": "Server Tier", "value": f"`Level {tier}`", "inline": True}
                ]
            )
        elif before.premium_since is not None and after.premium_since is None:
            boost_count = getattr(guild, "premium_subscription_count", 0)
            tier = getattr(guild, "premium_tier", 0)
            await LoggerServiceV2.send_v2_log(
                guild=guild,
                channel_key="boost",
                title="Server Boost Removed",
                description=f"💔 {after.mention} **({after})** stopped boosting the server.",
                color=0xED4245,
                user=after,
                fields=[
                    {"name": "Total Boosts Remaining", "value": f"`{boost_count}`", "inline": True},
                    {"name": "Server Tier", "value": f"`Level {tier}`", "inline": True}
                ]
            )

        if before.nick != after.nick:
            old_nick = before.nick or before.name
            new_nick = after.nick or after.name
            await LoggerServiceV2.send_v2_log(
                guild=guild,
                channel_key="member",
                event_key="nick_change",
                title="Nickname Changed",
                description=f"✏️ {after.mention} **({after})** changed nickname.",
                color=0xFEE75C,
                user=after,
                fields=[
                    {"name": "Before", "value": f"`{old_nick}`", "inline": True},
                    {"name": "After", "value": f"`{new_nick}`", "inline": True}
                ]
            )

        if before.roles != after.roles:
            added_roles = [r for r in after.roles if r not in before.roles]
            removed_roles = [r for r in before.roles if r not in after.roles]
            if added_roles or removed_roles:
                executor = await LoggerServiceV2.get_executor(guild, discord.AuditLogAction.member_role_update, after.id)
                if added_roles:
                    await LoggerServiceV2.send_v2_log(
                        guild=guild,
                        channel_key="role",
                        event_key="role_given",
                        title="Member Roles Added",
                        description=f"🟢 Roles given to {after.mention} **({after})**: {', '.join(r.mention for r in added_roles)}",
                        color=0x57F287,
                        user=after,
                        executor=executor,
                    )
                if removed_roles:
                    await LoggerServiceV2.send_v2_log(
                        guild=guild,
                        channel_key="role",
                        event_key="role_removed",
                        title="Member Roles Removed",
                        description=f"🔴 Roles removed from {after.mention} **({after})**: {', '.join(r.mention for r in removed_roles)}",
                        color=0xED4245,
                        user=after,
                        executor=executor,
                    )

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Logs invite creation to 'invite' channel."""
        if not invite.guild:
            return
        await LoggerServiceV2.send_v2_log(
            guild=invite.guild,
            channel_key="invite",
            event_key="invite_create",
            source_channel=invite.channel,
            title="Invite Created",
            description=f"📨 Invite `{invite.code}` created by {invite.inviter.mention if invite.inviter else 'Unknown'}.",
            color=0x57F287,
            user=invite.inviter,
            fields=[
                {"name": "Channel", "value": invite.channel.mention if invite.channel else "Unknown", "inline": True},
                {"name": "Max Uses", "value": f"`{invite.max_uses or 'Unlimited'}`", "inline": True}
            ]
        )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Logs invite deletion to 'invite' channel."""
        if not invite.guild:
            return
        await LoggerServiceV2.send_v2_log(
            guild=invite.guild,
            channel_key="invite",
            event_key="invite_delete",
            source_channel=invite.channel,
            title="Invite Deleted",
            description=f"🗑️ Invite `{invite.code}` was deleted or expired.",
            color=0xED4245,
            fields=[
                {"name": "Channel", "value": invite.channel.mention if invite.channel else "Unknown", "inline": True}
            ]
        )

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent):
        executor = await LoggerServiceV2.get_executor(event.guild, discord.AuditLogAction.scheduled_event_create, event.id)
        await LoggerServiceV2.send_v2_log(
            guild=event.guild,
            channel_key="server",
            event_key="event_create",
            title="Server Event Created",
            description=f"Scheduled event **{event.name}** was created.",
            color=0x57F287,
            executor=executor,
            fields=[
                {"name": "Starts", "value": event.start_time.strftime("%Y-%m-%d %H:%M UTC") if event.start_time else "Not set", "inline": True},
                {"name": "Event ID", "value": str(event.id), "inline": True},
            ],
        )

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        changes = []
        for attribute, label in (("name", "Name"), ("description", "Description"), ("start_time", "Start time"), ("end_time", "End time"), ("status", "Status"), ("location", "Location")):
            old = getattr(before, attribute, None)
            new = getattr(after, attribute, None)
            old_value = str(old) if old is not None else "None"
            new_value = str(new) if new is not None else "None"
            if old_value != new_value:
                changes.append(f"{label}: `{old_value}` → `{new_value}`")
        if not changes:
            return
        executor = await LoggerServiceV2.get_executor(after.guild, discord.AuditLogAction.scheduled_event_update, after.id)
        await LoggerServiceV2.send_v2_log(
            guild=after.guild,
            channel_key="server",
            event_key="event_update",
            title="Server Event Updated",
            description=f"Scheduled event **{after.name}** was updated.\n" + "\n".join(changes),
            color=0x5865F2,
            executor=executor,
        )

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        executor = await LoggerServiceV2.get_executor(event.guild, discord.AuditLogAction.scheduled_event_delete, event.id)
        await LoggerServiceV2.send_v2_log(
            guild=event.guild,
            channel_key="server",
            event_key="event_delete",
            title="Server Event Deleted",
            description=f"Scheduled event **{event.name}** was deleted.",
            color=0xED4245,
            executor=executor,
            fields=[{"name": "Event ID", "value": str(event.id), "inline": True}],
        )

    @commands.Cog.listener()
    async def on_raw_app_command_permissions_update(self, payload: discord.RawAppCommandPermissionsUpdateEvent):
        permission_count = len(getattr(payload, "permissions", []) or [])
        await LoggerServiceV2.send_v2_log(
            guild=payload.guild,
            channel_key="server",
            event_key="cmd_perms",
            title="Application Command Permissions Updated",
            description="Application command access rules were updated. Discord does not include the executor in this gateway event.",
            color=0xFEE75C,
            fields=[
                {"name": "Command / Application ID", "value": str(payload.target_id), "inline": True},
                {"name": "Application ID", "value": str(payload.application_id), "inline": True},
                {"name": "Permission entries", "value": str(permission_count), "inline": True},
            ],
        )

    @commands.Cog.listener()
    async def on_automod_rule_create(self, rule: discord.AutoModRule):
        await self._log_automod_rule(rule, "automod_rule_create", "AutoMod Rule Created", discord.AuditLogAction.automod_rule_create)

    @commands.Cog.listener()
    async def on_automod_rule_update(self, rule: discord.AutoModRule):
        await self._log_automod_rule(rule, "automod_rule_update", "AutoMod Rule Updated", discord.AuditLogAction.automod_rule_update)

    @commands.Cog.listener()
    async def on_automod_rule_delete(self, rule: discord.AutoModRule):
        await self._log_automod_rule(rule, "automod_rule_delete", "AutoMod Rule Deleted", discord.AuditLogAction.automod_rule_delete)

    async def _log_automod_rule(self, rule: discord.AutoModRule, event_key: str, title: str, audit_action: discord.AuditLogAction):
        executor = await LoggerServiceV2.get_executor(rule.guild, audit_action, rule.id)
        action_types = [getattr(getattr(action, "type", None), "name", str(getattr(action, "type", "unknown"))) for action in (rule.actions or [])]
        await LoggerServiceV2.send_v2_log(
            guild=rule.guild,
            channel_key="automod",
            event_key=event_key,
            title=title,
            description=f"AutoMod rule **{rule.name}** was {event_key.rsplit('_', 1)[-1]}.",
            color=0xFEE75C if event_key.endswith("update") else (0xED4245 if event_key.endswith("delete") else 0x57F287),
            executor=executor,
            fields=[
                {"name": "Rule ID", "value": str(rule.id), "inline": True},
                {"name": "Actions", "value": ", ".join(action_types)[:1000] or "None", "inline": True},
            ],
        )

    @commands.Cog.listener()
    async def on_automod_action(self, action: discord.AutoModAction):
        guild = action.guild
        member = action.member
        channel = action.channel
        action_type = getattr(getattr(action.action, "type", None), "name", "")
        event_key = {
            "timeout": "automod_timeout",
            "send_alert_message": "automod_flag",
            "block_message": "automod_block",
            "block_member_interactions": "automod_block",
        }.get(action_type, "automod_flag")
        details = [f"Rule ID: `{action.rule_id}`", f"Action: `{action_type or 'unknown'}`"]
        if channel:
            details.append(f"Channel: {channel.mention}")
        matched = getattr(action, "matched_keyword", None)
        if matched:
            details.append(f"Matched keyword: `{str(matched)[:200]}`")
        member_label = member.mention if member else f"user {action.user_id}"
        await LoggerServiceV2.send_v2_log(
            guild=guild,
            channel_key="automod",
            event_key=event_key,
            title="AutoMod Action Triggered",
            description=f"AutoMod acted on {member_label}.\n" + "\n".join(details),
            color=0xED4245 if event_key in {"automod_block", "automod_timeout"} else 0xFEE75C,
            user=member,
            source_channel=channel,
            fields=[{"name": "Rule ID", "value": str(action.rule_id), "inline": True}],
        )


async def setup(bot: commands.Bot):
    try:
        from services.whitelist_panel import WhitelistPanelV2View, WhitelistNoticeV2View
        bot.add_view(WhitelistPanelV2View())
        bot.add_view(WhitelistNoticeV2View())
    except Exception as e:
        print(f"[Logs Setup] Failed to register whitelist persistent views: {e}")
    await bot.add_cog(ServerLogs(bot))
