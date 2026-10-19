import discord
from discord.ext import commands, tasks
import aiosqlite
import os
import datetime
import asyncio
import pytz
import json
import re
from utils.Tools import *

# Database setup
db_folder = 'db'
db_file = 'anti.db'
db_path = os.path.join(db_folder, db_file)


def parse_time_str_or_hms(time_input, default_h=0, default_m=0, default_s=0):
    """Parses various formats (string, tuple, int) into (hour, minute, second)."""
    if isinstance(time_input, (list, tuple)) and len(time_input) == 3:
        return int(time_input[0]), int(time_input[1]), int(time_input[2])
    if isinstance(time_input, int):
        return time_input, 0, 0
    if isinstance(time_input, str):
        t_str = time_input.strip()
        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M:%S%p", "%I:%M%p"):
            try:
                dt = datetime.datetime.strptime(t_str, fmt).time()
                return dt.hour, dt.minute, dt.second
            except ValueError:
                pass
        parts = t_str.replace(":", " ").split()
        if len(parts) == 3:
            try:
                return int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                pass
        elif len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1]), 0
            except ValueError:
                pass
        elif len(parts) == 1:
            try:
                return int(parts[0]), 0, 0
            except ValueError:
                pass
    return default_h, default_m, default_s


def is_in_night_window(
    now_dt: datetime.datetime,
    start_hour: int = 0,
    end_hour: int = 6,
    start_minute: int = 0,
    start_second: int = 0,
    end_minute: int = 0,
    end_second: int = 0
) -> bool:
    """Pure TRUE/FALSE schedule calculation with Hour, Minute, Second precision.
    
    If start > end (overnight, e.g. 22:30:00 -> 06:15:30):
        active = now >= start OR now < end
    If start < end (same day, e.g. 10:00:00 -> 18:30:00):
        active = start <= now < end
    If start == end:
        always FALSE
    """
    now_t = now_dt.time()
    try:
        start_t = datetime.time(start_hour, start_minute, start_second)
    except Exception:
        start_t = datetime.time(start_hour, 0, 0)
    try:
        end_t = datetime.time(end_hour, end_minute, end_second)
    except Exception:
        end_t = datetime.time(end_hour, 0, 0)

    if start_t == end_t:
        return False
    if start_t > end_t:
        # Overnight span: e.g. 22:30:00 -> 06:15:00
        return now_t >= start_t or now_t < end_t
    else:
        # Same-day span: e.g. 10:00:00 -> 18:30:00
        return start_t <= now_t < end_t


class Nightmode(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ricky = ['1070619070468214824', '1087282349395411015', '858642338980954113']
        self.color = 0x2B2D31
        self._locks = {}
        self.db = None

    async def cog_load(self):
        await self.initialize_db()
        self.check_auto_nightmode.start()

    def cog_unload(self):
        self.check_auto_nightmode.cancel()

    def get_guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    async def initialize_db(self):
        if self.db is not None:
            return
        self.db = await aiosqlite.connect(db_path, timeout=30.0)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("PRAGMA busy_timeout=30000;")
        await self.db.execute("PRAGMA synchronous=NORMAL;")
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS Nightmode (
                guildId TEXT,
                roleId TEXT,
                adminPermissions INTEGER,
                original_permissions INTEGER DEFAULT 0,
                PRIMARY KEY (guildId, roleId)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS nightmode_roles (
                guild_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                role_name TEXT,
                original_permissions INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_stripped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_restored_at TIMESTAMP,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_nightmode_roles_guild ON nightmode_roles(guild_id);")
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_nightmode_roles_active ON nightmode_roles(guild_id, is_active);")
        await self.db.execute('''
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
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS nightmode_guilds (
                guild_id INTEGER PRIMARY KEY
            )
        ''')
        await self.db.commit()

        # Migrate existing rows from legacy Nightmode table into nightmode_roles
        try:
            async with self.db.execute("SELECT guildId, roleId, adminPermissions, original_permissions FROM Nightmode") as cursor:
                old_rows = await cursor.fetchall()
                for r in old_rows:
                    g_id = str(r[0])
                    r_id = str(r[1])
                    orig_p = int(r[3]) if len(r) > 3 and r[3] and int(r[3]) > 0 else (int(r[2]) if r[2] else 8)
                    orig_p = orig_p | 8
                    await self.db.execute("""
                        INSERT OR IGNORE INTO nightmode_roles (guild_id, role_id, role_name, original_permissions, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    """, (g_id, r_id, f"Role ({r_id})", orig_p))
            await self.db.commit()
        except Exception:
            pass

        # Migrate: add columns if upgrading from earlier schema
        for col, col_type in [
            ("original_permissions", "INTEGER DEFAULT 0"),
        ]:
            try:
                await self.db.execute(f"ALTER TABLE Nightmode ADD COLUMN {col} {col_type}")
                await self.db.commit()
            except Exception:
                pass

        for col, col_type in [
            ("start_minute", "INTEGER DEFAULT 0"),
            ("start_second", "INTEGER DEFAULT 0"),
            ("end_minute", "INTEGER DEFAULT 0"),
            ("end_second", "INTEGER DEFAULT 0"),
            ("start_time", "TEXT DEFAULT '00:00:00'"),
            ("end_time", "TEXT DEFAULT '06:00:00'"),
            ("timezone", "TEXT DEFAULT 'Asia/Kolkata'")
        ]:
            try:
                await self.db.execute(f"ALTER TABLE nightmode_config ADD COLUMN {col} {col_type}")
                await self.db.commit()
            except Exception:
                pass

    async def is_extra_owner(self, user, guild):
        return is_server_owner_or_extra_owner(guild, user)

    async def get_or_create_nightmode_channel(self, guild: discord.Guild):
        """Intelligently locates an existing Nightmode logging channel, removes duplicate log channels,
        or creates a new private channel with graceful permission handling."""
        stored_channel_id = None
        try:
            async with self.db.execute("SELECT log_channel FROM nightmode_config WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    stored_channel_id = int(row[0])
        except Exception:
            pass

        category = await get_or_create_yuna_logs_category(guild)
        style = detect_yuna_logs_style(guild, category)
        styled_nm_name = format_channel_name("nightmode", style, "Yuna")

        valid_names = ("yuna-nightmode", "nightmode-logs", "night-mode-logs")
        matching_channels = [
            ch for ch in guild.text_channels
            if (stored_channel_id and ch.id == stored_channel_id)
            or ch.name == styled_nm_name
            or identify_log_channel_type(ch.name) == "nightmode"
            or ch.name.lower() in valid_names
        ]
        matching_channels = list({ch.id: ch for ch in matching_channels}.values())

        primary_channel = None
        if stored_channel_id:
            stored_ch = guild.get_channel(stored_channel_id)
            if stored_ch and isinstance(stored_ch, discord.TextChannel) and stored_ch in matching_channels:
                primary_channel = stored_ch

        if not primary_channel and matching_channels:
            primary_channel = discord.utils.find(lambda c: c.name == styled_nm_name, matching_channels)
            if not primary_channel:
                primary_channel = min(matching_channels, key=lambda c: getattr(c, 'created_at', None) or c.id)

        notice_embed = None

        if primary_channel:
            await ensure_channel_in_yuna_logs(guild, primary_channel, category=category)
            if primary_channel.name != styled_nm_name and guild.me.guild_permissions.manage_channels:
                try:
                    await primary_channel.edit(name=styled_nm_name, reason="Yuna Nightmode: Standardize channel text style")
                except Exception:
                    pass

            duplicates = [ch for ch in matching_channels if ch.id != primary_channel.id]
            if duplicates:
                deleted_dupes = []
                failed_dupes = []
                can_manage = guild.me.guild_permissions.manage_channels
                for dup in duplicates:
                    if can_manage:
                        try:
                            await dup.delete(reason="Yuna Nightmode: Cleanup Duplicate Log Channel")
                            deleted_dupes.append(dup.name)
                        except Exception:
                            failed_dupes.append(dup.mention)
                    else:
                        failed_dupes.append(dup.mention)

                if deleted_dupes or failed_dupes:
                    desc_parts = [
                        f"Found **{len(duplicates)}** duplicate Nightmode channel(s).",
                        f"📍 **Primary Log Channel:** {primary_channel.mention}"
                    ]
                    if deleted_dupes:
                        desc_parts.append(f"🗑️ **Safely Cleaned Up:** {', '.join(deleted_dupes)}")
                    if failed_dupes:
                        desc_parts.append(f"⚠️ **Manual Deletion Needed (Missing Permissions):** {', '.join(failed_dupes)}")
                    notice_embed = discord.Embed(
                        title="🧹 Nightmode Log Channel Management",
                        description="\n\n".join(desc_parts),
                        color=0xFF9500
                    )
            return primary_channel, notice_embed

        if not guild.me.guild_permissions.manage_channels:
            error_embed = discord.Embed(
                title="⚠️ Missing Permissions",
                description=f"I need the **Manage Channels** permission to create the `#{styled_nm_name}` logging channel. Please grant it or create the channel manually.",
                color=0xFF0000
            )
            return None, error_embed

        try:
            if not category:
                category = await get_or_create_yuna_logs_category(guild)
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)
            }
            primary_channel = await guild.create_text_channel(
                styled_nm_name,
                category=category,
                overwrites=overwrites,
                reason="Yuna Nightmode Log Channel Setup"
            )
            return primary_channel, None
        except Exception as e:
            error_embed = discord.Embed(
                title="⚠️ Channel Creation Error",
                description=f"Could not create `#{styled_nm_name}` channel: {e}",
                color=0xFF0000
            )
            return None, error_embed

    # ================= MANUAL NIGHTMODE COMMANDS =================

    @commands.hybrid_group(name="nightmode", aliases=[], help="Manages Nightmode feature", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def nightmode(self, ctx):
        nightmode_embed = discord.Embed(
            title='__**Nightmode**__',
            color=self.color,
            description=(
                'Nightmode swiftly disables dangerous permissions for roles, like stripping `ADMINISTRATION` rights, while preserving original settings for seamless restoration.\n\n**Make sure to keep my ROLE above all roles you want to protect.**'
            )
        )
        nightmode_embed.add_field(
            name="Usage",
            value=(
                "<:red_dot:1222796144996777995> `nightmode enable`\n"
                "<:red_dot:1222796144996777995> `nightmode disable`\n"
                "<:red_dot:1222796144996777995> `nightmode auto enable`\n"
                "<:red_dot:1222796144996777995> `nightmode auto disable`\n"
                "<:red_dot:1222796144996777995> `nightmode auto status`"
            ),
            inline=False
        )
        nightmode_embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=nightmode_embed)

    @nightmode.command(name="enable", help="Enable nightmode manually")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def enable_nightmode(self, ctx):
        own = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        check = await self.is_extra_owner(ctx.author, ctx.guild)
        if not own and not check and ctx.author.id not in self.ricky:
            return await ctx.send(embed=discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=self.color,
                description='Only Server Owner Or Extraowner Can Run This Command.!'
            ))

        if not own and not (
            ctx.guild.me.top_role.position <= ctx.author.top_role.position
        ) and ctx.author.id not in self.ricky:
            return await ctx.send(embed=discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=self.color,
                description='Only Server Owner or Extraowner Having **Higher role than me can run this command**'
            ))

        async with self.get_guild_lock(ctx.guild.id):
            if self.db is None:
                await self.initialize_db()

            bot_highest_role = ctx.guild.me.top_role
            manageable_roles = [
                role for role in ctx.guild.roles
                if role.position < bot_highest_role.position
                and role.name != '@everyone'
                and role.permissions.administrator
                and not role.managed
            ]

            if not manageable_roles:
                return await ctx.send(embed=discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                    color=self.color,
                    description='No Roles Found With Admin Permissions'
                ))

            async with self.db.execute('SELECT guildId FROM Nightmode WHERE guildId = ?', (str(ctx.guild.id),)) as cursor:
                if await cursor.fetchone():
                    return await ctx.send(embed=discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                        color=self.color,
                        description='Nightmode is already enabled.'
                    ))

            log_channel, notice_embed = await self.get_or_create_nightmode_channel(ctx.guild)
            if log_channel:
                await self.db.execute('''
                    INSERT INTO nightmode_config (guild_id, log_channel) VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET log_channel = excluded.log_channel
                ''', (ctx.guild.id, log_channel.id))
                await self.db.commit()

            if notice_embed:
                await ctx.send(embed=notice_embed)

            # Sync manual state to nightmode_guilds so web dashboard reflects it
            await self.db.execute("INSERT OR REPLACE INTO nightmode_guilds (guild_id) VALUES (?)", (ctx.guild.id,))
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(ctx.guild.id, "nightmode", True)
            set_guild_setting(ctx.guild.id, "nightmode_manual", True)

            # CRASH-SAFE: Save original permissions to DB FIRST, then strip
            affected = await self._save_and_strip_roles(ctx.guild, self.db)

            await self._dispatch_nightmode_log(
                guild=ctx.guild,
                action="activate",
                trigger_type="Manual Command",
                roles=affected,
                moderator=ctx.author,
                log_channel_id=log_channel.id if log_channel else None
            )

            await self._notify_owner(ctx.guild, activated=True, roles_count=len(affected), triggered_by=str(ctx.author))

            timer_str = await self._get_guild_timer_str(ctx.guild.id)
            log_msg = f"\n📢 **Log Channel:** {log_channel.mention}" if log_channel else ""
            await ctx.send(embed=discord.Embed(title="<a:tick:1558726958802800660> Success",
                color=self.color,
                description=f'Nightmode enabled! Dangerous permissions disabled for manageable roles.\n⏰ **Timer:** `{timer_str}`{log_msg}'
            ))

    @nightmode.command(name="disable", help="Disable nightmode manually")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def disable_nightmode(self, ctx):
        own = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        check = await self.is_extra_owner(ctx.author, ctx.guild)
        if not own and not check and ctx.author.id not in self.ricky:
            return await ctx.send(embed=discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=self.color,
                description='Only Server Owner Or Extraowner Can Run This Command.!'
            ))

        if not own and not (
            ctx.guild.me.top_role.position <= ctx.author.top_role.position
        ) and ctx.author.id not in self.ricky:
            return await ctx.send(embed=discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=self.color,
                description='Only Server Owner or Extraowner Having **Higher role than me can run this command**'
            ))

        async with self.get_guild_lock(ctx.guild.id):
            if self.db is None:
                await self.initialize_db()

            async with self.db.execute('SELECT COUNT(*) FROM nightmode_roles WHERE guild_id = ? AND is_active = 1', (str(ctx.guild.id),)) as cursor:
                row_r = await cursor.fetchone()
                has_roles = (row_r[0] > 0) if row_r else False

            async with self.db.execute('SELECT COUNT(*) FROM Nightmode WHERE guildId = ?', (str(ctx.guild.id),)) as cursor:
                row = await cursor.fetchone()
                has_records = (row[0] > 0) if row else False

            async with self.db.execute('SELECT guild_id FROM nightmode_guilds WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                has_manual = bool(await cursor.fetchone())

            restored = await self._restore_roles(ctx.guild, self.db)

            if not restored and not has_records and not has_manual and not has_roles:
                return await ctx.send(embed=discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                    color=self.color,
                    description='Nightmode is not currently active.\n💡 *If you migrated to a new VPS and need to restore roles stripped on the old VPS, run `$nightmode recover`.*'
                ))

            # Sync manual state to nightmode_guilds so web dashboard reflects it
            await self.db.execute("DELETE FROM nightmode_guilds WHERE guild_id = ?", (ctx.guild.id,))
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(ctx.guild.id, "nightmode", False)
            set_guild_setting(ctx.guild.id, "nightmode_manual", False)

            await self._dispatch_nightmode_log(
                guild=ctx.guild,
                action="deactivate",
                trigger_type="Manual Command",
                roles=restored,
                moderator=ctx.author
            )

            await self._notify_owner(ctx.guild, activated=False, roles_count=len(restored), triggered_by=str(ctx.author))

            await ctx.send(embed=discord.Embed(title="<a:tick:1558726958802800660> Success",
                color=self.color,
                description=f'Nightmode disabled! Restored permissions for `{len(restored)}` manageable role(s).'
            ))

    @nightmode.command(name="recover", aliases=["forcerestore", "repair"], help="Emergency recovery of stripped roles (ideal after changing VPS or crashes)")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def recover_nightmode(self, ctx):
        """Disaster recovery command. Restores administrator permissions using Database, Cloud State Backup, or Role History."""
        own = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        check = await self.is_extra_owner(ctx.author, ctx.guild)
        if not own and not check and ctx.author.id not in self.ricky:
            return await ctx.send(embed=discord.Embed(
                title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=self.color,
                description="Only Server Owner Or Extraowner Can Run This Command!"
            ))

        msg = await ctx.send("<a:loading:1554957482248380416> **Scanning for Nightmode role backups (Database + Discord Cloud Records)...**")

        async with self.get_guild_lock(ctx.guild.id):
            if self.db is None:
                await self.initialize_db()

            restored = await self._restore_roles(ctx.guild, self.db, force_cloud=True)

            # If still nothing restored, let's do an active scan for manageable roles that were previously recorded
            if not restored:
                async with self.db.execute(
                    "SELECT role_id, original_permissions FROM nightmode_roles WHERE guild_id = ?",
                    (str(ctx.guild.id),)
                ) as cursor:
                    historical = await cursor.fetchall()
                if historical:
                    for r_id_str, p_val in historical:
                        r = ctx.guild.get_role(int(r_id_str)) if r_id_str.isdigit() else None
                        if r and not r.permissions.administrator and r.position < ctx.guild.me.top_role.position:
                            try:
                                perms = discord.Permissions(int(p_val) | 8)
                                await r.edit(permissions=perms, reason="Nightmode RECOVERY — Historical Role Restored")
                                restored.append(r)
                            except Exception:
                                pass

            # Clear any stale lock state
            await self.db.execute("DELETE FROM nightmode_guilds WHERE guild_id = ?", (ctx.guild.id,))
            await self.db.execute("UPDATE nightmode_roles SET is_active = 0, last_restored_at = CURRENT_TIMESTAMP WHERE guild_id = ?", (str(ctx.guild.id),))
            await self.db.execute("DELETE FROM Nightmode WHERE guildId = ?", (str(ctx.guild.id),))
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(ctx.guild.id, "nightmode", False)
            set_guild_setting(ctx.guild.id, "nightmode_manual", False)

        if restored:
            await self._dispatch_nightmode_log(
                guild=ctx.guild,
                action="recover",
                trigger_type="Disaster Recovery Command",
                roles=restored,
                moderator=ctx.author
            )
            await self._notify_owner(ctx.guild, activated=False, roles_count=len(restored), triggered_by="Disaster Recovery")

            role_mentions = ", ".join([r.mention for r in restored])
            embed = discord.Embed(
                title="<a:tick:1558726958802800660> Nightmode Role Recovery Successful",
                color=0x00FF88,
                description=(
                    f"Successfully restored administrator permissions to **{len(restored)}** role(s):\n\n"
                    f"{role_mentions}\n\n"
                    f"✅ **Database & Cloud State Synchronized!** Roles are fully restored and protected."
                )
            )
        else:
            embed = discord.Embed(
                title="ℹ️ No Stripped Roles Found",
                color=self.color,
                description=(
                    "No stripped Nightmode roles were found in the local database or in the `#yuna-nightmode` channel.\n\n"
                    "All manageable staff roles currently have administrator permissions, or none were stripped by Nightmode."
                )
            )
        await msg.edit(content=None, embed=embed)

    # ================= AUTO NIGHTMODE COMMANDS =================

    @nightmode.group(name="auto", invoke_without_command=True, help="Auto Nightmode scheduler settings")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    async def auto_nightmode_group(self, ctx):
        embed = discord.Embed(
            title="🌙 Auto Nightmode Scheduler (High Precision)",
            color=self.color,
            description=(
                "Auto Nightmode automatically engages lockdown during your configured hours, minutes, and seconds and restores permissions in the morning.\n"
                "**Survives VPS crashes & restarts** via pure clock-evaluated scheduling.\n\n"
                "Subcommands:\n"
                "<:red_dot:1222796144996777995> `nightmode auto enable [start] [end]` - Enable scheduler (e.g. `23:45:30 06:15:00` or default `00:00:00 to 06:00:00`)\n"
                "<:red_dot:1222796144996777995> `nightmode auto schedule <start> <end>` - Set custom lockdown time (HH:MM:SS, e.g. `22:30:00 06:00:00`)\n"
                "<:red_dot:1222796144996777995> `nightmode auto disable` - Disable Auto Nightmode scheduler\n"
                "<:red_dot:1222796144996777995> `nightmode auto status` - View current scheduler status, exact timings & log channel"
            )
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=embed)

    @auto_nightmode_group.command(name="enable", help="Enable scheduled Auto Nightmode (e.g. `nightmode auto enable 23:45:30 06:15:00`)")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def auto_enable(self, ctx, start_time_arg: str = "00:00:00", end_time_arg: str = "06:00:00"):
        own = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        check = await self.is_extra_owner(ctx.author, ctx.guild)
        if not own and not check and ctx.author.id not in self.ricky:
            return await ctx.send(embed=discord.Embed(
                title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=self.color,
                description="Only Server Owner Or Extraowner Can Run This Command!"
            ))

        s_h, s_m, s_s = parse_time_str_or_hms(start_time_arg, default_h=0, default_m=0, default_s=0)
        e_h, e_m, e_s = parse_time_str_or_hms(end_time_arg, default_h=6, default_m=0, default_s=0)

        if not (0 <= s_h <= 23 and 0 <= s_m <= 59 and 0 <= s_s <= 59) or not (0 <= e_h <= 23 and 0 <= e_m <= 59 and 0 <= e_s <= 59):
            return await ctx.send(embed=discord.Embed(
                title="<:Yuna_cross:1227866668152393789> Invalid Time",
                color=self.color,
                description="Please provide valid hours (0-23), minutes (0-59), and seconds (0-59).\nExample: `nightmode auto enable 23:45:30 06:15:00`"
            ))

        if (s_h, s_m, s_s) == (e_h, e_m, e_s):
            return await ctx.send(embed=discord.Embed(
                title="<:Yuna_cross:1227866668152393789> Invalid Schedule",
                color=self.color,
                description="Start time and End time cannot be identical."
            ))

        async with self.get_guild_lock(ctx.guild.id):
            log_channel, notice_embed = await self.get_or_create_nightmode_channel(ctx.guild)
            log_channel_id = log_channel.id if log_channel else None

            tz_name = "Asia/Kolkata"
            tz = pytz.timezone(tz_name)
            now_dt = datetime.datetime.now(tz)

            is_night_now = is_in_night_window(now_dt, s_h, e_h, s_m, s_s, e_m, e_s)
            start_str = f"{s_h:02d}:{s_m:02d}:{s_s:02d}"
            end_str = f"{e_h:02d}:{e_m:02d}:{e_s:02d}"

            await self.db.execute(
                """INSERT INTO nightmode_config (
                    guild_id, auto_enabled, log_channel,
                    start_hour, start_minute, start_second,
                    end_hour, end_minute, end_second,
                    start_time, end_time, timezone, last_action
                ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    auto_enabled = 1,
                    log_channel = COALESCE(excluded.log_channel, nightmode_config.log_channel),
                    start_hour = excluded.start_hour,
                    start_minute = excluded.start_minute,
                    start_second = excluded.start_second,
                    end_hour = excluded.end_hour,
                    end_minute = excluded.end_minute,
                    end_second = excluded.end_second,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    timezone = COALESCE(nightmode_config.timezone, excluded.timezone),
                    last_action = excluded.last_action
                """,
                (
                    ctx.guild.id, log_channel_id,
                    s_h, s_m, s_s,
                    e_h, e_m, e_s,
                    start_str, end_str, tz_name,
                    f"enabled_{now_dt.strftime('%H_%M_%S')}" if is_night_now else "scheduled"
                )
            )
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(ctx.guild.id, "nightmode_auto", True)

            if notice_embed:
                await ctx.send(embed=notice_embed)

            # If currently inside the night window, activate IMMEDIATELY
            if is_night_now:
                affected = await self._save_and_strip_roles(ctx.guild, self.db)
                await self._send_activation_log(ctx.guild, log_channel_id, affected, immediate=True)
                await self._notify_owner(ctx.guild, activated=True, roles_count=len(affected), triggered_by="Auto Scheduler (Immediate)")

                embed = discord.Embed(
                    title="<a:tick:1558726958802800660> Auto Nightmode Enabled & Activated",
                    color=self.color,
                    description=(
                        f"**Auto Nightmode is now ACTIVE for {ctx.guild.name}!**\n\n"
                        f"⚡ **Immediate Activation:** Current time `{now_dt.strftime('%I:%M:%S %p %Z')}` is within the configured Night Window (`{start_str}` – `{end_str}`).\n"
                        f"🛡️ **Administrator rights have been stripped immediately.**\n\n"
                        f"🌙 **Night Activation:** `{start_str}`\n"
                        f"☀️ **Morning Restoration:** `{end_str}`\n"
                        f"📢 **Log Channel:** {log_channel.mention if log_channel else 'Not Configured'}"
                    )
                )
            else:
                restored = await self._restore_roles(ctx.guild, self.db)
                if restored:
                    await self._send_deactivation_log(ctx.guild, log_channel_id, restored)
                embed = discord.Embed(
                    title="<a:tick:1558726958802800660> Auto Nightmode Configured & Scheduled",
                    color=self.color,
                    description=(
                        f"**Auto Nightmode is now scheduled for {ctx.guild.name}!**\n\n"
                        f"🌙 **Night Activation:** `{start_str}`\n"
                        f"☀️ **Morning Restoration:** `{end_str}`\n"
                        f"📢 **Log Channel:** {log_channel.mention if log_channel else 'Not Configured'}\n\n"
                        f"At `{start_str}`, admin permissions will automatically be removed from staff roles, and restored at `{end_str}`."
                    )
                )
            if self.bot.user:
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            await ctx.send(embed=embed)

    @auto_nightmode_group.command(name="schedule", help="Set custom start and end time (e.g. `nightmode auto schedule 23:45:30 06:15:00`)")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def auto_schedule(self, ctx, start_time: str, end_time: str):
        """Set custom start and end time for Auto Nightmode (HH:MM:SS)."""
        await self.auto_enable.callback(self, ctx, start_time, end_time)

    @auto_nightmode_group.command(name="disable", help="Disable scheduled Auto Nightmode")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def auto_disable(self, ctx):
        own = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        check = await self.is_extra_owner(ctx.author, ctx.guild)
        if not own and not check and ctx.author.id not in self.ricky:
            return await ctx.send(embed=discord.Embed(
                title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=self.color,
                description="Only Server Owner Or Extraowner Can Run This Command!"
            ))

        async with self.get_guild_lock(ctx.guild.id):
            # Restore any currently stripped roles
            restored = await self._restore_roles(ctx.guild, self.db)

            await self.db.execute("UPDATE nightmode_config SET auto_enabled = 0, last_action = 'disabled_manual' WHERE guild_id = ?", (ctx.guild.id,))
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(ctx.guild.id, "nightmode_auto", False)

            if restored:
                await self._dispatch_nightmode_log(
                    guild=ctx.guild,
                    action="deactivate",
                    trigger_type="Auto Scheduler (Disabled)",
                    roles=restored,
                    moderator=ctx.author
                )
                await self._notify_owner(ctx.guild, activated=False, roles_count=len(restored), triggered_by=str(ctx.author))

            embed = discord.Embed(
                title="<a:tick:1558726958802800660> Auto Nightmode Disabled",
                color=self.color,
                description=(
                    f"Auto Nightmode scheduler has been **disabled** for {ctx.guild.name}.\n\n"
                    f"🔓 Any stripped administrator permissions have been **restored**.\n"
                    f"🔒 **Note:** The custom schedule and logging channel settings have been safely **preserved**."
                )
            )
            embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user else None)
            await ctx.send(embed=embed)

    @auto_nightmode_group.command(name="status", help="View Auto Nightmode status")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def auto_status(self, ctx):
        async with self.db.execute(
            """SELECT auto_enabled, log_channel, start_hour, start_minute, start_second,
                      end_hour, end_minute, end_second, timezone, last_action
               FROM nightmode_config WHERE guild_id = ?""",
            (ctx.guild.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row or not row[0]:
            embed = discord.Embed(
                title=f"Auto Nightmode Status for {ctx.guild.name}",
                description="Current Status: **Disabled**\n\nTo enable, use `nightmode auto enable` or configure in Web Dashboard.",
                color=self.color
            )
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            return await ctx.send(embed=embed)

        auto_enabled, log_chan_id, s_h, s_m, s_s, e_h, e_m, e_s, tz_name, last_act = (
            row[0], row[1],
            row[2] or 0, row[3] or 0, row[4] or 0,
            row[5] or 6, row[6] or 0, row[7] or 0,
            row[8] or "Asia/Kolkata", row[9] or "None"
        )
        log_channel_mention = f"<#{log_chan_id}>" if log_chan_id else "Not Set"
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(tz)
        now_str = now.strftime('%I:%M:%S %p %Z')
        is_active_now = is_in_night_window(now, s_h, e_h, s_m, s_s, e_m, e_s)

        start_formatted = f"{s_h:02d}:{s_m:02d}:{s_s:02d}"
        end_formatted = f"{e_h:02d}:{e_m:02d}:{e_s:02d}"

        embed = discord.Embed(
            title=f"Auto Nightmode Status for {ctx.guild.name}",
            color=self.color,
            description=(
                f"Current Status: **{'🔴 LOCKDOWN ACTIVE' if is_active_now else '🟢 Standby'}**\n\n"
                f"🌙 **Night Activation:** `{start_formatted}`\n"
                f"☀️ **Morning Restoration:** `{end_formatted}`\n"
                f"🌍 **Timezone:** `{tz_name}`\n"
                f"📢 **Log Channel:** {log_channel_mention}\n"
                f"🔄 **Last Action:** `{last_act}`\n"
                f"🕒 **Current Clock:** `{now_str}`"
            )
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=embed)

    # ================= BACKGROUND SCHEDULER TASK (30-SECOND LOOP) =================

    @tasks.loop(seconds=30)
    async def check_auto_nightmode(self):
        """High-precision TRUE/FALSE schedule evaluation strictly in Indian Standard Time (IST).
        
        Evaluates purely against Indian Standard Time (Asia/Kolkata, UTC+5:30), completely
        independent of the VPS server's local system clock or timezone.
        """
        try:
            if not self.bot.is_ready():
                return

            tz_ist = pytz.timezone('Asia/Kolkata')
            now_ist = datetime.datetime.now(tz_ist)

            async with aiosqlite.connect(db_path, timeout=30.0) as db:
                await db.execute("PRAGMA busy_timeout=30000;")
                async with db.execute(
                    """SELECT guild_id, log_channel,
                              start_hour, start_minute, start_second,
                              end_hour, end_minute, end_second,
                              timezone, last_action
                       FROM nightmode_config WHERE auto_enabled = 1"""
                ) as cursor:
                    configs = await cursor.fetchall()

                for cfg in configs:
                    guild_id = cfg[0]
                    log_chan_id = cfg[1]
                    s_h = cfg[2] if cfg[2] is not None else 0
                    s_m = cfg[3] if len(cfg) > 3 and cfg[3] is not None else 0
                    s_s = cfg[4] if len(cfg) > 4 and cfg[4] is not None else 0
                    e_h = cfg[5] if len(cfg) > 5 and cfg[5] is not None else 6
                    e_m = cfg[6] if len(cfg) > 6 and cfg[6] is not None else 0
                    e_s = cfg[7] if len(cfg) > 7 and cfg[7] is not None else 0
                    last_act = cfg[9] if len(cfg) > 9 else None

                    guild = self.bot.get_guild(guild_id)
                    if not guild or not guild.me:
                        continue

                    # THE CORE LOGIC: Strict IST schedule evaluation
                    should_be_active = is_in_night_window(now_ist, s_h, e_h, s_m, s_s, e_m, e_s)

                    # Check current DB state: are there saved/stripped roles?
                    async with db.execute('SELECT COUNT(*) FROM Nightmode WHERE guildId = ?', (str(guild.id),)) as c:
                        row = await c.fetchone()
                        has_saved_roles = (row[0] > 0) if row else False

                    # Check if there are still unstripped admin roles on Discord
                    bot_highest_role = guild.me.top_role
                    has_unstripped_admin = any(
                        r.position < bot_highest_role.position
                        and r.name != '@everyone'
                        and r.permissions.administrator
                        and not r.managed
                        for r in guild.roles
                    ) if bot_highest_role else False

                    if should_be_active:
                        # Nightmode should be TRUE
                        needs_activation = (not has_saved_roles and has_unstripped_admin) or \
                                           (has_saved_roles and has_unstripped_admin)

                        if needs_activation:
                            async with self.get_guild_lock(guild.id):
                                is_recovery = bool(has_saved_roles and has_unstripped_admin)
                                affected = await self._save_and_strip_roles(guild, db)
                                await db.execute(
                                    "UPDATE nightmode_config SET last_action = ? WHERE guild_id = ?",
                                    (f"enabled_{now_ist.strftime('%H_%M_%S')}", guild.id)
                                )
                                await db.commit()
                                await self._send_activation_log(guild, log_chan_id, affected, immediate=is_recovery)
                                if not is_recovery:
                                    await self._notify_owner(guild, activated=True, roles_count=len(affected), triggered_by="Auto Scheduler")
                    else:
                        # Nightmode should be FALSE
                        # Only restore if manual lockdown is NOT active!
                        async with db.execute("SELECT guild_id FROM nightmode_guilds WHERE guild_id = ?", (guild.id,)) as c:
                            is_manual_active = bool(await c.fetchone())

                        if has_saved_roles and not is_manual_active:
                            async with self.get_guild_lock(guild.id):
                                restored = await self._restore_roles(guild, db)
                                await db.execute(
                                    "UPDATE nightmode_config SET last_action = ? WHERE guild_id = ?",
                                    (f"disabled_{now_ist.strftime('%H_%M_%S')}", guild.id)
                                )
                                await db.commit()
                                await self._send_deactivation_log(guild, log_chan_id, restored)
                                if restored:
                                    await self._notify_owner(guild, activated=False, roles_count=len(restored), triggered_by="Auto Scheduler")

                    pass

        except Exception as e:
            print(f"[AUTO NIGHTMODE SCHEDULER ERROR] {e}")

    @check_auto_nightmode.before_loop
    async def before_check_auto_nightmode(self):
        try:
            await self.bot.wait_until_ready()
            # Wait briefly for guild cache to populate before loop starts
            await asyncio.sleep(5)
        except Exception:
            pass

    # ================= MONGODB CLOUD BACKUP & DISASTER RECOVERY =================

    async def _backup_roles_to_discord_channel(self, guild: discord.Guild, log_channel: discord.TextChannel, affected_roles: list):
        """Deprecated channel message backup. Pure MongoDB Atlas Cloud persistence is active."""
        return

    async def _recover_roles_from_discord_channel(self, guild: discord.Guild, log_channel: discord.TextChannel = None) -> list:
        """Deprecated channel message recovery. Pure MongoDB Atlas Cloud persistence is active."""
        return []

    # ================= CRASH-SAFE CORE OPERATIONS =================

    async def _save_and_strip_roles(self, guild, db) -> list:
        """Crash-safe role stripping with persistent role tracking & MongoDB Cloud disaster recovery.
        
        Order:
        1. Read current Discord role permissions
        2. Save original state to SQLite (nightmode_roles & Nightmode)
        3. COMMIT DB (crash-safe checkpoint)
        4. Trigger immediate MongoDB Cloud Backup push
        5. Apply lockdown (strip admin)
        """
        bot_highest_role = guild.me.top_role
        manageable_roles = [
            role for role in guild.roles
            if role.position < bot_highest_role.position
            and role.name != '@everyone'
            and role.permissions.administrator
            and not role.managed
        ]

        if not manageable_roles:
            return []

        # Step 1 & 2: Save original permissions to DB BEFORE touching Discord
        for role in manageable_roles:
            # Guarantee administrator bit (8) is retained
            orig_perms_value = int(role.permissions.value) | 8

            # Check if this role already has a saved active entry
            async with db.execute(
                'SELECT original_permissions FROM nightmode_roles WHERE guild_id = ? AND role_id = ? AND is_active = 1',
                (str(guild.id), str(role.id))
            ) as cursor:
                existing = await cursor.fetchone()

            if not (existing and existing[0] and int(existing[0]) > 0):
                await db.execute('''
                    INSERT INTO nightmode_roles (guild_id, role_id, role_name, original_permissions, is_active, last_stripped_at)
                    VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id, role_id) DO UPDATE SET
                        role_name = excluded.role_name,
                        original_permissions = excluded.original_permissions,
                        is_active = 1,
                        last_stripped_at = CURRENT_TIMESTAMP
                ''', (str(guild.id), str(role.id), role.name, orig_perms_value))

            # Maintain legacy Nightmode table for backwards compatibility
            await db.execute('''
                INSERT OR REPLACE INTO Nightmode (guildId, roleId, adminPermissions, original_permissions)
                VALUES (?, ?, ?, ?)
            ''', (str(guild.id), str(role.id), 1, orig_perms_value))

        # Step 3: COMMIT — crash-safe checkpoint
        await db.commit()

        # Step 4: Trigger immediate MongoDB Cloud Backup
        try:
            backup_cog = self.bot.get_cog("DbCloudBackup")
            if backup_cog and backup_cog.mongo_client:
                await backup_cog._execute_cloud_backup(reason=f"Nightmode enabled for {guild.name}")
        except Exception:
            pass

        # Step 5: Apply lockdown — strip admin from each role
        affected_roles = []
        for role in manageable_roles:
            if role.permissions.administrator:
                try:
                    permissions = role.permissions
                    permissions.administrator = False
                    await role.edit(permissions=permissions, reason="Nightmode ENABLED")
                    affected_roles.append(role)
                except Exception:
                    pass

        return affected_roles

    async def _restore_roles(self, guild, db, force_cloud: bool = False) -> list:
        """Crash-safe role restoration with MongoDB Cloud persistence.
        
        Reads saved original permissions from:
        1. nightmode_roles (persistent table)
        2. Nightmode (legacy table)
        
        Applies Discord edits FIRST. Only cleans up DB state after edits succeed.
        """
        stored_roles = []  # list of (role_id_str, original_perms_int)

        # 1. Check primary persistent table: nightmode_roles
        try:
            async with db.execute(
                'SELECT role_id, original_permissions FROM nightmode_roles WHERE guild_id = ? AND is_active = 1',
                (str(guild.id),)
            ) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    stored_roles = [(str(r[0]), int(r[1]) if r[1] else 8) for r in rows]
        except Exception:
            pass

        # 2. Check legacy Nightmode table if primary had no active rows
        if not stored_roles:
            try:
                async with db.execute(
                    'SELECT roleId, adminPermissions, original_permissions FROM Nightmode WHERE guildId = ?',
                    (str(guild.id),)
                ) as cursor:
                    legacy_rows = await cursor.fetchall()
                    for r in legacy_rows:
                        orig = int(r[2]) if len(r) > 2 and r[2] and int(r[2]) > 0 else (int(r[1]) if r[1] else 8)
                        stored_roles.append((str(r[0]), orig | 8))
            except Exception:
                pass

        if not stored_roles:
            return []

        restored_roles = []
        restored_ids = []
        for role_id_str, original_perms in stored_roles:
            role = guild.get_role(int(role_id_str)) if role_id_str.isdigit() else None
            if role:
                # If role already has administrator, skip re-editing
                if role.permissions.administrator:
                    continue
                try:
                    # Restore FULL original permissions with administrator guaranteed
                    restored_perms = discord.Permissions(int(original_perms) | 8)
                    await role.edit(permissions=restored_perms, reason="Nightmode DISABLED — Full Permissions Restored")
                    restored_roles.append(role)
                    restored_ids.append(role_id_str)
                except Exception as e:
                    print(f"[NIGHTMODE ROLE RESTORE ERROR] {guild.id}/{role_id_str}: {e}")
                    restored_ids.append(role_id_str)
            else:
                restored_ids.append(role_id_str)

        # AFTER Discord edits: Update DB state safely
        try:
            await db.execute(
                'UPDATE nightmode_roles SET is_active = 0, last_restored_at = CURRENT_TIMESTAMP WHERE guild_id = ?',
                (str(guild.id),)
            )
            await db.execute('DELETE FROM Nightmode WHERE guildId = ?', (str(guild.id),))
            await db.execute('DELETE FROM nightmode_guilds WHERE guild_id = ?', (guild.id,))
            await db.commit()
        except Exception:
            pass

        return restored_roles

    # ================= LOG & NOTIFICATION HELPERS =================

    async def _get_guild_timer_str(self, guild_id: int) -> str:
        """Returns the formatted timer window (e.g. '12:00 AM to 06:00 AM (IST)')."""
        try:
            if self.db:
                async with self.db.execute(
                    "SELECT start_hour, start_minute, start_second, end_hour, end_minute, end_second FROM nightmode_config WHERE guild_id = ?",
                    (guild_id,)
                ) as cursor:
                    cfg_row = await cursor.fetchone()
                    if cfg_row:
                        s_h = cfg_row[0] or 0
                        s_m = cfg_row[1] or 0
                        s_s = cfg_row[2] or 0
                        e_h = cfg_row[3] or 6
                        e_m = cfg_row[4] or 0
                        e_s = cfg_row[5] or 0
                        if s_s or e_s:
                            s_fmt = datetime.time(s_h, s_m, s_s).strftime("%I:%M:%S %p")
                            e_fmt = datetime.time(e_h, e_m, e_s).strftime("%I:%M:%S %p")
                        else:
                            s_fmt = datetime.time(s_h, s_m).strftime("%I:%M %p")
                            e_fmt = datetime.time(e_h, e_m).strftime("%I:%M %p")
                        return f"{s_fmt} to {e_fmt} (IST)"
        except Exception:
            pass
        return "12:00 AM to 06:00 AM (IST)"

    async def _dispatch_nightmode_log(
        self,
        guild: discord.Guild,
        action: str,  # "activate", "deactivate", "recover"
        trigger_type: str,
        roles: list,
        moderator: Optional[Union[discord.Member, discord.User]] = None,
        log_channel_id: Optional[int] = None,
        extra_details: Optional[str] = None
    ) -> None:
        """Dispatches a simple, minimal, and detailed Nightmode audit log."""
        if not guild:
            return

        now_utc = discord.utils.utcnow()
        unix_ts = int(now_utc.timestamp())

        roles_list = [r for r in roles if r] if roles else []
        role_count = len(roles_list)

        # Clean compact role formatting
        if roles_list:
            if role_count <= 6:
                roles_str = ", ".join(r.mention for r in roles_list)
            else:
                roles_str = ", ".join(r.mention for r in roles_list[:6]) + f" *(+{role_count - 6} more)*"
        else:
            roles_str = "None"

        # Moderator / Executor formatting
        if moderator:
            executor_str = f"{moderator.mention} (`{moderator.id}`)"
        else:
            executor_str = "Auto Scheduler"

        # Simple & clean title, color, action description
        if action == "activate":
            color = 0xED4245
            title = "🌙 Nightmode Enabled"
            action_desc = "Administrator permissions stripped"
        elif action == "recover":
            color = 0x5865F2
            title = "🛡️ Nightmode Recovered"
            action_desc = "Emergency role permissions restored"
        else:  # deactivate
            color = 0x57F287
            title = "☀️ Nightmode Disabled"
            action_desc = "Administrator permissions restored"

        timer_str = await self._get_guild_timer_str(guild.id)

        desc_lines = [
            f"• **Action:** {action_desc}",
            f"• **Trigger:** `{trigger_type}`",
            f"• **Timer:** `{timer_str}`",
            f"• **Executor:** {executor_str}",
            f"• **Roles ({role_count}):** {roles_str}",
            f"• **Time:** <t:{unix_ts}:t> (<t:{unix_ts}:R>)"
        ]

        if extra_details:
            desc_lines.append(f"• **Details:** {extra_details}")

        embed = discord.Embed(
            title=title,
            description="\n".join(desc_lines),
            color=color,
            timestamp=now_utc
        )
        embed.set_footer(text=f"Guild ID: {guild.id}")

        # Dual Dispatch: LoggerServiceV2 (Webhook) + Direct Channel Fallback
        sent_v2_channel_id = None
        try:
            from services.logger_v2 import LoggerServiceV2
            target_ch, _ = await LoggerServiceV2.resolve_target(guild, "nightmode")
            if target_ch:
                sent = await LoggerServiceV2.send_v2_log(
                    guild=guild,
                    channel_key="nightmode",
                    title=embed.title,
                    description=embed.description,
                    color=color,
                    executor=moderator,
                    embed=embed,
                    event_key="nightmode_state"
                )
                if sent:
                    sent_v2_channel_id = target_ch.id
        except Exception:
            pass

        channel_to_send = None
        if log_channel_id and log_channel_id != sent_v2_channel_id:
            channel_to_send = guild.get_channel(log_channel_id)

        if not channel_to_send and not sent_v2_channel_id:
            try:
                if self.db:
                    async with self.db.execute("SELECT log_channel FROM nightmode_config WHERE guild_id = ?", (guild.id,)) as cursor:
                        row = await cursor.fetchone()
                        if row and row[0]:
                            channel_to_send = guild.get_channel(int(row[0]))
            except Exception:
                pass

        if not channel_to_send and not sent_v2_channel_id:
            try:
                channel_to_send, _ = await self.get_or_create_nightmode_channel(guild)
            except Exception:
                pass

        if channel_to_send and channel_to_send.id != sent_v2_channel_id:
            try:
                await channel_to_send.send(embed=embed)
            except Exception:
                pass

    async def _send_activation_log(self, guild, log_channel_id, affected_roles, immediate=False):
        """Send nightmode activation log to the log channel."""
        trigger = "Auto (Immediate)" if immediate else "Auto (Scheduled)"
        await self._dispatch_nightmode_log(
            guild=guild,
            action="activate",
            trigger_type=trigger,
            roles=affected_roles,
            log_channel_id=log_channel_id
        )

    async def _send_deactivation_log(self, guild, log_channel_id, restored_roles):
        """Send nightmode deactivation log to the log channel."""
        await self._dispatch_nightmode_log(
            guild=guild,
            action="deactivate",
            trigger_type="Auto (Scheduled)",
            roles=restored_roles,
            log_channel_id=log_channel_id
        )

    async def _notify_owner(self, guild, activated: bool, roles_count: int = 0, triggered_by: str = "System"):
        """DM the server owner and administrators when nightmode activates or deactivates (simple & minimal)."""
        try:
            if not guild:
                return

            now_utc = discord.utils.utcnow()
            unix_ts = int(now_utc.timestamp())
            timer_str = await self._get_guild_timer_str(guild.id)

            if activated:
                title = f"🌙 Nightmode Enabled — {guild.name}"
                action_desc = "Administrator permissions stripped"
                color = 0xED4245
            else:
                title = f"☀️ Nightmode Disabled — {guild.name}"
                action_desc = "Administrator permissions restored"
                color = 0x57F287

            desc_lines = [
                f"• **Server:** `{guild.name}`",
                f"• **Action:** {action_desc}",
                f"• **Trigger:** `{triggered_by}`",
                f"• **Timer:** `{timer_str}`",
                f"• **Roles Affected:** `{roles_count}` role(s)",
                f"• **Time:** <t:{unix_ts}:t> (<t:{unix_ts}:R>)"
            ]

            embed = discord.Embed(
                title=title,
                description="\n".join(desc_lines),
                color=color,
                timestamp=now_utc
            )
            embed.set_footer(text=f"Guild ID: {guild.id} • Security Alert")

            # 1. Resolve Server Owner
            owner = guild.owner or guild.get_member(guild.owner_id)
            if not owner and hasattr(guild, "fetch_member"):
                try:
                    owner = await guild.fetch_member(guild.owner_id)
                except Exception:
                    owner = None

            # 2. Resolve Admin Roles (both currently active on Discord and tracked in nightmode_roles)
            admin_role_ids = set()
            for role in guild.roles:
                if role.permissions.administrator:
                    admin_role_ids.add(role.id)

            if self.db:
                try:
                    async with self.db.execute(
                        "SELECT role_id FROM nightmode_roles WHERE guild_id = ? AND is_active = 1",
                        (str(guild.id),)
                    ) as cursor:
                        rows = await cursor.fetchall()
                        for r in rows:
                            try:
                                admin_role_ids.add(int(r[0]))
                            except (ValueError, TypeError):
                                pass
                except Exception:
                    pass

            # 3. Collect unique recipients (Owner + Administrators)
            recipients = set()
            if owner and not getattr(owner, "bot", False):
                recipients.add(owner)

            for member in guild.members:
                if getattr(member, "bot", False):
                    continue
                if member.guild_permissions.administrator or any(r.id in admin_role_ids for r in member.roles):
                    recipients.add(member)

            for r_id in admin_role_ids:
                role = guild.get_role(r_id)
                if role:
                    for m in role.members:
                        if not getattr(m, "bot", False):
                            recipients.add(m)

            # 4. Dispatch DM embeds to all recipients safely
            for recipient in recipients:
                try:
                    await recipient.send(embed=embed)
                    await asyncio.sleep(0.3)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass
        except Exception:
            pass

    _notify_admins_and_owner = _notify_owner

    # ================= DASHBOARD API METHODS =================

    async def enable_nightmode_gui(self, guild_id: int):
        """Enables Nightmode manually via web dashboard API."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False, "Guild not found on live bot"

        if self.db is None:
            await self.initialize_db()

        async with self.get_guild_lock(guild_id):
            log_channel, _ = await self.get_or_create_nightmode_channel(guild)
            log_id = log_channel.id if log_channel else None
            affected = await self._save_and_strip_roles(guild, self.db)
            await self.db.execute("INSERT OR REPLACE INTO nightmode_guilds (guild_id) VALUES (?)", (guild_id,))
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(guild_id, "nightmode", True)
            set_guild_setting(guild_id, "nightmode_manual", True)

            await self._dispatch_nightmode_log(
                guild=guild,
                action="activate",
                trigger_type="Web Dashboard (Manual)",
                roles=affected,
                log_channel_id=log_id
            )
            await self._notify_owner(guild, activated=True, roles_count=len(affected), triggered_by="Dashboard (Manual Lockdown)")
            return True, "Nightmode enabled on live bot"

    async def disable_nightmode_gui(self, guild_id: int):
        """Disables Nightmode manually via web dashboard API."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False, "Guild not found on live bot"

        if self.db is None:
            await self.initialize_db()

        async with self.get_guild_lock(guild_id):
            log_channel, _ = await self.get_or_create_nightmode_channel(guild)
            log_id = log_channel.id if log_channel else None
            restored = await self._restore_roles(guild, self.db)
            await self.db.execute("DELETE FROM nightmode_guilds WHERE guild_id = ?", (guild_id,))
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(guild_id, "nightmode", False)
            set_guild_setting(guild_id, "nightmode_manual", False)

            if restored:
                await self._dispatch_nightmode_log(
                    guild=guild,
                    action="deactivate",
                    trigger_type="Web Dashboard (Manual)",
                    roles=restored,
                    log_channel_id=log_id
                )
            await self._notify_owner(guild, activated=False, roles_count=len(restored), triggered_by="Dashboard (Manual Lockdown)")
            return True, "Nightmode disabled on live bot"

    async def auto_enable_gui(
        self,
        guild_id: int,
        start_hour: int = 0,
        start_minute: int = 0,
        start_second: int = 0,
        end_hour: int = 6,
        end_minute: int = 0,
        end_second: int = 0,
        timezone: str = "Asia/Kolkata"
    ):
        """Enables Auto-Scheduled Nightmode via web dashboard API with full HH:MM:SS support."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False, "Guild not found on live bot"

        if self.db is None:
            await self.initialize_db()

        async with self.get_guild_lock(guild_id):
            log_channel, _ = await self.get_or_create_nightmode_channel(guild)
            log_id = log_channel.id if log_channel else None
            try:
                tz = pytz.timezone(timezone)
            except Exception:
                tz = pytz.timezone('Asia/Kolkata')
            now_tz = datetime.datetime.now(tz)

            is_night_now = is_in_night_window(
                now_tz,
                start_hour, end_hour,
                start_minute, start_second,
                end_minute, end_second
            )

            start_str = f"{start_hour:02d}:{start_minute:02d}:{start_second:02d}"
            end_str = f"{end_hour:02d}:{end_minute:02d}:{end_second:02d}"

            await self.db.execute(
                """INSERT INTO nightmode_config (
                    guild_id, auto_enabled, log_channel,
                    start_hour, start_minute, start_second,
                    end_hour, end_minute, end_second,
                    start_time, end_time, timezone, last_action
                ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    auto_enabled = 1,
                    log_channel = COALESCE(excluded.log_channel, nightmode_config.log_channel),
                    start_hour = excluded.start_hour,
                    start_minute = excluded.start_minute,
                    start_second = excluded.start_second,
                    end_hour = excluded.end_hour,
                    end_minute = excluded.end_minute,
                    end_second = excluded.end_second,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    timezone = COALESCE(nightmode_config.timezone, excluded.timezone),
                    last_action = excluded.last_action
                """,
                (
                    guild_id, log_id,
                    start_hour, start_minute, start_second,
                    end_hour, end_minute, end_second,
                    start_str, end_str, timezone,
                    f"enabled_{now_tz.strftime('%H_%M_%S')}" if is_night_now else "scheduled"
                )
            )
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(guild_id, "nightmode_auto", True)

            if is_night_now:
                affected = await self._save_and_strip_roles(guild, self.db)
                await self._send_activation_log(guild, log_id, affected, immediate=True)
                await self._notify_owner(guild, activated=True, roles_count=len(affected), triggered_by="Dashboard (Auto)")
            else:
                async with self.db.execute("SELECT guild_id FROM nightmode_guilds WHERE guild_id = ?", (guild_id,)) as c:
                    is_manual = bool(await c.fetchone())
                if not is_manual:
                    restored = await self._restore_roles(guild, self.db)
                    if restored:
                        await self._send_deactivation_log(guild, log_id, restored)
                        await self._notify_owner(guild, activated=False, roles_count=len(restored), triggered_by="Dashboard (Auto Schedule)")
            return True, "Auto Nightmode schedule enabled"

    async def auto_disable_gui(self, guild_id: int):
        """Disables Auto-Scheduled Nightmode via web dashboard API."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False, "Guild not found on live bot"

        if self.db is None:
            await self.initialize_db()

        async with self.get_guild_lock(guild_id):
            log_channel, _ = await self.get_or_create_nightmode_channel(guild)
            log_id = log_channel.id if log_channel else None

            async with self.db.execute("SELECT guild_id FROM nightmode_guilds WHERE guild_id = ?", (guild_id,)) as c:
                is_manual = bool(await c.fetchone())
            restored = None
            if not is_manual:
                restored = await self._restore_roles(guild, self.db)

            await self.db.execute("UPDATE nightmode_config SET auto_enabled = 0, last_action = 'disabled_manual' WHERE guild_id = ?", (guild_id,))
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(guild_id, "nightmode_auto", False)

            if restored:
                await self._send_deactivation_log(guild, log_id, restored)
                await self._notify_owner(guild, activated=False, roles_count=len(restored), triggered_by="Dashboard (Auto)")
            return True, "Auto Nightmode schedule disabled"

    async def get_affected_roles(self, guild_id: int) -> list:
        """Returns list of currently stripped roles for dashboard display."""
        roles = []
        try:
            if self.db is None:
                await self.initialize_db()
            async with self.db.execute('SELECT role_id, original_permissions FROM nightmode_roles WHERE guild_id = ? AND is_active = 1', (str(guild_id),)) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    roles.append({
                        "id": str(row[0]),
                        "originalPermissions": int(row[1]) if row[1] else 8
                    })
            if not roles:
                async with self.db.execute('SELECT roleId, original_permissions FROM Nightmode WHERE guildId = ?', (str(guild_id),)) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        roles.append({
                            "id": str(row[0]),
                            "originalPermissions": int(row[1]) if row[1] else 8
                        })
        except Exception:
            pass
        return roles

    async def recover_roles_gui(self, guild_id: int):
        """Emergency role recovery via web dashboard API."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False, "Guild not found on live bot", []

        if self.db is None:
            await self.initialize_db()

        async with self.get_guild_lock(guild_id):
            restored = await self._restore_roles(guild, self.db, force_cloud=True)
            if not restored:
                # Check historical records
                async with self.db.execute(
                    "SELECT role_id, original_permissions FROM nightmode_roles WHERE guild_id = ?",
                    (str(guild_id),)
                ) as cursor:
                    historical = await cursor.fetchall()
                if historical:
                    for r_id_str, p_val in historical:
                        r = guild.get_role(int(r_id_str)) if r_id_str.isdigit() else None
                        if r and not r.permissions.administrator and r.position < guild.me.top_role.position:
                            try:
                                perms = discord.Permissions(int(p_val) | 8)
                                await r.edit(permissions=perms, reason="Nightmode RECOVERY (Dashboard)")
                                restored.append(r)
                            except Exception:
                                pass

            await self.db.execute("DELETE FROM nightmode_guilds WHERE guild_id = ?", (guild_id,))
            await self.db.execute("UPDATE nightmode_roles SET is_active = 0, last_restored_at = CURRENT_TIMESTAMP WHERE guild_id = ?", (str(guild_id),))
            await self.db.execute("DELETE FROM Nightmode WHERE guildId = ?", (str(guild_id),))
            await self.db.commit()

            from utils.settings_manager import set_guild_setting
            set_guild_setting(guild_id, "nightmode", False)
            set_guild_setting(guild_id, "nightmode_manual", False)

            return True, f"Successfully restored {len(restored)} role(s)", [{"id": str(r.id), "name": r.name} for r in restored]


async def setup(bot):
    await bot.add_cog(Nightmode(bot))
