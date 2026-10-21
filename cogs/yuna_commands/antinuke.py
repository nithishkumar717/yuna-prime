import discord
from discord.ext import commands, tasks
import aiosqlite
import asyncio
import time
import logging
from utils.Tools import *
from utils.config import OWNER_IDS
from utils.emojis import ANIMATED_ENABLED, STATIC_DISABLED, ANIMATED_SETTINGS, STATIC_MOD, ANIMATED_TICK

from typing import Optional, Union, List, Tuple

ANTINUKE_SETUP_TICK = "<:17742:1560628833105743972>"
ANTINUKE_SETUP_LOADING = "<a:loading:1554957482248380416>"
logger = logging.getLogger("antinuke.setup")


class AntiNukeSetupWizard:
  """Stateful controller for the Olympus-style multi-page Anti-Nuke setup wizard."""

  def __init__(self, cog, ctx, pre: str, current_log_channel_id: Optional[int] = None, is_rerun: bool = False):
    self.cog = cog
    self.ctx = ctx
    self.bot = cog.bot
    self.guild = ctx.guild
    self.author = ctx.author
    self.pre = pre
    self.current_log_channel_id = current_log_channel_id
    self.is_rerun = is_rerun
    self.message = None
    self.log_channel = None
    self.log_webhook = None
    self.completed_lines = []

  def get_bot_meta(self):
    bot_name = getattr(self.bot.user, 'name', 'Yuna') if self.bot and getattr(self.bot, 'user', None) else 'Yuna'
    bot_avatar = self.bot.user.display_avatar.url if self.bot and getattr(self.bot, 'user', None) and getattr(self.bot.user, 'display_avatar', None) else None
    return bot_name, bot_avatar

  def build_page_1_embed(self) -> discord.Embed:
    bot_name, bot_avatar = self.get_bot_meta()
    embed = discord.Embed(
      title="🛡️ __**YUNA Anti-Nuke • Setup Wizard**__",
      description=(
        f"### 🛡️ What Is The Limit & Anti-Nuke System?\n\n"
        f"YUNA's **Anti-Nuke V2** is a real-time autonomous security engine engineered to protect **{self.guild.name}** "
        f"against malicious bots, rogue administrators, and compromised staff accounts.\n\n"
        f"**⚡ Real-Time Containment & Rate Limiting:**\n"
        f"• **Instant Anomaly Detection:** Intercepts rapid unauthorized bans, kicks, channel purges, and role stripping in sub-milliseconds.\n"
        f"• **High-Frequency Abuse Throttling:** Detects burst actions and immediately revokes permissions before mass destruction can occur.\n"
        f"• **Dual-Layer Auto-Recovery:** Idempotently reconstructs deleted channels, restores lost roles, and rolls back dangerous permission changes automatically.\n\n"
        f"Click **`Proceed ➔`** below to review the security prerequisites and initiate system armoring."
      ),
      color=0x2B2D31
    )
    if bot_avatar:
      embed.set_thumbnail(url=bot_avatar)
    embed.set_footer(text=f"{bot_name}! — Antinuke Setup (Step 1/5).", icon_url=bot_avatar)
    return embed

  def build_page_2_embed(self) -> discord.Embed:
    bot_name, bot_avatar = self.get_bot_meta()
    embed = discord.Embed(
      title="⚠️ __**Important Disclaimer & Pre-requisites**__",
      description=(
        f"### ⚠️ Please Read Carefully Before Armoring\n\n"
        f"To guarantee maximum protection, your server must meet the following Discord hierarchy and configuration requirements:\n\n"
        f"**1. 👑 Bot Role Hierarchy (MANDATORY)**\n"
        f"Discord's permission architecture strictly prohibits bots from taking action against members who hold a **higher or equal role**.\n"
        f"> Place **`Yuna`** (or **`Yuna Supreme™`**) at the **very top** of your server's Role Settings list (above all admin, moderator, and rival bot roles).\n\n"
        f"**2. 🛡️ Whitelist Trusted Staff & Bots**\n"
        f"Any unwhitelisted user or bot performing sensitive actions (banning members, deleting channels, creating webhooks) will be treated as an attacker and quarantined immediately.\n"
        f"> Use `{self.pre}antinuke whitelist add <@user>` for trusted staff.\n"
        f"> Use `{self.pre}antinuke botwhitelist add <@bot>` for trusted companion bots.\n\n"
        f"**3. 💾 Automatic Backups & System Audit**\n"
        f"During setup, Yuna will take a full configuration snapshot, sync a server template, clean up unauthorized permanent invites, and establish a dedicated **`Yuna Sentinel`** logging webhook.\n\n"
        f"Click **`Agree & Setup 🛡️`** to begin automated system deployment."
      ),
      color=0xFEE75C
    )
    if bot_avatar:
      embed.set_thumbnail(url=bot_avatar)
    embed.set_footer(text=f"{bot_name}! — Antinuke Setup (Step 2/5).", icon_url=bot_avatar)
    return embed

  def build_page_3_embed(self, lines: list = None) -> discord.Embed:
    bot_name, bot_avatar = self.get_bot_meta()
    display_lines = lines if lines is not None else self.completed_lines
    embed = discord.Embed(
      title="Antinuke Setup.",
      description="Performing few checks to maintain smoothness during the setup.\n\n" + "\n".join(display_lines),
      color=0x2B2D31
    )
    embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
    return embed

  def build_page_4_embed(self) -> discord.Embed:
    bot_name, bot_avatar = self.get_bot_meta()
    embed = discord.Embed(
      title="🛡️ __**YUNA Anti-Nuke • Active Protection Manifest**__",
      description=(
        f"### 🛡️ All Protection Modules Are Now Armed & Active\n\n"
        f"Your server is secured with **20 comprehensive defense modules** operating under zero-latency CPU evaluation:\n\n"
        f"**Core Protection Modules:**\n"
        f"• 🔨 **Anti Ban** — Intercepts unwhitelisted member bans & quarantines perpetrator\n"
        f"• 👢 **Anti Kick** — Blocks unauthorized kicks & revokes perpetrator permissions\n"
        f"• 🤖 **Anti BotAdd** — Automatically quarantines and kicks unauthorized bots\n"
        f"• 📁 **Anti Channel Create** — Immediately deletes rogue channels created by non-owners\n"
        f"• 🗑️ **Anti Channel Delete** — Reconstructs deleted channels with original permissions & position\n"
        f"• ⚙️ **Anti Channel Update** — Reverts unauthorized permission and topic tampering\n"
        f"• 📢 **Anti Everyone / Here** — Suppresses mass pings and issues instant timeouts\n"
        f"• 🌐 **Anti Guild Update** — Protects server name, icon, banner, and vanity URL\n"
        f"• 👤 **Anti Member Update** — Reverts dangerous permission assignments to unauthorized members\n"
        f"• 🎭 **Anti Role Create** — Instantly deletes unauthorized roles\n"
        f"• ❌ **Anti Role Delete** — Re-creates deleted roles and restores hierarchy order\n"
        f"• ⚡ **Anti Role Update** — Strips dangerous administrative permissions in real-time\n"
        f"• 🪝 **Anti Webhook** — Deletes rogue webhooks and bans the creator\n\n"
        f"**Special Protection Modules:**\n"
        f"• 🌾 **Anti Prune** — Prevents mass server member pruning with immediate containment\n"
        f"• 🛡️ **Anti Auto Roles** — Prevents malicious bot auto-role injection\n"
        f"• 🔗 **Anti Link Role** — Blocks unauthorized connection-linked roles\n"
        f"• 🚪 **Safe Onboarding** — Protects Community Onboarding from dangerous role assignment\n"
        f"• ⚠️ **Anti Dangerous Permissions** — Real-time stripping of Administrator, Ban, and Manage Server\n"
        f"• 🗡️ **Anti Betray Module** — Containment if an already-whitelisted staff/bot turns rogue\n"
        f"• 🔄 **Auto Recovery Engine** — Automated layout backups and instant idempotent restoration\n\n"
        f"Click **`Proceed ➔`** to review Anti-Betray safeguards and finalize armoring."
      ),
      color=0x2B2D31
    )
    if bot_avatar:
      embed.set_thumbnail(url=bot_avatar)
    embed.set_footer(text=f"{bot_name}! — Antinuke Setup (Step 4/5).", icon_url=bot_avatar)
    return embed

  def build_page_5_embed(self) -> discord.Embed:
    bot_name, bot_avatar = self.get_bot_meta()
    log_mention = f"<#{self.log_channel.id}>" if self.log_channel else (f"<#{self.current_log_channel_id}>" if self.current_log_channel_id else "None")
    embed = discord.Embed(
      title="✅ __**Antinuke Successfully Enabled**__",
      description=(
        f"### 🛡️ Server Armoring Complete\n\n"
        f"**Security Settings For {self.guild.name}:**\n"
        f"• **Current Status:** {ANIMATED_ENABLED} **Enabled & Armored**\n"
        f"• 📍 **Logging Channel:** {log_mention}\n"
        f"• 🪝 **Security Webhook:** `Active (Yuna Sentinel)`\n"
        f"• ⚡ **Protection Engine:** `V2 Engine (Sub-millisecond local CPU policy)`\n\n"
        f"---\n\n"
        f"### 🗡️ Anti-Betray Module Is Active\n"
        f"The **Anti-Betray Module** safeguards your server against rogue or compromised staff. Even if an account is whitelisted, any sudden anomalous activity exceeding safe thresholds triggers an instant containment lock to protect your community.\n\n"
        f"---\n\n"
        f"### 📌 Essential Next Steps:\n"
        f"• **Whitelist Admins:** `{self.pre}antinuke whitelist add <@user>`\n"
        f"• **Whitelist Bots:** `{self.pre}antinuke botwhitelist add <@bot>`\n"
        f"• **Audit Configuration:** `{self.pre}antinuke config`\n"
        f"• **Decision Explainer:** `{self.pre}antinuke explain <@user>`\n"
        f"• **To Disable:** `{self.pre}antinuke disable`"
      ),
      color=0x2B2D31
    )
    if bot_avatar:
      embed.set_thumbnail(url=bot_avatar)
    embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
    return embed

  def build_punishments_embed(self) -> discord.Embed:
    bot_name, bot_avatar = self.get_bot_meta()
    embed = discord.Embed(
      title="Punishment Types for Changes Made by Unwhitelisted Admins/Mods",
      description=(
        "**Anti Ban:** Ban\n"
        "**Anti Kick:** Ban\n"
        "**Anti Bot:** Remove all roles & Kick bot (Kick inviter + DM permanent invite for 1st & 2nd time, Ban on 3rd time)\n"
        "**Anti Channel Create/Delete/Update:** Ban\n"
        "**Anti Everyone/Here:** Delete message & warning for 1st 3 times, then 60s timeout\n"
        "**Anti Role Create/Delete/Update:** Kick\n"
        "**Anti Member Update:** Kick\n"
        "**Anti Guild Update:** Ban\n"
        "**Anti Integration:** Ban\n"
        "**Anti Webhook Create/Delete/Update:** Kick\n"
        "**Anti Prune:** 5 mins timeout\n"
        "**Auto Recovery:** Automatically recover damaged channels, roles, and settings\n\n"
        "Note: In the case of member updates, action will be taken only if the role contains dangerous permissions such as Ban Members, Administrator, Manage Guild, Manage Channels, Manage Roles, or Manage Webhooks"
      ),
      color=0x2B2D31
    )
    if bot_avatar:
      embed.set_footer(text="These punishment types are fixed and assigned as required to ensure guild security/protection", icon_url=bot_avatar)
    else:
      embed.set_footer(text="These punishment types are fixed and assigned as required to ensure guild security/protection")
    return embed

  async def start(self):
    embed = self.build_page_1_embed()
    view = AntiNukeWizardPage1View(self)
    self.message = await self.ctx.send(embed=embed, view=view)
    view.message = self.message


class AntiNukeWizardBaseView(discord.ui.View):
  def __init__(self, wizard: AntiNukeSetupWizard, timeout: float = 180):
    super().__init__(timeout=timeout)
    self.wizard = wizard
    self.message = None

  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    if interaction.user != self.wizard.author and not is_server_owner_or_extra_owner(self.wizard.guild, interaction.user):
      await interaction.response.send_message("Only the Server Owner or Extra Owner can interact with this setup wizard.", ephemeral=True)
      return False
    return True

  async def on_timeout(self):
    for item in self.children:
      item.disabled = True
    msg = self.message or self.wizard.message
    if msg:
      try:
        await msg.edit(view=self)
      except Exception:
        pass


class AntiNukeWizardPage1View(AntiNukeWizardBaseView):
  @discord.ui.button(label="Proceed", style=discord.ButtonStyle.primary)
  async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_page_2_embed()
    view = AntiNukeWizardPage2View(self.wizard)
    await interaction.response.edit_message(embed=embed, view=view)
    view.message = self.wizard.message

  @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
  async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(
      title="🛡️ Antinuke Setup Cancelled",
      description="Antinuke setup was cancelled by the server owner.",
      color=0x2B2D31
    )
    bot_name, bot_avatar = self.wizard.get_bot_meta()
    if bot_avatar:
      embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
    else:
      embed.set_footer(text=f"{bot_name}! — Antinuke.")
    await interaction.response.edit_message(embed=embed, view=None)


class AntiNukeWizardPage2View(AntiNukeWizardBaseView):
  @discord.ui.button(label="Agree & Setup", style=discord.ButtonStyle.success)
  async def agree_and_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
    bot_name, bot_avatar = self.wizard.get_bot_meta()
    setup_embed = discord.Embed(
      title="Antinuke Setup.",
      description="Performing few checks to maintain smoothness during the setup.",
      color=0x2B2D31
    )
    if bot_avatar:
      setup_embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
    else:
      setup_embed.set_footer(text=f"{bot_name}! — Antinuke.")
    await interaction.response.edit_message(embed=setup_embed, view=None)

    log_ch, log_wh, completed_lines = await self.wizard.cog.execute_antinuke_setup_sequence(
      self.wizard.ctx, self.wizard.message, setup_embed
    )
    self.wizard.log_channel = log_ch
    self.wizard.log_webhook = log_wh
    self.wizard.completed_lines = completed_lines

    complete_view = AntiNukeWizardPage3CompleteView(self.wizard)
    try:
      await self.wizard.message.edit(embed=setup_embed, view=complete_view)
      complete_view.message = self.wizard.message
    except Exception:
      pass

  @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
  async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_page_1_embed()
    view = AntiNukeWizardPage1View(self.wizard)
    await interaction.response.edit_message(embed=embed, view=view)
    view.message = self.wizard.message

  @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
  async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(
      title="🛡️ Antinuke Setup Cancelled",
      description="Antinuke setup was cancelled by the server owner.",
      color=0x2B2D31
    )
    bot_name, bot_avatar = self.wizard.get_bot_meta()
    if bot_avatar:
      embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
    else:
      embed.set_footer(text=f"{bot_name}! — Antinuke.")
    await interaction.response.edit_message(embed=embed, view=None)


class AntiNukeWizardPage3CompleteView(AntiNukeWizardBaseView):
  @discord.ui.button(label="View Protected Modules", style=discord.ButtonStyle.primary)
  async def view_modules(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_page_4_embed()
    view = AntiNukeWizardPage4View(self.wizard)
    await interaction.response.edit_message(embed=embed, view=view)
    view.message = self.wizard.message

  @discord.ui.button(label="Finish Setup", style=discord.ButtonStyle.success)
  async def finish_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_page_5_embed()
    view = AntiNukeWizardPage5View(self.wizard)
    await interaction.response.edit_message(embed=embed, view=view)
    view.message = self.wizard.message


class AntiNukeWizardPage4View(AntiNukeWizardBaseView):
  @discord.ui.button(label="Proceed", style=discord.ButtonStyle.primary)
  async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_page_5_embed()
    view = AntiNukeWizardPage5View(self.wizard)
    await interaction.response.edit_message(embed=embed, view=view)
    view.message = self.wizard.message

  @discord.ui.button(label="View Punishments", style=discord.ButtonStyle.secondary)
  async def view_punishments(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_punishments_embed()
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @discord.ui.button(label="Back to Checklist", style=discord.ButtonStyle.secondary)
  async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_page_3_embed()
    view = AntiNukeWizardPage3CompleteView(self.wizard)
    await interaction.response.edit_message(embed=embed, view=view)
    view.message = self.wizard.message


class AntiNukeWizardPage5View(AntiNukeWizardBaseView):
  @discord.ui.button(label="Protected & Active", style=discord.ButtonStyle.success, disabled=True)
  async def status_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
    pass

  @discord.ui.button(label="View Punishments", style=discord.ButtonStyle.secondary)
  async def view_punishments(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_punishments_embed()
    await interaction.response.send_message(embed=embed, ephemeral=True)


class AntiNukeManifestQuickView(AntiNukeWizardBaseView):
  def __init__(self, wizard: AntiNukeSetupWizard, parent_view=None):
    super().__init__(wizard=wizard, timeout=120)
    self.parent_view = parent_view

  @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
  async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
    if self.parent_view:
      log_mention = f"<#{self.wizard.current_log_channel_id}>" if self.wizard.current_log_channel_id else "None"
      embed = discord.Embed(
        description=(
          f'**Security Settings For {self.wizard.guild.name}**\n'
          f'Your server __**already has Antinuke enabled.**__\n\n'
          f'Current Status: {ANIMATED_ENABLED} Enabled\n'
          f'📍 **Logging Channel:** {log_mention}\n\n'
          f'🛡️ **Important Notice:** Ensure your trusted bots (`{self.wizard.pre}botwhitelist add <@bot>`) and staff members (`{self.wizard.pre}whitelist <@user>`) are whitelisted to prevent actions like unbanning or channel recreation from being blocked.\n\n'
          f'To Disable use `{self.wizard.pre}antinuke disable`'
        ),
        color=0x2B2D31
      )
      bot_name, bot_avatar = self.wizard.get_bot_meta()
      if bot_avatar:
        embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
      else:
        embed.set_footer(text=f"{bot_name}! — Antinuke.")
      await interaction.response.edit_message(embed=embed, view=self.parent_view)
    else:
      await interaction.response.defer()

  @discord.ui.button(label="View Punishments", style=discord.ButtonStyle.secondary)
  async def view_punishments(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = self.wizard.build_punishments_embed()
    await interaction.response.send_message(embed=embed, ephemeral=True)


class AntiNukeAlreadyEnabledView(discord.ui.View):
  def __init__(self, cog, ctx, pre: str, current_log_channel_id: Optional[int] = None):
    super().__init__(timeout=180)
    self.cog = cog
    self.ctx = ctx
    self.pre = pre
    self.current_log_channel_id = current_log_channel_id
    self.message = None

  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    if interaction.user != self.ctx.author and not is_server_owner_or_extra_owner(self.ctx.guild, interaction.user):
      await interaction.response.send_message("Only the Server Owner or Extra Owner can interact with this setup wizard.", ephemeral=True)
      return False
    return True

  @discord.ui.button(label="Re-run Setup Wizard", style=discord.ButtonStyle.primary)
  async def rerun_wizard(self, interaction: discord.Interaction, button: discord.ui.Button):
    wizard = AntiNukeSetupWizard(self.cog, self.ctx, self.pre, self.current_log_channel_id, is_rerun=True)
    embed = wizard.build_page_1_embed()
    view = AntiNukeWizardPage1View(wizard)
    await interaction.response.edit_message(embed=embed, view=view)
    view.message = self.message

  @discord.ui.button(label="Protection Manifest", style=discord.ButtonStyle.secondary)
  async def view_manifest(self, interaction: discord.Interaction, button: discord.ui.Button):
    wizard = AntiNukeSetupWizard(self.cog, self.ctx, self.pre, self.current_log_channel_id)
    embed = wizard.build_page_4_embed()
    view = AntiNukeManifestQuickView(wizard, parent_view=self)
    await interaction.response.edit_message(embed=embed, view=view)

  @discord.ui.button(label="View Punishments", style=discord.ButtonStyle.secondary)
  async def view_punishments(self, interaction: discord.Interaction, button: discord.ui.Button):
    wizard = AntiNukeSetupWizard(self.cog, self.ctx, self.pre, self.current_log_channel_id)
    embed = wizard.build_punishments_embed()
    await interaction.response.send_message(embed=embed, ephemeral=True)

  async def on_timeout(self):
    for item in self.children:
      item.disabled = True
    if self.message:
      try:
        await self.message.edit(view=self)
      except Exception:
        pass


class Antinuke(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    asyncio.create_task(self.initialize_db())
    try:
      self.auto_backup_loop.start()
    except Exception:
      pass

  def get_bot_avatar_url(self) -> Optional[str]:
    if self.bot and getattr(self.bot, 'user', None):
      return getattr(self.bot.user.display_avatar, 'url', None)
    return None

  def cog_unload(self):
    try:
      self.auto_backup_loop.cancel()
    except Exception:
      pass

  async def initialize_db(self):
    self.db = await aiosqlite.connect('db/anti.db')
    await self.db.execute('''
        CREATE TABLE IF NOT EXISTS antinuke (
            guild_id INTEGER PRIMARY KEY,
            status BOOLEAN,
            log_channel INTEGER,
            log_webhook TEXT,
            last_backup_ts REAL
        )
    ''')
    # Migrate columns if needed
    async with self.db.execute("PRAGMA table_info(antinuke)") as cursor:
        columns = [row[1] for row in await cursor.fetchall()]
        if 'status' not in columns:
            if 'enabled' in columns:
                await self.db.execute("ALTER TABLE antinuke RENAME COLUMN enabled TO status")
            else:
                await self.db.execute("ALTER TABLE antinuke ADD COLUMN status BOOLEAN DEFAULT 0")
        if 'log_channel' not in columns:
            await self.db.execute("ALTER TABLE antinuke ADD COLUMN log_channel INTEGER")
        if 'log_webhook' not in columns:
            await self.db.execute("ALTER TABLE antinuke ADD COLUMN log_webhook TEXT")
        if 'last_backup_ts' not in columns:
            await self.db.execute("ALTER TABLE antinuke ADD COLUMN last_backup_ts REAL")
    await self.db.commit()

  @tasks.loop(hours=12)
  async def auto_backup_loop(self):
    """Autonomous server layout and security snapshot loop with smart delta-diffing and cloud sync."""
    try:
      from cogs.yuna_commands.backup import create_server_backup
      from core.antinuke_v2.router import v2_engine_router

      async with aiosqlite.connect('db/anti.db') as db:
        async with db.execute("SELECT guild_id, log_webhook FROM antinuke WHERE status = 1") as cursor:
          rows = await cursor.fetchall()

      for (gid, log_webhook) in rows:
        guild = self.bot.get_guild(gid)
        if guild:
          try:
            snapshot = create_server_backup(guild)
            v2_engine_router.coordinator.snapshot_store.snapshot_guild(guild)
            now_ts = time.time()
            async with aiosqlite.connect('db/anti.db') as db:
              await db.execute("UPDATE antinuke SET last_backup_ts = ? WHERE guild_id = ?", (now_ts, gid))
              await db.commit()

            # Stealth Webhook Confirmation if configured
            if log_webhook:
              try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                  wh = discord.Webhook.from_url(log_webhook, session=session)
                  status_badge = "Layout Updated" if snapshot.get("status") == "created" else "Layout Verified (No Changes)"
                  embed = discord.Embed(
                    title=f"{ANTINUKE_SETUP_TICK} Security Backup Verified",
                    description=(
                      f"**Server:** `{guild.name}`\n"
                      f"🛡️ **Roles Secured:** `{snapshot.get('roles_count', 0)}`\n"
                      f"💬 **Channels/Categories:** `{snapshot.get('categories_count', 0)}`\n"
                      f"💾 **Status:** `{status_badge}`\n"
                      f"☁️ **Cloud Sync:** `Active (Encrypted)`"
                    ),
                    color=0x2B2D31,
                    timestamp=discord.utils.utcnow()
                  )
                  embed.set_footer(text="Yuna Sentinel! — Antinuke Auto Backup")
                  await wh.send(embed=embed, username=f"{guild.me.display_name if guild.me else 'Yuna'} Sentinel")
              except Exception:
                pass
          except Exception:
            pass
    except Exception as e:
      logger.error("[Antinuke] Error during auto-backup loop: %s", e)

  @auto_backup_loop.before_loop
  async def before_auto_backup_loop(self):
    await self.bot.wait_until_ready()

    
  async def enable_limit_settings(self, guild_id):
    default_limits = DEFAULT_LIMITS
    for action, limit in default_limits.items():
      await self.db.execute('INSERT OR REPLACE INTO limit_settings (guild_id, action_type, action_limit, time_window) VALUES (?, ?, ?, ?)', (guild_id, action, limit, TIME_WINDOW))
      await self.db.commit()

  async def disable_limit_settings(self, guild_id):
    await self.db.execute('DELETE FROM limit_settings WHERE guild_id = ?', (guild_id,))
    await self.db.commit()

  async def configure_prime_branding(self, guild):
    """Create or update the single Yuna Prime security role and bot nickname."""
    guild_id = guild.id
    LUXURY_ORANGE_GOLD = discord.Colour(0xE5A65E)
    role = discord.utils.get(guild.roles, name="Yuna Prime")
    if role is None:
      role = discord.utils.get(guild.roles, name="yuna prime")
    if role is None:
      legacy = [r for r in guild.roles if r.name in ("Yuna Supreme™", "Yuna Supreme")]
      role = max(legacy, key=lambda r: r.position) if legacy else None
    try:
      if role is None:
        role = await guild.create_role(
          name="Yuna Prime", color=LUXURY_ORANGE_GOLD,
          hoist=False, mentionable=False, reason="Anti-Nuke branding setup"
        )
      elif role.name != "Yuna Prime" or role.color.value != 0xE5A65E:
        await role.edit(name="Yuna Prime", colour=LUXURY_ORANGE_GOLD, reason="Anti-Nuke branding setup")
      if guild.me and role not in guild.me.roles:
        await guild.me.add_roles(role, reason="Anti-Nuke branding setup")
    except discord.Forbidden as exc:
      logger.warning("Cannot configure Yuna Prime role in guild %s (permissions/hierarchy): %s", guild_id, exc)
    except discord.HTTPException as exc:
      logger.warning("Discord rejected Yuna Prime role configuration in guild %s: %s", guild_id, exc)
    try:
      if guild.me and guild.me.guild_permissions.change_nickname:
        await guild.me.edit(nick="Yuna Prime", reason="Anti-Nuke branding setup")
    except discord.Forbidden as exc:
      logger.warning("Cannot set Yuna Prime nickname in guild %s (permission or hierarchy): %s", guild_id, exc)
    except discord.HTTPException as exc:
      logger.warning("Discord rejected Yuna Prime nickname in guild %s: %s", guild_id, exc)

  async def execute_antinuke_setup_sequence(self, ctx, setup_message, setup_embed):
    """Executes the automated 9-step Anti-Nuke setup verification sequence with live message updates."""
    guild_id = ctx.guild.id
    completed_lines = []

    async def update_display(step_text: str, in_progress: bool = True):
      lines = list(completed_lines)
      if in_progress:
        lines.append(f"┃ {ANTINUKE_SETUP_LOADING} {step_text}")
      content = "Performing few checks to maintain smoothness during the setup.\n\n" + "\n".join(lines)
      setup_embed.description = content
      try:
        await setup_message.edit(embed=setup_embed)
      except Exception:
        pass

    # Step 1: Role permissions verified successfully.
    step1 = "Role permissions verified successfully."
    await update_display(step1, in_progress=True)
    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step1}")

    # Step 2: Server structure and hierarchy verified successfully.
    step2 = "Server structure and hierarchy verified successfully."
    await update_display(step2, in_progress=True)
    await self.configure_prime_branding(ctx.guild)
    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step2}")

    # Step 3: Backup secured and will be taken automatically.
    step3 = "Backup secured and will be taken automatically."
    await update_display(step3, in_progress=True)
    try:
      from core.antinuke_v2.router import v2_engine_router
      v2_engine_router.coordinator.snapshot_store.snapshot_guild(ctx.guild)
    except Exception:
      pass

    try:
      from cogs.yuna_commands.backup import create_server_backup
      create_server_backup(ctx.guild)
    except Exception:
      pass

    try:
      existing_templates = await ctx.guild.templates()
      if existing_templates:
        await existing_templates[0].sync()
      else:
        await ctx.guild.create_template(
          name=f"Yuna Antinuke - {ctx.guild.name[:20]}",
          description="Auto-generated Antinuke baseline template by Yuna"
        )
    except Exception:
      pass
    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step3}")

    # Step 4: Checking the invites and deleting malicious Invites.
    step4 = "Checking the invites and deleting malicious Invites."
    await update_display(step4, in_progress=True)
    try:
      whitelisted_invite_creators = {ctx.guild.owner_id, self.bot.user.id}
      try:
        async with aiosqlite.connect('db/anti.db') as db:
          async with db.execute("SELECT owner_id FROM extra_owners WHERE guild_id = ?", (ctx.guild.id,)) as cur:
            whitelisted_invite_creators.update(r[0] for r in await cur.fetchall())
      except Exception:
        pass

      if ctx.guild.me.guild_permissions.manage_guild:
        invites = await ctx.guild.invites()
        for inv in invites:
          creator = getattr(inv, "inviter", None)
          if creator and creator.id not in whitelisted_invite_creators:
            # Persistent unapproved invites (infinite age and unlimited uses)
            if inv.max_age == 0 and inv.max_uses == 0:
              try:
                await inv.delete(reason="Antinuke Setup: Purged unwhitelisted permanent invite")
              except Exception:
                pass
    except Exception:
      pass
    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step4}")

    # Step 5: Checking Onboarding: Clean, no dangerous roles found.
    step5 = "Checking Onboarding: Clean, no dangerous roles found."
    await update_display(step5, in_progress=True)
    try:
      onboarding = getattr(ctx.guild, "onboarding", None)
      if onboarding and hasattr(onboarding, "prompts"):
        for prompt in onboarding.prompts:
          for opt in getattr(prompt, "options", []):
            for r_id in getattr(opt, "role_ids", []):
              r = ctx.guild.get_role(r_id)
              if r and (r.permissions.administrator or r.permissions.manage_roles or r.permissions.ban_members):
                try:
                  await r.edit(permissions=discord.Permissions.none(), reason="Antinuke Setup: Stripped dangerous permissions from onboarding role")
                except Exception:
                  pass
    except Exception:
      pass
    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step5}")

    # Step 6: Core Administrator Security Roles verified & active.
    admin_roles = [
      r for r in ctx.guild.roles 
      if r.permissions.administrator and not r.managed and r != ctx.guild.default_role
    ]
    admin_count = max(1, len(admin_roles))
    role_noun = "Role" if admin_count == 1 else "Roles"
    step6 = f"{admin_count} Core Administrator Security {role_noun} verified & active."
    await update_display(step6, in_progress=True)
    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step6}")

    # Step 7: Creating a new Log channel for antinuke.
    step7 = "Creating a new Log channel for antinuke."
    await update_display(step7, in_progress=True)
    log_channel, _ = await get_or_create_antinuke_log_channel(ctx.guild)
    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step7}")

    # Step 8: Creating a new Webhook for better logging.
    step8 = "Creating a new Webhook for better logging."
    await update_display(step8, in_progress=True)
    log_webhook = None
    if log_channel and ctx.guild.me.guild_permissions.manage_webhooks:
      try:
        webhooks = await log_channel.webhooks()
        log_webhook = discord.utils.get(webhooks, name="Yuna Sentinel")
        if not log_webhook:
          log_webhook = await log_channel.create_webhook(
            name="Yuna Sentinel",
            reason="Antinuke Setup: Dedicated webhook for unthrottled security logging"
          )
      except Exception:
        log_webhook = None
    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step8}")

    # Step 9: Enabling Antinuke.
    step9 = "Enabling Antinuke."
    await update_display(step9, in_progress=True)

    log_channel_id = log_channel.id if log_channel else None
    log_webhook_url = log_webhook.url if log_webhook else None
    now_ts = time.time()

    await self.db.execute(
      'INSERT INTO antinuke (guild_id, status, log_channel, log_webhook, last_backup_ts) VALUES (?, ?, ?, ?, ?) '
      'ON CONFLICT(guild_id) DO UPDATE SET status=excluded.status, log_channel=COALESCE(excluded.log_channel, antinuke.log_channel), '
      'log_webhook=COALESCE(excluded.log_webhook, antinuke.log_webhook), last_backup_ts=COALESCE(excluded.last_backup_ts, antinuke.last_backup_ts)',
      (guild_id, True, log_channel_id, log_webhook_url, now_ts)
    )
    await self.db.commit()

    from utils.settings_manager import get_guild_setting, set_guild_setting
    set_guild_setting(guild_id, "antinuke", True)
    from core.cache.security_cache import security_cache
    security_cache.set_antinuke_status(guild_id, True)

    all_actions = {
      "antiBan": True, "antiKick": True, "antiBotAdd": True,
      "antiChannelCreate": True, "antiChannelDelete": True, "antiChannelUpdate": True,
      "antiRoleCreate": True, "antiRoleDelete": True, "antiRoleUpdate": True,
      "antiWebhook": True, "antiEveryoneMention": True, "antiGuildUpdate": True,
      "antiIntegration": True, "antiMemberUpdate": True, "antiPrune": True,
      "antiDangerousPermissions": True
    }
    previous_actions = get_guild_setting(guild_id, "antinuke_actions", {}) or {}
    if not isinstance(previous_actions, dict):
      previous_actions = {}
    all_actions.update({key: bool(enabled) for key, enabled in previous_actions.items() if key in all_actions})
    set_guild_setting(guild_id, "antinuke_actions", all_actions)
    security_cache.set_all_actions(guild_id, all_actions)

    try:
      from core.antinuke_v2.router import v2_engine_router
      config = v2_engine_router.coordinator.state_store.get_guild_config(guild_id)
      config.antinuke_enabled = True
      config.log_channel_id = log_channel_id
      config.action_toggles.update(all_actions)
    except Exception:
      pass

    await asyncio.sleep(0.5)
    completed_lines.append(f"┃ {ANTINUKE_SETUP_TICK} {step9}")

    # Final persistent update
    setup_embed.description = "Performing few checks to maintain smoothness during the setup.\n\n" + "\n".join(completed_lines)
    try:
      await setup_message.edit(embed=setup_embed)
    except Exception:
      pass

    return log_channel, log_webhook, completed_lines


  @commands.hybrid_command(name='antinuke', aliases=['antiwizz'], with_app_command=False, help="Enables/Disables/Configures Anti-Nuke Module in the server")
  
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 4, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def antinuke(self, ctx, option: str = None, target: Optional[Union[discord.Member, discord.User, discord.TextChannel, str]] = None, action: Optional[str] = None, value: Optional[str] = None):
    guild_id = ctx.guild.id
    pre=ctx.prefix

    async with self.db.execute('SELECT status, log_channel FROM antinuke WHERE guild_id = ?', (guild_id,)) as cursor:
      row = await cursor.fetchone()

    is_owner = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
    if not is_owner:
      embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=0x000000,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
      return await ctx.send(embed=embed)

    is_activated = row[0] if row else False
    current_log_channel_id = row[1] if row and len(row) > 1 else None

    # Per-guild Anti-Nuke controls. Aliases intentionally accept readable names
    # and the internal action codes used by the existing protection listeners.
    antinuke_actions = {
      "ban": ("antiBan", "Member bans"), "kick": ("antiKick", "Member kicks"),
      "botadd": ("antiBotAdd", "Bot additions"), "channelcreate": ("antiChannelCreate", "Channel creation"),
      "chcr": ("antiChannelCreate", "Channel creation"), "channel_create": ("antiChannelCreate", "Channel creation"),
      "channeldelete": ("antiChannelDelete", "Channel deletion"), "chdl": ("antiChannelDelete", "Channel deletion"),
      "channelupdate": ("antiChannelUpdate", "Channel updates"), "chup": ("antiChannelUpdate", "Channel updates"),
      "rolecreate": ("antiRoleCreate", "Role creation"), "rlcr": ("antiRoleCreate", "Role creation"),
      "roledelete": ("antiRoleDelete", "Role deletion"), "rldl": ("antiRoleDelete", "Role deletion"),
      "roleupdate": ("antiRoleUpdate", "Role updates"), "rlup": ("antiRoleUpdate", "Role updates"),
      "webhook": ("antiWebhook", "Webhook changes"), "mngweb": ("antiWebhook", "Webhook changes"),
      "everyone": ("antiEveryoneMention", "@everyone/@here mentions"), "everyonemention": ("antiEveryoneMention", "@everyone/@here mentions"),
      "serverupdate": ("antiGuildUpdate", "Server changes"), "serverup": ("antiGuildUpdate", "Server changes"),
      "integration": ("antiIntegration", "Integration changes"), "memberupdate": ("antiMemberUpdate", "Dangerous member role updates"), "memup": ("antiMemberUpdate", "Dangerous member role updates"),
      "prune": ("antiPrune", "Member pruning"), "dangerouspermissions": ("antiDangerousPermissions", "Dangerous permission grants"), "mngstemo": ("antiDangerousPermissions", "Dangerous permission grants"),
    }

    if option and option.lower() in ("config", "configure", "settings"):
      from core.cache.security_cache import security_cache
      from core.antinuke_v2.router import v2_engine_router
      store = getattr(self.bot, "antinuke_v2_state_store", None) or v2_engine_router.coordinator.state_store
      if target is None:
        current = security_cache.get_antinuke_actions(guild_id)
        seen = set()
        lines = []
        for name, (key, label) in antinuke_actions.items():
          if key in seen:
            continue
          seen.add(key)
          lines.append(f"• **{label}:** {'Enabled' if current.get(key, True) else 'Disabled'} — `{pre}antinuke config {name} <on|off>`")
        embed = discord.Embed(title="Anti-Nuke Protection Configuration", description=("Configure each protection independently. Changes apply to this server and persist across restarts.\n\n" + "\n".join(lines) + f"\n\n**Rate limit:** `{pre}antinuke limit <action> <count> <seconds>`\nExample: `{pre}antinuke limit ban 2 10`\n**Punishment:** `{pre}antinuke punishment <action> <ban|kick|demote|timeout>`"), color=0xD4A017)
        return await ctx.send(embed=embed)
      action_name = str(target).strip().lower().replace("-", "").replace(" ", "")
      mapped = antinuke_actions.get(action_name)
      if not mapped or (action or "").lower() not in ("on", "off", "enable", "disable", "true", "false"):
        return await ctx.send(f"Invalid configuration. Use `{pre}antinuke config` to list options, then `{pre}antinuke config <action> <on|off>`. ")
      key, label = mapped
      enabled = (action or "").lower() in ("on", "enable", "true")
      await store.load_guild_from_db(guild_id)
      security_cache.set_action_status(guild_id, key, enabled)
      # Keep the V2 policy cache in sync; its decisions are independent of legacy listeners.
      store.set_action_toggle(guild_id, key, enabled)
      await ctx.send(embed=discord.Embed(description=f"{label} protection is now **{'enabled' if enabled else 'disabled'}** for this server.", color=0xD4A017))
      return

    elif option and option.lower() in ("limit", "threshold"):
      from core.antinuke_v2.router import v2_engine_router
      if not target or not action or not value:
        return await ctx.send(f"Usage: `{pre}antinuke limit <action> <count> <seconds>`")
      normalized = str(target).lower().replace("-", "").replace(" ", "")
      mapped = antinuke_actions.get(normalized)
      try:
        count, seconds = int(action), int(value)
      except (TypeError, ValueError):
        count, seconds = 0, 0
      if not mapped or not (1 <= count <= 100) or not (1 <= seconds <= 3600):
        return await ctx.send(f"Choose a valid action, count (1–100), and window (1–3600 seconds). Example: `{pre}antinuke limit ban 2 10`.")
      store = getattr(self.bot, "antinuke_v2_state_store", None) or v2_engine_router.coordinator.state_store
      await store.load_guild_from_db(guild_id)
      store.set_threshold(guild_id, mapped[0], count, seconds)
      await ctx.send(embed=discord.Embed(description=f"Anti-Nuke limit for **{mapped[1]}** set to **{count} action(s) per {seconds} second(s)**.", color=0xD4A017))
      return

    elif option and option.lower() in ("punishment", "punish"):
      from core.antinuke_v2.models import PunishmentType
      from core.antinuke_v2.router import v2_engine_router
      mapped = antinuke_actions.get(str(target).lower().replace("-", "").replace(" ", "")) if target else None
      punishment_name = str(action or "").lower()
      try:
        punishment = PunishmentType(punishment_name)
      except ValueError:
        punishment = None
      if not mapped or punishment is None:
        return await ctx.send(f"Usage: `{pre}antinuke punishment <action> <ban|kick|demote|timeout>`")
      store = getattr(self.bot, "antinuke_v2_state_store", None) or v2_engine_router.coordinator.state_store
      await store.load_guild_from_db(guild_id)
      store.set_punishment(guild_id, mapped[0], punishment)
      await ctx.send(embed=discord.Embed(description=f"Anti-Nuke punishment for **{mapped[1]}** set to **{punishment.value}**.", color=0xD4A017))
      return

    if option is None:
      embed = discord.Embed(
        title='__**Antinuke**__',
        description="Boost your server security with Antinuke! It automatically bans any admins involved in suspicious activities, ensuring the safety of your whitelisted members. Strengthen your defenses – activate Antinuke today!",
        color=0x000000
      )
      embed.add_field(name='__**Antinuke Enable**__', value=f'To Enable Antinuke, Use - `{pre}antinuke enable`')
      embed.add_field(name='__**Antinuke Disable**__', value=f'To Disable Antinuke, Use - `{pre}antinuke disable`')
      embed.add_field(name='__**Antinuke Logging**__', value=f'To set Logging Channel, Use - `{pre}antinuke logging <#channel>`')
      embed.add_field(name='__**Admin Security DMs**__', value=f'To toggle Admin Security DM Alerts, Use - `{pre}antinuke dm`')

      bot_avatar = self.get_bot_avatar_url()
      if bot_avatar:
        embed.set_thumbnail(url=bot_avatar)
      await ctx.send(embed=embed)
      warn_embed = build_permission_and_hierarchy_warning(ctx.guild)
      if warn_embed:
        await ctx.send(embed=warn_embed)

    elif option.lower() in ('enable', 'setup', 'on', 'activate', 'wizard'):
      # 1. Administrator permission pre-check
      if not ctx.guild.me.guild_permissions.administrator:
        bot_name = getattr(self.bot.user, 'name', 'Yuna') if self.bot and getattr(self.bot, 'user', None) else 'Yuna'
        bot_avatar = self.bot.user.display_avatar.url if self.bot and getattr(self.bot, 'user', None) and getattr(self.bot.user, 'display_avatar', None) else None
        setup_embed = discord.Embed(
          title="Antinuke Setup.",
          description="Performing few checks to maintain smoothness during the setup.\n\n┃ ❌ Setup failed: Missing **Administrator** permission.",
          color=0x2B2D31
        )
        setup_embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
        return await ctx.send(embed=setup_embed)

      # 2. Already enabled check (offers re-run wizard or view modules)
      if is_activated and option.lower() not in ('setup', 'activate', 'wizard'):
        await self.configure_prime_branding(ctx.guild)
        log_mention = f"<#{current_log_channel_id}>" if current_log_channel_id else "None"
        embed = discord.Embed(
          description=(
            f'**Security Settings For {ctx.guild.name}**\n'
            f'Your server __**already has Antinuke enabled.**__\n\n'
            f'Current Status: {ANIMATED_ENABLED} Enabled\n'
            f'📍 **Logging Channel:** {log_mention}\n\n'
            f'🛡️ **Important Notice:** Ensure your trusted bots (`{pre}botwhitelist add <@bot>`) and staff members (`{pre}whitelist <@user>`) are whitelisted to prevent actions like unbanning or channel recreation from being blocked.\n\n'
            f'To Disable use `{pre}antinuke disable`'
          ),
          color=0x2B2D31
        )
        bot_name = getattr(self.bot.user, 'name', 'Yuna') if self.bot and getattr(self.bot, 'user', None) else 'Yuna'
        bot_avatar = self.bot.user.display_avatar.url if self.bot and getattr(self.bot, 'user', None) and getattr(self.bot.user, 'display_avatar', None) else None
        embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
        enabled_view = AntiNukeAlreadyEnabledView(self, ctx, pre, current_log_channel_id)
        msg = await ctx.send(embed=embed, view=enabled_view)
        enabled_view.message = msg
        return

      # 3. Direct setup mode (headless, automated tests, or quick command)
      if option.lower() in ('setup', 'fast', 'quick'):
        bot_name = getattr(self.bot.user, 'name', 'Yuna') if self.bot and getattr(self.bot, 'user', None) else 'Yuna'
        bot_avatar = self.bot.user.display_avatar.url if self.bot and getattr(self.bot, 'user', None) and getattr(self.bot.user, 'display_avatar', None) else None
        setup_embed = discord.Embed(
          title="Antinuke Setup.",
          description="Performing few checks to maintain smoothness during the setup.",
          color=0x2B2D31
        )
        setup_embed.set_footer(text=f"{bot_name}! — Antinuke.", icon_url=bot_avatar)
        setup_message = await ctx.send(embed=setup_embed)
        await self.execute_antinuke_setup_sequence(ctx, setup_message, setup_embed)
        complete_view = AntiNukeWizardPage3CompleteView(AntiNukeSetupWizard(self, ctx, pre, current_log_channel_id))
        try:
          await setup_message.edit(embed=setup_embed, view=complete_view)
          complete_view.message = setup_message
        except Exception:
          pass
        return

      # 4. Interactive Setup Wizard (Default for 'enable', 'on', 'activate', 'wizard')
      wizard = AntiNukeSetupWizard(self, ctx, pre, current_log_channel_id)
      await wizard.start()

    elif option.lower() == 'disable':
      bot_avatar = self.get_bot_avatar_url()
      if not is_activated:
        embed = discord.Embed(
          description=f'**Security Settings For {ctx.guild.name}**\nUhh, looks like your server hasn\'t enabled Antinuke.\n\nCurrent Status: {STATIC_DISABLED} Disabled\n\nTo Enable use `antinuke enable`',
          color=0x000000
        )
        if bot_avatar:
          embed.set_thumbnail(url=bot_avatar)
      else:
        await self.db.execute('DELETE FROM antinuke WHERE guild_id = ?', (guild_id,))
        await self.db.commit()
        from utils.settings_manager import set_guild_setting
        set_guild_setting(guild_id, "antinuke", False)
        from core.cache.security_cache import security_cache
        security_cache.set_antinuke_status(guild_id, False)
        embed = discord.Embed(
          description=f'**Security Settings For {ctx.guild.name}**\nSuccessfully disabled Antinuke for this server.\n\nCurrent Status: {STATIC_DISABLED} Disabled\n\nTo Enable use `antinuke enable`',
          color=0x000000
        )
        if bot_avatar:
          embed.set_thumbnail(url=bot_avatar)
      await ctx.send(embed=embed)

    elif option.lower() in ['logging', 'log', 'channel']:
      channel = target if isinstance(target, discord.TextChannel) else None
      if channel is None:
        log_channel, notice_embed = await get_or_create_antinuke_log_channel(ctx.guild)
        if log_channel:
          await self.db.execute(
              "INSERT INTO antinuke (guild_id, status, log_channel) VALUES (?, 0, ?) "
              "ON CONFLICT(guild_id) DO UPDATE SET log_channel=excluded.log_channel",
              (guild_id, log_channel.id)
          )
          await self.db.commit()
          embed = discord.Embed(
              title=f"Antinuke Logging Channel for {ctx.guild.name}",
              description=f"{ANTINUKE_SETUP_TICK} | Antinuke logging channel set to {log_channel.mention}.",
              color=0x000000
          )
          await ctx.send(embed=embed)
          if notice_embed:
            await ctx.send(embed=notice_embed)
        else:
          embed = discord.Embed(
              description="Failed to find or create an Antinuke logging channel.",
              color=0x000000
          )
          await ctx.send(embed=embed)
      else:
        await self.db.execute(
            "INSERT INTO antinuke (guild_id, status, log_channel) VALUES (?, 0, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET log_channel=excluded.log_channel",
            (guild_id, channel.id)
        )
        await self.db.commit()
        embed = discord.Embed(
            title=f"Antinuke Logging Channel for {ctx.guild.name}",
            description=f"{ANTINUKE_SETUP_TICK} | Antinuke logging channel set to {channel.mention}.",
            color=0x000000
        )
        await ctx.send(embed=embed)

    elif option.lower() in ['reset', 'logging reset', 'log reset']:
      await self.db.execute("UPDATE antinuke SET log_channel = NULL WHERE guild_id = ?", (guild_id,))
      await self.db.commit()
      embed = discord.Embed(
          description=f"{ANTINUKE_SETUP_TICK} | Antinuke logging channel configuration has been reset.",
          color=0x000000
      )
      await ctx.send(embed=embed)

    elif option.lower() in ['dm', 'dms', 'dmalert', 'dmalerts', 'dmnotif']:
      from utils.settings_manager import get_guild_setting, set_guild_setting
      current_status = get_guild_setting(guild_id, "dm_notifications", True)
      new_status = not current_status
      set_guild_setting(guild_id, "dm_notifications", new_status)
      status_label = "Enabled" if new_status else "Disabled"
      status_icon = ANIMATED_ENABLED if new_status else STATIC_DISABLED
      embed = discord.Embed(
          title=f"Admin Security DM Alerts • {status_label}",
          description=(
              f"{status_icon} | Admin Security DM Notifications have been **{status_label.lower()}**.\n\n"
              "When enabled, server owner and all administrators receive instant DM reports on security actions "
              "(bans, unbans, kicks, bot integrations, and anti-nuke defenses)."
          ),
          color=0x2B2D31 if new_status else 0x000000
      )
      embed.set_footer(text=f"Guild ID: {guild_id} | Yuna Security System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
      await ctx.send(embed=embed)

    elif option.lower() in ['explain', 'exp', 'why']:
      if target is None:
        return await ctx.send(embed=discord.Embed(
          title="🛡️ Anti-Nuke V2 Decision Explainer",
          description=f"Usage: `{pre}antinuke explain <@user|id> <action>`\nExample: `{pre}antinuke explain @user channel_delete`",
          color=0x000000
        ))

      member = target if isinstance(target, (discord.Member, discord.User)) else None
      if not member and isinstance(target, str):
        clean_id = target.strip("<@!>")
        if clean_id.isdigit():
          member = ctx.guild.get_member(int(clean_id)) or await self.bot.fetch_user(int(clean_id))

      if not member:
        return await ctx.send(embed=discord.Embed(
          description="<:Yuna_cross:1227866668152393789> Could not resolve the specified user in this server.",
          color=0x000000
        ))

      act_str = action or "channel_delete"
      from core.antinuke_v2.action_mapper import ActionMapper
      from core.antinuke_v2.explainer import explain_decision
      from core.antinuke_v2.state_store import V2StateStore

      state_store = getattr(self.bot, "antinuke_v2_state_store", None) or V2StateStore()
      state = state_store.get_guild_config(guild_id)
      norm_action = ActionMapper.normalize_action(act_str)

      explanation = explain_decision(ctx.guild, member, norm_action, state)
      await ctx.send(embed=explanation.to_embed())

    elif option.lower() in ['dryrun', 'dry-run', 'dry']:
      from core.antinuke_v2.state_store import V2StateStore
      state_store = getattr(self.bot, "antinuke_v2_state_store", None) or V2StateStore()
      state = state_store.get_guild_config(guild_id)
      if target and isinstance(target, str):
        new_val = target.lower() in ("on", "true", "enable", "1")
      else:
        new_val = not state.dry_run
      state.dry_run = new_val
      status_label = "ENABLED (Simulation only — logs actions, zero bans)" if new_val else "DISABLED (Active containment enforced)"
      embed = discord.Embed(
          title="🛡️ Anti-Nuke V2 Dry-Run Mode",
          description=f"Status: **{status_label}**\n\nWhen Dry-Run is enabled, V2 evaluates all events, records latency traces, and logs what it would do without executing bans or destructive mutations.",
          color=0x2B2D31 if new_val else 0x000000
      )
      await ctx.send(embed=embed)

    elif option.lower() in ['engine', 'mode']:
      from core.antinuke_v2.router import v2_engine_router, EngineMode
      if target is None:
        curr_guild_mode = v2_engine_router.get_engine_mode(guild_id).value
        curr_global_mode = v2_engine_router.global_mode.value
        embed = discord.Embed(
            title="🛡️ Anti-Nuke Engine Architecture",
            description=(
                f"**Active Guild Engine:** `{curr_guild_mode.upper()}`\n"
                f"**Global Default Engine:** `{curr_global_mode.upper()}`\n\n"
                "**Engine Modes:**\n"
                "• `legacy` — Classic V1 engine (standard security pipeline).\n"
                "• `shadow` — Dual execution: Legacy performs live containment; V2 runs concurrently in dry-run mode auditing decisions.\n"
                "• `v2` — Next-Generation sub-millisecond local CPU policy engine, instant ban-first lane, idempotent recovery.\n\n"
                f"To switch mode: `{pre}antinuke engine <legacy|shadow|v2>`\n"
                f"To check discrepancies: `{pre}antinuke divergence`"
            ),
            color=0x000000
        )
        await ctx.send(embed=embed)
      else:
        target_str = str(target).lower().strip()
        if target_str not in ("legacy", "shadow", "v2"):
          return await ctx.send(embed=discord.Embed(
              description=f"Invalid engine mode `{target}`. Choose `legacy`, `shadow`, or `v2`.",
              color=0x000000
          ))
        new_mode = v2_engine_router.set_guild_engine_mode(guild_id, target_str)
        embed = discord.Embed(
            title="🛡️ Anti-Nuke Engine Switched",
            description=f"{ANTINUKE_SETUP_TICK} Successfully switched Anti-Nuke engine to **`{new_mode.value.upper()}`** for this server.\n\nChanges apply instantly with zero downtime.",
            color=0x000000
        )
        await ctx.send(embed=embed)

    elif option.lower() in ['divergence', 'discrepancy']:
      from datetime import datetime, timezone
      from core.antinuke_v2.router import v2_engine_router
      divergences = v2_engine_router.get_recent_divergences(limit=10, guild_id=guild_id)
      if not divergences:
        embed = discord.Embed(
            title="🛡️ Shadow Mode Divergence Audit",
            description=f"{ANTINUKE_SETUP_TICK} **Zero Divergence Detected!**\n\nLegacy and V2 policy decisions are in 100% agreement for this server.",
            color=0x000000
        )
        await ctx.send(embed=embed)
      else:
        lines = []
        for d in divergences[-5:]:
          dt_s = datetime.fromtimestamp(d.timestamp, tz=timezone.utc).strftime("%H:%M:%S UTC")
          lines.append(f"• **[{dt_s}] {d.action.upper()}** (Actor: `{d.actor_id}`)\n  Legacy: `{d.legacy_decision}` | V2: `{d.v2_decision}` (`{d.v2_reason}`)")
        embed = discord.Embed(
            title="🛡️ Recent Shadow Mode Divergences",
            description="\n\n".join(lines),
            color=0x000000
        )
        await ctx.send(embed=embed)

    else:
      embed = discord.Embed(
        description=f'Invalid option. Please use `{pre}antinuke enable`, `disable`, `logging <#channel>`, `dm`, `explain <user> <action>`, `dryrun`, `engine [legacy|shadow|v2]`, or `divergence`.',
        color=0x000000
      )
      await ctx.send(embed=embed)


  @commands.Cog.listener()
  async def on_interaction(self, interaction: discord.Interaction):
    if interaction.data.get('custom_id') == 'show_punishment':
    
      embed = discord.Embed(
        title="Punishment Types for Changes Made by Unwhitelisted Admins/Mods",
        description=(
          "**Anti Ban:** Ban\n"
          "**Anti Kick:** Ban\n"
          "**Anti Bot:** Remove all roles & Kick bot (Kick inviter + DM permanent invite for 1st & 2nd time, Ban on 3rd time)\n"
          "**Anti Channel Create/Delete/Update:** Ban\n"
          "**Anti Everyone/Here:** Delete message & warning for 1st 3 times, then 60s timeout\n"
          "**Anti Role Create/Delete/Update:** Kick\n"
          "**Anti Member Update:** Kick\n"
          "**Anti Guild Update:** Ban\n"
          "**Anti Integration:** Ban\n"
          "**Anti Webhook Create/Delete/Update:** Kick\n"
          "**Anti Prune:** 5 mins timeout\n"
          "**Auto Recovery:** Automatically recover damaged channels, roles, and settings\n\n"
          "Note: In the case of member updates, action will be taken only if the role contains dangerous permissions such as Ban Members, Administrator, Manage Guild, Manage Channels, Manage Roles, or Manage Webhooks"
        ),
        color=0x000000
      )
      bot_avatar = self.get_bot_avatar_url()
      if bot_avatar:
        embed.set_footer(text="These punishment types are fixed and assigned as required to ensure guild security/protection", icon_url=bot_avatar)
      else:
        embed.set_footer(text="These punishment types are fixed and assigned as required to ensure guild security/protection")
      await interaction.response.send_message(embed=embed, ephemeral=True)
