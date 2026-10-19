from __future__ import annotations
import typing
from discord.ext import commands
from discord import *
from PIL import Image, ImageDraw, ImageFont
import discord
import json
import datetime
import asyncio
import time
import aiosqlite
from utils import Paginator, DescriptionEmbedPaginator
from utils.Tools import *
from utils.config import OWNER_IDS
from core import Context
import sqlite3
import os
import requests
import aiohttp
from io import BytesIO
from discord.errors import Forbidden
from discord import Embed
from collections import Counter

_BADGE_CACHE: dict[str, bytes] = {}




BADGE_URLS = {
    "owner": "https://cdn.discordapp.com/emojis/1228227536207740989.png",
    "staff": "https://cdn.discordapp.com/emojis/1228227884481515613.png",
    "partner": "https://cdn.discordapp.com/emojis/1228228301089144976.png",
    "sponsor": "https://cdn.discordapp.com/emojis/1228246375180013678.png",
    "friend": "https://cdn.discordapp.com/emojis/1228229690376982549.png",
    "early": "https://cdn.discordapp.com/emojis/1228241490246111302.png",
    "vip": "https://cdn.discordapp.com/emojis/1228230884583276584.png",
    "bug": "https://cdn.discordapp.com/emojis/1228231513456382015.png"
}

BADGE_NAMES = {
    "owner": "Owner",
    "staff": "Staff",
    "partner": "Partner",
    "sponsor": "Sponsor",
    "friend": "Owner's Friend",
    "early": "Early Supporter",
    "vip": "VIP",
    "bug": "Bug Hunter"
}


db_folder = 'db'
db_file = 'badges.db'
db_path = os.path.join(db_folder, db_file)
FONT_PATH = os.path.join('utils', 'arial.ttf')


conn = sqlite3.connect(db_path)
c = conn.cursor()


c.execute('''CREATE TABLE IF NOT EXISTS badges (
    user_id INTEGER PRIMARY KEY,
    owner INTEGER DEFAULT 0,
    staff INTEGER DEFAULT 0,
    partner INTEGER DEFAULT 0,
    sponsor INTEGER DEFAULT 0,
    friend INTEGER DEFAULT 0,
    early INTEGER DEFAULT 0,
    vip INTEGER DEFAULT 0,
    bug INTEGER DEFAULT 0
)''')
conn.commit()

def add_badge(user_id, badge):
    c.execute(f"SELECT {badge} FROM badges WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result is None:
        c.execute(f"INSERT INTO badges (user_id, {badge}) VALUES (?, 1)", (user_id,))
    elif result[0] == 0:
        c.execute(f"UPDATE badges SET {badge} = 1 WHERE user_id = ?", (user_id,))
    else:
        return False
    conn.commit()
    return True

def remove_badge(user_id, badge):
    c.execute(f"SELECT {badge} FROM badges WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0] == 1:
        c.execute(f"UPDATE badges SET {badge} = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    return False


def convert_time_to_seconds(time_str):
    time_units = {
        "h": "hours",
        "d": "days",
        "m": "months"
    }
    num = int(time_str[:-1])
    unit = time_units.get(time_str[-1])
    return datetime.timedelta(**{unit: num})


async def do_removal(ctx, limit, predicate, *, before=None, after=None):
  if limit > 100:
      limit = 100
  if limit <= 0:
      return await ctx.error("Amount of messages to clear must be between 1 and 100.")

  if before is None:
      before = ctx.message
  elif isinstance(before, int):
      before = discord.Object(id=before)
  elif hasattr(before, "id"):
      before = discord.Object(id=before.id)

  if after is not None:
      if isinstance(after, int):
          after = discord.Object(id=after)
      elif hasattr(after, "id"):
          after = discord.Object(id=after.id)

  try:
      deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
  except discord.Forbidden:
      return await ctx.error("I do not have permissions to delete messages.")
  except discord.HTTPException as e:
      if getattr(e, "status", None) == 429:
          return await ctx.error("Discord API is temporarily rate limited. Please wait a few moments and try again.")
      return await ctx.error(f"Error: {e} (try a smaller search?)")
  except Exception as e:
      return await ctx.error(f"Failed to clear messages: {e}")

  spammers = Counter(
      getattr(m.author, "display_name", getattr(m.author, "name", "Unknown"))
      if getattr(m, "author", None) else "Unknown"
      for m in deleted
  )
  count_deleted = len(deleted)
  messages = [f'<a:tick:1558726958802800660> | {count_deleted} message{" was" if count_deleted == 1 else "s were"} removed.']
  if count_deleted:
      messages.append("")
      spammers_list = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
      messages.extend(f"**{name}**: {count}" for name, count in spammers_list)

  to_send = "\n".join(messages)

  if len(to_send) > 2000:
      await ctx.send(f"<a:tick:1558726958802800660> | Successfully removed {count_deleted} messages.", delete_after=3)
  else:
      await ctx.send(to_send, delete_after=3)

def load_owner_ids():
    return OWNER_IDS



async def is_staff(user, staff_ids):
    return user.id in staff_ids


async def is_owner_or_staff(ctx):
    return await is_staff(ctx.author, ctx.cog.staff) or ctx.author.id in OWNER_IDS


class Owner(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.staff = set()
        self.np_cache = []
        self.db_path = 'db/np.db'
        self.stop_tour = False
        self.bot_owner_ids = OWNER_IDS
        self._last_sync_time = 0
        asyncio.create_task(self.setup_database())
        asyncio.create_task(self.load_staff())
        

    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS staff (
                    id INTEGER PRIMARY KEY
                )
            ''')
            await db.commit()

    

    async def load_staff(self):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT id FROM staff') as cursor:
                    self.staff = {row[0] for row in await cursor.fetchall()}
        except Exception:
            pass

    @commands.command(name="syncemojis", aliases=["emojisync", "appemojis"], hidden=True, help="Syncs and maps all application emojis from Discord Developer Portal.")
    @commands.is_owner()
    async def sync_emojis_command(self, ctx: commands.Context):
        msg = await ctx.reply("🔄 Fetching and mapping application emojis from Discord Developer Portal...")
        try:
            bot = self.client
            total, added = await bot.sync_application_emojis()
            embed = discord.Embed(
                title="<a:tick:1558726958802800660> Application Emojis Synced",
                description=(
                    f"Successfully synced with the Discord Developer Portal!\n\n"
                    f"• **Total Application Emojis:** `{total}`\n"
                    f"• **Newly Mapped:** `{added}`\n"
                    f"• **Saved To:** `utils/application_emojis.json`\n"
                    f"• **Dashboard Cache:** `Refreshed`\n\n"
                    f"All new emojis are immediately available for bot commands, embeds, and the web dashboard!"
                ),
                color=0x2B2D31
            )
            await msg.edit(content=None, embed=embed)
        except Exception as e:
            await msg.edit(content=f"❌ Failed to sync application emojis: {e}")

    @commands.command(name="adminhelp", aliases=["ah", "adminh", "ownerhelp", "owner.help", "owner-help"], hidden=True, help="Displays the confidential Bot Owner Admin Help menu.")
    @commands.is_owner()
    async def adminhelp(self, ctx: commands.Context):
        prefix = ctx.prefix
        embed = discord.Embed(
            title="🛡️ Yuna Confidential Owner & Admin Help",
            description=f"Welcome, **{ctx.author.name}**! Listed below are all high-security owner commands available exclusively to bot owners.\n\n"
                        f"`Prefix:` `{prefix}` • `Total Categories:` `7`\n"
                        "──────────────────────────────────────────────",
            color=0x2B2D31
        )
        if ctx.bot.user:
            embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)

        embed.add_field(
            name="⚙️ System & VPS Management",
            value=(
                f"`{prefix}gitpull` • Pull latest code from GitHub & restart VPS\n"
                f"`{prefix}gitstatus` • View deployed Git commit info & version\n"
                f"`{prefix}webhookstatus` • Check webhook deployment server\n"
                f"`{prefix}sync` [guild/db/force/clear] • Sync slash commands & databases\n"
                f"`{prefix}Yuna.restart` • Restart bot process\n"
                f"`{prefix}save_settings` • Export & backup settings to JSON"
            ),
            inline=False
        )

        embed.add_field(
            name="🌐 Server & Guild Operations",
            value=(
                f"`{prefix}slist` • List joined servers sorted by member count\n"
                f"`{prefix}getguild` <guild_id> • View server details by ID\n"
                f"`{prefix}getinvite` [guild_id/channel_id] • Fetch/create guild invite\n"
                f"`{prefix}leaveguild` <guild_id> • Force bot to leave a server\n"
                f"`{prefix}guildinfo` <guild_id> • Detailed technical footprint of guild\n"
                f"`{prefix}servertour` • Toggle channel/guild inspection tour\n"
                f"`{prefix}mutual` <user> • View mutual servers with user"
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Global Multi-Guild Moderation",
            value=(
                f"`{prefix}globalban` <user> [reason] • Multi-guild ban user\n"
                f"`{prefix}globalunban` <user> • Lift multi-guild ban\n"
                f"`{prefix}guildban` <guild_id> <user> • Remote ban in target guild\n"
                f"`{prefix}guildunban` <guild_id> <user> • Remote unban in target guild\n"
                f"`{prefix}kick` <user> [reason] • Multi-guild kick user\n"
                f"`{prefix}timeout` <user> • 28-day multi-guild timeout\n"
                f"`{prefix}nick` <user> <nickname> • Multi-guild nickname change\n"
                f"`{prefix}clearnick` <user> • Reset nickname across mutual guilds\n"
                f"`{prefix}freezenick` <user> • Freeze user nickname across guilds\n"
                f"`{prefix}unfreezenick` <user> • Unfreeze user nickname\n"
                f"`{prefix}forcepurgebots` [amount] • Owner bot message purge\n"
                f"`{prefix}forcepurgeuser` <user> [amount] • Owner user message purge"
            ),
            inline=False
        )

        embed.add_field(
            name="🔒 Access Control & Blacklists",
            value=(
                f"`{prefix}ownerban` <user> • Global owner ban from bot access\n"
                f"`{prefix}ownerunban` <user> • Remove global owner ban\n"
                f"`{prefix}owners` • List authorized bot owners\n"
                f"`{prefix}blacklist` user/guild add/remove/show • Blacklist user/guild\n"
                f"`{prefix}block` user/guild add/remove • Block user/guild access"
            ),
            inline=False
        )

        embed.add_field(
            name="⚡ No-Prefix & Partner Systems",
            value=(
                f"`{prefix}np` add/remove/list/status • Manage user no-prefix\n"
                f"`{prefix}autonp` add/remove/list • Partner guild auto no-prefix"
            ),
            inline=False
        )

        embed.add_field(
            name="👥 Staff & Badges Administration",
            value=(
                f"`{prefix}staff_add` <user> • Grant bot staff privileges\n"
                f"`{prefix}staff_remove` <user> • Revoke bot staff privileges\n"
                f"`{prefix}staff_list` • List all active bot staff members\n"
                f"`{prefix}bdg` add/remove <user> <badge> • Manage profile badges"
            ),
            inline=False
        )

        embed.add_field(
            name="💳 Payment & Direct Communication",
            value=(
                f"`{prefix}payment_add` <amount> <url> • Add payment QR override\n"
                f"`{prefix}payment_remove` <amount> • Remove payment QR override\n"
                f"`{prefix}dm` <user> <message> • Direct message user as bot"
            ),
            inline=False
        )

        embed.set_footer(
            text=f"Requested by {ctx.author} • Strictly Confidential Bot Owner Controls",
            icon_url=ctx.author.display_avatar.url
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="sync", aliases=["syncapp", "syncslash", "slashsync", "appsync"], hidden=True, help="Syncs slash commands, active guilds, and databases.")
    @commands.is_owner()
    @commands.cooldown(1, 10, commands.BucketType.default)
    async def sync_commands(self, ctx: commands.Context, spec: typing.Optional[str] = None):
        spec_lower = str(spec or "").lower().strip()
        now = time.time()
        cooldown_seconds = 60
        if not hasattr(self, "_last_sync_time"):
            self._last_sync_time = 0

        # Sub-mode: Database-only synchronization
        if spec_lower in ("db", "database", "databases", "settings", "mongo"):
            msg = await ctx.reply("🌸 **Synchronizing database settings & guild logs...**", mention_author=False)
            try:
                from utils.settings_manager import settings_manager
                from utils.guild_logs_db import sync_all_active_guilds

                settings_manager.sync_all_from_databases()
                for guild in self.client.guilds:
                    settings_manager.get_guild_settings(guild.id)
                settings_manager._save_to_disk_sync()
                settings_manager.schedule_save()

                guild_stats = sync_all_active_guilds(self.client)

                embed = discord.Embed(
                    title="<a:tick:1558726958802800660> Database Synchronization Complete",
                    description=(
                        f"• Synced settings for **{len(self.client.guilds)}** joined guilds.\n"
                        f"• Verified **{guild_stats.get('total', len(self.client.guilds))}** active guild log records.\n"
                        f"• Local cache saved to `db/local_settings.json` and mirrored to MongoDB Atlas."
                    ),
                    color=0x2ECC71
                )
                await msg.edit(content=None, embed=embed)
            except Exception as e:
                await msg.edit(content=f"❌ **Database sync failed:** `{e}`")
            return

        # Slash sync sub-modes: guild, clear, force, or global
        is_force = (spec_lower == "force")
        if spec_lower not in ("guild", "clear") and not is_force and (now - self._last_sync_time) < cooldown_seconds:
            remaining = int(cooldown_seconds - (now - self._last_sync_time))
            embed = discord.Embed(
                title="⏳ Rate-Limit Protection",
                description=f"Slash command sync was run recently. Please wait **{remaining}s** before syncing again to avoid Discord API rate limits (HTTP 429).\n\n*Tip: Use `{ctx.prefix}sync force` if you explicitly need to bypass this cooldown, or `{ctx.prefix}sync db` to sync databases only.*",
                color=0xE74C3C
            )
            return await ctx.reply(embed=embed, mention_author=False)

        msg = await ctx.reply("🌸 **Synchronizing slash commands and database records...**", mention_author=False)
        self._last_sync_time = now

        # 1. Background database & settings sync for active guilds
        db_synced_count = len(self.client.guilds)
        try:
            from utils.settings_manager import settings_manager
            from utils.guild_logs_db import sync_all_active_guilds
            for guild in self.client.guilds:
                settings_manager.get_guild_settings(guild.id)
            settings_manager._save_to_disk_sync()
            settings_manager.schedule_save()
            sync_all_active_guilds(self.client)
        except Exception as db_err:
            print(f"[SYNC] Non-fatal DB sync warning: {db_err}")

        # 2. Perform tree slash command synchronization with Discord API
        try:
            from core.discord.request_manager import request_manager, Priority

            if spec_lower == "guild":
                self.client.tree.copy_global_to(guild=ctx.guild)
                async def _sync_guild():
                    return await self.client.tree.sync(guild=ctx.guild)
                synced = await request_manager.enqueue(
                    priority=Priority.P0_CRITICAL,
                    task_id=f"sync_guild_{ctx.guild.id}_{now}",
                    coro_func=_sync_guild,
                    guild_id=ctx.guild.id
                )
                embed = discord.Embed(
                    title="<a:tick:1558726958802800660> Guild Slash Commands Synced",
                    description=(
                        f"• Synced **{len(synced)}** slash commands directly to **{ctx.guild.name}** (`{ctx.guild.id}`).\n"
                        f"• Verified database records for **{db_synced_count}** servers."
                    ),
                    color=0x2ECC71
                )
                await msg.edit(content=None, embed=embed)

            elif spec_lower == "clear":
                self.client.tree.clear_commands(guild=ctx.guild)
                async def _clear_sync():
                    return await self.client.tree.sync(guild=ctx.guild)
                await request_manager.enqueue(
                    priority=Priority.P0_CRITICAL,
                    task_id=f"sync_clear_{ctx.guild.id}_{now}",
                    coro_func=_clear_sync,
                    guild_id=ctx.guild.id
                )
                embed = discord.Embed(
                    title="🧹 Guild Commands Cleared",
                    description=f"Cleared and synchronized slash commands for **{ctx.guild.name}**.",
                    color=0x2ECC71
                )
                await msg.edit(content=None, embed=embed)

            else:
                async def _sync_global():
                    return await self.client.tree.sync()
                synced = await request_manager.enqueue(
                    priority=Priority.P0_CRITICAL,
                    task_id=f"sync_global_{now}",
                    coro_func=_sync_global
                )
                import os
                hash_file = "db/slash_sync.hash"
                if os.path.exists(hash_file):
                    try:
                        os.remove(hash_file)
                    except Exception:
                        pass
                cmd_count = len(synced)
                quota_warning = f" (⚠️ **{100 - cmd_count} slots left**)" if cmd_count >= 90 else ""
                embed = discord.Embed(
                    title="<a:tick:1558726958802800660> Global Synchronization Complete",
                    description=(
                        f"• Successfully synced **{cmd_count}/100** application slash commands globally with Discord!{quota_warning}\n"
                        f"• Synchronized & verified settings across **{db_synced_count}** active servers."
                    ),
                    color=0x2ECC71
                )
                await msg.edit(content=None, embed=embed)

        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = getattr(e, 'retry_after', 60.0)
                await msg.edit(content=f"⚠️ **Discord API Rate Limited (HTTP 429):** Discord is rate-limiting slash command syncs. Please wait **{retry_after:.1f}s** before trying again.")
            else:
                await msg.edit(content=f"❌ **Discord HTTP Error ({e.status}):** `{e.text}`")
        except Exception as e:
            await msg.edit(content=f"❌ **Failed to sync commands:** `{e}`")

    @commands.command(hidden=True, name="staff_add", aliases=["staffadd", "addstaff"], help="Adds a user to the staff list.")
    @commands.is_owner()
    async def staff_add(self, ctx, user: discord.User):
        if user.id in self.staff:
            sonu = discord.Embed(title="<:Yuna_notify:1227866804630720565> Access Denied", description=f"{user} is already in the staff list.", color=0x000000)
            await ctx.reply(embed=sonu, mention_author=False)
        else:
            self.staff.add(user.id)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('INSERT OR IGNORE INTO staff (id) VALUES (?)', (user.id,))
                await db.commit()
            sonu2 = discord.Embed(title="<a:tick:1558726958802800660> Success", description=f"Added {user} to the staff list.", color=0x000000)
            await ctx.reply(embed=sonu2, mention_author=False)

    @commands.command(hidden=True, name="staff_remove", aliases=["staffremove", "removestaff"], help="Removes a user from the staff list.")
    @commands.is_owner()
    async def staff_remove(self, ctx, user: discord.User):
        if user.id not in self.staff:
            sonu = discord.Embed(title="<:Yuna_notify:1227866804630720565> Access Denied", description=f"{user} is not in the staff list.", color=0x000000)
            await ctx.reply(embed=sonu, mention_author=False)
        else:
            self.staff.remove(user.id)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('DELETE FROM staff WHERE id = ?', (user.id,))
                await db.commit()
                sonu2 = discord.Embed(title="<a:tick:1558726958802800660> Success", description=f"Removed {user} from the staff list.", color=0x000000)
            await ctx.reply(embed=sonu2, mention_author=False)

    @commands.command(hidden=True, name="staff_list", aliases=["stafflist", "liststaff", "staffs"], help="Lists all staff members.")
    @commands.is_owner()
    async def staff_list(self, ctx):
        if not self.staff:
            await ctx.send("The staff list is currently empty.")
        else:
            member_list = []
            for staff_id in self.staff:
                member = await self.client.fetch_user(staff_id)
                member_list.append(f"{member.name}#{member.discriminator} (ID: {staff_id})")
            staff_display = "\n".join(member_list)
            sonu = discord.Embed(title="<:Yuna_staff:1228227884481515613> Yuna Staffs", description=f"\n{staff_display}", color=0x000000)
            await ctx.send(embed=sonu)

    @commands.command(hidden=True, name="slist")
    @commands.check(is_owner_or_staff)
    async def _slist(self, ctx):
        sonuop = sorted(self.client.guilds, key=lambda g: g.member_count, reverse=True)
        entries = [
            f"`#{i}` | [{g.name}](https://discord.com/guilds/{g.id}) - {g.member_count}"
            for i, g in enumerate(sonuop, start=1)
        ]
        embeds = DescriptionEmbedPaginator(
            entries=entries,
            description="",
            title=f"Guild List of Yuna [{len(self.client.guilds)}]",
            color=0x000000,
            per_page=10).get_pages()
        paginator = Paginator(ctx, embeds)
        await paginator.paginate()

    @commands.command(hidden=True, name="mutual", aliases=["mutuals"])
    @commands.is_owner()
    async def mutual_servers(self, ctx: Context, user: discord.User):
        
        if not user:
            await ctx.send("User not found.")
            return
        
        mutual_guilds = [guild for guild in self.client.guilds if user in guild.members]

        if mutual_guilds:
            entries = [
                f"`{no}` | [{guild.name}](https://discord.com/channels/{guild.id}) (ID: {guild.id})"
                for no, guild in enumerate(mutual_guilds, start=1)
            ]
            embeds = DescriptionEmbedPaginator(
                entries=entries,
                title=f"Mutual Guilds with {user.name} [{len(mutual_guilds)}]",
                description="",
                per_page=10,
                color=0x00ff00).get_pages()
            paginator = Paginator(ctx, embeds)
            await paginator.paginate()
        else:
            await ctx.send("No mutual guilds found.")

    @commands.command(hidden=True, name="getinvite", aliases=["gi", "getinvites"], help="Get invites for a guild or channel.")
    @commands.is_owner()
    async def getinvite(self, ctx, guild_id: int = None, channel_id: int = None):
        guild = None
        channel = None

        if guild_id:
            guild = self.client.get_guild(guild_id)
            if not guild:
                await ctx.send("Invalid guild ID.")
                return
            
        elif channel_id:
            channel = self.client.get_channel(channel_id)
            if not channel:
                await ctx.send("Invalid channel ID.")
                return
            guild = channel.guild 

        else:
            await ctx.send("Please provide a guild ID or channel ID.")
            return

        can_create_invites = guild.me.guild_permissions.create_instant_invite if guild else False

        try:
            if guild_id:
                invites = await guild.invites()
                if invites:
                    embed = discord.Embed(
                        title=f"Active Invites for {guild.name}",
                        color=0xff0000
                    )
                    invites_list = [f"{invite.url} - {invite.uses} uses" for invite in invites]
                    embeds = DescriptionEmbedPaginator(
                        entries=invites_list,
                        title=f"Active Invites for {guild.name}",
                        description="",
                        per_page=10,
                        color=0xff0000).get_pages()
                    paginator = Paginator(ctx, embeds)
                    await paginator.paginate()
                elif can_create_invites:
                    
                    channel = guild.system_channel or next(
                        (ch for ch in guild.text_channels if ch.permissions_for(guild.me).create_instant_invite),
                        None
                    )
                    if channel:
                        invite = await channel.create_invite(max_age=604800, max_uses=None, reason="No active invites found, creating a new one.")
                        await ctx.send(f"Created new invite: {invite.url}")
                    else:
                        await ctx.send("No suitable channel found to create an invite.")
                else:
                    await ctx.send("Bot lacks permission to create invites for the guild.")

            
            elif channel_id:
                if channel.permissions_for(guild.me).create_instant_invite:
                    invite = await channel.create_invite(max_age=604800, max_uses=None, reason="Creating invite for the specified channel.")
                    await ctx.send(f"Created new invite for the channel: {invite.url}")
                else:
                    await ctx.send("Bot lacks permission to create invites for the specified channel.")

        except discord.Forbidden:
            await ctx.send("Bot lacks permission to access or create invites.")

    @commands.command(hidden=True, name="getguild")
    @commands.is_owner()
    async def get_guild(self, ctx, channel_id: int):
        channel = self.client.get_channel(channel_id)

        if channel:
            guild = channel.guild
            embed = discord.Embed(
                title=f"Guild Information for {guild.name}",
                color=0x000000
            )
            embed.add_field(name="Guild Name", value=guild.name)
            embed.add_field(name="Guild ID", value=guild.id)
            embed.add_field(name="Member Count", value=guild.member_count)
            embed.add_field(name="Owner", value=guild.owner)
            embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("Invalid channel ID or bot has no access to the channel.")
            
    @commands.command(hidden=True, name="Yuna.restart", help="Restarts the client.")
    @commands.is_owner()
    async def _restart(self, ctx: Context):
        await ctx.reply("Restarting Yuna...")
        restart_program()


    @commands.command(hidden=True, name="owners")
    @commands.is_owner()
    async def own_list(self, ctx):
        nplist = OWNER_IDS
        npl = ([await self.client.fetch_user(nplu) for nplu in nplist])
        npl = sorted(npl, key=lambda nop: nop.created_at)
        entries = [
            f"`#{no}` | [{mem}](https://discord.com/users/{mem.id}) (ID: {mem.id})"
            for no, mem in enumerate(npl, start=1)
        ]
        embeds = DescriptionEmbedPaginator(
            entries=entries,
            title=f"Yuna Owners [{len(nplist)}]",
            description="",
            per_page=10,
            color=0x000000).get_pages()
        paginator = Paginator(ctx, embeds)
        await paginator.paginate()





    @commands.command(hidden=True, )
    @commands.is_owner()
    async def dm(self, ctx, user: discord.User, *, message: str):
        """ DM the user of your choice """
        try:
            await user.send(message)
            await ctx.send(f"<a:tick:1558726958802800660> | Successfully Sent a DM to **{user}**")
        except discord.Forbidden:
            await ctx.send("This user might be having DMs blocked or it's a bot account...")           



    @commands.group(hidden=True, )
    @commands.is_owner()
    async def change(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))


    @change.command(name="nickname")
    @commands.is_owner()
    async def change_nickname(self, ctx, *, name: str = None):
        """ Change nickname. """
        try:
            await ctx.guild.me.edit(nick=name)
            if name:
                await ctx.send(f"<a:tick:1558726958802800660> | Successfully changed nickname to **{name}**")
            else:
                await ctx.send("<a:tick:1558726958802800660> | Successfully removed nickname")
        except Exception as err:
            await ctx.send(err) 


    @commands.command(hidden=True, name="ownerban", aliases=["forceban", "dna"])
    @commands.is_owner()
    async def _ownerban(self, ctx: Context, user_id: int, *, reason: str = "No reason provided"):
        
        member = ctx.guild.get_member(user_id)
        if member:
            try:
                await member.ban(reason=reason)
                embed = discord.Embed(
                    title="Successfully Banned",
                    description=f"<a:tick:1558726958802800660> | **{member.name}** has been successfully banned from {ctx.guild.name} by the Bot Owner.",
                    color=0x000000)
                await ctx.reply(embed=embed, mention_author=False, delete_after=3)
                await ctx.message.delete()
            except discord.Forbidden:
                embed = discord.Embed(
                    title="Error!",
                    description=f"<:Yuna_notify:1227866804630720565> I do not have permission to ban **{member.name}** in this guild.",
                    color=0x000000
                )
                await ctx.reply(embed=embed, mention_author=False, delete_after=5)
                await ctx.message.delete()
            except discord.HTTPException:
                embed = discord.Embed(
                    title="Error!",
                    description=f"<:Yuna_notify:1227866804630720565> An error occurred while banning **{member.name}**.",
                    color=0x000000
                )
                await ctx.reply(embed=embed, mention_author=False, delete_after=5)
                await ctx.message.delete()
        else:
            await ctx.reply("User not found in this guild.", mention_author=False, delete_after=3)
            await ctx.message.delete()

    @commands.command(hidden=True, name="ownerunban", aliases=["forceunban"])
    @commands.is_owner()
    async def _ownerunban(self, ctx: Context, user_id: int, *, reason: str = "No reason provided"):
        user = self.client.get_user(user_id)
        if user:
            try:
                await ctx.guild.unban(user, reason=reason)
                embed = discord.Embed(
                    title="Successfully Unbanned",
                    description=f"<a:tick:1558726958802800660> | **{user.name}** has been successfully unbanned from {ctx.guild.name} by the Bot Owner.",
                    color=0x000000
                )
                await ctx.reply(embed=embed, mention_author=False)
            except discord.Forbidden:
                embed = discord.Embed(
                    title="Error!",
                    description=f"<:Yuna_notify:1227866804630720565> I do not have permission to unban **{user.name}** in this guild.",
                    color=0x000000
                )
                await ctx.reply(embed=embed, mention_author=False)
            except discord.HTTPException:
                embed = discord.Embed(
                    title="Error!",
                    description=f"<:Yuna_notify:1227866804630720565> An error occurred while unbanning **{user.name}**.",
                    color=0x000000
                )
                await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.reply("User not found.", mention_author=False)



    @commands.command(hidden=True, name="globalunban")
    @commands.is_owner()
    async def globalunban(self, ctx: Context, user: discord.User):
        success_guilds = []
        error_guilds = []

        for guild in self.client.guilds:
            bans = await guild.bans()
            if any(ban_entry.user.id == user.id for ban_entry in bans):
                try:
                    await guild.unban(user, reason="Global Unban")
                    success_guilds.append(guild.name)
                except discord.HTTPException:
                    error_guilds.append(guild.name)
                except discord.Forbidden:
                    error_guilds.append(guild.name)

        user_mention = f"{user.mention} (**{user.name}**)"

        success_message = f"Successfully unbanned {user_mention} from the following guild(s):\n{',     '.join(success_guilds)}" if success_guilds else "No guilds where the user was successfully unbanned."
        error_message = f"Failed to unban {user_mention} from the following guild(s):\n{',    '.join(error_guilds)}" if error_guilds else "No errors during unbanning."

        await ctx.reply(f"{success_message}\n{error_message}", mention_author=False)

    @commands.command(hidden=True, name="guildban")
    @commands.is_owner()
    async def guildban(self, ctx: Context, guild_id: int, user_id: int, *, reason: str = "No reason provided"):
        guild = self.client.get_guild(guild_id)
        if not guild:
            await ctx.reply("Bot is not present in the specified guild.", mention_author=False)
            return

        member = guild.get_member(user_id)
        if member:
            try:
                await guild.ban(member, reason=reason)
                await ctx.reply(f"Successfully banned **{member.name}** from {guild.name}.", mention_author=False)
            except discord.Forbidden:
                await ctx.reply(f"Missing permissions to ban **{member.name}** in {guild.name}.", mention_author=False)
            except discord.HTTPException as e:
                await ctx.reply(f"An error occurred while banning **{member.name}** in {guild.name}: {str(e)}", mention_author=False)
        else:
            await ctx.reply(f"User not found in the specified guild {guild.name}.", mention_author=False)

    @commands.command(hidden=True, name="guildunban")
    @commands.is_owner()
    async def guildunban(self, ctx: Context, guild_id: int, user_id: int, *, reason: str = "No reason provided"):
        guild = self.client.get_guild(guild_id)
        if not guild:
            await ctx.reply("Bot is not present in the specified guild.", mention_author=False)
            return
        #member = guild.get_member(user_id)

        try:
            user = await self.client.fetch_user(user_id)
        except discord.NotFound:
            await ctx.reply(f"User with ID {user_id} not found.", mention_author=False)
            return

        user = discord.Object(id=user_id)
        try:
            await guild.unban(user, reason=reason)
            await ctx.reply(f"Successfully unbanned user ID {user_id} from {guild.name}.", mention_author=False)
        except discord.Forbidden:
            await ctx.reply(f"Missing permissions to unban user ID {user_id} in {guild.name}.", mention_author=False)
        except discord.HTTPException as e:
            await ctx.reply(f"An error occurred while unbanning user ID {user_id} in {guild.name}: {str(e)}", mention_author=False)


    @commands.command(hidden=True, name="leaveguild")
    @commands.is_owner()
    async def leave_guild(self, ctx, guild_id: int):
        guild = self.client.get_guild(guild_id)
        if guild is None:
            await ctx.send(f"Guild with ID {guild_id} not found.")
            return

        await guild.leave()
        await ctx.send(f"Left the guild: {guild.name} ({guild.id})")

    @commands.command(hidden=True, name="guildinfo")
    @commands.check(is_owner_or_staff)
    async def guild_info(self, ctx, guild_id: int):
        guild = self.client.get_guild(guild_id)
        if guild is None:
            await ctx.send(f"Guild with ID {guild_id} not found.")
            return

        embed = discord.Embed(
            title=guild.name,
            description=f"Information for guild ID {guild.id}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Owner", value=str(guild.owner), inline=True)
        embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
        embed.add_field(name="Text Channels", value=len(guild.text_channels), inline=True)
        embed.add_field(name="Voice Channels", value=len(guild.voice_channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Created at: {guild.created_at}")

        await ctx.send(embed=embed)

    @commands.command(hidden=True, )
    @commands.is_owner()
    async def servertour(self, ctx, time_in_seconds: int, member: discord.Member):
        guild = ctx.guild

        if time_in_seconds > 3600:
            await ctx.send("Time cannot be greater than 3600 seconds (1 hour).")
            return

        if not member.voice:
            await ctx.send(f"{member.display_name} is not in a voice channel.")
            return

        voice_channels = [ch for ch in guild.voice_channels if ch.permissions_for(guild.me).move_members]

        if len(voice_channels) < 2:
            await ctx.send("Not enough voice channels to move the user.")
            return

        self.stop_tour = False

        class StopButton(discord.ui.View):
            def __init__(self, outer_self):
                super().__init__(timeout=time_in_seconds)
                self.outer_self = outer_self

            @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
            async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                is_allowed = (
                    interaction.user.id in self.outer_self.bot_owner_ids or 
                    (interaction.guild and interaction.user.id == interaction.guild.owner_id)
                )
                if not is_allowed:
                    await interaction.response.send_message("Only the bot owner or server owner can stop this process.", ephemeral=True)
                    return
                self.outer_self.stop_tour = True
                await interaction.response.send_message("Server tour has been stopped.", ephemeral=True)
                self.stop()

        view = StopButton(self)
        message = await ctx.send(f"Started moving {member.display_name} for {time_in_seconds} seconds. Click the button to stop.", view=view)

        end_time = asyncio.get_event_loop().time() + time_in_seconds

        while asyncio.get_event_loop().time() < end_time and not self.stop_tour:
            for ch in voice_channels:
                if self.stop_tour:
                    await ctx.send("Tour stopped.")
                    return
                if not member.voice:
                    await ctx.send(f"{member.display_name} left the voice channel.")
                    return
                try:
                    await member.move_to(ch)
                    await asyncio.sleep(1)
                except Forbidden:
                    await ctx.send(f"Missing permissions to move {member.display_name}.")
                    return
                except Exception as e:
                    await ctx.send(f"Error: {str(e)}")
                    return

        if not self.stop_tour:
            await message.edit(content=f"Finished moving {member.display_name} after {time_in_seconds} seconds.", view=None)




    


    @commands.group(hidden=True, )
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def bdg(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(description='Invalid `bdg` command passed. Use `add` or `remove`.', color=0x000000)
            await ctx.send(embed=embed)

    @bdg.command()
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def add(self, ctx, member: discord.Member, badge: str):
        badge = badge.lower()
        user_id = member.id
        if badge in BADGE_URLS or badge == 'bug' or badge == 'all':
            if badge == 'all':
                for b in BADGE_URLS.keys():
                    add_badge(user_id, b)
                add_badge(user_id, 'bug')
                embed = discord.Embed(description=f"All badges added to {member.mention}.", color=0x000000)
                await ctx.send(embed=embed)
            else:
                success = add_badge(user_id, badge)
                if success:
                    embed = discord.Embed(description=f"Badge `{badge}` added to {member.mention}.", color=0x000000)
                else:
                    embed = discord.Embed(description=f"{member.mention} already has the badge `{badge}`.", color=0x000000)
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description=f"Invalid badge: `{badge}`", color=0x000000)
            await ctx.send(embed=embed)

    @bdg.command()
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def remove(self, ctx, member: discord.Member, badge: str):
        badge = badge.lower()
        user_id = member.id
        if badge in BADGE_URLS or badge == 'bug' or badge == 'all':
            if badge == 'all':
                for b in BADGE_URLS.keys():
                    remove_badge(user_id, b)
                remove_badge(user_id, 'bug')
                embed = discord.Embed(description=f"All badges removed from {member.mention}.", color=0x000000)
                await ctx.send(embed=embed)
            else:
                success = remove_badge(user_id, badge)
                if success:
                    embed = discord.Embed(description=f"Badge `{badge}` removed from {member.mention}.", color=0x000000)
                else:
                    embed = discord.Embed(description=f"{member.mention} does not have the badge `{badge}`.", color=0x000000)
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description=f"Invalid badge: `{badge}`", color=0x000000)
            await ctx.send(embed=embed)


    @commands.command(name="forcepurgebots",
        aliases=["fpb"],
        hidden=True,
        help="Clear recently bot messages in channel (Bot owner only)")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_owner()
    @commands.bot_has_permissions(manage_messages=True)
    async def _purgebot(self, ctx, prefix=None, search=100):
        
        await ctx.message.delete()
        
        def predicate(m):
            return (getattr(m, "webhook_id", None) is None and getattr(getattr(m, "author", None), "bot", False)) or (prefix and getattr(m, "content", "").startswith(prefix))
        
        await do_removal(ctx, search, predicate)


    @commands.command(name="forcepurgeuser",
        aliases=["fpu"],
        hidden=True,
        help="Clear recent messages of a user in channel (Bot owner only)")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_owner()
    @commands.bot_has_permissions(manage_messages=True)
    async def purguser(self, ctx, member: discord.Member, search=100):
        
        await ctx.message.delete()
        
        await do_removal(ctx, search, lambda e: getattr(e, "author", None) == member)

    @commands.command(name="antinukelatency", aliases=["seclatency", "seclcy", "secmetrics"], hidden=True)
    @commands.is_owner()
    async def latency_metrics(self, ctx: Context):
        """Displays real-time p50/p95/p99 Anti-Nuke latency percentiles and incident counts per path."""
        from core.antinuke_v2.trace import v2_trace_aggregator
        from core.antinuke_v2.lag_sampler import event_loop_lag_sampler
        from core.antinuke_v2.router import v2_engine_router, EngineMode
        from core.metrics.security_metrics import security_metrics

        if not event_loop_lag_sampler.is_running:
            try:
                event_loop_lag_sampler.start()
            except Exception:
                pass

        v2_traces = v2_trace_aggregator.get_filtered_traces()
        if v2_traces or v2_engine_router.mode != EngineMode.LEGACY_ONLY or event_loop_lag_sampler.is_running:
            report = v2_trace_aggregator.generate_latency_report()
        else:
            report = security_metrics.get_detailed_latency_report()
        if len(report) <= 1980:
            await ctx.send(f"```text\n{report}\n```")
        else:
            chunks = []
            curr = ""
            for line in report.split("\n"):
                if len(curr) + len(line) + 1 > 1950:
                    chunks.append(curr)
                    curr = line + "\n"
                else:
                    curr += line + "\n"
            if curr:
                chunks.append(curr)
            for ch in chunks:
                await ctx.send(f"```text\n{ch}\n```")



class Badges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'db/np.db'

        
    @commands.hybrid_command(aliases=['profile', 'pr'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def badges(self, ctx, member: discord.Member = None):

        processing_message = await ctx.send("<a:loading:1554957482248380416> Loading your profile...")

        member = member or ctx.author
        user_id = member.id

        
        c.execute("SELECT * FROM badges WHERE user_id = ?", (user_id,))
        badges = c.fetchone()

        if badges:
            badges = dict(zip([column[0] for column in c.description], badges))
        else:
            badges = {k: 0 for k in BADGE_URLS.keys()}

        
        badge_size = 120
        padding = 80
        num_columns = 4
        image_width = 960
        image_height = 540



        def calculate_text_dimensions(badge_name, font, padding=1):
            text_bbox = draw.textbbox((0, 0), badge_name, font=font)
            text_width = (text_bbox[2] - text_bbox[0]) + 2 * padding
            text_height = (text_bbox[3] - text_bbox[1]) + 2 * padding
            return text_width, text_height

        
        async def draw_badges(badges, draw, img):

            
            upper_y = (image_height // 4) - (badge_size // 2)
            lower_y = (3 * image_height // 4) - (badge_size // 2)
            
            x_positions = [padding + i * ((image_width - 2 * padding) // (num_columns - 1)) for i in range(num_columns)]

            badge_positions = []
            for badge in BADGE_URLS.keys():
                if badges.get(badge):
                    badge_positions.append(badge)

            for i, badge in enumerate(badge_positions):
                y = upper_y if i < num_columns else lower_y
                x = x_positions[i % num_columns]
                content = _BADGE_CACHE.get(badge)
                if not content:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(BADGE_URLS[badge]) as response:
                                if response.status == 200:
                                    content = await response.read()
                                    _BADGE_CACHE[badge] = content
                    except Exception as e:
                        print(f"Failed to fetch badge {badge}: {e}")
                        continue

                if content:
                    badge_img = Image.open(BytesIO(content)).resize((badge_size, badge_size))
                    img.paste(badge_img, (x - badge_size // 2, y), badge_img)
                    text_width, text_height = calculate_text_dimensions(BADGE_NAMES[badge], font)
                    draw.text((x - text_width // 2, y + badge_size + 5), BADGE_NAMES[badge], fill=(255, 0, 0), font=font)  

        
        has_badges = any(value == 1 for value in badges.values())

        if has_badges:
            
            img = Image.new('RGBA', (image_width, image_height), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(FONT_PATH, 25)  

            
            await draw_badges(badges, draw, img)

            with BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)
                file = discord.File(fp=image_binary, filename='badge.png')

            embed = discord.Embed(title=f"{member.display_name}'s Profile", color=0x000000)

            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            else:
                embed.set_thumbnail(url=member.default_avatar.url)
            embed.add_field(name="__**Account Created At**__", value=f"<t:{int(member.created_at.timestamp())}:F>", inline=True)
            embed.add_field(name="__**Joined This Guild At**__", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=True)



            # User Badges
            user_flags = member.public_flags
            user_badges = []

            badge_mapping = {
              "staff": "<:Staff:1219285127444566056> Discord Employee",
              "partner": "<:Partnered:1219285024688443443> Partnered Server Owner",
              "discord_certified_moderator": "<:ModeratorProgamsAlumini:1274717806067187814> Moderator Programs Alumni",
              "hypesquad_balance": "<:Balance:1219282289020637344> House Balance Member",
              "hypesquad_bravery": "<:Bravery:1219282462975201352> House Bravery Member",
              "hypesquad_brilliance": "<:Brilliance:1219284165317361685> House Brilliance Member",
              "hypesquad": "<:HypeEvent:1219284814214205531> HypeSquad Events Member",
              "early_supporter": "<:Early:1219284700292579328> Early Supporter",
              "bug_hunter": "<:Bugter:1219284193440436224> Bug Hunter Level 1",
              "bug_hunter_level_2": "<:GoldenBugHunter:1274718350689304630> Bug Hunter Level 2",
              "verified_bot": "<:VERIFIED_BOT:1274718475583098982> Verified Bot",
              "verified_bot_developer": "<:VerifiedBotDev:1219285243849080884> Verified Bot Developer",
              "active_developer": "<:Activedev:1219280536959189144> Active Developer",
              "early_verified_bot_developer": "<:VerifiedBotDev:1219285243849080884> Early Verified Bot Developer",
              "system": "<:system_user:1274718577185787954> System User",
              "team_user": "👷 User is a [Team](https://discord.com/developers/docs/topics/teams)",
              "spammer": "<:BarDiscord:1274718831352217620> Marked as Spammer",
              "bot_http_interactions": "<:HTTP_INTERACTION_BOT:1274719023401013279> Bot uses only [HTTP interactions](https://discord.com/developers/docs/interactions/receiving-and-responding#receiving-an-interaction) and is shown in the online member list."
            }

            for flag, value in badge_mapping.items():
              if getattr(user_flags, flag):
                user_badges.append(value)

            
            user = await self.bot.fetch_user(member.id)
            wtf = bool(user.avatar and user.avatar.is_animated())
            omg = bool(user.banner)
            if not member.bot:
                if omg or wtf:
                    user_badges.append("<:BadgeNitro:1274895915689443431> Nitro Subscriber")
                for guild in self.bot.guilds:
                    if member in guild.members:
                        if guild.premium_subscription_count > 0 and member in guild.premium_subscribers:
                            user_badges.append("<:booster:1274896054810312816> Server Booster Badge")
                            
            if user_badges:
              embed.add_field(name="__**User Badges**__", value="\n".join(user_badges), inline=False)
            else:
              embed.add_field(name="__**User Badges**__", value="None", inline=False)

            # Bot Badges
            embed.add_field(name="__**Bot Badges**__", value="Below", inline=False)
            embed.set_image(url="attachment://badge.png")
            embed.set_footer(text=f"Requested by {ctx.author} | Nitro badge if banner/animated avatar; Booster badge if boosting a mutual guild with bot.", icon_url=ctx.author.avatar.url
                               if ctx.author.avatar else ctx.author.default_avatar.url)

            await ctx.send(embed=embed, file=file)
            await processing_message.delete()
        else:
            embed = discord.Embed(title=f"{member.display_name}'s Profile", color=0x000000)

            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            else:
                embed.set_thumbnail(url=member.default_avatar.url)
            embed.add_field(name="__**Account Created At**__", value=f"<t:{int(member.created_at.timestamp())}:F>", inline=True)
            embed.add_field(name="__**Joined This Guild At**__", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=True)




            # User Badges
            user_flags = member.public_flags
            user_badges = []

            badge_mapping = {
              "staff": "<:Staff:1219285127444566056> Discord Employee",
              "partner": "<:Partnered:1219285024688443443> Partnered Server Owner",
              "discord_certified_moderator": "<:ModeratorProgamsAlumini:1274717806067187814> Moderator Programs Alumni",
              "hypesquad_balance": "<:Balance:1219282289020637344> House Balance Member",
              "hypesquad_bravery": "<:Bravery:1219282462975201352> House Bravery Member",
              "hypesquad_brilliance": "<:Brilliance:1219284165317361685> House Brilliance Member",
              "hypesquad": "<:HypeEvent:1219284814214205531> HypeSquad Events Member",
              "early_supporter": "<:Early:1219284700292579328> Early Supporter",
              "bug_hunter": "<:Bugter:1219284193440436224> Bug Hunter Level 1",
              "bug_hunter_level_2": "<:GoldenBugHunter:1274718350689304630> Bug Hunter Level 2",
              "verified_bot": "<:VERIFIED_BOT:1274718475583098982> Verified Bot",
              "verified_bot_developer": "<:VerifiedBotDev:1219285243849080884> Verified Bot Developer",
              "active_developer": "<:Activedev:1219280536959189144> Active Developer",
              "early_verified_bot_developer": "<:VerifiedBotDev:1219285243849080884> Early Verified Bot Developer",
              "system": "<:system_user:1274718577185787954> System User",
              "team_user": "👷 User is a [Team](https://discord.com/developers/docs/topics/teams)",
              "spammer": "<:BarDiscord:1274718831352217620> Marked as Spammer",
              "bot_http_interactions": "<:HTTP_INTERACTION_BOT:1274719023401013279> Bot uses only [HTTP interactions](https://discord.com/developers/docs/interactions/receiving-and-responding#receiving-an-interaction) and is shown in the online member list."
            }

            for flag, value in badge_mapping.items():
              if getattr(user_flags, flag):
                user_badges.append(value)

            user = await self.bot.fetch_user(member.id)
            wtf = bool(user.avatar and user.avatar.is_animated())
            omg = bool(user.banner)
            if not member.bot:
                if omg or wtf:
                    user_badges.append("<:BadgeNitro:1274895915689443431> Nitro Subscriber")
                for guild in self.bot.guilds:
                    if member in guild.members:
                        if guild.premium_subscription_count > 0 and member in guild.premium_subscribers:
                            user_badges.append("<:booster:1274896054810312816> Server Booster Badge")

            if user_badges:
              embed.add_field(name="__**User Badges**__", value="\n".join(user_badges), inline=False)
            else:
              embed.add_field(name="__**User Badges**__", value="None", inline=False)

            # Bot Badges
            embed.add_field(name="__**Bot Badges**__", value="No bot badges", inline=False)
            embed.set_footer(text=f"Requested by {ctx.author} | Nitro badge if banner/animated avatar; Booster badge if boosting a mutual guild with bot.", icon_url=ctx.author.avatar.url
                               if ctx.author.avatar else ctx.author.default_avatar.url)

            await ctx.send(embed=embed)
            await processing_message.delete()
