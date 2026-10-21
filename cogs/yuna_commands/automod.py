import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *

class ShowRules(discord.ui.View):
    def __init__(self, author, selected_events):
        super().__init__(timeout=60)
        self.author = author
        self.selected_events = selected_events

    @discord.ui.button(label="Show Rules", style=discord.ButtonStyle.secondary)
    async def show_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            await interaction.response.send_message("You are not allowed to interact with this button.", ephemeral=True)
            return

        rules = {
            "Anti NSFW link": "__**Anti NSFW Link**__:\n• Takes action if the message contains a NSFW link.\n• Default punishment: Block message (unchangeable)",
            "Anti caps": "__**Anti Caps**__:\n• Takes action if the message contains >70% caps.\n• Messages under 45 characters are bypassed\n• Default punishment: Mute (1 minutes)",
            "Anti link": "__**Anti Link**__:\n• Takes action if the message contains a link.\n• Server invites, Spotify Music and GIF links are bypassed\n• Default punishment: Mute (7 minutes)",
            "Anti invites": "__**Anti Invites**__:\n• Takes action if the message contains a Discord server invite.\n• Invites from the current server are bypassed\n• Default punishment: Mute (12 minutes)",
            "Anti emoji spam": "__**Anti Emoji Spam**__:\n• Takes action if a message contains more than 5 emojis.\n• Default punishment: Mute (1 minute)",
            "Anti mass mention": "__**Anti Mass Mention**__:\n• Takes action if a message contains more than 4 mentions.\n• Default punishment: Mute (3 minutes)",
            "Anti everyone": "__**Anti Everyone / Here**__:\n• Takes action if a message mentions @everyone or @here.\n• Default punishment: None (Disabled)",
            "Anti spam": "__**Anti Spam**__:\n• Takes action if more than 5 messages are sent rapidly in a short time.\n• Default punishment: Mute (12 minutes)",
        }

        enabled_rules = "\n\n".join([rules[event] for event in self.selected_events if event in rules])

        embed = discord.Embed(title="Enabled Automod Rules", description=enabled_rules or "No specific rules active.", color=0xff0000)
        embed.set_footer(text="Punishment type of each event is changeable except for Anti NSFW.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CustomMuteDurationModal(discord.ui.Modal, title="Set Mute / Timeout Duration"):
    duration_input = discord.ui.TextInput(
        label="Mute / Timeout Timer",
        placeholder="e.g. 60s, 1m, 15m, 1h, 1d, 7d (Max 28d)",
        required=True,
        max_length=20
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        from utils.Tools import parse_duration_string
        raw_val = self.duration_input.value.strip()
        parsed = parse_duration_string(raw_val)
        if not parsed:
            return await interaction.response.send_message(
                "❌ Invalid duration format. Please enter a valid timer like `60s`, `1m`, `5m`, `15m`, `1h`, `1d`, `7d` (up to 28 days max).",
                ephemeral=True
            )

        td, label = parsed
        punishment_str = f"Mute ({label})"
        await self.parent_view.set_punishment(interaction, punishment_str)


class CustomThresholdModal(discord.ui.Modal, title="Set Trigger Limit / Count"):
    threshold_input = discord.ui.TextInput(
        label="Trigger Limit / Count Threshold",
        placeholder="e.g. 5 for spam/emojis/pings, 70 for caps %, 1 for links",
        required=True,
        max_length=5
    )

    def __init__(self, parent_view, selected_event):
        super().__init__()
        self.parent_view = parent_view
        self.selected_event = selected_event

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.threshold_input.value.strip()
        if not raw_val.isdigit():
            return await interaction.response.send_message("❌ Please enter a valid positive number for threshold count.", ephemeral=True)

        val = max(1, min(100, int(raw_val)))
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS automod_thresholds (guild_id INTEGER, event TEXT, threshold INTEGER, PRIMARY KEY (guild_id, event))")
            await db.execute("INSERT OR REPLACE INTO automod_thresholds (guild_id, event, threshold) VALUES (?, ?, ?)", (self.parent_view.guild_id, self.selected_event, val))
            await db.commit()

        self.parent_view.current_thresholds[self.selected_event] = val
        embed = self.parent_view.build_embed(interaction.guild)
        await interaction.response.send_message(f"✅ Set trigger limit threshold for **{self.selected_event}** to **{val}**.", ephemeral=True)
        try:
            if interaction.message:
                await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self.parent_view)
        except Exception:
            pass


class AutoModPunishmentSubView(discord.ui.View):
    def __init__(self, author, guild_id, current_punishments, hub_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.current_punishments = {ev: p for ev, p in current_punishments}
        self.current_thresholds = {
            "Anti link": 1,
            "Anti invites": 1,
            "Anti spam": 5,
            "Anti caps": 70,
            "Anti mass mention": 5,
            "Anti emoji spam": 5
        }
        self.hub_view = hub_view
        self.selected_event = "Anti link"
        self.update_components()

    def update_components(self):
        self.clear_items()

        events_list = [
            ("Anti link", "Anti-Link", "Unauthorized HTTP/HTTPS links"),
            ("Anti invites", "Anti-Invites", "Discord server invite links"),
            ("Anti spam", "Anti-Spam", "Rapid messages & repeat text"),
            ("Anti caps", "Anti-Caps", "Excessive uppercase messages"),
            ("Anti mass mention", "Anti-Mass Mention", "Mass user mentions and pings"),
            ("Anti everyone", "Anti-Everyone / Here", "@everyone and @here mention filter"),
            ("Anti emoji spam", "Anti-Emoji Spam", "Excessive emoji flooding"),
        ]

        options = []
        for raw_event, label, desc in events_list:
            current_p = self.current_punishments.get(raw_event, "None")
            options.append(
                discord.SelectOption(
                    label=label,
                    value=raw_event,
                    description=f"Active: {current_p} • {desc}"[:100],
                    default=(raw_event == self.selected_event)
                )
            )

        select = discord.ui.Select(
            placeholder="Select an AutoMod event to configure...",
            options=options,
            min_values=1,
            max_values=1,
            row=0
        )
        select.callback = self.on_select_event
        self.add_item(select)

        # Row 1: None (Default), Mute, Kick, Ban, Back
        btn_none = discord.ui.Button(label="None (Default)", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_p_none")
        btn_mute = discord.ui.Button(label="Mute", style=discord.ButtonStyle.primary, row=1, custom_id="btn_p_mute")
        btn_kick = discord.ui.Button(label="Kick", style=discord.ButtonStyle.danger, row=1, custom_id="btn_p_kick")
        btn_ban = discord.ui.Button(label="Ban", style=discord.ButtonStyle.danger, row=1, custom_id="btn_p_ban")
        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=1, custom_id="btn_p_back")

        btn_none.callback = lambda i: self.set_punishment(i, "None")
        btn_mute.callback = self.open_mute_modal
        btn_kick.callback = lambda i: self.set_punishment(i, "Kick")
        btn_ban.callback = lambda i: self.set_punishment(i, "Ban")
        btn_back.callback = self.back_to_hub

        self.add_item(btn_none)
        self.add_item(btn_mute)
        self.add_item(btn_kick)
        self.add_item(btn_ban)

        # Row 2: Trigger Limit Threshold & Back
        btn_limit = discord.ui.Button(label="Set Trigger Limit / Count", style=discord.ButtonStyle.secondary, row=2, custom_id="btn_p_limit")
        btn_limit.callback = self.open_threshold_modal
        self.add_item(btn_limit)
        self.add_item(btn_back)

    async def open_mute_modal(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        modal = CustomMuteDurationModal(self)
        await interaction.response.send_modal(modal)

    async def open_threshold_modal(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        modal = CustomThresholdModal(self, self.selected_event)
        await interaction.response.send_modal(modal)

    def build_embed(self, guild) -> discord.Embed:
        embed = discord.Embed(
            title=f"AutoMod Punishment Manager — {guild.name}",
            description=(
                "Configure how Yuna punishes rule violators for each security filter.\n"
                "• **Step 1:** Select an event from the dropdown.\n"
                "• **Step 2:** Click a punishment button (`Mute`, `Kick`, `Ban`, `None`) or `Set Trigger Limit`.\n\n"
                f"**Currently Selected:** **`{self.selected_event}`**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0x2B2D31
        )

        event_labels = {
            "Anti link": "Anti-Link",
            "Anti invites": "Anti-Invites",
            "Anti spam": "Anti-Spam",
            "Anti caps": "Anti-Caps",
            "Anti mass mention": "Anti-Mass Mention",
            "Anti everyone": "Anti-Everyone / Here",
            "Anti emoji spam": "Anti-Emoji Spam",
            "Anti NSFW link": "Anti-NSFW Link"
        }

        status_text = []
        for ev, lbl in event_labels.items():
            if ev == "Anti NSFW link":
                p_val = "Block Message (Auto)"
            else:
                p_val = self.current_punishments.get(ev, "None")
                if p_val in (None, "None", "Disabled", ""):
                    p_val = "None (Default)"
                elif p_val == "Ban":
                    p_val = "Ban"
                elif p_val == "Kick":
                    p_val = "Kick"
                else:
                    p_val = f"{p_val}"

            th_val = self.current_thresholds.get(ev)
            limit_str = f" [Limit: {th_val}]" if th_val else ""

            selected_mark = " (Selected)" if ev == self.selected_event else ""
            status_text.append(f"• **{lbl}**: {p_val}{limit_str}{selected_mark}")

        embed.add_field(
            name="Active Filters & Punishments",
            value="\n".join(status_text),
            inline=False
        )

        embed.set_footer(text=f"Requested by {self.author} • AutoMod Suite", icon_url=self.author.display_avatar.url)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    async def on_select_event(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        
        self.selected_event = interaction.data["values"][0]
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def set_punishment(self, interaction: discord.Interaction, punishment: str):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)

        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("INSERT OR REPLACE INTO automod (guild_id, enabled) VALUES (?, 1)", (self.guild_id,))
            if punishment in ("None", "Disabled"):
                self.current_punishments.pop(self.selected_event, None)
                await db.execute("DELETE FROM automod_punishments WHERE guild_id = ? AND event = ?", (self.guild_id, self.selected_event))
            else:
                self.current_punishments[self.selected_event] = punishment
                await db.execute("INSERT OR REPLACE INTO automod_punishments (guild_id, event, punishment) VALUES (?, ?, ?)", (self.guild_id, self.selected_event, punishment))
            await db.commit()

        from utils.settings_manager import set_guild_setting
        set_guild_setting(self.guild_id, "automod", True)
        try:
            from cogs.yuna_automod.cache import automod_cache
            automod_cache.invalidate(self.guild_id)
        except Exception:
            pass

        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_hub(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        await self.hub_view.load_and_display(interaction)


class AutoModIgnoreSubView(discord.ui.View):
    def __init__(self, author, guild_id, hub_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.hub_view = hub_view
        self.ignored_channels = []
        self.ignored_roles = []
        self.update_components()

    async def load_data(self):
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_ignored (
                    guild_id INTEGER,
                    type TEXT,
                    id INTEGER,
                    PRIMARY KEY (guild_id, type, id)
                )
            """)
            cursor = await db.execute("SELECT type, id FROM automod_ignored WHERE guild_id = ?", (self.guild_id,))
            items = await cursor.fetchall()
            self.ignored_channels = [item_id for item_type, item_id in items if item_type == "channel"]
            self.ignored_roles = [item_id for item_type, item_id in items if item_type == "role"]
        self.update_components()

    def update_components(self):
        self.clear_items()

        # Row 0: Channel Select to Ignore / Unignore (No symbols)
        chan_select = discord.ui.ChannelSelect(
            placeholder="Select Channel to Ignore / Unignore...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            row=0
        )
        chan_select.callback = self.toggle_channel_ignore
        self.add_item(chan_select)

        # Row 1: Role Select to Ignore / Unignore (No symbols)
        role_select = discord.ui.RoleSelect(
            placeholder="Select Role to Ignore / Unignore...",
            min_values=1,
            max_values=1,
            row=1
        )
        role_select.callback = self.toggle_role_ignore
        self.add_item(role_select)

        # Row 2: Reset Button + Back Button (No symbols)
        btn_reset = discord.ui.Button(label="Reset All", style=discord.ButtonStyle.danger, row=2, custom_id="btn_ig_reset")
        btn_reset.callback = self.reset_ignored

        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=2, custom_id="btn_ig_back")
        btn_back.callback = self.back_to_hub

        self.add_item(btn_reset)
        self.add_item(btn_back)

    def build_embed(self, guild) -> discord.Embed:
        chan_lines = [f"• <#{cid}> (`{cid}`)" for cid in self.ignored_channels] if self.ignored_channels else ["*No channels ignored.*"]
        role_lines = [f"• <@&{rid}> (`{rid}`)" for rid in self.ignored_roles] if self.ignored_roles else ["*No roles ignored.*"]

        embed = discord.Embed(
            title=f"AutoMod Ignored Channels & Roles — {guild.name}",
            description=(
                "Whitelisted channels and roles bypass all AutoMod filters (Links, Invites, Spam, Caps, Mentions, Emojis).\n\n"
                "**Ignored Channels:**\n" + "\n".join(chan_lines) + "\n\n"
                "**Ignored Roles:**\n" + "\n".join(role_lines) + "\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Select a channel or role from dropdowns below to toggle ignore status."
            ),
            color=0x2B2D31
        )
        embed.set_footer(text=f"Requested by {self.author} • AutoMod Suite", icon_url=self.author.display_avatar.url)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    async def toggle_channel_ignore(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)

        channel = interaction.data["values"][0]
        channel_id = int(channel)

        async with aiosqlite.connect("db/automod.db") as db:
            if channel_id in self.ignored_channels:
                await db.execute("DELETE FROM automod_ignored WHERE guild_id = ? AND type = 'channel' AND id = ?", (self.guild_id, channel_id))
            else:
                await db.execute("INSERT OR REPLACE INTO automod_ignored (guild_id, type, id) VALUES (?, 'channel', ?)", (self.guild_id, channel_id))
            await db.commit()

        await self.load_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def toggle_role_ignore(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)

        role_id = int(interaction.data["values"][0])

        async with aiosqlite.connect("db/automod.db") as db:
            if role_id in self.ignored_roles:
                await db.execute("DELETE FROM automod_ignored WHERE guild_id = ? AND type = 'role' AND id = ?", (self.guild_id, role_id))
            else:
                await db.execute("INSERT OR REPLACE INTO automod_ignored (guild_id, type, id) VALUES (?, 'role', ?)", (self.guild_id, role_id))
            await db.commit()

        await self.load_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def reset_ignored(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)

        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("DELETE FROM automod_ignored WHERE guild_id = ?", (self.guild_id,))
            await db.commit()

        self.ignored_channels = []
        self.ignored_roles = []
        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_hub(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        await self.hub_view.load_and_display(interaction)


class AutoModConfigSubView(discord.ui.View):
    def __init__(self, author, guild_id, hub_view):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.hub_view = hub_view
        self.update_components()

    def update_components(self):
        self.clear_items()

        btn_back = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, row=0, custom_id="btn_cfg_back")
        btn_back.callback = self.back_to_hub

        btn_refresh = discord.ui.Button(label="Refresh", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_cfg_rf")
        btn_refresh.callback = self.refresh_view

        self.add_item(btn_back)
        self.add_item(btn_refresh)

    def build_embed(self, guild, is_enabled, punishments, log_channel_id, ignored_ch_count, ignored_role_count, bot_spam_enabled) -> discord.Embed:
        status_badge = "ENABLED" if is_enabled else "DISABLED"
        bot_spam_badge = "Active" if bot_spam_enabled else "Disabled"
        log_mention = f"<#{log_channel_id}>" if log_channel_id else "None"

        embed = discord.Embed(
            title=f"Full AutoMod Configuration — {guild.name}",
            description=(
                f"**Overall Status:** `{status_badge}`\n"
                f"**Bot Spam Raid Shield:** `{bot_spam_badge}`\n"
                f"**Logging Channel:** {log_mention}\n\n"
                f"**Whitelist Summary:**\n"
                f"• Ignored Channels: `{ignored_ch_count}`\n"
                f"• Ignored Roles: `{ignored_role_count}`\n\n"
                "**Active Filter Punishments:**"
            ),
            color=0x00FF88 if is_enabled else 0xFF0055
        )

        events_list = [
            ("Anti link", "Anti-Link"),
            ("Anti invites", "Anti-Invites"),
            ("Anti spam", "Anti-Spam"),
            ("Anti caps", "Anti-Caps"),
            ("Anti mass mention", "Anti-Mass Mention"),
            ("Anti emoji spam", "Anti-Emoji Spam"),
        ]

        for raw_ev, label in events_list:
            p_val = punishments.get(raw_ev, "Disabled")
            p_display = f"`{p_val}`" if (is_enabled and p_val not in (None, "None", "Disabled", "")) else "*Disabled*"
            embed.add_field(name=label, value=p_display, inline=True)

        embed.set_footer(text=f"Requested by {self.author} • AutoMod Suite", icon_url=self.author.display_avatar.url)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    async def refresh_view(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        await self.hub_view.load_and_display_config(interaction, self)

    async def back_to_hub(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        await self.hub_view.load_and_display(interaction)


async def ensure_automod_log_channel(guild: discord.Guild, db=None) -> int:
    """
    Finds or creates the official AutoMod log channel for a guild.
    - Searches existing text channels matching 'yuna-automod' or 'automod'.
    - Keeps the oldest created channel (first created by date/time).
    - Deletes any extra/duplicate automod log channels.
    - Creates 'yuna-automod' if no automod channel exists.
    - Saves the log channel ID in db/automod.db -> automod_logging.
    """
    if not guild:
        return None

    channels = getattr(guild, "text_channels", [])
    if not channels and hasattr(guild, "channels"):
        channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]

    category = await get_or_create_yuna_logs_category(guild)
    style = detect_yuna_logs_style(guild, category)
    styled_am_name = format_channel_name("automod", style, "Yuna")

    matching_channels = []
    for ch in channels:
        if ch.name == styled_am_name or identify_log_channel_type(ch.name) == "automod" or "automod" in ch.name.lower():
            matching_channels.append(ch)
    matching_channels = list({ch.id: ch for ch in matching_channels}.values())

    stored_channel_id = None
    try:
        from core.database.connection_pool import db_pool
        row = await db_pool.fetch_one('db/automod.db', "SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
        if row and row[0]:
            stored_channel_id = int(row[0])
    except Exception:
        pass

    target_channel = None
    if matching_channels:
        if stored_channel_id:
            stored_ch = discord.utils.get(matching_channels, id=stored_channel_id)
            if stored_ch:
                target_channel = stored_ch
        if not target_channel:
            target_channel = discord.utils.find(lambda c: c.name == styled_am_name, matching_channels)
        if not target_channel:
            matching_channels.sort(key=lambda c: getattr(c, 'created_at', None) or c.id)
            target_channel = matching_channels[0]

        await ensure_channel_in_yuna_logs(guild, target_channel, category=category)
        if target_channel.name != styled_am_name and getattr(guild.me, "guild_permissions", None) and guild.me.guild_permissions.manage_channels:
            try:
                await target_channel.edit(name=styled_am_name, reason="Yuna AutoMod: Standardize channel text style")
            except Exception:
                pass

        # Delete any extra duplicate channels created later
        for extra_ch in matching_channels:
            if extra_ch.id != target_channel.id:
                try:
                    await extra_ch.delete(reason="Cleaning duplicate AutoMod channels (kept primary channel)")
                    await asyncio.sleep(0.3)
                except Exception as e:
                    print(f"[AUTOMOD LOG CLEANUP ERROR] {e}")
    else:
        me = guild.me
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False)
        }
        if me:
            overwrites[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)

        try:
            if not category:
                category = await get_or_create_yuna_logs_category(guild)
            target_channel = await guild.create_text_channel(
                name=styled_am_name,
                category=category,
                topic="Official AutoMod Logging Channel",
                overwrites=overwrites,
                reason="AutoMod Enabled: Automatically created log channel"
            )
            print(f"[AUTOMOD LOG CREATED] Successfully created {styled_am_name} channel ({target_channel.id}) for guild {guild.id}")
        except Exception as e:
            print(f"[AUTOMOD LOG CREATE ERROR] Failed to create {styled_am_name} channel in guild {guild.id}: {e}")

    if target_channel:
        if db:
            await db.execute("CREATE TABLE IF NOT EXISTS automod_logging (guild_id INTEGER PRIMARY KEY, log_channel INTEGER)")
            await db.execute("INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?, ?)", (guild.id, target_channel.id))
        else:
            async with aiosqlite.connect("db/automod.db", timeout=30.0) as local_db:
                await local_db.execute("CREATE TABLE IF NOT EXISTS automod_logging (guild_id INTEGER PRIMARY KEY, log_channel INTEGER)")
                await local_db.execute("INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?, ?)", (guild.id, target_channel.id))
                await local_db.commit()
        return target_channel.id
    return None


class AutoModControlView(discord.ui.View):
    def __init__(self, author, guild_id, is_enabled, current_punishments, log_channel_id, cog):
        super().__init__(timeout=180)
        self.author = author
        self.guild_id = guild_id
        self.is_enabled = is_enabled
        self.current_punishments = {ev: p for ev, p in current_punishments}
        self.log_channel_id = log_channel_id
        self.bot_spam_enabled = True
        self.ignored_ch_count = 0
        self.ignored_role_count = 0
        self.cog = cog
        self.update_components()

    async def load_hub_data(self):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT enabled FROM automod WHERE guild_id = ?", (self.guild_id,))
            row = await cursor.fetchone()
            self.is_enabled = bool(row and row[0] == 1)

            cursor = await db.execute("SELECT event, punishment FROM automod_punishments WHERE guild_id = ?", (self.guild_id,))
            self.current_punishments = {r[0]: r[1] for r in await cursor.fetchall()}

            cursor = await db.execute("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (self.guild_id,))
            row = await cursor.fetchone()
            self.log_channel_id = row[0] if row else None

            cursor = await db.execute("SELECT COUNT(*) FROM automod_ignored WHERE guild_id = ? AND type = 'channel'", (self.guild_id,))
            self.ignored_ch_count = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM automod_ignored WHERE guild_id = ? AND type = 'role'", (self.guild_id,))
            self.ignored_role_count = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT enabled FROM bot_spam_protection WHERE guild_id = ?", (str(self.guild_id),))
            row = await cursor.fetchone()
            self.bot_spam_enabled = True if (row is None or row[0] == 1) else False

        self.update_components()

    def update_components(self):
        self.clear_items()

        # Row 0: Master Quick Controls (No symbols/emojis)
        if self.is_enabled:
            btn_toggle = discord.ui.Button(label="Disable AutoMod", style=discord.ButtonStyle.danger, row=0, custom_id="btn_toggle")
        else:
            btn_toggle = discord.ui.Button(label="Enable AutoMod", style=discord.ButtonStyle.success, row=0, custom_id="btn_toggle")
        btn_toggle.callback = self.toggle_automod

        btn_all_mute = discord.ui.Button(label="Set All Mute", style=discord.ButtonStyle.primary, row=0, custom_id="btn_all_mute")
        btn_all_mute.callback = self.set_all_mute

        btn_log = discord.ui.Button(label="Setup Logging", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_log")
        btn_log.callback = self.setup_logging

        btn_bot_spam = discord.ui.Button(label="Anti Bot-Spam", style=discord.ButtonStyle.primary if self.bot_spam_enabled else discord.ButtonStyle.secondary, row=0, custom_id="btn_bot_spam")
        btn_bot_spam.callback = self.toggle_bot_spam

        self.add_item(btn_toggle)
        self.add_item(btn_all_mute)
        self.add_item(btn_log)
        self.add_item(btn_bot_spam)

        # Row 1: Sub-View Navigation Buttons (No symbols/emojis)
        btn_punishments = discord.ui.Button(label="Punishments", style=discord.ButtonStyle.primary, row=1, custom_id="btn_nav_punish")
        btn_ignored = discord.ui.Button(label="Ignored Roles/Channels", style=discord.ButtonStyle.primary, row=1, custom_id="btn_nav_ignored")
        btn_config = discord.ui.Button(label="Full Config", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_nav_config")
        btn_refresh = discord.ui.Button(label="Refresh", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_refresh")

        btn_punishments.callback = self.goto_punishments
        btn_ignored.callback = self.goto_ignored
        btn_config.callback = self.goto_config
        btn_refresh.callback = self.refresh_view

        self.add_item(btn_punishments)
        self.add_item(btn_ignored)
        self.add_item(btn_config)
        self.add_item(btn_refresh)

    def build_embed(self, guild) -> discord.Embed:
        status_badge = "ENABLED" if self.is_enabled else "DISABLED"
        
        embed = discord.Embed(
            title=f"AutoMod Control Center — {guild.name}",
            description=(
                f"**System Status:** `{status_badge}`\n"
                "Control all AutoMod features using the buttons below.\n\n"
                f"**Bot Spam Raid Shield:** `{'Active' if self.bot_spam_enabled else 'Disabled'}`\n"
                f"**Ignored List:** `{self.ignored_ch_count} Channels` • `{self.ignored_role_count} Roles`\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0x00FF88 if self.is_enabled else 0xFF0055
        )

        smart_threat_events = {
            "Anti spam": "Anti-Spam (`antispam`)",
            "Anti caps": "Anti-Caps (`anticaps`)",
            "Anti link": "Anti-Link (`antilink`)",
            "Anti invites": "Anti-Invites (`antiinvite`)",
            "Anti mass mention": "Anti-Mass Mention (`anti_mass_mention`)",
            "Anti emoji spam": "Anti-Emoji Spam (`anti_emoji_spam`)",
            "Anti everyone": "Anti Everyone / Anti Here (`antieveryone`)",
        }

        threat_status_text = []
        for ev, lbl in smart_threat_events.items():
            p_val = self.current_punishments.get(ev, "None")
            if not self.is_enabled or p_val in (None, "None", "Disabled", ""):
                p_val = "Disabled"
            else:
                p_val = f"Active ({p_val})"
            threat_status_text.append(f"• **{lbl}**: {p_val}")

        embed.add_field(
            name="🛡️ Smart Threat Filters & External App Spam",
            value="\n".join(threat_status_text),
            inline=False
        )

        # Word Blacklist & Bypass Guard section
        bl_val = self.current_punishments.get("Anti blacklisted words", "Warn User")
        bl_status = f"Active ({bl_val})" if self.is_enabled else "Disabled"
        
        embed.add_field(
            name="🔤 Word Blacklist & Bypass Guard",
            value=(
                f"• **Word Filter (`blacklistword`)**: {bl_status}\n"
                f"• **Commands**: `blacklistword add <word>` | `remove` | `config` | `reset`\n"
                f"• **Bypass Guard**: `blacklistword bypass add/remove/show <#channel/@role>`"
            ),
            inline=False
        )

        log_ch_mention = f"<#{self.log_channel_id}>" if self.log_channel_id else "Not Configured (Click 'Setup Logging')"
        embed.add_field(
            name="Logging Channel",
            value=log_ch_mention,
            inline=False
        )

        embed.set_footer(text=f"Requested by {self.author} • Interactive AutoMod UI", icon_url=self.author.display_avatar.url)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    async def load_and_display(self, interaction: discord.Interaction):
        await self.load_hub_data()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def load_and_display_config(self, interaction: discord.Interaction, config_view):
        await self.load_hub_data()
        embed = config_view.build_embed(
            interaction.guild,
            self.is_enabled,
            self.current_punishments,
            self.log_channel_id,
            self.ignored_ch_count,
            self.ignored_role_count,
            self.bot_spam_enabled
        )
        await interaction.response.edit_message(embed=embed, view=config_view)

    async def toggle_automod(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)

        self.is_enabled = not self.is_enabled
        async with aiosqlite.connect("db/automod.db") as db:
            # Always ensure tables exist with correct schema
            await db.execute("CREATE TABLE IF NOT EXISTS automod (guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0)")
            try:
                await db.execute("ALTER TABLE automod ADD COLUMN enabled INTEGER DEFAULT 0")
            except Exception:
                pass
            await db.execute("CREATE TABLE IF NOT EXISTS automod_punishments (guild_id INTEGER, event TEXT, punishment TEXT, PRIMARY KEY (guild_id, event))")

            if self.is_enabled:
                await db.execute("INSERT INTO automod (guild_id, enabled) VALUES (?, 1) ON CONFLICT(guild_id) DO UPDATE SET enabled=1", (self.guild_id,))
                if not self.current_punishments:
                    events_list = ["Anti link", "Anti invites", "Anti spam", "Anti caps", "Anti mass mention", "Anti emoji spam"]
                    for ev in events_list:
                        self.current_punishments[ev] = "Mute (7 mins)"
                        await db.execute("INSERT OR REPLACE INTO automod_punishments (guild_id, event, punishment) VALUES (?, ?, ?)", (self.guild_id, ev, "Mute (7 mins)"))
            else:
                # Write disabled row instead of deleting — dashboard needs this to read enabled=0
                await db.execute("INSERT INTO automod (guild_id, enabled) VALUES (?, 0) ON CONFLICT(guild_id) DO UPDATE SET enabled=0", (self.guild_id,))
                self.current_punishments.clear()
            await db.commit()

        if self.is_enabled and interaction.guild:
            log_id = await ensure_automod_log_channel(interaction.guild)
            if log_id:
                self.log_channel_id = log_id

        from utils.settings_manager import set_guild_setting
        set_guild_setting(self.guild_id, "automod", self.is_enabled)
        from core.cache.security_cache import security_cache
        security_cache.set_automod_status(self.guild_id, self.is_enabled)

        self.update_components()
        embed = self.build_embed(interaction.guild)
        if interaction.response.is_done():
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def set_all_mute(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)

        self.is_enabled = True
        events_list = ["Anti link", "Anti invites", "Anti spam", "Anti caps", "Anti mass mention", "Anti emoji spam"]
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("INSERT OR REPLACE INTO automod (guild_id, enabled) VALUES (?, 1)", (self.guild_id,))
            for ev in events_list:
                self.current_punishments[ev] = "Mute (10 mins)"
                await db.execute("INSERT OR REPLACE INTO automod_punishments (guild_id, event, punishment) VALUES (?, ?, ?)", (self.guild_id, ev, "Mute (10 mins)"))
            await db.commit()

        if interaction.guild:
            log_id = await ensure_automod_log_channel(interaction.guild)
            if log_id:
                self.log_channel_id = log_id

        from utils.settings_manager import set_guild_setting
        set_guild_setting(self.guild_id, "automod", True)

        self.update_components()
        embed = self.build_embed(interaction.guild)
        if interaction.response.is_done():
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def setup_logging(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)

        guild = interaction.guild
        if not guild.me.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ I need `Manage Channels` permission to create the automod log channel.", ephemeral=True)

        log_id = await ensure_automod_log_channel(guild)
        if log_id:
            self.log_channel_id = log_id

        self.update_components()
        embed = self.build_embed(guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def toggle_bot_spam(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)

        self.bot_spam_enabled = not self.bot_spam_enabled
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS bot_spam_protection (guild_id TEXT PRIMARY KEY, enabled BOOLEAN DEFAULT 0)")
            val = 1 if self.bot_spam_enabled else 0
            await db.execute("INSERT OR REPLACE INTO bot_spam_protection (guild_id, enabled) VALUES (?, ?)", (str(self.guild_id), val))
            await db.commit()

        self.update_components()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def goto_punishments(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        sub_view = AutoModPunishmentSubView(self.author, self.guild_id, [(k, v) for k, v in self.current_punishments.items()], self)
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def goto_ignored(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        sub_view = AutoModIgnoreSubView(self.author, self.guild_id, self)
        await sub_view.load_data()
        embed = sub_view.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def goto_config(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        sub_view = AutoModConfigSubView(self.author, self.guild_id, self)
        embed = sub_view.build_embed(
            interaction.guild,
            self.is_enabled,
            self.current_punishments,
            self.log_channel_id,
            self.ignored_ch_count,
            self.ignored_role_count,
            self.bot_spam_enabled
        )
        await interaction.response.edit_message(embed=embed, view=sub_view)

    async def refresh_view(self, interaction: discord.Interaction):
        if interaction.user != self.author and not is_server_owner_or_extra_owner(interaction.guild, interaction.user):
            return await interaction.response.send_message("❌ This panel is only for the command author.", ephemeral=True)
        await self.load_and_display(interaction)


class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.default_punishment = "Mute"
        asyncio.create_task(self.init_db())

    async def get_exempt_roles_channels(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            roles_cursor = await db.execute("SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'role'", (guild_id,))
            channels_cursor = await db.execute("SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'channel'", (guild_id,))
            
            exempt_roles = [discord.Object(id) for (id,) in await roles_cursor.fetchall()]
            exempt_channels = [discord.Object(id) for (id,) in await channels_cursor.fetchall()]
            
            return exempt_roles, exempt_channels

    async def is_automod_enabled(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT enabled FROM automod WHERE guild_id = ?", (guild_id,))
            result = await cursor.fetchone()
            if result is not None:
                return bool(result[0] == 1)
            return False

    async def update_punishments(self, guild_id, event, punishment):
        async with aiosqlite.connect("db/automod.db") as db:
            if str(punishment).strip().lower() not in ("disabled", "none", "off", "0"):
                await db.execute("INSERT INTO automod (guild_id, enabled) VALUES (?, 1) ON CONFLICT(guild_id) DO UPDATE SET enabled=1", (guild_id,))
            await db.execute("INSERT OR REPLACE INTO automod_punishments (guild_id, event, punishment) VALUES (?, ?, ?)", (guild_id, event, punishment))
            await db.commit()

    async def get_current_punishments(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            async with db.execute(
                "SELECT event, punishment FROM automod_punishments WHERE guild_id = ? AND event != 'Anti NSFW link'", 
                (guild_id,)
            ) as cursor:
                return await cursor.fetchall()

    async def is_anti_nsfw_enabled(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti NSFW link'", (guild_id,))
            result = await cursor.fetchone()
            return result is not None

    async def init_db(self):
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod (
                    guild_id INTEGER PRIMARY KEY,
                    enabled INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_punishments (
                    guild_id INTEGER,
                    event TEXT,
                    punishment TEXT,
                    PRIMARY KEY (guild_id, event)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_ignored (
                    guild_id INTEGER,
                    type TEXT,
                    id INTEGER,
                    PRIMARY KEY (guild_id, type, id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_logging (
                    guild_id INTEGER,
                    log_channel INTEGER,
                    PRIMARY KEY (guild_id)
                )
            """)
            await db.commit()

    @commands.hybrid_group(name="automod", aliases=["automodui", "automodpanel", "automodconfig"], invoke_without_command=True, help="Open the interactive AutoMod UI Control Panel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def automod(self, ctx):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.send(embed=embed)

        view = AutoModControlView(ctx.author, guild_id, False, [], None, self)
        await view.load_hub_data()
        embed = view.build_embed(ctx.guild)
        await ctx.send(embed=embed, view=view)




    @automod.group(name="ignore", aliases=["exempt", "whitelist", "wl"], help="Manage whitelisted roles and channels for Automod.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def ignore(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)
            

    @ignore.command(name="channel", help="Add a channel to the whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_channel(self, ctx, channel: discord.TextChannel):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT 1 FROM automod_ignored WHERE guild_id = ? AND type = 'channel' AND id = ?", (guild_id, channel.id))
            if await cursor.fetchone() is not None:
                embed = discord.Embed(title="__Channel Already Whitelisted!__", description=f"<:Denied:1294218790082711553> The channel {channel.mention} is already in the ignore list.\n\n➜ Use **{ctx.prefix}automod unignore channel {channel.mention}** to remove it.", color=0x000000)
                
                embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await ctx.send(embed=embed)
                return
                
            count_cursor = await db.execute("SELECT COUNT(*) FROM automod_ignored WHERE guild_id = ? AND type = 'channel'", (guild_id,))
            count = await count_cursor.fetchone()

            if count[0] >= 10:
                await ctx.send("You can only ignore up to 10 channels.")
                return

            await db.execute("INSERT OR REPLACE INTO automod_ignored (guild_id, type, id) VALUES (?, 'channel', ?)", (guild_id, channel.id))
            await db.commit()
            
            if await self.is_anti_nsfw_enabled(guild_id):
                try:
                    rules = await ctx.guild.fetch_automod_rules()
                    for rule in rules:
                        if rule.name == "Anti NSFW Links":
                            exempt_channels = list(rule.exempt_channels)  
                            exempt_channels.append(channel) 
                            await rule.edit(
                                exempt_channels=exempt_channels,
                                reason="Channel exempted from Anti NSFW Links via automod ignore command"
                            )
                            break
                except discord.HTTPException:
                    pass

                    
            success = discord.Embed(title="<a:tick:1558726958802800660> Channel Whitelisted", description=f"The channel {channel.mention} has been added to the ignore list \n\n➜ Use `{ctx.prefix}automod ignore show` to view the ignore list.", color=0x000000)
            success.set_thumbnail(url=self.bot.user.avatar.url)
            success.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.send(embed=success)

    @ignore.command(name="role", help="Add a role to the whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_role(self, ctx, role: discord.Role):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT 1 FROM automod_ignored WHERE guild_id = ? AND type = 'role' AND id = ?", (guild_id, role.id))
            
            if await cursor.fetchone() is not None:
                embed = discord.Embed(title="__Role Already Whitelisted!__", description=f"<:Denied:1294218790082711553> The role {role.mention} is already in the ignore list.\n\n➜ Use **{ctx.prefix}automod unignore role {role.mention}** to remove it.", color=0x000000)
                embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await ctx.send(embed=embed)
                return
                
            count_cursor = await db.execute("SELECT COUNT(*) FROM automod_ignored WHERE guild_id = ? AND type = 'role'", (guild_id,))
            count = await count_cursor.fetchone()


            if count[0] >= 10:
                await ctx.send("You can only ignore up to 10 roles.")
                return

            await db.execute("INSERT OR REPLACE INTO automod_ignored (guild_id, type, id) VALUES (?, 'role', ?)", (guild_id, role.id))
            await db.commit()

            if await self.is_anti_nsfw_enabled(guild_id):
                try:
                    rules = await ctx.guild.fetch_automod_rules()
                    for rule in rules:
                        if rule.name == "Anti NSFW Links":
                            exempt_roles = list(rule.exempt_roles)  
                            exempt_roles.append(role) 
                            await rule.edit(
                                exempt_roles=exempt_roles,
                                reason="Role exempted from Anti NSFW Links via automod ignore command"
                            )
                            break
                except discord.HTTPException:
                    pass
                    
                    
            success = discord.Embed(title="<a:tick:1558726958802800660> Role Whitelisted", description=f"The role {role.mention} has been added to the ignore list \n\n➜ Use `{ctx.prefix}automod ignore show` to view the ignore list.", color=0x000000)
            success.set_thumbnail(url=self.bot.user.avatar.url)
            success.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.send(embed=success)

    @ignore.command(name="show", aliases=["list"], help="Show the whitelisted roles and channels.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_show(self, ctx):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return
            

        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT type, id FROM automod_ignored WHERE guild_id = ?", (guild_id,))
            ignored_items = await cursor.fetchall()

        if not ignored_items:
            await ctx.reply("No ignored channels or roles found.")
            return

        ignored_channels = []
        ignored_roles = []

        for item_type, item_id in ignored_items:
            if item_type == "channel":
                channel = ctx.guild.get_channel(item_id)
                if channel:
                    ignored_channels.append(f"{channel.mention} (ID: {channel.id})")
                else:
                    ignored_channels.append(f"Deleted Channel (ID: {item_id})")
            elif item_type == "role":
                role = ctx.guild.get_role(item_id)
                if role:
                    ignored_roles.append(f"{role.mention} (ID: {role.id})")
                else:
                    ignored_roles.append(f"Deleted Role (ID: {item_id})")

        embed = discord.Embed(title="Ignored Channels & Roles for Automod", color=0x000000)

        if ignored_channels:
            embed.add_field(name="__Ignored Channels:__", value="\n".join(ignored_channels), inline=False)
        else:
            embed.add_field(name="__Ignored Channels:__", value="None", inline=False)

        if ignored_roles:
            embed.add_field(name="__Ignored Roles:__", value="\n".join(ignored_roles), inline=False)
        else:
            embed.add_field(name="__Ignored Roles:__", value="None", inline=False)

        await ctx.send(embed=embed)


    @ignore.command(name="reset", help="Reset the whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_reset(self, ctx):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("DELETE FROM automod_ignored WHERE guild_id = ?", (guild_id,))
            await db.commit()
        embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"** <a:tick:1558726958802800660> | All ignored channels and roles have been reset!**\n\nTo view current Automod settings use `{ctx.prefix}automod config`", color=0x000000)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=embed)
        

    @automod.group(name="unignore", aliases=["unwhitelist", "unwl"], invoke_without_command=True, help="Remove channels and roles from the whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unignore(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @unignore.command(name="channel", help="Remove a channel from the whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def unignore_channel(self, ctx, channel: discord.TextChannel):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        if await self.is_anti_nsfw_enabled(guild_id):
            try:
                rules = await ctx.guild.fetch_automod_rules()
                for rule in rules:
                    if rule.name == "Anti NSFW Links":
                        exempt_channels = list(rule.exempt_channels)  
                        exempt_channels = [ch for ch in exempt_channels if ch.id != channel.id]
                        await rule.edit(
                            exempt_channels=exempt_channels,
                            reason="Channel removed from Anti NSFW Links exemption via automod unignore command"
                        )
                        break
            except discord.HTTPException:
                pass
        
        async with aiosqlite.connect("db/automod.db") as db:
            result = await db.execute("DELETE FROM automod_ignored WHERE guild_id = ? AND type = 'channel' AND id = ?", (guild_id, channel.id))
            await db.commit()

        if result.rowcount > 0:
            embed = discord.Embed(title="<a:tick:1558726958802800660> Success", description=f"{channel.mention} has been removed from the automod ignore list.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error", description=f"{channel.mention} is not in the automod ignore list.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            

    @unignore.command(name="role", help="Remove a role from the whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def unignore_role(self, ctx, role: discord.Role):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        if await self.is_anti_nsfw_enabled(guild_id):
            try:
                rules = await ctx.guild.fetch_automod_rules()
                for rule in rules:
                    if rule.name == "Anti NSFW Links":
                        exempt_roles = list(rule.exempt_roles)  
                        exempt_roles = [ch for ch in exempt_roles if ch.id != role.id]
                        await rule.edit(
                            exempt_roles=exempt_roles,
                            reason="Role removed from Anti NSFW Links exemption via automod unignore command"
                        )
                        break
            except discord.HTTPException:
                pass

        
        async with aiosqlite.connect("db/automod.db") as db:
            result = await db.execute("DELETE FROM automod_ignored WHERE guild_id = ? AND type = 'role' AND id = ?", (guild_id, role.id))
            await db.commit()

        if result.rowcount > 0:
            embed = discord.Embed(title="<a:tick:1558726958802800660> Success", description=f"{role.mention} has been removed from the automod ignore list.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error", description=f"{role.mention} is not in the automod ignore list.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
    

    @automod.command(name="disable", help="Disable Automod in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return
            
        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return
            
        embed = discord.Embed(
            title="Disable Automod Confirmation",
            description="**Are you sure you want to disable Automod?**\n\nThis will remove all custom event settings, punishments, ignored roles/channels, & logging channel data.",
            color=0x0000000
        )
        embed.set_footer(text="Click 'Yes' to disable Automod or 'No' to cancel.")
        embed.set_thumbnail(url=self.bot.user.avatar.url)

        view = ConfirmDisable(ctx.author)
        message = await ctx.send(embed=embed, view=view)

        await view.wait()

        if view.value is None:
            embed.title = "Automod Disable Cancelled"
            embed.description = "You took too long to respond. Automod disable process has been canceled."
            embed.color = 0x000000
            
            await message.edit(embed=embed, view=None)

        elif view.value:
            
            async with aiosqlite.connect("db/automod.db") as db:
                await db.execute("DELETE FROM automod WHERE guild_id = ?", (guild_id,))
                await db.execute("DELETE FROM automod_punishments WHERE guild_id = ?", (guild_id,))
                await db.execute("DELETE FROM automod_ignored WHERE guild_id = ?", (guild_id,))
                await db.execute("DELETE FROM automod_logging WHERE guild_id = ?", (guild_id,))
                await db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(guild_id, "automod", False)

            rules = await ctx.guild.fetch_automod_rules()
            for rule in rules:
                if rule.name == "Anti NSFW Links":
                    try:
                        await rule.delete(reason="Automod disabled - removing Anti NSFW Link rule")
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException:
                        pass


            embed.title = "<a:tick:1558726958802800660> Automod Disabled"
            embed.description = f"Automod has been successfully disabled for **{ctx.guild.name}.** \nAll settings, punishments, and logs have been removed.\n\nCurrent Status: Disabled\n➜ To Re-enable use `{ctx.prefix}automod enable`."
            embed.color = 0x000000
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await message.edit(embed=embed, view=None)
            

        else:
            embed.title = "Automod Disable Cancelled"
            embed.description = "Automod disable process has been canceled."
            embed.color = 0x00000
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await message.edit(embed=embed, view=None)

        

    @automod.command(name="config", aliases=["settings", "show"], help="View Automod settings.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return
            
        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return

        current_punishments = await self.get_current_punishments(guild_id)
        embed = discord.Embed(title=f"Enabled Automod Events & their punishment type for {ctx.guild.name}", color=0x000000)
        embed.set_footer(text="Manage punishment type for events by executing “automod punishment” command.", icon_url=self.bot.user.avatar.url)

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        else:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        for event, punishment in current_punishments:
            embed.add_field(name=event, value=punishment or "None", inline=False)

        if await self.is_anti_nsfw_enabled(guild_id):
            embed.add_field(name="Anti NSFW Links", value="Block Message", inline=False)

        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild_id,))
            log_channel_id = await cursor.fetchone()

        if log_channel_id and log_channel_id[0]:
            log_channel = ctx.guild.get_channel(log_channel_id[0])
            if log_channel:
                embed.add_field(name="Logging Channel", value=f"{log_channel.mention}", inline=False)
            else:
                embed.add_field(name="Logging Channel", value="Deleted Channel", inline=False)
        else:
            embed.add_field(name="Logging Channel", value="No logging channel", inline=False)

        await ctx.send(embed=embed)


    @automod.command(name="logging", help="Set the logging channel for Automod events.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def logging(self, ctx, channel: discord.TextChannel):
        guild_id = ctx.guild.id
        if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position < ctx.guild.me.top_role.position:
            embed = discord.Embed(title="<:Denied:1294218790082711553> Access Denied", description="Your top role must be at the **same** position or **higher** than my top role.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return
        if not await self.is_automod_enabled(guild_id):
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"Uhh, looks like your server hasn't enabled Automoderation.\n\nCurrent Status: Disabled\nTo Enable use `{ctx.prefix}automod enable`", color=0x000000)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
            return
            
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?, ?)", (guild_id, channel.id))
            await db.commit()
            embed=discord.Embed(title=f"Automod Settings for {ctx.guild.name}", description=f"**<a:tick:1558726958802800660> | Automoderation Logging channel set to {channel.mention}.**\n\n➜ Use `{ctx.prefix}automod config` to view current Automod settings.", color=0x000000)
            embed.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        guild_id = guild.id

        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("DELETE FROM automod WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM automod_punishments WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM automod_ignored WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM automod_logging WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM bot_spam_protection WHERE guild_id = ?", (str(guild_id),))
            await db.commit()

    @commands.command(name="blockspamraid", aliases=["antispambot", "botspam", "blockbotspam", "antispamraid"], help="Toggle or view Bot Spam Raid Protection.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def blockspamraid(self, ctx: commands.Context, option: str = None):
        guild_id = ctx.guild.id
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS bot_spam_protection (guild_id TEXT PRIMARY KEY, enabled BOOLEAN DEFAULT 0)")
            await db.commit()

            if option is None:
                cursor = await db.execute("SELECT enabled FROM bot_spam_protection WHERE guild_id = ?", (str(guild_id),))
                row = await cursor.fetchone()
                status = "Enabled" if (row is None or row[0] == 1) else "Disabled"
                embed = discord.Embed(
                    title=f"Bot Spam Raid Protection for {ctx.guild.name}",
                    description=f"Status: **{status}**\n\n*Usage:* `{ctx.prefix}blockspamraid enable` or `{ctx.prefix}blockspamraid disable`",
                    color=0x000000
                )
                embed.set_footer(text=f"Executed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
                return await ctx.send(embed=embed)

            opt = option.lower()
            if opt in ["enable", "on", "true"]:
                await db.execute("INSERT OR REPLACE INTO bot_spam_protection (guild_id, enabled) VALUES (?, 1)", (str(guild_id),))
                await db.commit()
                embed = discord.Embed(
                    title="Bot Spam Raid Protection",
                    description="<a:tick:1558726958802800660> **Bot Spam Raid Protection has been ENABLED!** Spamming bots will be auto-deleted & punished instantly.",
                    color=0x000000
                )
                embed.set_footer(text=f"Executed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)
            elif opt in ["disable", "off", "false"]:
                await db.execute("DELETE FROM bot_spam_protection WHERE guild_id = ?", (str(guild_id),))
                await db.commit()
                embed = discord.Embed(
                    title="Bot Spam Raid Protection",
                    description="<:Yuna_cross:1227866668152393789> **Bot Spam Raid Protection has been DISABLED.**",
                    color=0x000000
                )
                embed.set_footer(text=f"Executed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Invalid option! Use `enable` or `disable`.")
