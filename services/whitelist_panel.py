"""
Yuna Whitelist Interactive Control Panel & Dispatcher Service - Components V2
Provides native Discord Components V2 (ui.LayoutView, ui.Container, ui.TextDisplay, ui.ActionRow)
for the persistent interactive Whitelist Control Panel in the ․yuna․whitelist․ channel.

Automatically sent during /logs setup, dynamically edited upon any whitelist change,
and dispatches real-time audit log messages.
"""

from __future__ import annotations
import os
import re
import time
import json
import asyncio
import datetime
import unicodedata
from typing import Optional, Dict, Any, List, Union

import discord
from discord import ui
from discord.ext import commands
import aiosqlite

from services.logger_v2 import LoggerServiceV2
from core.cache.security_cache import security_cache

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_AUDIT_PATH = os.path.join(_BASE_DIR, "db", "audit_logs.db") if os.path.exists(os.path.join(_BASE_DIR, "db")) else "db/audit_logs.db"
DB_ANTI_PATH = os.path.join(_BASE_DIR, "db", "anti.db") if os.path.exists(os.path.join(_BASE_DIR, "db")) else "db/anti.db"
PANEL_ACCENT_COLOR = 0x5865F2  # Blurple modern accent


class WhitelistPanelService:
    """Central service managing the Components V2 live interactive whitelist panel."""

    @classmethod
    async def init_db(cls):
        """Ensures whitelist_panel_config table exists in db/audit_logs.db."""
        os.makedirs("db", exist_ok=True)
        async with aiosqlite.connect(DB_AUDIT_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelist_panel_config (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    message_id INTEGER,
                    updated_at TEXT
                )
            """)
            await db.commit()

    @classmethod
    async def fetch_whitelist_data(cls, guild: discord.Guild) -> Dict[str, Any]:
        """Fetches all whitelisted users, bots, roles, and extra owners for the guild."""
        users: List[int] = []
        bots: List[int] = []
        roles: List[int] = []
        extra_owner_id = None

        try:
            if os.path.exists(DB_ANTI_PATH):
                async with aiosqlite.connect(DB_ANTI_PATH, timeout=10.0) as db:
                    # 1. Whitelisted Users
                    try:
                        async with db.execute(
                            "SELECT user_id FROM whitelisted_users WHERE guild_id = ?",
                            (guild.id,)
                        ) as cursor:
                            users = [r[0] for r in await cursor.fetchall() if r[0]]
                    except Exception:
                        users = []

                    # 2. Whitelisted Bots
                    try:
                        async with db.execute(
                            "SELECT bot_id FROM whitelisted_bots WHERE guild_id = ?",
                            (guild.id,)
                        ) as cursor:
                            bots = [r[0] for r in await cursor.fetchall() if r[0]]
                    except Exception:
                        bots = []

                    # 3. Whitelisted Roles
                    try:
                        async with db.execute(
                            "SELECT role_id FROM whitelisted_roles WHERE guild_id = ?",
                            (guild.id,)
                        ) as cursor:
                            roles = [r[0] for r in await cursor.fetchall() if r[0]]
                    except Exception:
                        roles = []

                    # 4. Extra Owner
                    try:
                        async with db.execute(
                            "SELECT owner_id FROM extraowners WHERE guild_id = ?",
                            (guild.id,)
                        ) as cursor:
                            row = await cursor.fetchone()
                            if row:
                                extra_owner_id = row[0]
                    except Exception:
                        pass
        except Exception:
            pass

        if not extra_owner_id:
            try:
                extra_owner_id = security_cache.get_extra_owner(guild.id)
            except Exception:
                pass

        return {
            "users": users,
            "bots": bots,
            "roles": roles,
            "extra_owner_id": extra_owner_id
        }

    @classmethod
    async def get_whitelist_channel(cls, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Locates the dedicated ﹒yuna﹒whitelist﹒ channel in the guild."""
        for ch in guild.text_channels:
            norm = unicodedata.normalize('NFKD', ch.name).lower()
            if "whitelist" in norm and ("yuna" in norm or (ch.category and "logs" in ch.category.name.lower())):
                return ch
        # Fallback to any text channel with whitelist in name
        for ch in guild.text_channels:
            norm = unicodedata.normalize('NFKD', ch.name).lower()
            if "whitelist" in norm:
                return ch
        return None

    @classmethod
    async def setup_panel(cls, guild: discord.Guild, channel: Optional[discord.TextChannel] = None) -> Optional[discord.Message]:
        """
        Ensures the live Components V2 interactive whitelist panel is posted and tracked in ﹒yuna﹒whitelist﹒ channel.
        Edits existing panel if present, or creates a clean new one.
        """
        if not guild:
            return None

        await cls.init_db()

        target_channel = channel
        if not target_channel:
            try:
                async with aiosqlite.connect(DB_AUDIT_PATH, timeout=10.0) as db:
                    async with db.execute(
                        "SELECT channel_id FROM whitelist_panel_config WHERE guild_id = ?",
                        (guild.id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row and row[0]:
                            target_channel = guild.get_channel(row[0])
            except Exception:
                pass

        if not target_channel:
            target_channel = await cls.get_whitelist_channel(guild)

        if not target_channel:
            return None

        data = await cls.fetch_whitelist_data(guild)
        view = WhitelistPanelV2View(guild=guild, data=data)

        existing_msg = None
        async with aiosqlite.connect(DB_AUDIT_PATH, timeout=10.0) as db:
            async with db.execute(
                "SELECT message_id FROM whitelist_panel_config WHERE guild_id = ? AND channel_id = ?",
                (guild.id, target_channel.id)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    try:
                        existing_msg = await target_channel.fetch_message(row[0])
                    except Exception:
                        existing_msg = None

        client = getattr(guild, "_state", None)
        bot_client = client._get_client() if client and hasattr(client, "_get_client") else None

        if existing_msg:
            try:
                await existing_msg.edit(view=view)
                if bot_client:
                    bot_client.add_view(view, message_id=existing_msg.id)
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                async with aiosqlite.connect(DB_AUDIT_PATH, timeout=10.0) as db:
                    await db.execute("""
                        INSERT OR REPLACE INTO whitelist_panel_config (guild_id, channel_id, message_id, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (guild.id, target_channel.id, existing_msg.id, now_iso))
                    await db.commit()
                return existing_msg
            except Exception:
                existing_msg = None

        # Look in channel history if there's already a panel message sent by bot
        if not existing_msg:
            try:
                bot_id = guild.me.id if guild.me else None
                async for m in target_channel.history(limit=10):
                    if bot_id and m.author.id == bot_id and m.components:
                        found_wl = False
                        for c in m.components:
                            children = getattr(c, "children", [])
                            if any(getattr(ch, "custom_id", None) in ("wl_v2_add_user", "wl_v2_refresh") for ch in children):
                                found_wl = True
                                break
                        if found_wl:
                            existing_msg = m
                            break
                if existing_msg:
                    await existing_msg.edit(view=view)
                    if bot_client:
                        bot_client.add_view(view, message_id=existing_msg.id)
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    async with aiosqlite.connect(DB_AUDIT_PATH, timeout=10.0) as db:
                        await db.execute("""
                            INSERT OR REPLACE INTO whitelist_panel_config (guild_id, channel_id, message_id, updated_at)
                            VALUES (?, ?, ?, ?)
                        """, (guild.id, target_channel.id, existing_msg.id, now_iso))
                        await db.commit()
                    return existing_msg
            except Exception:
                pass

        # Post fresh V2 panel
        try:
            new_msg = await target_channel.send(view=view)
            if bot_client:
                bot_client.add_view(view, message_id=new_msg.id)
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            async with aiosqlite.connect(DB_AUDIT_PATH, timeout=10.0) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO whitelist_panel_config (guild_id, channel_id, message_id, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (guild.id, target_channel.id, new_msg.id, now_iso))
                await db.commit()
            return new_msg
        except Exception as e:
            print(f"[WhitelistPanelService] Failed to send V2 panel in {target_channel.name}: {e}")
            return None

    @classmethod
    async def reconnect_all_panels(cls, bot: discord.Client):
        """
        Runs on bot startup/restart (on_ready).
        1. Globally registers persistent WhitelistPanelV2View with bot.add_view(WhitelistPanelV2View()).
        2. Iterates over all configured panels in whitelist_panel_config.
        3. For each guild, fetches the channel and message, binds the view with message_id tracking,
           and updates the panel content so it reflects live data.
        4. For any connected guild that has a whitelist log channel, ensures its panel is connected.
        """
        await cls.init_db()

        # 1. Register persistent view globally so all buttons route correctly
        try:
            bot.add_view(WhitelistPanelV2View())
        except Exception as e:
            print(f"[WhitelistPanelService] Global view registration warning: {e}", flush=True)

        # 2. Reconnect all saved panels from database
        reconnected_count = 0
        handled_guilds = set()
        try:
            async with aiosqlite.connect(DB_AUDIT_PATH, timeout=15.0) as db:
                async with db.execute(
                    "SELECT guild_id, channel_id, message_id FROM whitelist_panel_config"
                ) as cursor:
                    rows = await cursor.fetchall()

            for guild_id, channel_id, message_id in rows:
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue

                handled_guilds.add(guild.id)
                channel = guild.get_channel(channel_id)
                if not channel:
                    continue

                try:
                    data = await cls.fetch_whitelist_data(guild)
                    view = WhitelistPanelV2View(guild=guild, data=data)
                    bot.add_view(view, message_id=message_id)

                    try:
                        msg = await channel.fetch_message(message_id)
                        if msg:
                            await msg.edit(view=view)
                            reconnected_count += 1
                    except discord.NotFound:
                        # Message was deleted while bot was offline - recreate it
                        new_msg = await cls.setup_panel(guild, channel)
                        if new_msg:
                            reconnected_count += 1
                except Exception as g_err:
                    print(f"[WhitelistPanelService] Error reconnecting guild '{guild.name}' ({guild.id}): {g_err}", flush=True)

        except Exception as db_err:
            print(f"[WhitelistPanelService] Reconnect database scan error: {db_err}", flush=True)

        # 3. Check any connected guilds that have a dedicated whitelist channel but missing from config
        for guild in bot.guilds:
            if guild.id in handled_guilds:
                continue
            wl_channel = await cls.get_whitelist_channel(guild)
            if wl_channel:
                try:
                    pnl_msg = await cls.setup_panel(guild, wl_channel)
                    if pnl_msg:
                        reconnected_count += 1
                except Exception:
                    pass

        print(f"[WHITELIST UI] Reconnected & synced Whitelist UI panels for {reconnected_count} guild(s).", flush=True)

    @classmethod
    async def on_whitelist_update(
        cls,
        guild: discord.Guild,
        action_type: str,
        target: Any,
        author: Any,
        details: Optional[str] = None
    ):
        """
        Core update hook:
        1. Re-renders & EDITS the persistent Components V2 panel in ․yuna․whitelist․
        2. SENDS a rich notification log to the channel (and via webhook).
        """
        if not guild:
            return

        # 1. Update/Edit the persistent UI panel with Components V2
        try:
            await cls.setup_panel(guild)
        except Exception as e:
            print(f"[WhitelistPanelService] V2 Panel refresh error: {e}")

        # 2. Send the real-time event log
        try:
            is_added = "add" in action_type.lower() or "trusted" in action_type.lower()
            embed_color = 0x57F287 if is_added else 0xED4245
            tick = "<a:tick:1558726958802800660>"

            target_mention = getattr(target, "mention", f"`{getattr(target, 'id', target)}`")
            target_id = getattr(target, "id", "N/A")
            target_name = getattr(target, "name", str(target))
            author_mention = getattr(author, "mention", f"`{getattr(author, 'id', author)}`")

            log_embed = discord.Embed(
                title=f"{tick} Whitelist Event: {action_type}",
                description=f"A change has been recorded in the server's Anti-Nuke whitelist.",
                color=embed_color,
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Target Entity", value=f"{target_mention} (`{target_name}` - `{target_id}`)", inline=False)
            log_embed.add_field(name="Authorized By", value=f"{author_mention}", inline=True)
            if details:
                log_embed.add_field(name="Details", value=f"`{details}`", inline=True)

            bot_icon = getattr(getattr(guild.me, "display_avatar", None), "url", None) if guild.me else None
            log_embed.set_footer(text=f"Guild ID: {guild.id} • Whitelist Audit", icon_url=bot_icon)

            await LoggerServiceV2.send_v2_log(
                guild=guild,
                channel_key="whitelist",
                embed=log_embed
            )
        except Exception as log_err:
            print(f"[WhitelistPanelService] Log dispatch error: {log_err}")


# =============================================================================
# COMPONENTS V2 PERSISTENT WHITELIST CONTROL PANEL VIEW
# =============================================================================

class WhitelistPanelV2View(ui.LayoutView):
    """
    Native Components V2 LayoutView for the persistent interactive Whitelist Control Panel.
    Uses ui.Container, ui.TextDisplay, ui.Separator, and ui.ActionRow.
    """

    def __init__(self, guild: Optional[discord.Guild] = None, data: Optional[Dict[str, Any]] = None):
        super().__init__(timeout=None)
        self.guild = guild
        self.data = data
        self.build_panel()

    def build_panel(self):
        """Builds or rebuilds the Components V2 container and layout elements."""
        self.clear_items()
        container = ui.Container(accent_color=PANEL_ACCENT_COLOR)

        guild_name = self.guild.name if self.guild else "Discord Server"
        guild_id = self.guild.id if self.guild else 0
        owner_id = self.guild.owner_id if self.guild else 0

        wh_channel_name = "whitelist-logs"
        if self.guild:
            cfg = LoggerServiceV2._guild_config_cache.get(self.guild.id, {})
            wh_entry = cfg.get("whitelist", {})
            if wh_entry.get("channel_id"):
                ch = self.guild.get_channel(int(wh_entry["channel_id"]))
                if ch:
                    wh_channel_name = ch.name
                else:
                    wh_channel_name = wh_entry.get("channel_name", "whitelist-logs")
            elif wh_entry.get("channel_name"):
                wh_channel_name = wh_entry.get("channel_name")

        # Header Title (Components V2 TextDisplay)
        header = ui.TextDisplay(
            f"## Anti-Nuke Whitelist Control Hub\n"
            f"**Server:** `{guild_name}` • **Channel:** `#{wh_channel_name}`"
        )
        container.add_item(header)
        container.add_item(ui.Separator())

        # Description
        description = ui.TextDisplay(
            "> **Whitelisted accounts & staff roles bypass all Yuna Anti-Nuke protections.**\n"
            "> Trusted staff and security bots can perform moderation without trigger reversion.\n\n"
            "*Click the interactive buttons below to manage trusted users, security bots, and roles.*"
        )
        container.add_item(description)
        container.add_item(ui.Separator())

        # Whitelist Data Lists
        users = self.data.get("users", []) if self.data else []
        bots = self.data.get("bots", []) if self.data else []
        roles = self.data.get("roles", []) if self.data else []
        extra_owner_id = self.data.get("extra_owner_id") if self.data else None

        owner_str = f"<@{owner_id}>" if owner_id else "N/A"
        extra_str = f"<@{extra_owner_id}>" if extra_owner_id else "*None Configured*"

        users_formatted = ", ".join(f"<@{u}>" for u in users[:15]) if users else "*No users whitelisted*"
        if len(users) > 15:
            users_formatted += f" *(+{len(users)-15} more)*"

        bots_formatted = ", ".join(f"<@{b}>" for b in bots[:15]) if bots else "*No security bots whitelisted*"
        if len(bots) > 15:
            bots_formatted += f" *(+{len(bots)-15} more)*"

        roles_formatted = ", ".join(f"<@&{r}>" for r in roles[:15]) if roles else "*No staff roles whitelisted*"
        if len(roles) > 15:
            roles_formatted += f" *(+{len(roles)-15} more)*"

        status_text = (
            f"### Server Immunity Hierarchy\n"
            f"• **Server Owner:** {owner_str} *(Permanent Global Bypass)*\n"
            f"• **Extra Owner:** {extra_str} *(Full Bypass)*\n\n"
            f"### Whitelisted Staff Users ({len(users)})\n"
            f"{users_formatted}\n\n"
            f"### Whitelisted Security Bots ({len(bots)})\n"
            f"{bots_formatted}\n\n"
            f"### Whitelisted Staff Roles ({len(roles)})\n"
            f"{roles_formatted}"
        )
        container.add_item(ui.TextDisplay(status_text))
        container.add_item(ui.Separator())

        # Section Header for Controls
        container.add_item(ui.TextDisplay("### Quick Interactive Controls"))

        # ROW 0: Add Options (Components V2 ActionRow)
        r0 = ui.ActionRow()
        b_add_user = ui.Button(label="Whitelist User", style=discord.ButtonStyle.success, custom_id="wl_v2_add_user")
        b_add_user.callback = self.add_user_callback
        r0.add_item(b_add_user)

        b_add_bot = ui.Button(label="Whitelist Bot", style=discord.ButtonStyle.primary, custom_id="wl_v2_add_bot")
        b_add_bot.callback = self.add_bot_callback
        r0.add_item(b_add_bot)

        b_add_role = ui.Button(label="Whitelist Role", style=discord.ButtonStyle.primary, custom_id="wl_v2_add_role")
        b_add_role.callback = self.add_role_callback
        r0.add_item(b_add_role)
        container.add_item(r0)

        # ROW 1: Manage & Remove (Components V2 ActionRow)
        r1 = ui.ActionRow()
        b_remove = ui.Button(label="Remove Entry", style=discord.ButtonStyle.danger, custom_id="wl_v2_remove")
        b_remove.callback = self.remove_callback
        r1.add_item(b_remove)

        b_refresh = ui.Button(label="Refresh Panel", style=discord.ButtonStyle.secondary, custom_id="wl_v2_refresh")
        b_refresh.callback = self.refresh_callback
        r1.add_item(b_refresh)
        container.add_item(r1)

        container.add_item(ui.Separator())

        # Footer (Components V2 TextDisplay)
        now_ts = int(time.time())
        footer = ui.TextDisplay(f"-# YUNA • Components V2 Whitelist Hub • Updated <t:{now_ts}:R>")
        container.add_item(footer)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        guild = interaction.guild
        if not guild:
            return False

        user = interaction.user
        is_owner = user.id == guild.owner_id
        is_extra = security_cache.is_extra_owner(guild.id, user.id)
        is_admin = getattr(getattr(user, "guild_permissions", None), "administrator", False)

        if not (is_owner or is_extra or is_admin):
            await interaction.response.send_message("Only Server Owner, Extra Owner, or Administrators can manage the Whitelist.", ephemeral=True)
            return False
        return True

    async def add_user_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddUserModalV2())

    async def add_bot_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddBotModalV2())

    async def add_role_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Select a staff role to whitelist:", view=SelectRoleViewV2(), ephemeral=True)

    async def remove_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        data = await WhitelistPanelService.fetch_whitelist_data(guild)

        options: List[discord.SelectOption] = []

        # Users
        for u_id in data["users"][:8]:
            u = guild.get_member(u_id) or interaction.client.get_user(u_id)
            name = u.name if u else f"User {u_id}"
            options.append(discord.SelectOption(label=f"User: {name[:25]}", value=f"user:{u_id}", description=f"ID: {u_id}"))

        # Bots
        for b_id in data["bots"][:8]:
            b = guild.get_member(b_id) or interaction.client.get_user(b_id)
            name = b.name if b else f"Bot {b_id}"
            options.append(discord.SelectOption(label=f"Bot: {name[:25]}", value=f"bot:{b_id}", description=f"ID: {b_id}"))

        # Roles
        for r_id in data["roles"][:8]:
            r = guild.get_role(r_id)
            name = r.name if r else f"Role {r_id}"
            options.append(discord.SelectOption(label=f"Role: {name[:25]}", value=f"role:{r_id}", description=f"ID: {r_id}"))

        if not options:
            return await interaction.response.send_message("There are currently no whitelisted users, bots, or roles to remove.", ephemeral=True)

        await interaction.response.send_message("Choose which entry to remove from the whitelist:", view=RemoveEntryViewV2(options), ephemeral=True)

    async def refresh_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        await WhitelistPanelService.setup_panel(guild)
        await interaction.response.send_message("<a:tick:1558726958802800660> Whitelist panel refreshed to latest state.", ephemeral=True)


# =============================================================================
# MODALS & SELECT VIEWS FOR COMPONENTS V2 INTERACTION
# =============================================================================

class AddUserModalV2(ui.Modal, title="Whitelist Staff User"):
    user_input = ui.TextInput(
        label="User Mention or User ID",
        placeholder="e.g. @Moderator or 123456789012345678",
        min_length=3,
        max_length=40,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return

        raw = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        member = None
        if raw.isdigit():
            member = guild.get_member(int(raw))
            if not member:
                try:
                    member = await guild.fetch_member(int(raw))
                except Exception:
                    pass
        if not member:
            member = discord.utils.find(lambda m: m.name.lower() == raw.lower() or m.display_name.lower() == raw.lower(), guild.members)

        if not member:
            return await interaction.response.send_message("❌ Member not found in this server. Please enter a valid User ID or @Mention.", ephemeral=True)

        if member.bot:
            return await interaction.response.send_message("❌ This account is a bot. Please use the **Whitelist Bot** button instead.", ephemeral=True)

        # Insert into DB
        async with aiosqlite.connect(DB_ANTI_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelisted_users (
                    guild_id INTEGER, user_id INTEGER,
                    ban BOOLEAN DEFAULT 1, kick BOOLEAN DEFAULT 1, prune BOOLEAN DEFAULT 1,
                    botadd BOOLEAN DEFAULT 1, serverup BOOLEAN DEFAULT 1, memup BOOLEAN DEFAULT 1,
                    chcr BOOLEAN DEFAULT 1, chdl BOOLEAN DEFAULT 1, chup BOOLEAN DEFAULT 1,
                    rlcr BOOLEAN DEFAULT 1, rldl BOOLEAN DEFAULT 1, rlup BOOLEAN DEFAULT 1,
                    meneve BOOLEAN DEFAULT 1, mngweb BOOLEAN DEFAULT 1, mngstemo BOOLEAN DEFAULT 1,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute("""
                INSERT OR REPLACE INTO whitelisted_users 
                (guild_id, user_id, ban, kick, prune, botadd, serverup, memup, chcr, chdl, chup, rlcr, rldl, rlup, meneve, mngweb, mngstemo)
                VALUES (?, ?, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
            """, (guild.id, member.id))
            await db.commit()

        security_cache.invalidate_guild(guild.id)
        await interaction.response.send_message(f"<a:tick:1558726958802800660> {member.mention} has been **whitelisted** with full Anti-Nuke immunity!", ephemeral=True)

        # Trigger V2 panel update & notification log
        await WhitelistPanelService.on_whitelist_update(guild, "Staff User Whitelisted", member, interaction.user)


class AddBotModalV2(ui.Modal, title="Whitelist Trusted Security Bot"):
    bot_input = ui.TextInput(
        label="Bot ID or Bot Mention",
        placeholder="e.g. @Wick or 123456789012345678",
        min_length=3,
        max_length=40,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return

        raw = self.bot_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        bot_user = None
        if raw.isdigit():
            bot_user = guild.get_member(int(raw)) or interaction.client.get_user(int(raw))
            if not bot_user:
                try:
                    bot_user = await interaction.client.fetch_user(int(raw))
                except Exception:
                    pass

        if not bot_user:
            bot_user = discord.utils.find(lambda m: m.bot and (m.name.lower() == raw.lower()), guild.members)

        if not bot_user:
            return await interaction.response.send_message("❌ Bot not found. Please provide a valid Bot ID or mention.", ephemeral=True)

        if not getattr(bot_user, "bot", False):
            return await interaction.response.send_message("❌ This account is a human member. Use **Whitelist User** instead.", ephemeral=True)

        # Insert into DB
        async with aiosqlite.connect(DB_ANTI_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelisted_bots (
                    guild_id INTEGER, bot_id INTEGER, added_by INTEGER, added_at TEXT,
                    PRIMARY KEY (guild_id, bot_id)
                )
            """)
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await db.execute("""
                INSERT OR REPLACE INTO whitelisted_bots (guild_id, bot_id, added_by, added_at)
                VALUES (?, ?, ?, ?)
            """, (guild.id, bot_user.id, interaction.user.id, now_iso))
            await db.commit()

        security_cache.add_whitelisted_bot(guild.id, bot_user.id)
        await interaction.response.send_message(f"<a:tick:1558726958802800660> Bot {bot_user.mention} is now **whitelisted**! Its moderation actions will no longer be reverted.", ephemeral=True)

        # Trigger V2 panel update & notification log
        await WhitelistPanelService.on_whitelist_update(guild, "Security Bot Whitelisted", bot_user, interaction.user)


class RoleSelectV2(ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select a staff role to whitelist...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        role = self.values[0]

        async with aiosqlite.connect(DB_ANTI_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER, role_id INTEGER, added_by INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            await db.execute("""
                INSERT OR REPLACE INTO whitelisted_roles (guild_id, role_id, added_by)
                VALUES (?, ?, ?)
            """, (guild.id, role.id, interaction.user.id))
            await db.commit()

        security_cache.add_whitelisted_role(guild.id, role.id)
        await interaction.response.send_message(f"<a:tick:1558726958802800660> Role {role.mention} has been **whitelisted**! Members with this role have Anti-Nuke immunity.", ephemeral=True)

        # Trigger V2 panel update & notification log
        await WhitelistPanelService.on_whitelist_update(guild, "Staff Role Whitelisted", role, interaction.user)


class SelectRoleViewV2(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(RoleSelectV2())


class RemoveEntrySelectV2(ui.Select):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(placeholder="Select an entry to remove from whitelist...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]  # format: "user:123" or "bot:123" or "role:123"
        kind, target_id_str = val.split(":")
        target_id = int(target_id_str)
        guild = interaction.guild

        target_obj = None
        if kind == "user":
            target_obj = guild.get_member(target_id) or interaction.client.get_user(target_id)
            async with aiosqlite.connect(DB_ANTI_PATH) as db:
                await db.execute("DELETE FROM whitelisted_users WHERE guild_id = ? AND user_id = ?", (guild.id, target_id))
                await db.commit()
            security_cache.invalidate_guild(guild.id)
            label = "Staff User Removed"
        elif kind == "bot":
            target_obj = guild.get_member(target_id) or interaction.client.get_user(target_id)
            async with aiosqlite.connect(DB_ANTI_PATH) as db:
                await db.execute("DELETE FROM whitelisted_bots WHERE guild_id = ? AND bot_id = ?", (guild.id, target_id))
                await db.commit()
            security_cache.remove_whitelisted_bot(guild.id, target_id)
            label = "Security Bot Removed"
        else:
            target_obj = guild.get_role(target_id)
            async with aiosqlite.connect(DB_ANTI_PATH) as db:
                await db.execute("DELETE FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?", (guild.id, target_id))
                await db.commit()
            security_cache.remove_whitelisted_role(guild.id, target_id)
            label = "Staff Role Removed"

        display_name = getattr(target_obj, "mention", f"`{target_id}`")
        await interaction.response.send_message(f"<a:tick:1558726958802800660> Successfully removed {display_name} from the whitelist.", ephemeral=True)

        # Trigger V2 panel update & notification log
        await WhitelistPanelService.on_whitelist_update(guild, label, target_obj or target_id, interaction.user)


class RemoveEntryViewV2(ui.View):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(timeout=60)
        self.add_item(RemoveEntrySelectV2(options))


class WhitelistNoticeV2View(ui.LayoutView):
    """
    Discord Components V2 Notice Container for Critical Security Whitelist Notice.
    Renders structured text using ui.Container, ui.TextDisplay, and ui.Separator,
    with interactive action buttons below to directly whitelist staff, bots, and roles.
    """
    def __init__(self, guild: Optional[discord.Guild] = None, prefix: str = "$", timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.guild = guild
        self.prefix = prefix
        self.build_ui()

    def build_ui(self):
        self.clear_items()
        pre = self.prefix or "$"
        web_url = os.getenv("FRONTEND_URL", "https://yuna.dpdns.org").rstrip("/")
        dash_url = f"{web_url}/?guild_id={self.guild.id}" if self.guild else web_url

        # Sleek Security Gold accent
        container = ui.Container(accent_color=0xF59E0B)

        notice_content = (
            "### Critical Security Notice: Whitelist Configuration\n"
            "**Anti-Nuke is now actively guarding your server.**\n\n"
            "> **Prevent Unusual Activities & Accidental Punishments:**\n"
            "> Unwhitelisted administrators or bots performing administrative actions "
            "(such as **unbanning members**, **creating/deleting/recreating channels**, "
            "**modifying roles**, or **creating webhooks**) will be detected as unusual activity and automatically neutralized.\n\n"
            "**Please whitelist your trusted staff and bots now:**\n"
            f"- **Whitelist Staff / Admins:** `{pre}whitelist <@user>` *(or `{pre}wl <@user>`)*\n"
            f"- **Whitelist Staff Roles:** `{pre}whitelist <@role>` *(members with this role bypass limits)*\n"
            f"- **Whitelist Other Bots:** `{pre}botwhitelist add <@bot>` *(immunity for Ticket/Music/Mod bots)*\n"
            f"- **Web Dashboard:** Manage all whitelists in real-time under **AntiNuke > Whitelist**\n\n"
            "-# Tip: Only whitelist trusted staff members and verified bots."
        )

        container.add_item(ui.TextDisplay(notice_content))
        container.add_item(ui.Separator())

        # Action Deck Row 0: Direct Whitelist Actions
        row0 = ui.ActionRow()
        b_user = ui.Button(label="Whitelist Staff", style=discord.ButtonStyle.primary, custom_id="wl_notice_add_user")
        b_user.callback = self.add_user_callback
        row0.add_item(b_user)

        b_bot = ui.Button(label="Whitelist Bot", style=discord.ButtonStyle.primary, custom_id="wl_notice_add_bot")
        b_bot.callback = self.add_bot_callback
        row0.add_item(b_bot)

        b_role = ui.Button(label="Whitelist Role", style=discord.ButtonStyle.primary, custom_id="wl_notice_add_role")
        b_role.callback = self.add_role_callback
        row0.add_item(b_role)
        container.add_item(row0)

        # Action Deck Row 1: Status & Web Dashboard
        row1 = ui.ActionRow()
        b_list = ui.Button(label="View Whitelist", style=discord.ButtonStyle.secondary, custom_id="wl_notice_view_list")
        b_list.callback = self.view_whitelist_callback
        row1.add_item(b_list)

        b_dash = ui.Button(label="Web Dashboard", style=discord.ButtonStyle.link, url=dash_url)
        row1.add_item(b_dash)
        container.add_item(row1)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        guild = interaction.guild or self.guild
        if not guild:
            return False

        user = interaction.user
        is_owner = user.id == guild.owner_id
        is_extra = security_cache.is_extra_owner(guild.id, user.id)
        is_admin = getattr(getattr(user, "guild_permissions", None), "administrator", False)

        if not (is_owner or is_extra or is_admin):
            await interaction.response.send_message("❌ Only Server Owner, Extra Owner, or Administrators can manage the Whitelist.", ephemeral=True)
            return False
        return True

    async def add_user_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddUserModalV2())

    async def add_bot_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddBotModalV2())

    async def add_role_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Select a staff role to whitelist:", view=SelectRoleViewV2(), ephemeral=True)

    async def view_whitelist_callback(self, interaction: discord.Interaction):
        guild = interaction.guild or self.guild
        data = await WhitelistPanelService.fetch_whitelist_data(guild)
        users = data.get("users", [])
        bots = data.get("bots", [])
        roles = data.get("roles", [])
        extra_owner_id = data.get("extra_owner_id")

        users_formatted = ", ".join(f"<@{u}>" for u in users[:15]) if users else "*No staff users whitelisted*"
        if len(users) > 15:
            users_formatted += f" *(+{len(users)-15} more)*"

        bots_formatted = ", ".join(f"<@{b}>" for b in bots[:15]) if bots else "*No security bots whitelisted*"
        if len(bots) > 15:
            bots_formatted += f" *(+{len(bots)-15} more)*"

        roles_formatted = ", ".join(f"<@&{r}>" for r in roles[:15]) if roles else "*No staff roles whitelisted*"
        if len(roles) > 15:
            roles_formatted += f" *(+{len(roles)-15} more)*"

        owner_str = f"<@{guild.owner_id}>" if guild and guild.owner_id else "N/A"
        extra_str = f"<@{extra_owner_id}>" if extra_owner_id else "*None Configured*"

        embed = discord.Embed(
            title="Anti-Nuke Whitelist Status",
            color=0x2B2D31
        )
        embed.description = (
            f"**Server Immunity Hierarchy:**\n"
            f"• **Server Owner:** {owner_str} *(Immune)*\n"
            f"• **Extra Owner:** {extra_str}\n\n"
            f"**Whitelisted Staff Users ({len(users)}):**\n{users_formatted}\n\n"
            f"**Whitelisted Security Bots ({len(bots)}):**\n{bots_formatted}\n\n"
            f"**Whitelisted Staff Roles ({len(roles)}):**\n{roles_formatted}"
        )
        embed.set_footer(text="Yuna Security • Live Immunity Registry")
        await interaction.response.send_message(embed=embed, ephemeral=True)

