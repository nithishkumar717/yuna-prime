import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz
from utils.Tools import (
    blacklist_check, ignore_check, get_or_create_antinuke_log_channel,
    is_server_owner_or_extra_owner, get_or_create_yuna_logs_category,
    ensure_channel_in_yuna_logs, detect_yuna_logs_style, format_channel_name,
    identify_log_channel_type
)
from utils.settings_manager import get_guild_setting, set_guild_setting
from core.cache.security_cache import security_cache


# ==========================================================
# 📝 MODALS
# ==========================================================
class AddExtraOwnerModal(discord.ui.Modal, title="Add Extra Owner"):
    user_input = discord.ui.TextInput(
        label="User ID or @Mention",
        placeholder="Enter user ID (e.g. 123456789012345678)",
        required=True,
        max_length=30
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        if not raw_val.isdigit():
            return await interaction.response.send_message("❌ Please provide a valid numerical User ID.", ephemeral=True)
        
        user_id = int(raw_val)
        guild = interaction.guild

        if user_id == guild.owner_id:
            return await interaction.response.send_message("❌ Server Owner is already the primary owner.", ephemeral=True)

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS extraowners (
                    guild_id INTEGER PRIMARY KEY,
                    owner_id INTEGER
                )
            ''')
            await db.execute("INSERT OR REPLACE INTO extraowners (guild_id, owner_id) VALUES (?, ?)", (guild.id, user_id))
            await db.commit()

        set_guild_setting(guild.id, "extraowner", str(user_id))
        security_cache.add_extra_owner(guild.id, user_id)
        await self.parent_view.refresh_extraowners(interaction)


class RemoveExtraOwnerModal(discord.ui.Modal, title="Remove Extra Owner"):
    user_input = discord.ui.TextInput(
        label="User ID or @Mention",
        placeholder="Enter user ID to remove",
        required=True,
        max_length=30
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        if not raw_val.isdigit():
            return await interaction.response.send_message("❌ Please provide a valid numerical User ID.", ephemeral=True)

        user_id = int(raw_val)
        guild = interaction.guild

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM extraowners WHERE guild_id = ? AND owner_id = ?", (guild.id, user_id))
            await db.commit()

        set_guild_setting(guild.id, "extraowner", None)
        security_cache.remove_extra_owner(guild.id, user_id)
        await self.parent_view.refresh_extraowners(interaction)


class AddWhitelistUserModal(discord.ui.Modal, title="Whitelist User"):
    user_input = discord.ui.TextInput(
        label="User ID, Mention, or Username",
        placeholder="Enter User ID (e.g. 123456789), @User, or Username",
        required=True,
        max_length=50
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "").replace("@", "").strip()
        guild = interaction.guild
        target_user = None

        if raw_val.isdigit():
            user_id = int(raw_val)
            target_user = guild.get_member(user_id) or interaction.client.get_user(user_id)

        if not target_user:
            clean_name = self.user_input.value.strip().lstrip("@")
            target_user = discord.utils.get(guild.members, name=clean_name)
        if not target_user:
            target_user = discord.utils.get(guild.members, display_name=clean_name)
        if not target_user:
            for m in guild.members:
                if m.name.lower() == clean_name.lower() or m.display_name.lower() == clean_name.lower():
                    target_user = m
                    break

        if not target_user:
            if raw_val.isdigit():
                user_id = int(raw_val)
            else:
                return await interaction.response.send_message(f"❌ Could not find user **`{self.user_input.value}`** in this server.", ephemeral=True)
        else:
            user_id = target_user.id

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_users (
                    guild_id INTEGER,
                    user_id INTEGER,
                    ban INTEGER DEFAULT 1,
                    kick INTEGER DEFAULT 1,
                    prune INTEGER DEFAULT 1,
                    botadd INTEGER DEFAULT 1,
                    serverup INTEGER DEFAULT 1,
                    memup INTEGER DEFAULT 1,
                    chcr INTEGER DEFAULT 1,
                    chdl INTEGER DEFAULT 1,
                    chup INTEGER DEFAULT 1,
                    rlcr INTEGER DEFAULT 1,
                    rldl INTEGER DEFAULT 1,
                    rlup INTEGER DEFAULT 1,
                    meneve INTEGER DEFAULT 1,
                    mngweb INTEGER DEFAULT 1,
                    mngstemo INTEGER DEFAULT 1,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            await db.execute('''
                INSERT OR REPLACE INTO whitelisted_users 
                (guild_id, user_id, ban, kick, prune, botadd, serverup, memup, chcr, chdl, chup, rlcr, rldl, rlup, meneve, mngweb, mngstemo)
                VALUES (?, ?, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
            ''', (guild.id, user_id))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.invalidate_guild(guild.id)
        await security_cache.warm_guild(guild.id)

        await self.parent_view.refresh_users(interaction)


class RemoveWhitelistUserModal(discord.ui.Modal, title="Unwhitelist User"):
    user_input = discord.ui.TextInput(
        label="User ID, Mention, or Username",
        placeholder="Enter User ID, @User, or Username to unwhitelist",
        required=True,
        max_length=50
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "").replace("@", "").strip()
        guild = interaction.guild
        target_user = None

        if raw_val.isdigit():
            user_id = int(raw_val)
            target_user = guild.get_member(user_id) or interaction.client.get_user(user_id)

        if not target_user:
            clean_name = self.user_input.value.strip().lstrip("@")
            target_user = discord.utils.get(guild.members, name=clean_name)
        if not target_user:
            target_user = discord.utils.get(guild.members, display_name=clean_name)
        if not target_user:
            for m in guild.members:
                if m.name.lower() == clean_name.lower() or m.display_name.lower() == clean_name.lower():
                    target_user = m
                    break

        if not target_user:
            if raw_val.isdigit():
                user_id = int(raw_val)
            else:
                return await interaction.response.send_message(f"❌ Could not find user **`{self.user_input.value}`** in this server.", ephemeral=True)
        else:
            user_id = target_user.id

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM whitelisted_users WHERE guild_id = ? AND user_id = ?", (guild.id, user_id))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.remove_whitelist_user(guild.id, user_id)
        security_cache.invalidate_guild(guild.id)
        await security_cache.warm_guild(guild.id)

        await self.parent_view.refresh_users(interaction)


class AddWhitelistBotModal(discord.ui.Modal, title="Whitelist Trusted Bot"):
    bot_input = discord.ui.TextInput(
        label="Bot Application ID",
        placeholder="Enter Bot ID (e.g. 123456789012345678)",
        required=True,
        max_length=30
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.bot_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        if not raw_val.isdigit():
            return await interaction.response.send_message("❌ Please provide a valid numerical Bot ID.", ephemeral=True)

        bot_id = int(raw_val)
        guild = interaction.guild

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_bots (
                    guild_id INTEGER,
                    bot_id INTEGER,
                    added_by INTEGER,
                    added_at TIMESTAMP,
                    PRIMARY KEY (guild_id, bot_id)
                )
            ''')
            await db.execute('''
                INSERT OR REPLACE INTO whitelisted_bots (guild_id, bot_id, added_by, added_at)
                VALUES (?, ?, ?, datetime('now'))
            ''', (guild.id, bot_id, interaction.user.id))
            await db.commit()

        await self.parent_view.refresh_bots(interaction)


class RemoveWhitelistBotModal(discord.ui.Modal, title="Remove Whitelisted Bot"):
    bot_input = discord.ui.TextInput(
        label="Bot Application ID",
        placeholder="Enter Bot ID to remove",
        required=True,
        max_length=30
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.bot_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        if not raw_val.isdigit():
            return await interaction.response.send_message("❌ Please provide a valid numerical Bot ID.", ephemeral=True)

        bot_id = int(raw_val)
        guild = interaction.guild

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM whitelisted_bots WHERE guild_id = ? AND bot_id = ?", (guild.id, bot_id))
            await db.commit()

        await self.parent_view.refresh_bots(interaction)


# ==========================================================
# 🛡️ SUB-VIEW 1: CONFIGURE PROTECTION HUB & SUB-VIEWS
# ==========================================================
class SecurityBotProtectionSubView(discord.ui.View):
    def __init__(self, author, guild_id, protection_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.protection_view = protection_view
        self.is_enabled = False
        self.update_components()

    async def load_data(self):
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bot_protection (
                    guild_id INTEGER PRIMARY KEY,
                    status BOOLEAN DEFAULT 0
                )
            ''')
            async with db.execute("SELECT status FROM bot_protection WHERE guild_id = ?", (self.guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    self.is_enabled = bool(row[0] in (1, "on", True, "true"))
                else:
                    self.is_enabled = False
        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_enable = discord.ui.Button(label="Enable", style=discord.ButtonStyle.success, row=0, custom_id="btn_bp_enable")
        btn_disable = discord.ui.Button(label="Disable", style=discord.ButtonStyle.danger, row=0, custom_id="btn_bp_disable")
        btn_wl_bot = discord.ui.Button(label="Whitelist Bot", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_bp_wl_bot")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_bp_back")

        btn_enable.callback = self.enable_bot_protection
        btn_disable.callback = self.disable_bot_protection
        btn_wl_bot.callback = self.goto_whitelist_bot
        btn_back.callback = self.back_to_protection

        self.add_item(btn_enable)
        self.add_item(btn_disable)
        self.add_item(btn_wl_bot)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        status_str = "Enabled" if self.is_enabled else "Disabled"

        embed = discord.Embed(
            title="Configure Bot Protection",
            description=(
                "**Enterprise Rogue Bot Defense & Periodic Audit**\n"
                "• **Bot Punishment:** Instant Kick / Ban\n"
                "• **Inviter Action:** Ban, Kick, or Demote\n"
                "• **Audit Engine:** Periodic Audit & 10m Rolling Window\n\n"
                f"**Current Status:** {status_str}"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def load_and_display(self, interaction: discord.Interaction):
        await self.load_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def enable_bot_protection(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)

        self.is_enabled = True
        log_channel, notice_embed = await get_or_create_antinuke_log_channel(interaction.guild)
        log_channel_id = log_channel.id if log_channel else None

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bot_protection (
                    guild_id INTEGER PRIMARY KEY,
                    status BOOLEAN DEFAULT 1
                )
            ''')
            await db.execute("INSERT OR REPLACE INTO bot_protection (guild_id, status) VALUES (?, 1)", (self.guild_id,))
            if log_channel_id:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS antinuke (
                        guild_id INTEGER PRIMARY KEY,
                        status BOOLEAN DEFAULT 0,
                        log_channel INTEGER
                    )
                ''')
                await db.execute(
                    "INSERT INTO antinuke (guild_id, status, log_channel) VALUES (?, 0, ?) "
                    "ON CONFLICT(guild_id) DO UPDATE SET log_channel=COALESCE(excluded.log_channel, antinuke.log_channel)",
                    (self.guild_id, log_channel_id)
                )
            await db.commit()

        set_guild_setting(self.guild_id, "bot_protection", True)
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

        anti_bot_cog = interaction.client.get_cog("AntiBotAdd")
        if anti_bot_cog and hasattr(anti_bot_cog, "purge_unwhitelisted_bots"):
            res = anti_bot_cog.purge_unwhitelisted_bots(interaction.guild)
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)

    async def disable_bot_protection(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)

        self.is_enabled = False
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bot_protection (
                    guild_id INTEGER PRIMARY KEY,
                    status BOOLEAN DEFAULT 1
                )
            ''')
            await db.execute("INSERT OR REPLACE INTO bot_protection (guild_id, status) VALUES (?, 0)", (self.guild_id,))
            await db.commit()

        set_guild_setting(self.guild_id, "bot_protection", False)
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def goto_whitelist_bot(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        sub_view = SecurityBotWhitelistSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def back_to_protection(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.protection_view.load_and_display(interaction)


class SecurityAntinukeSubView(discord.ui.View):
    def __init__(self, author, guild_id, protection_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.protection_view = protection_view
        self.is_enabled = False
        self.update_components()

    async def load_data(self):
        from core.cache.security_cache import security_cache
        if self.guild_id not in security_cache._loaded_guilds:
            await security_cache.warm_guild(self.guild_id)
        self.is_enabled = security_cache.is_antinuke_enabled(self.guild_id)
        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_enable = discord.ui.Button(label="Enable", style=discord.ButtonStyle.success, row=0, custom_id="btn_an_enable")
        btn_disable = discord.ui.Button(label="Disable", style=discord.ButtonStyle.danger, row=0, custom_id="btn_an_disable")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_an_back")

        btn_enable.callback = self.enable_antinuke
        btn_disable.callback = self.disable_antinuke
        btn_back.callback = self.back_to_protection

        self.add_item(btn_enable)
        self.add_item(btn_disable)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        status_str = "Enabled" if self.is_enabled else "Disabled"

        embed = discord.Embed(
            title="Configure Antinuke",
            description=(
                "Prevent harmful activities with active monitoring.\n\n"
                f"**Current Status:** {status_str}"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def enable_antinuke(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)

        self.is_enabled = True
        log_channel, notice_embed = await get_or_create_antinuke_log_channel(interaction.guild)
        log_channel_id = log_channel.id if log_channel else None

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS antinuke (
                    guild_id INTEGER PRIMARY KEY,
                    status BOOLEAN DEFAULT 0,
                    log_channel INTEGER
                )
            ''')
            await db.execute(
                "INSERT INTO antinuke (guild_id, status, log_channel) VALUES (?, 1, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET status=1, log_channel=COALESCE(excluded.log_channel, antinuke.log_channel)",
                (self.guild_id, log_channel_id)
            )
            await db.commit()

        set_guild_setting(self.guild_id, "antinuke", True)
        from core.cache.security_cache import security_cache
        security_cache.set_antinuke_status(self.guild_id, True)

        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

        # Critical Notice: Whitelist Bots & Staff Members (Components V2 LayoutView)
        from services.whitelist_panel import WhitelistNoticeV2View
        if log_channel:
            try:
                v2_dash_notice = WhitelistNoticeV2View(guild=interaction.guild, prefix="$")
                await log_channel.send(view=v2_dash_notice)
            except Exception:
                try:
                    wl_notice_embed = discord.Embed(
                        title="Critical Security Notice: Whitelist Configuration",
                        description=(
                            "**Anti-Nuke is now actively guarding your server.**\n\n"
                            "> **Prevent Unusual Activities & Accidental Punishments:**\n"
                            "> Unwhitelisted administrators or bots performing administrative actions "
                            "(such as **unbanning members**, **creating/deleting/recreating channels**, "
                            "**modifying roles**, or **creating webhooks**) will be detected as unusual activity and automatically neutralized.\n\n"
                            "**Please whitelist your trusted staff and bots now:**\n"
                            f"- **Whitelist Staff / Admins:** `$whitelist <@user>` *(or `$wl <@user>`)*\n"
                            f"- **Whitelist Staff Roles:** `$whitelist <@role>` *(members with this role bypass limits)*\n"
                            f"- **Whitelist Other Bots:** `$botwhitelist add <@bot>` *(immunity for Ticket/Music/Mod bots)*\n"
                            f"- **Web Dashboard:** Manage all whitelists in real-time under **AntiNuke > Whitelist**"
                        ),
                        color=0x2B2D31
                    )
                    wl_notice_embed.set_footer(text="Tip: Only whitelist trusted staff members and verified bots.")
                    await log_channel.send(embed=wl_notice_embed)
                except Exception:
                    pass

        if notice_embed and log_channel:
            try:
                await log_channel.send(embed=notice_embed)
            except Exception:
                pass

    async def disable_antinuke(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)

        self.is_enabled = False
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM antinuke WHERE guild_id = ?", (self.guild_id,))
            await db.commit()

        set_guild_setting(self.guild_id, "antinuke", False)
        from core.cache.security_cache import security_cache
        security_cache.set_antinuke_status(self.guild_id, False)
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_protection(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.protection_view.load_and_display(interaction)


class SecurityProtectionHubSubView(discord.ui.View):
    def __init__(self, author, guild_id, main_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.main_view = main_view
        self.antinuke_status = False
        self.bot_protection_status = False
        self.update_components()

    async def load_data(self):
        from core.cache.security_cache import security_cache
        if self.guild_id not in security_cache._loaded_guilds:
            await security_cache.warm_guild(self.guild_id)

        self.antinuke_status = security_cache.is_antinuke_enabled(self.guild_id)
        self.bot_protection_status = security_cache.is_bot_protection_active(self.guild_id)
        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_antinuke = discord.ui.Button(label="Antinuke", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_prot_an")
        btn_bot_protection = discord.ui.Button(label="Bot Protection", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_prot_bp")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_prot_back")

        btn_antinuke.callback = self.goto_antinuke
        btn_bot_protection.callback = self.goto_bot_protection
        btn_back.callback = self.back_to_main

        self.add_item(btn_antinuke)
        self.add_item(btn_bot_protection)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        an_str = "Enabled" if self.antinuke_status else "Disabled"
        bp_str = "Enabled" if self.bot_protection_status else "Disabled"

        embed = discord.Embed(
            title="Configure Protection",
            description=(
                "Manage server anti-nuke defense and rogue bot protection.\n\n"
                f"**Antinuke Status:** {an_str}\n"
                f"**Bot Protection Status:** {bp_str}"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def load_and_display(self, interaction: discord.Interaction):
        await self.load_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def goto_antinuke(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        sub_view = SecurityAntinukeSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def goto_bot_protection(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        sub_view = SecurityBotProtectionSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def back_to_main(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.main_view.load_and_display(interaction)


# ==========================================================
# 👑 SUB-VIEW 2: CONFIGURE EXTRAOWNER
# ==========================================================
class SecurityExtraownerSubView(discord.ui.View):
    def __init__(self, author, guild_id, main_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.main_view = main_view
        self.extra_owners = []
        self.update_components()

    async def load_data(self):
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS extraowners (
                    guild_id INTEGER PRIMARY KEY,
                    owner_id INTEGER
                )
            ''')
            async with db.execute("SELECT owner_id FROM extraowners WHERE guild_id = ?", (self.guild_id,)) as cursor:
                self.extra_owners = [row[0] for row in await cursor.fetchall()]
        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_add = discord.ui.Button(label="Add", style=discord.ButtonStyle.success, row=0, custom_id="btn_eo_add")
        btn_remove = discord.ui.Button(label="Remove", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_eo_remove")
        btn_clear = discord.ui.Button(label="Clear", style=discord.ButtonStyle.danger, row=0, custom_id="btn_eo_clear")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_eo_back")

        btn_add.callback = self.add_extraowner
        btn_remove.callback = self.remove_extraowner
        btn_clear.callback = self.clear_extraowners
        btn_back.callback = self.back_to_main

        self.add_item(btn_add)
        self.add_item(btn_remove)
        self.add_item(btn_clear)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        if self.extra_owners:
            extra_lines = "\n".join([f"<a:arrow:1557834336571494480> <@{oid}>" for oid in self.extra_owners])
        else:
            extra_lines = "<a:arrow:1557834336571494480> **No Extraowners**"

        embed = discord.Embed(
            title="Configure Extraowner",
            description=(
                "Designated user with owner-level command access\n\n"
                f"**Current Extraowners:**\n{extra_lines}"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def add_extraowner(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only the Server Owner can add Extra Owners.", ephemeral=True)
        modal = AddExtraOwnerModal(self)
        await interaction.response.send_modal(modal)

    async def remove_extraowner(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only the Server Owner can remove Extra Owners.", ephemeral=True)
        modal = RemoveExtraOwnerModal(self)
        await interaction.response.send_modal(modal)

    async def refresh_extraowners(self, interaction: discord.Interaction):
        await self.load_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def clear_extraowners(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only the Server Owner can clear Extra Owners.", ephemeral=True)

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM extraowners WHERE guild_id = ?", (self.guild_id,))
            await db.commit()

        set_guild_setting(self.guild_id, "extraowner", None)
        self.extra_owners = []
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_main(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.main_view.load_and_display(interaction)


# ==========================================================
# 👥 SUB-VIEW 3A: USER WHITELIST MANAGER
# ==========================================================
class SecurityUserWhitelistSubView(discord.ui.View):
    def __init__(self, author, guild_id, wl_hub_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.wl_hub_view = wl_hub_view
        self.whitelisted_users = []
        self.update_components()

    async def load_data(self):
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_users (
                    guild_id INTEGER,
                    user_id INTEGER,
                    ban INTEGER DEFAULT 1,
                    kick INTEGER DEFAULT 1,
                    prune INTEGER DEFAULT 1,
                    botadd INTEGER DEFAULT 1,
                    serverup INTEGER DEFAULT 1,
                    memup INTEGER DEFAULT 1,
                    chcr INTEGER DEFAULT 1,
                    chdl INTEGER DEFAULT 1,
                    chup INTEGER DEFAULT 1,
                    rlcr INTEGER DEFAULT 1,
                    rldl INTEGER DEFAULT 1,
                    rlup INTEGER DEFAULT 1,
                    meneve INTEGER DEFAULT 1,
                    mngweb INTEGER DEFAULT 1,
                    mngstemo INTEGER DEFAULT 1,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            async with db.execute("SELECT user_id FROM whitelisted_users WHERE guild_id = ?", (self.guild_id,)) as cursor:
                self.whitelisted_users = [row[0] for row in await cursor.fetchall()]
        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_add = discord.ui.Button(label="Add", style=discord.ButtonStyle.success, row=0, custom_id="btn_uwl_add")
        btn_remove = discord.ui.Button(label="Remove", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_uwl_remove")
        btn_clear = discord.ui.Button(label="Clear", style=discord.ButtonStyle.danger, row=0, custom_id="btn_uwl_clear")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_uwl_back")

        btn_add.callback = self.add_user
        btn_remove.callback = self.remove_user
        btn_clear.callback = self.clear_users
        btn_back.callback = self.back_to_wl_hub

        self.add_item(btn_add)
        self.add_item(btn_remove)
        self.add_item(btn_clear)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        if self.whitelisted_users:
            user_lines = "\n".join([f"<a:arrow:1557834336571494480> <@{uid}>" for uid in self.whitelisted_users])
        else:
            user_lines = "<a:arrow:1557834336571494480> **No Whitelisted All Access Users**"

        embed = discord.Embed(
            title="Configure Whitelist All Access",
            description=(
                "Trusted users permitted to perform all administrative actions\n\n"
                f"**Current Whitelisted All Access Users:**\n{user_lines}"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def add_user(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only the Server Owner can manage whitelisted users.", ephemeral=True)
        modal = AddWhitelistUserModal(self)
        await interaction.response.send_modal(modal)

    async def remove_user(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only the Server Owner can manage whitelisted users.", ephemeral=True)
        modal = RemoveWhitelistUserModal(self)
        await interaction.response.send_modal(modal)

    async def refresh_users(self, interaction: discord.Interaction):
        await self.load_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def clear_users(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only the Server Owner can clear whitelisted users.", ephemeral=True)

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM whitelisted_users WHERE guild_id = ?", (self.guild_id,))
            await db.commit()

        self.whitelisted_users = []
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_wl_hub(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.wl_hub_view.load_and_display(interaction)


# ==========================================================
# 🤖 SUB-VIEW 3B: BOT WHITELIST MANAGER
# ==========================================================
class SecurityBotSelectDropdown(discord.ui.Select):
    def __init__(self, parent_view, guild):
        self.parent_view = parent_view
        other_bots = [m for m in guild.members if m.bot and m.id != guild.me.id][:25]

        options = []
        if other_bots:
            for b in other_bots:
                is_wl = b.id in parent_view.whitelisted_bots
                label = f"{b.name[:25]}"
                desc = f"ID: {b.id} • {'Whitelisted' if is_wl else 'Not Whitelisted'}"
                emoji = "✅" if is_wl else "🤖"
                options.append(discord.SelectOption(label=label, value=str(b.id), description=desc, emoji=emoji))
        else:
            options.append(discord.SelectOption(label="No other bots in server", value="none", description="Use 'Add' button for Bot ID", emoji="ℹ️"))

        super().__init__(placeholder="Select a bot from server to Whitelist...", min_values=1, max_values=1, options=options, row=1, custom_id="select_bwl_bot")

    async def callback(self, interaction: discord.Interaction):
        selected_val = self.values[0] if self.values else (interaction.data.get("values", [None])[0] if hasattr(interaction, 'data') and isinstance(interaction.data, dict) else None)
        if not selected_val or selected_val == "none":
            return await interaction.response.send_message("ℹ️ No other bots found in this server. Click **Add** to enter a Bot ID manually.", ephemeral=True)

        is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, "guild_permissions") else False
        if not is_admin and interaction.user != self.parent_view.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only Server Administrators can manage whitelisted bots.", ephemeral=True)

        bot_id = int(selected_val)
        guild = interaction.guild
        bot_member = guild.get_member(bot_id)

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_bots (
                    guild_id INTEGER,
                    bot_id INTEGER,
                    added_by INTEGER,
                    added_at TIMESTAMP,
                    PRIMARY KEY (guild_id, bot_id)
                )
            ''')
            await db.execute('''
                INSERT OR REPLACE INTO whitelisted_bots (guild_id, bot_id, added_by, added_at)
                VALUES (?, ?, ?, datetime('now'))
            ''', (guild.id, bot_id, interaction.user.id))
            await db.commit()

        await self.parent_view.load_data()
        self.parent_view.update_components(guild)
        embed = self.parent_view.build_embed(guild)
        bot_str = bot_member.mention if bot_member else f"`{bot_id}`"
        await interaction.response.send_message(f"✅ Successfully whitelisted bot {bot_str} (`{bot_id}`).", ephemeral=True)
        try:
            await interaction.message.edit(embed=embed, view=self.parent_view)
        except Exception:
            pass


# ==========================================================
# 🤖 SUB-VIEW 3B: BOT WHITELIST MANAGER
# ==========================================================
class SecurityBotWhitelistSubView(discord.ui.View):
    def __init__(self, author, guild_id, parent_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.parent_view = parent_view
        self.whitelisted_bots = []
        self.update_components()

    async def load_data(self):
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_bots (
                    guild_id INTEGER,
                    bot_id INTEGER,
                    added_by INTEGER,
                    added_at TIMESTAMP,
                    PRIMARY KEY (guild_id, bot_id)
                )
            ''')
            async with db.execute("SELECT bot_id FROM whitelisted_bots WHERE guild_id = ?", (self.guild_id,)) as cursor:
                self.whitelisted_bots = [row[0] for row in await cursor.fetchall()]
        self.update_components()

    def update_components(self, guild=None):
        self.clear_items()

        btn_add = discord.ui.Button(label="Add (ID)", style=discord.ButtonStyle.success, row=0, custom_id="btn_bwl_add")
        btn_remove = discord.ui.Button(label="Remove", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_bwl_remove")
        btn_list = discord.ui.Button(label="List All Bots", style=discord.ButtonStyle.primary, row=0, custom_id="btn_bwl_list")
        btn_clear = discord.ui.Button(label="Clear", style=discord.ButtonStyle.danger, row=0, custom_id="btn_bwl_clear")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_bwl_back")

        btn_add.callback = self.add_bot
        btn_remove.callback = self.remove_bot
        btn_list.callback = self.list_bots
        btn_clear.callback = self.clear_bots
        btn_back.callback = self.back_to_parent

        self.add_item(btn_add)
        self.add_item(btn_remove)
        self.add_item(btn_list)
        self.add_item(btn_clear)
        self.add_item(btn_back)

        if guild:
            self.add_item(SecurityBotSelectDropdown(self, guild))

    def build_embed(self, guild) -> discord.Embed:
        if self.whitelisted_bots:
            bot_lines = "\n".join([f"<a:arrow:1557834336571494480> <@{bid}>" for bid in self.whitelisted_bots])
        else:
            bot_lines = "<a:arrow:1557834336571494480> **No Whitelisted Bots**"

        embed = discord.Embed(
            title="Configure Bot Whitelist",
            description=(
                "Trusted bots permitted to join the server with admin access.\n\n"
                f"**Current Whitelisted Bots:**\n{bot_lines}"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def load_and_display(self, interaction: discord.Interaction):
        await self.load_data()
        self.update_components(interaction.guild)
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def add_bot(self, interaction: discord.Interaction):
        is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, "guild_permissions") else False
        if not is_admin and interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only Server Administrators can manage whitelisted bots.", ephemeral=True)
        modal = AddWhitelistBotModal(self)
        await interaction.response.send_modal(modal)

    async def remove_bot(self, interaction: discord.Interaction):
        is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, "guild_permissions") else False
        if not is_admin and interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only Server Administrators can manage whitelisted bots.", ephemeral=True)
        modal = RemoveWhitelistBotModal(self)
        await interaction.response.send_modal(modal)

    async def list_bots(self, interaction: discord.Interaction):
        guild = interaction.guild
        all_bots = [m for m in guild.members if m.bot]
        wl_set = set(self.whitelisted_bots)

        wl_lines = []
        unwl_lines = []

        for b in all_bots:
            if b.id == guild.me.id:
                continue
            if b.id in wl_set:
                wl_lines.append(f"🟢 {b.mention} (`{b.name}` — `{b.id}`)")
            else:
                unwl_lines.append(f"🔴 {b.mention} (`{b.name}` — `{b.id}`)")

        for b_id in wl_set:
            if not any(m.id == b_id for m in all_bots):
                wl_lines.append(f"🟢 `<@{b_id}>` (`{b_id}`) *(Not currently in server)*")

        wl_str = "\n".join(wl_lines) if wl_lines else "*None*"
        unwl_str = "\n".join(unwl_lines) if unwl_lines else "*None*"

        embed = discord.Embed(
            title=f"🤖 Bot Protection Status • {guild.name}",
            color=0x2B2D31,
            description=(
                f"**Total Server Bots:** `{len(all_bots)}` (including Yuna)\n\n"
                f"**✅ Whitelisted Bots (Permitted Access):**\n{wl_str}\n\n"
                f"**⚠️ Unwhitelisted Bots (Purged if Protection Enabled):**\n{unwl_str}"
            )
        )
        embed.set_footer(text="Powered by Yuna Development • Bot Whitelist")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def refresh_bots(self, interaction: discord.Interaction):
        await self.load_data()
        self.update_components(interaction.guild)
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def clear_bots(self, interaction: discord.Interaction):
        is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, "guild_permissions") else False
        if not is_admin and interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only Server Administrators can clear whitelisted bots.", ephemeral=True)

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM whitelisted_bots WHERE guild_id = ?", (self.guild_id,))
            await db.commit()

        self.whitelisted_bots = []
        self.update_components(interaction.guild)
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_parent(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.parent_view.load_and_display(interaction)


class AddWhitelistRoleDashboardModal(discord.ui.Modal, title="Whitelist Trusted Role"):
    role_input = discord.ui.TextInput(
        label="Role ID, Mention, or Name",
        placeholder="Enter Role ID, @Role, or Role Name",
        required=True,
        max_length=50
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        clean_val = self.role_input.value.strip().replace("<@&", "").replace(">", "").replace("!", "").replace("@", "").strip()
        guild = interaction.guild
        target_role = None

        if clean_val.isdigit():
            target_role = guild.get_role(int(clean_val))

        if not target_role:
            target_role = discord.utils.get(guild.roles, name=self.role_input.value.strip())
        if not target_role:
            target_role = discord.utils.get(guild.roles, name=clean_val)
        if not target_role:
            for r in guild.roles:
                if r.name.lower() == clean_val.lower() or r.name.lower() == self.role_input.value.strip().lower():
                    target_role = r
                    break

        if not target_role:
            return await interaction.response.send_message(f"❌ Could not find role **`{self.role_input.value}`** in this server.", ephemeral=True)

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER,
                    role_id INTEGER,
                    added_by INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
            ''')
            try:
                await db.execute("ALTER TABLE whitelisted_roles ADD COLUMN added_by INTEGER;")
            except Exception:
                pass
            await db.execute('''
                INSERT OR REPLACE INTO whitelisted_roles (guild_id, role_id, added_by)
                VALUES (?, ?, ?)
            ''', (guild.id, target_role.id, interaction.user.id))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.add_whitelisted_role(guild.id, target_role.id)

        await self.parent_view.refresh_roles(interaction)


class RemoveWhitelistRoleDashboardModal(discord.ui.Modal, title="Remove Whitelisted Role"):
    role_input = discord.ui.TextInput(
        label="Role ID, Mention, or Name",
        placeholder="Enter Role ID, @Role, or Role Name to remove",
        required=True,
        max_length=50
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        clean_val = self.role_input.value.strip().replace("<@&", "").replace(">", "").replace("!", "").replace("@", "").strip()
        guild = interaction.guild
        target_role = None

        if clean_val.isdigit():
            role_id = int(clean_val)
            target_role = guild.get_role(role_id)

        if not target_role:
            for r in guild.roles:
                if r.name.lower() == clean_val.lower() or r.name.lower() == self.role_input.value.strip().lower():
                    target_role = r
                    break

        role_id = target_role.id if target_role else (int(clean_val) if clean_val.isdigit() else None)

        if not role_id:
            return await interaction.response.send_message(f"❌ Could not find role **`{self.role_input.value}`** in this server.", ephemeral=True)

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?", (guild.id, role_id))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.remove_whitelisted_role(guild.id, role_id)

        await self.parent_view.refresh_roles(interaction)


class SecurityRoleWhitelistSubView(discord.ui.View):
    def __init__(self, author, guild_id, wl_hub_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.wl_hub_view = wl_hub_view
        self.whitelisted_roles = []
        self.update_components()

    async def load_data(self):
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
            ''')
            async with db.execute("SELECT role_id FROM whitelisted_roles WHERE guild_id = ?", (self.guild_id,)) as cursor:
                self.whitelisted_roles = [row[0] for row in await cursor.fetchall()]
        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_add = discord.ui.Button(label="Add", style=discord.ButtonStyle.success, row=0, custom_id="btn_rwl_add")
        btn_remove = discord.ui.Button(label="Remove", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_rwl_remove")
        btn_clear = discord.ui.Button(label="Clear", style=discord.ButtonStyle.danger, row=0, custom_id="btn_rwl_clear")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_rwl_back")

        btn_add.callback = self.add_role
        btn_remove.callback = self.remove_role
        btn_clear.callback = self.clear_roles
        btn_back.callback = self.back_to_wl_hub

        self.add_item(btn_add)
        self.add_item(btn_remove)
        self.add_item(btn_clear)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        if self.whitelisted_roles:
            role_lines = "\n".join([f"🛡️ <@&{rid}>" for rid in self.whitelisted_roles])
        else:
            role_lines = "🛡️ **No Whitelisted Roles**"

        embed = discord.Embed(
            title="Configure Role Whitelist",
            description=(
                "Trusted roles whose members receive **Full Whitelist Immunity**.\n\n"
                f"**Current Whitelisted Roles:**\n{role_lines}"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def add_role(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only administrators can manage whitelisted roles.", ephemeral=True)
        modal = AddWhitelistRoleDashboardModal(self)
        await interaction.response.send_modal(modal)

    async def remove_role(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only administrators can manage whitelisted roles.", ephemeral=True)
        modal = RemoveWhitelistRoleDashboardModal(self)
        await interaction.response.send_modal(modal)

    async def refresh_roles(self, interaction: discord.Interaction):
        await self.load_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def clear_roles(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ Only administrators can clear whitelisted roles.", ephemeral=True)

        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute("DELETE FROM whitelisted_roles WHERE guild_id = ?", (self.guild_id,))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.reset_whitelisted_roles(self.guild_id)

        self.whitelisted_roles = []
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_wl_hub(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.wl_hub_view.load_and_display(interaction)


# ==========================================================
# 🛡️ SUB-VIEW 3: CONFIGURE WHITELIST (INTERMEDIATE HUB)
# ==========================================================
class SecurityWhitelistHubSubView(discord.ui.View):
    def __init__(self, author, guild_id, main_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.main_view = main_view
        self.user_count = 0
        self.role_count = 0
        self.update_components()

    async def load_data(self):
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_users (
                    guild_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            async with db.execute("SELECT COUNT(*) FROM whitelisted_users WHERE guild_id = ?", (self.guild_id,)) as cursor:
                self.user_count = (await cursor.fetchone())[0]

            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
            ''')
            async with db.execute("SELECT COUNT(*) FROM whitelisted_roles WHERE guild_id = ?", (self.guild_id,)) as cursor:
                self.role_count = (await cursor.fetchone())[0]

        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_wl_all_access = discord.ui.Button(label="Whitelist All Access", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_hub_wl_all_access")
        btn_wl_role = discord.ui.Button(label="Whitelist Role", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_hub_wl_role")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_hub_wl_back")

        btn_wl_all_access.callback = self.goto_whitelist_all_access
        btn_wl_role.callback = self.goto_whitelist_role
        btn_back.callback = self.back_to_main

        self.add_item(btn_wl_all_access)
        self.add_item(btn_wl_role)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        embed = discord.Embed(
            title="Configure Whitelist",
            description=(
                "Manage trusted users and roles exempted from security actions.\n\n"
                f"**Whitelisted All Access Users:** `{self.user_count}`\n"
                f"**Whitelisted Roles:** `{self.role_count}`"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def load_and_display(self, interaction: discord.Interaction):
        await self.load_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def goto_whitelist_all_access(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        sub_view = SecurityUserWhitelistSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def goto_whitelist_role(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        sub_view = SecurityRoleWhitelistSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def goto_whitelist_role(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        sub_view = SecurityRoleWhitelistSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def back_to_main(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.main_view.load_and_display(interaction)


# ==========================================================
# 🌙 SUB-VIEW 4: CONFIGURE NIGHTMODE
# ==========================================================
class SecurityNightmodeSubView(discord.ui.View):
    def __init__(self, author, guild_id, main_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.main_view = main_view
        self.is_enabled = False
        self.auto_enabled = False
        self.log_channel_id = None
        self.update_components()

    async def load_data(self):
        async with aiosqlite.connect("db/anti.db", timeout=30.0) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS Nightmode (
                    guildId TEXT,
                    roleId TEXT,
                    adminPermissions INTEGER,
                    original_permissions INTEGER DEFAULT 0,
                    PRIMARY KEY (guildId, roleId)
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS nightmode_guilds (
                    guild_id INTEGER PRIMARY KEY
                )
            ''')
            async with db.execute("SELECT guild_id FROM nightmode_guilds WHERE guild_id = ?", (self.guild_id,)) as cursor:
                has_manual = bool(await cursor.fetchone())

            async with db.execute("SELECT COUNT(*) FROM Nightmode WHERE guildId = ?", (str(self.guild_id),)) as cursor:
                count = (await cursor.fetchone())[0]
                self.is_enabled = count > 0 or has_manual

            await db.execute('''
                CREATE TABLE IF NOT EXISTS nightmode_config (
                    guild_id INTEGER PRIMARY KEY,
                    auto_enabled INTEGER DEFAULT 0,
                    log_channel INTEGER,
                    start_hour INTEGER DEFAULT 0,
                    start_minute INTEGER DEFAULT 0,
                    start_second INTEGER DEFAULT 0,
                    end_hour INTEGER DEFAULT 6,
                    end_minute INTEGER DEFAULT 0,
                    end_second INTEGER DEFAULT 0,
                    start_time TEXT DEFAULT '00:00:00',
                    end_time TEXT DEFAULT '06:00:00',
                    timezone TEXT DEFAULT 'Asia/Kolkata',
                    last_action TEXT
                )
            ''')
            async with db.execute("SELECT auto_enabled, log_channel FROM nightmode_config WHERE guild_id = ?", (self.guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    self.auto_enabled = bool(row[0] == 1)
                    self.log_channel_id = row[1]
                else:
                    self.auto_enabled = False
                    self.log_channel_id = None
        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_enable = discord.ui.Button(label="Enable", style=discord.ButtonStyle.success, row=0, custom_id="btn_nm_enable")
        btn_disable = discord.ui.Button(label="Disable", style=discord.ButtonStyle.danger, row=0, custom_id="btn_nm_disable")
        
        # Explicit, unambiguous UI feedback
        auto_label = "Auto: ON" if self.auto_enabled else "Auto: OFF"
        auto_style = discord.ButtonStyle.success if self.auto_enabled else discord.ButtonStyle.secondary
        btn_auto = discord.ui.Button(label=auto_label, style=auto_style, row=0, custom_id="btn_nm_auto")
        
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_nm_back")

        btn_enable.callback = self.enable_nightmode
        btn_disable.callback = self.disable_nightmode
        btn_auto.callback = self.toggle_auto_nightmode
        btn_back.callback = self.back_to_main

        self.add_item(btn_enable)
        self.add_item(btn_disable)
        self.add_item(btn_auto)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        status_str = "**Active (Admin Stripped)**" if self.is_enabled else "**Inactive**"
        auto_str = "**Enabled (12:00 AM – 6:00 AM IST)**" if self.auto_enabled else "**Disabled**"
        log_str = f"<#{self.log_channel_id}>" if self.log_channel_id else "Auto-Created on Enable"

        import pytz
        tz_ist = pytz.timezone('Asia/Kolkata')
        ist_now = datetime.datetime.now(tz_ist).strftime('%I:%M:%S %p IST')

        embed = discord.Embed(
            title="🌙 Configure Nightmode",
            description=(
                "Prevent off-peak raids by automatically stripping administrator permissions from staff roles during the night in Indian Standard Time (IST).\n\n"
                f"**Current Status:** {status_str}\n"
                f"**Auto Nightmode Scheduler:** {auto_str}\n"
                f"**Logging Channel:** {log_str}\n"
                f"**Current Time (IST):** `{ist_now}`"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development • Nightmode Suite")
        return embed

    async def enable_nightmode(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)

        self.is_enabled = True

        # Step 1: Set up log channel and update config (quick DB, release connection)
        category = await get_or_create_yuna_logs_category(interaction.guild)
        style = detect_yuna_logs_style(interaction.guild, category)
        styled_nm_name = format_channel_name("nightmode", style, "Yuna")

        matching_channels = [
            ch for ch in interaction.guild.text_channels
            if (self.log_channel_id and ch.id == self.log_channel_id)
            or ch.name == styled_nm_name
            or identify_log_channel_type(ch.name) == "nightmode"
            or ch.name.lower() in ("yuna-nightmode", "nightmode-logs", "night-mode-logs")
        ]
        matching_channels = list({ch.id: ch for ch in matching_channels}.values())
        log_chan = None
        if matching_channels:
            log_chan = discord.utils.find(lambda c: c.name == styled_nm_name, matching_channels) or matching_channels[0]
            await ensure_channel_in_yuna_logs(interaction.guild, log_chan, category=category)
            if log_chan.name != styled_nm_name and interaction.guild.me.guild_permissions.manage_channels:
                try:
                    await log_chan.edit(name=styled_nm_name, reason="Yuna Nightmode: Standardize channel text style")
                except Exception:
                    pass
            if len(matching_channels) > 1 and interaction.guild.me.guild_permissions.manage_channels:
                for dup in matching_channels:
                    if dup.id != log_chan.id:
                        try:
                            await dup.delete(reason="Yuna Nightmode: Cleanup duplicate log channel")
                            await asyncio.sleep(0.3)
                        except Exception:
                            pass
        elif interaction.guild.me.guild_permissions.manage_channels:
            try:
                if not category:
                    category = await get_or_create_yuna_logs_category(interaction.guild)
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)
                }
                log_chan = await interaction.guild.create_text_channel(styled_nm_name, category=category, overwrites=overwrites)
            except Exception:
                pass
        self.log_channel_id = log_chan.id if log_chan else self.log_channel_id

        # Step 2: Identify manageable roles
        manageable_roles = [
            r for r in interaction.guild.roles
            if r.position < interaction.guild.me.top_role.position
            and r.name != "@everyone"
            and r.permissions.administrator
            and not r.managed
        ]

        # Step 3: Save original permissions to DB FIRST (crash-safe checkpoint)
        async with aiosqlite.connect("db/anti.db", timeout=30.0) as db:
            await db.execute("PRAGMA busy_timeout=30000;")
            if self.log_channel_id:
                await db.execute('''
                    INSERT INTO nightmode_config (guild_id, log_channel) VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET log_channel = excluded.log_channel
                ''', (self.guild_id, self.log_channel_id))

            for role in manageable_roles:
                # Don't overwrite existing saved state (partial crash recovery)
                async with db.execute(
                    'SELECT original_permissions FROM Nightmode WHERE guildId = ? AND roleId = ?',
                    (str(self.guild_id), str(role.id))
                ) as cursor:
                    existing = await cursor.fetchone()
                if not (existing and existing[0] and int(existing[0]) > 0):
                    await db.execute('''
                        INSERT OR REPLACE INTO Nightmode (guildId, roleId, adminPermissions, original_permissions)
                        VALUES (?, ?, ?, ?)
                    ''', (str(self.guild_id), str(role.id), int(discord.Permissions(administrator=True).value), role.permissions.value))

            await db.execute("INSERT OR REPLACE INTO nightmode_guilds (guild_id) VALUES (?)", (self.guild_id,))
            await db.commit()

        from utils.settings_manager import set_guild_setting
        set_guild_setting(self.guild_id, "nightmode", True)
        set_guild_setting(self.guild_id, "nightmode_manual", True)

        # Step 4: Strip admin permissions (slow Discord API calls, NO DB lock held)
        for role in manageable_roles:
            try:
                perms = role.permissions
                perms.administrator = False
                await role.edit(permissions=perms, reason="Security Dashboard Nightmode ENABLED")
            except Exception:
                pass

        # Step 5: Send activation audit log (no DB needed)
        if log_chan:
            import pytz
            tz_ist = pytz.timezone('Asia/Kolkata')
            now_ist = datetime.datetime.now(tz_ist)
            log_embed = discord.Embed(
                title="🌙 Nightmode Manually Activated (Dashboard)",
                description=(
                    f"**Moderator / Owner:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"**Roles Stripped:** `{len(manageable_roles)}` manageable role(s)\n"
                    f"**Time (IST):** `{now_ist.strftime('%I:%M:%S %p IST')}`"
                ),
                color=0xFF0000
            )
            log_embed.set_footer(text="❀ YUNΛ Nightmode Security")
            try:
                await log_chan.send(embed=log_embed)
            except Exception:
                pass

        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def disable_nightmode(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)

        self.is_enabled = False

        # Step 1: Read saved roles from DB (quick read, release connection)
        roles_to_restore = []
        async with aiosqlite.connect("db/anti.db", timeout=30.0) as db:
            await db.execute("PRAGMA busy_timeout=30000;")
            async with db.execute("SELECT roleId, adminPermissions, original_permissions FROM Nightmode WHERE guildId = ?", (str(self.guild_id),)) as cursor:
                roles_to_restore = await cursor.fetchall()

        # Step 2: Restore Discord roles (slow API calls, NO DB lock held)
        restored_ids = []
        for row in roles_to_restore:
            role_id_str = row[0]
            admin_val = row[1]
            original_perms = row[2] if len(row) > 2 else 0
            try:
                role = interaction.guild.get_role(int(role_id_str))
                if role:
                    if original_perms and int(original_perms) > 0:
                        restored_perms = discord.Permissions(int(original_perms))
                    else:
                        restored_perms = discord.Permissions(administrator=bool(admin_val))
                    await role.edit(permissions=restored_perms, reason="Security Dashboard Nightmode DISABLED")
                restored_ids.append(role_id_str)
            except Exception:
                restored_ids.append(role_id_str)  # Still clean up DB entry

        # Step 3: Clean up DB entries (quick write, release connection)
        async with aiosqlite.connect("db/anti.db", timeout=30.0) as db:
            await db.execute("PRAGMA busy_timeout=30000;")
            for role_id_str in restored_ids:
                await db.execute("DELETE FROM Nightmode WHERE guildId = ? AND roleId = ?", (str(self.guild_id), role_id_str))
            await db.execute("DELETE FROM Nightmode WHERE guildId = ?", (str(self.guild_id),))
            await db.execute("DELETE FROM nightmode_guilds WHERE guild_id = ?", (self.guild_id,))
            await db.commit()

        from utils.settings_manager import set_guild_setting
        set_guild_setting(self.guild_id, "nightmode", False)
        set_guild_setting(self.guild_id, "nightmode_manual", False)

        # Step 4: Send deactivation audit log (no DB needed)
        if self.log_channel_id:
            log_chan = interaction.guild.get_channel(self.log_channel_id)
            if log_chan:
                import pytz
                tz_ist = pytz.timezone('Asia/Kolkata')
                now_ist = datetime.datetime.now(tz_ist)
                log_embed = discord.Embed(
                    title="☀️ Nightmode Manually Deactivated (Dashboard)",
                    description=(
                        f"**Moderator / Owner:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                        f"**Roles Restored:** `{len(roles_to_restore)}` role(s)\n"
                        f"**Time (IST):** `{now_ist.strftime('%I:%M:%S %p IST')}`"
                    ),
                    color=0x00FF88
                )
                log_embed.set_footer(text="❀ YUNΛ Nightmode Security")
                try:
                    await log_chan.send(embed=log_embed)
                except Exception:
                    pass

        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def toggle_auto_nightmode(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)

        self.auto_enabled = not self.auto_enabled

        if self.auto_enabled:
            # Step 1: Set up log channel (no DB needed)
            category = await get_or_create_yuna_logs_category(interaction.guild)
            style = detect_yuna_logs_style(interaction.guild, category)
            styled_nm_name = format_channel_name("nightmode", style, "Yuna")

            matching_channels = [
                ch for ch in interaction.guild.text_channels
                if (self.log_channel_id and ch.id == self.log_channel_id)
                or ch.name == styled_nm_name
                or identify_log_channel_type(ch.name) == "nightmode"
                or ch.name.lower() in ("yuna-nightmode", "nightmode-logs", "night-mode-logs")
            ]
            matching_channels = list({ch.id: ch for ch in matching_channels}.values())
            log_chan = None
            if matching_channels:
                log_chan = discord.utils.find(lambda c: c.name == styled_nm_name, matching_channels) or matching_channels[0]
                await ensure_channel_in_yuna_logs(interaction.guild, log_chan, category=category)
                if log_chan.name != styled_nm_name and interaction.guild.me.guild_permissions.manage_channels:
                    try:
                        await log_chan.edit(name=styled_nm_name, reason="Yuna Nightmode: Standardize channel text style")
                    except Exception:
                        pass
                if len(matching_channels) > 1 and interaction.guild.me.guild_permissions.manage_channels:
                    for dup in matching_channels:
                        if dup.id != log_chan.id:
                            try:
                                await dup.delete(reason="Yuna Nightmode: Cleanup duplicate log channel")
                                await asyncio.sleep(0.3)
                            except Exception:
                                pass
            elif interaction.guild.me.guild_permissions.manage_channels:
                try:
                    if not category:
                        category = await get_or_create_yuna_logs_category(interaction.guild)
                    overwrites = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)
                    }
                    log_chan = await interaction.guild.create_text_channel(styled_nm_name, category=category, overwrites=overwrites)
                except Exception:
                    pass

            self.log_channel_id = log_chan.id if log_chan else None

            # Step 2: Read existing schedule from DB and check night window
            async with aiosqlite.connect("db/anti.db", timeout=15) as db:
                async with db.execute(
                    "SELECT start_hour, start_minute, start_second, end_hour, end_minute, end_second, timezone FROM nightmode_config WHERE guild_id = ?",
                    (self.guild_id,)
                ) as cursor:
                    s_row = await cursor.fetchone()

                s_h = s_row[0] if s_row and s_row[0] is not None else 0
                s_m = s_row[1] if s_row and len(s_row) > 1 and s_row[1] is not None else 0
                s_s = s_row[2] if s_row and len(s_row) > 2 and s_row[2] is not None else 0
                e_h = s_row[3] if s_row and len(s_row) > 3 and s_row[3] is not None else 6
                e_m = s_row[4] if s_row and len(s_row) > 4 and s_row[4] is not None else 0
                e_s = s_row[5] if s_row and len(s_row) > 5 and s_row[5] is not None else 0
                tz_name = s_row[6] if s_row and len(s_row) > 6 and s_row[6] else "Asia/Kolkata"

                import pytz
                try:
                    tz = pytz.timezone(tz_name)
                except Exception:
                    tz = pytz.timezone('Asia/Kolkata')
                now_tz = datetime.datetime.now(tz)

                # Evaluate window
                now_t = now_tz.time()
                try:
                    st_t = datetime.time(s_h, s_m, s_s)
                    en_t = datetime.time(e_h, e_m, e_s)
                    if st_t == en_t:
                        is_night_now = False
                    elif st_t > en_t:
                        is_night_now = now_t >= st_t or now_t < en_t
                    else:
                        is_night_now = st_t <= now_t < en_t
                except Exception:
                    is_night_now = False

                last_act = f"enabled_{now_tz.strftime('%H_%M_%S')}" if is_night_now else None

                manageable_roles = []
                if is_night_now:
                    manageable_roles = [
                        r for r in interaction.guild.roles
                        if r.position < interaction.guild.me.top_role.position
                        and r.name != "@everyone"
                        and r.permissions.administrator
                        and not r.managed
                    ]

                await db.execute('''
                    INSERT INTO nightmode_config (guild_id, auto_enabled, log_channel, last_action)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        auto_enabled = 1,
                        log_channel = COALESCE(excluded.log_channel, nightmode_config.log_channel),
                        last_action = excluded.last_action
                ''', (self.guild_id, self.log_channel_id, last_act))

                for r in manageable_roles:
                    async with db.execute(
                        'SELECT original_permissions FROM Nightmode WHERE guildId = ? AND roleId = ?',
                        (str(self.guild_id), str(r.id))
                    ) as cursor:
                        existing = await cursor.fetchone()
                    if not (existing and existing[0] and int(existing[0]) > 0):
                        await db.execute('''
                            INSERT OR REPLACE INTO Nightmode (guildId, roleId, adminPermissions, original_permissions)
                            VALUES (?, ?, ?, ?)
                        ''', (str(self.guild_id), str(r.id), int(discord.Permissions(administrator=True).value), r.permissions.value))
                await db.commit()

            # Step 3: Strip admin permissions (slow Discord API calls, NO DB lock held)
            if is_night_now:
                for r in manageable_roles:
                    try:
                        perms = r.permissions
                        perms.administrator = False
                        await r.edit(permissions=perms, reason="Auto Nightmode Immediate Activation")
                    except Exception:
                        pass
                self.is_enabled = True
        else:
            # Disabling auto: just update config and restore if not under manual lockdown
            async with aiosqlite.connect("db/anti.db", timeout=15) as db:
                await db.execute("UPDATE nightmode_config SET auto_enabled = 0, last_action = 'disabled_manual' WHERE guild_id = ?", (self.guild_id,))
                await db.commit()

                async with db.execute("SELECT guild_id FROM nightmode_guilds WHERE guild_id = ?", (self.guild_id,)) as c:
                    is_manually_enabled = bool(await c.fetchone())

                if not is_manually_enabled:
                    async with db.execute("SELECT roleId, adminPermissions, original_permissions FROM Nightmode WHERE guildId = ?", (str(self.guild_id),)) as cursor:
                        roles_to_restore = await cursor.fetchall()
                    for row in roles_to_restore:
                        role_id_str, admin_val = row[0], row[1]
                        orig_p = row[2] if len(row) > 2 else 0
                        try:
                            role = interaction.guild.get_role(int(role_id_str))
                            if role:
                                perms = discord.Permissions(int(orig_p)) if orig_p else discord.Permissions(administrator=bool(admin_val))
                                await role.edit(permissions=perms, reason="Auto Nightmode Disabled — Roles Restored")
                        except Exception:
                            pass
                    await db.execute("DELETE FROM Nightmode WHERE guildId = ?", (str(self.guild_id),))
                    await db.commit()
                    self.is_enabled = False

        set_guild_setting(self.guild_id, "nightmode_auto", self.auto_enabled)
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_main(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This control panel is only for the command author.", ephemeral=True)
        await self.main_view.load_and_display(interaction)


# ==========================================================
# 🏠 MAIN VIEW: CONFIGURE SECURITY
# ==========================================================
class SecurityMainView(discord.ui.View):
    def __init__(self, author, guild_id, cog):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.cog = cog
        self.antinuke_status = False
        self.extra_owners = []
        self.update_components()

    async def load_hub_data(self):
        async with aiosqlite.connect("db/anti.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS antinuke (
                    guild_id INTEGER PRIMARY KEY,
                    status BOOLEAN DEFAULT 0,
                    log_channel INTEGER
                )
            ''')
            async with db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (self.guild_id,)) as cursor:
                row = await cursor.fetchone()
                self.antinuke_status = bool(row and row[0] in (1, "on", True, "true"))

            await db.execute('''
                CREATE TABLE IF NOT EXISTS extraowners (
                    guild_id INTEGER PRIMARY KEY,
                    owner_id INTEGER
                )
            ''')
            async with db.execute("SELECT owner_id FROM extraowners WHERE guild_id = ?", (self.guild_id,)) as cursor:
                self.extra_owners = [r[0] for r in await cursor.fetchall()]

        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_protection = discord.ui.Button(label="Protection", style=discord.ButtonStyle.secondary, row=0, custom_id="sec_btn_prot")
        btn_extraowner = discord.ui.Button(label="Extraowner", style=discord.ButtonStyle.secondary, row=0, custom_id="sec_btn_eo")
        btn_whitelist = discord.ui.Button(label="Whitelist", style=discord.ButtonStyle.secondary, row=0, custom_id="sec_btn_wl")
        btn_nightmode = discord.ui.Button(label="Nightmode", style=discord.ButtonStyle.secondary, row=0, custom_id="sec_btn_nm")
        btn_close = discord.ui.Button(emoji="❌", style=discord.ButtonStyle.danger, row=0, custom_id="sec_btn_close")

        btn_protection.callback = self.goto_protection
        btn_extraowner.callback = self.goto_extraowner
        btn_whitelist.callback = self.goto_whitelist
        btn_nightmode.callback = self.goto_nightmode
        btn_close.callback = self.close_panel

        self.add_item(btn_protection)
        self.add_item(btn_extraowner)
        self.add_item(btn_whitelist)
        self.add_item(btn_nightmode)
        self.add_item(btn_close)

    def build_embed(self, guild) -> discord.Embed:
        status_text = "Enabled" if self.antinuke_status else "Disabled"

        if self.extra_owners:
            extra_text = "\n".join([f"<a:arrow:1557834336571494480> <@{oid}>" for oid in self.extra_owners])
        else:
            extra_text = "<a:arrow:1557834336571494480> **None**"

        embed = discord.Embed(
            title="Configure Security",
            description=(
                "Enhance server security with `protection`, `extraowner`, `whitelist`, and `nightmode`.\n\n"
                f"**Current Status:** {status_text}\n\n"
                f"**Current Extraowners:**\n{extra_text}"
            ),
            color=0x2B2D31
        )
        embed.set_footer(text="Powered by Yuna Development")
        return embed

    async def load_and_display(self, interaction: discord.Interaction):
        await self.load_hub_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def goto_protection(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        sub_view = SecurityProtectionHubSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def goto_extraowner(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        sub_view = SecurityExtraownerSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def goto_whitelist(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        sub_view = SecurityWhitelistHubSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def goto_nightmode(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        sub_view = SecurityNightmodeSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def close_panel(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            await interaction.response.edit_message(content="*Security panel closed.*", embed=None, view=None)


class SecurityDashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="security", aliases=["sec", "guard", "securitypanel", "securityui"], help="Open the Configure Security Control Center.", with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def security(self, ctx: commands.Context):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.send(embed=embed)

        view = SecurityMainView(ctx.author, guild_id, self)
        await view.load_hub_data()
        embed = view.build_embed(ctx.guild)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(SecurityDashboard(bot))
