import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *
from typing import Union
from utils.paginator import Paginator as sonu
import re

class BlacklistWordPaginator:
    def __init__(self, entries):
        self.entries = entries
        self.per_page = 4
        self.embeds = self.get_pages()

    def get_pages(self):
        pages = []
        total_pages = (len(self.entries) // self.per_page) + (1 if len(self.entries) % self.per_page else 0)

        for i in range(0, len(self.entries), self.per_page):
            embed = discord.Embed(
                title="Blacklist Word Commands",
                description="\n".join(self.entries[i:i + self.per_page]),
                color=0x000000
            )

            embed.set_footer(
                text=f'Page {i // self.per_page + 1}/{total_pages} | Users having Administrator can use Blacklisted Word',
                icon_url="https://cdn.discordapp.com/avatars/1525256351171739678/a_f061e6472786781e23bac32fa8d0a667.png?width=115&height=115"
            )
            pages.append(embed)

        return pages

DB_PATH = "db/blword.db"

async def create_blacklist_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                guild_id TEXT,
                word TEXT,
                PRIMARY KEY (guild_id, word)
            )
        """)
        await db.commit()


async def create_bypass_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bypass (
                guild_id TEXT,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.commit()


async def create_bypass_roles_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bypass_roles (
                guild_id TEXT,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )
        """)
        await db.commit()




class Blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        asyncio.create_task(create_blacklist_table())
        asyncio.create_task(create_bypass_table())
        asyncio.create_task(create_bypass_roles_table())
        
############ FUNCTIONS ############
    async def is_word_blacklisted(self, guild_id, word):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM blacklist WHERE guild_id = ? AND word = ?", (guild_id, word)) as cursor:
                return await cursor.fetchone() is not None
                

    async def add_word_to_blacklist(self, guild_id, word):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO blacklist (guild_id, word) VALUES (?, ?)", (guild_id, word))
            await db.commit()
            

    async def remove_word_from_blacklist(self, guild_id, word):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM blacklist WHERE guild_id = ? AND word = ?", (guild_id, word))
            await db.commit()
            

    async def get_blacklisted_words(self, guild_id):
        words = set()
        # 1. Check blword.db table: blacklist
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT word FROM blacklist WHERE guild_id = ? OR guild_id = ?", (str(guild_id), int(guild_id))) as cursor:
                    async for row in cursor:
                        if row[0]: words.add(str(row[0]).strip())
        except Exception:
            pass

        # 2. Check blword.db table: blword
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT word FROM blword WHERE guild_id = ? OR guild_id = ?", (str(guild_id), int(guild_id))) as cursor:
                    async for row in cursor:
                        if row[0]: words.add(str(row[0]).strip())
        except Exception:
            pass

        # 3. Check automod.db table: automod_blacklist
        try:
            async with aiosqlite.connect("db/automod.db") as am_db:
                async with am_db.execute("SELECT word FROM automod_blacklist WHERE guild_id = ? OR guild_id = ?", (int(guild_id), str(guild_id))) as cursor:
                    async for row in cursor:
                        if row[0]: words.add(str(row[0]).strip())
        except Exception:
            pass

        return list(words)
                

    async def is_user_bypassed(self, guild_id, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM bypass WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cursor:
                return await cursor.fetchone() is not None
                

    async def add_user_to_bypass(self, guild_id, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO bypass (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
            await db.commit()
            

    async def remove_user_from_bypass(self, guild_id, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM bypass WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await db.commit()
            

    async def get_bypassed_users(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id FROM bypass WHERE guild_id = ?", (guild_id,)) as cursor:
                return [row[0] async for row in cursor]
                

    async def is_role_bypassed(self, guild_id, role_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM bypass_roles WHERE guild_id = ? AND role_id = ?", (guild_id, role_id)) as cursor:
                return await cursor.fetchone() is not None
                

    async def add_role_to_bypass(self, guild_id, role_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO bypass_roles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
            await db.commit()
            

    async def remove_role_from_bypass(self, guild_id, role_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM bypass_roles WHERE guild_id = ? AND role_id = ?", (guild_id, role_id))
            await db.commit()
            

    async def get_bypassed_roles(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM bypass_roles WHERE guild_id = ?", (guild_id,)) as cursor:
                return [row[0] async for row in cursor]


    async def remove_all_words_from_blacklist(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM blacklist WHERE guild_id = ?", (guild_id,))
            await db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        words = await self.get_blacklisted_words(guild_id)
        if not words:
            return

        bypassed_users = await self.get_bypassed_users(guild_id)
        bypassed_roles = await self.get_bypassed_roles(guild_id)

        if message.author.guild_permissions.administrator or message.author.id in bypassed_users:
            return

        from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER
        if message.author.id in {message.guild.owner_id, self.bot.user.id} or message.author.id == PRIMARY_BOT_OWNER or message.author.id in GLOBAL_OWNER_IDS:
            return

        for role in getattr(message.author, 'roles', []):
            if role.id in bypassed_roles:
                return

        # Check whitelisted roles and users from security_cache
        from core.cache.security_cache import security_cache
        try:
            guild_int = int(message.guild.id)
            if security_cache.is_whitelisted(guild_int, message.author.id) or security_cache.is_extra_owner(guild_int, message.author.id):
                return
            wl_roles = security_cache._whitelisted_roles.get(guild_int, set())
            if any(role.id in wl_roles for role in getattr(message.author, 'roles', [])):
                return
        except Exception:
            pass

        # Check if AutoMod is active for this guild
        from core.cache.security_cache import security_cache
        try:
            guild_int = int(message.guild.id)
            if not security_cache.is_automod_enabled(guild_int):
                return
        except Exception:
            pass

        # Check ignored channels & roles from AutoMod in automod.db
        try:
            async with aiosqlite.connect("db/automod.db") as am_db:
                async with am_db.execute("SELECT type, id FROM automod_ignored WHERE guild_id = ?", (int(message.guild.id),)) as cursor:
                    rows = await cursor.fetchall()
                    for itype, iid in rows:
                        if itype == "channel" and message.channel.id == iid:
                            return
                        if itype == "role" and any(r.id == iid for r in getattr(message.author, "roles", [])):
                            return
                        if itype == "user" and message.author.id == iid:
                            return
        except Exception:
            pass

        content_lower = message.content.lower()
        content_normalized = re.sub(r'[\s_.\-*|~]+', ' ', content_lower).strip()

        # Check custom guild blacklisted words
        for word in words:
            if word.lower() in content_normalized or word.lower() in content_lower:
                from cogs.yuna_automod.executor import execute_automod_action
                await execute_automod_action(
                    self.bot,
                    message.guild,
                    message.author,
                    message.channel,
                    message,
                    'Anti blacklisted words',
                    f'Blacklisted Word ("{word}")'
                )
                return

    @commands.group(name="blacklistword", aliases=["blword"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def blacklistword(self, ctx):
        commands_list = [
            "➜ `blacklistword add <word>` - Add a word to the blacklist.\n",
            "➜ `blacklistword remove <word>` - Remove a word from the blacklist.\n",
            "➜ `blacklistword reset` - Clear all blacklisted words for the guild.\n",
            "➜ `blacklistword config` - Show the list of blacklisted words for the guild.\n",
            "➜ `blacklistword bypass add <role>/<user>` - Add a role/user to the bypass list.\n",
            "➜ `blacklistword bypass remove <role>/<user>` - Remove a role/user from the bypass list.\n",
            "➜ `blacklistword bypass list` - Show the list of bypassed roles/users."
        ]

        paginator = sonu(ctx, BlacklistWordPaginator(commands_list).embeds)
        await paginator.paginate()
    @blacklistword.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, *, words: str):
        guild_id = str(ctx.guild.id)
        raw_list = [w.strip().lower() for w in re.split(r'[\s,]+', words) if w.strip()]
        if not raw_list:
            return await ctx.reply("<:Yuna_cross:1227866668152393789> Please provide at least one word to add to the blacklist.")

        existing_words = set(await self.get_blacklisted_words(guild_id))
        
        added = []
        already_exists = []

        for w in raw_list:
            if w in existing_words:
                already_exists.append(w)
            else:
                await self.add_word_to_blacklist(guild_id, w)
                existing_words.add(w)
                added.append(w)

        desc = ""
        if added:
            desc += f"<a:tick:1558726958802800660> Added **{len(added)}** word(s) to blacklist: " + ", ".join([f"`{w}`" for w in added]) + "\n"
        if already_exists:
            desc += f"<:Yuna_notify:1227866804630720565> Already in blacklist: " + ", ".join([f"`{w}`" for w in already_exists]) + "\n"

        embed = discord.Embed(
            title="Blacklisted Words Updated",
            description=desc.strip(),
            color=discord.Color.from_rgb(0, 0, 0)
        )
        await ctx.reply(embed=embed)

    @blacklistword.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx, *, words: str):
        guild_id = str(ctx.guild.id)
        raw_list = [w.strip().lower() for w in re.split(r'[\s,]+', words) if w.strip()]
        if not raw_list:
            return await ctx.reply("<:Yuna_cross:1227866668152393789> Please provide at least one word to remove.")

        existing_words = set(await self.get_blacklisted_words(guild_id))
        
        removed = []
        not_found = []

        for w in raw_list:
            if w in existing_words:
                await self.remove_word_from_blacklist(guild_id, w)
                existing_words.remove(w)
                removed.append(w)
            else:
                not_found.append(w)

        desc = ""
        if removed:
            desc += f"<a:tick:1558726958802800660> Removed **{len(removed)}** word(s) from blacklist: " + ", ".join([f"`{w}`" for w in removed]) + "\n"
        if not_found:
            desc += f"<:Yuna_cross:1227866668152393789> Not in blacklist: " + ", ".join([f"`{w}`" for w in not_found]) + "\n"

        embed = discord.Embed(
            title="Blacklisted Words Updated",
            description=desc.strip(),
            color=discord.Color.from_rgb(0, 0, 0)
        )
        await ctx.reply(embed=embed)

    @blacklistword.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        guild_id = str(ctx.guild.id)
        words = await self.get_blacklisted_words(guild_id)

        if not words:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                description="No words are currently blacklisted.",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            await ctx.reply(embed=embed)
            return

        await self.remove_all_words_from_blacklist(guild_id)

        embed = discord.Embed(title="<a:tick:1558726958802800660> Success",
            description="Cleared all blacklisted words.",
            color=discord.Color.from_rgb(0, 0, 0)
        )
        await ctx.reply(embed=embed)


    @blacklistword.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        guild_id = str(ctx.guild.id)
        words = await self.get_blacklisted_words(guild_id)
        if not words:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                description="No words are currently blacklisted.",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            await ctx.reply(embed=embed)
            return

        embed = discord.Embed(
            title=f"Blacklisted Words for {ctx.guild.name}",
            description="\n".join(words),
            color=discord.Color.from_rgb(0, 0, 0)
        )
        await ctx.reply(embed=embed)

    @blacklistword.group(name="bypass", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass(self, ctx):
        embed = discord.Embed(
            title="Bypass User Commands",
            description=(
                "➜ `blacklistword bypass add <role>/<user>` - Add a role/user to the bypass list.\n\n"
                "➜ `blacklistword bypass remove <role>/<user>` - Remove a role/user from the bypass list.\n\n"
                "➜ `blacklistword bypass list` - Show the list of bypassed roles/users."
            ),
            color=discord.Color.from_rgb(0, 0, 0)
        )
        await ctx.send(embed=embed)


    @bypass.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_add(self, ctx, target: Union[discord.Member, discord.Role]):
        guild_id = str(ctx.guild.id)
        if isinstance(target, discord.Member):
            if len(await self.get_bypassed_users(guild_id)) >= 30:
                await ctx.reply("The bypass list for users is full. Maximum 30 users allowed.")
                return
            if await self.is_user_bypassed(guild_id, target.id):
                embed = discord.Embed(
                    description=f"<:Yuna_cross:1227866668152393789> | `{target}` is already bypassed.",
                    color=discord.Color.from_rgb(0, 0, 0)
                )
                await ctx.reply(embed=embed)
                return
            await self.add_user_to_bypass(guild_id, target.id)
            embed = discord.Embed(title="<a:tick:1558726958802800660> Success",
                description=f"Added `{target}` to the bypass list.",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            await ctx.reply(embed=embed)

        elif isinstance(target, discord.Role):
            if len(await self.get_bypassed_roles(guild_id)) >= 30:
                await ctx.reply("The bypass list for roles is full. Maximum 30 roles allowed.")
                return
            if await self.is_role_bypassed(guild_id, target.id):
                embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                    description=f"`{target}` is already bypassed.",
                    color=discord.Color.from_rgb(0, 0, 0)
                )
                await ctx.reply(embed=embed)
                return
            await self.add_role_to_bypass(guild_id, target.id)
            embed = discord.Embed(title="<a:tick:1558726958802800660> Success",
                description=f"Added `{target}` to the bypass list.",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            await ctx.reply(embed=embed)


    
    @bypass.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_remove(self, ctx, target: Union[discord.Member, discord.Role]):
        guild_id = str(ctx.guild.id)
        if isinstance(target, discord.Member):
            if not await self.is_user_bypassed(guild_id, target.id):
                embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                    description=f"`{target}` is not bypassed.",
                    color=discord.Color.from_rgb(0, 0, 0)
                )
                await ctx.reply(embed=embed)
                return
            await self.remove_user_from_bypass(guild_id, target.id)
            embed = discord.Embed(title="<a:tick:1558726958802800660> Success",
                description=f"Removed `{target}` from the bypass list.",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            await ctx.reply(embed=embed)

        elif isinstance(target, discord.Role):
            if not await self.is_role_bypassed(guild_id, target.id):
                embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                    description=f"`{target}` is not bypassed.",
                    color=discord.Color.from_rgb(0, 0, 0)
                )
                await ctx.reply(embed=embed)
                return
            await self.remove_role_from_bypass(guild_id, target.id)
            embed = discord.Embed(title="<a:tick:1558726958802800660> Success",
                description=f"Removed `{target}` from the bypass list.",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            await ctx.reply(embed=embed)

    @bypass.command(name="list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_list(self, ctx):
        guild_id = str(ctx.guild.id)
        users = await self.get_bypassed_users(guild_id)
        roles = await self.get_bypassed_roles(guild_id)

        if not users and not roles:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                description="No users or roles are currently bypassed.",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            await ctx.send(embed=embed)
            return

        bypassed_users = [ctx.guild.get_member(user_id) for user_id in users if ctx.guild.get_member(user_id)]
        bypassed_roles = [ctx.guild.get_role(role_id) for role_id in roles if ctx.guild.get_role(role_id)]
        embed = discord.Embed(
            title=f"Bypassed Users and Roles for {ctx.guild.name}",
            color=discord.Color.from_rgb(0, 0, 0)
        )

        if bypassed_users:
            embed.add_field(name="Users", value=", ".join([user.name for user in bypassed_users]), inline=False)

        if bypassed_roles:
            embed.add_field(name="Roles", value=", ".join([role.name for role in bypassed_roles]), inline=False)

        await ctx.send(embed=embed)


    @add.error
    @remove.error
    @reset.error
    @config.error
    @bypass_add.error
    @bypass_remove.error
    async def command_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            if not isinstance(error, commands.CommandOnCooldown):
                embed = discord.Embed(
                    description="<:Yuna_cross:1227866668152393789> | An error occurred while processing the command. Make sure you have **Administrator** permissios.",
                    color=discord.Color.from_rgb(0, 0, 0)
                )
                await ctx.reply(embed=embed)
