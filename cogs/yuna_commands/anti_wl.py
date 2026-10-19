import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *
from utils.config import OWNER_IDS


import asyncio
class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        asyncio.create_task(self.initialize_db())

    
    #@commands.Cog.listener()
    async def initialize_db(self):
        self.db = await aiosqlite.connect('db/anti.db')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS whitelisted_users (
                guild_id INTEGER,
                user_id INTEGER,
                ban BOOLEAN DEFAULT FALSE,
                kick BOOLEAN DEFAULT FALSE,
                prune BOOLEAN DEFAULT FALSE,
                botadd BOOLEAN DEFAULT FALSE,
                serverup BOOLEAN DEFAULT FALSE,
                memup BOOLEAN DEFAULT FALSE,
                chcr BOOLEAN DEFAULT FALSE,
                chdl BOOLEAN DEFAULT FALSE,
                chup BOOLEAN DEFAULT FALSE,
                rlcr BOOLEAN DEFAULT FALSE,
                rlup BOOLEAN DEFAULT FALSE,
                rldl BOOLEAN DEFAULT FALSE,
                meneve BOOLEAN DEFAULT FALSE,
                mngweb BOOLEAN DEFAULT FALSE,
                mngstemo BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await self.db.commit()

    @commands.hybrid_command(name='whitelist', aliases=['wl'], help="Whitelists a user from antinuke for a specific action.")

    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)

    async def whitelist(self, ctx, *, member_or_subcommand: str = None):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x000000,
                description="❌ | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        prefix=ctx.prefix

        is_owner = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        is_admin = ctx.author.guild_permissions.administrator if hasattr(ctx.author, "guild_permissions") else False
        if not is_owner and not is_admin:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=0x000000,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        if member_or_subcommand:
            sub_low = member_or_subcommand.strip().lower()
            if sub_low.startswith("evy1") or sub_low.startswith("everyone") or sub_low.startswith("here") or sub_low.startswith("ev1"):
                first_word = sub_low.split()[0]
                args_str = member_or_subcommand.strip()[len(first_word):].strip()
                return await self.handle_evy1_whitelist(ctx, args_str)

            # Strip optional 'add ' prefix (e.g. "$wl add @Role" -> "@Role", "$wl add @user" -> "@user")
            parsed_input = member_or_subcommand.strip()
            if parsed_input.lower().startswith("add "):
                parsed_input = parsed_input[4:].strip()
                sub_low = parsed_input.lower()

            if sub_low.startswith("role") or sub_low.startswith("roles"):
                bot_wl_cog = ctx.bot.get_cog("BotWhitelist")
                first_word = sub_low.split()[0]
                remainder = parsed_input[len(first_word):].strip()
                parts = remainder.split(maxsplit=1)
                action = parts[0].lower() if len(parts) > 0 else None
                target_role_str = parts[1] if len(parts) > 1 else (parts[0] if len(parts) == 1 and not parts[0].lower() in ["add", "remove", "del", "list", "reset", "show", "unwhitelist"] else None)

                if action in ["add", "remove", "del", "list", "reset", "show", "unwhitelist"] and len(parts) == 1:
                    target_role_str = None

                target_role = None
                if target_role_str:
                    try:
                        target_role = await commands.RoleConverter().convert(ctx, target_role_str)
                    except Exception:
                        target_role = None

                if bot_wl_cog:
                    if action == "add" and target_role:
                        return await bot_wl_cog.wr_add(ctx, target_role)
                    elif action in ["remove", "del", "unwhitelist"] and target_role:
                        return await bot_wl_cog.wr_remove(ctx, target_role)
                    elif action in ["list", "show"]:
                        return await bot_wl_cog.wr_list(ctx)
                    elif action == "reset":
                        return await bot_wl_cog.wr_reset(ctx)
                    elif target_role:
                        return await bot_wl_cog.wr_add(ctx, target_role)
                    else:
                        return await bot_wl_cog.whitelistrole(ctx)

            # Check if parsed_input is a Role directly (e.g. "$wl @Admin" or "$wl <@&123>")
            try:
                role_match = await commands.RoleConverter().convert(ctx, parsed_input)
                if role_match:
                    bot_wl_cog = ctx.bot.get_cog("BotWhitelist")
                    if bot_wl_cog:
                        return await bot_wl_cog.wr_add(ctx, role_match)
            except Exception:
                pass
        else:
            parsed_input = None

        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            antinuke = await cursor.fetchone()

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0x000000,
                description=(
                    f"**{ctx.guild.name} Security Settings <:MOD:1548704219517821089>\n"
                    "Ohh No! looks like your server doesn't enabled Antinuke\n\n"
                    "Current Status : <:disable:1548686459865792583>\n\n"
                    f"To enable use `{prefix}antinuke enable` **"
                )
            )
            embed.set_thumbnail(url=ctx.bot.user.avatar.url)
            return await ctx.send(embed=embed)

        if not parsed_input:
            embed = discord.Embed(
                color=0x000000,
                title="__**Whitelist Commands**__",
                description="**Adding a user or role to the whitelist means that no actions will be taken against them if they trigger the Anti-Nuke Module.**"
            )
            embed.add_field(name="__**Usage**__", value=f"<:red_dot:1222796144996777995> `{prefix}whitelist @user / @role`\n<:red_dot:1222796144996777995> `{prefix}wl role add @role`\n<:red_dot:1222796144996777995> `{prefix}wl @user`")
            embed.set_thumbnail(url=ctx.bot.user.avatar.url)
            return await ctx.send(embed=embed)

        try:
            member = await commands.MemberConverter().convert(ctx, parsed_input)
        except Exception:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                color=0x000000,
                description=f"Member or Role `{member_or_subcommand}` not found."
            )
            return await ctx.send(embed=embed)

        if is_server_owner_or_extra_owner(ctx.guild, member) or member.id == self.bot.user.id:
            embed = discord.Embed(
                title="<a:tick:1558726958802800660> Already Immune",
                color=0x000000,
                description=f"<@{member.id}> is a **Bot Owner / Server Owner / Extra Owner** and already has permanent global bypass immunity across all Antinuke & security systems!"
            )
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT * FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id)
        ) as cursor:
            data = await cursor.fetchone()

        if data:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                color=0x000000,
                description=f"<@{member.id}> is already a whitelisted member, **Unwhitelist** the user and try again."
            )
            return await ctx.send(embed=embed)

        await self.db.execute('''
            INSERT INTO whitelisted_users 
            (guild_id, user_id, ban, kick, prune, botadd, serverup, memup, chcr, chdl, chup, rlcr, rldl, rlup, meneve, mngweb, mngstemo)
            VALUES (?, ?, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
        ''', (ctx.guild.id, member.id))
        await self.db.commit()
        from core.cache.security_cache import security_cache
        security_cache.invalidate_guild(ctx.guild.id)
        await security_cache.warm_guild(ctx.guild.id)
        from utils.settings_manager import sync_all_settings
        sync_all_settings()

        try:
            from services.whitelist_panel import WhitelistPanelService
            asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Staff User Whitelisted", member, ctx.author))
        except Exception:
            pass

        options = [
            discord.SelectOption(label="Ban", description="Whitelist a member with ban permission", value="ban"),
            discord.SelectOption(label="Kick", description="Whitelist a member with kick permission", value="kick"),
            discord.SelectOption(label="Prune", description="Whitelist a member with prune permission", value="prune"),
            discord.SelectOption(label="Bot Add", description="Whitelist a member with bot add permission", value="botadd"),
            discord.SelectOption(label="Server Update", description="Whitelist a member with server update permission", value="serverup"),
            discord.SelectOption(label="Member Update", description="Whitelist a member with member update permission", value="memup"),
            discord.SelectOption(label="Channel Create", description="Whitelist a member with channel create permission", value="chcr"),
            discord.SelectOption(label="Channel Delete", description="Whitelist a member with channel delete permission", value="chdl"),
            discord.SelectOption(label="Channel Update", description="Whitelist a member with channel update permission", value="chup"),
            discord.SelectOption(label="Role Create", description="Whitelist a member with role create permission", value="rlcr"),
            discord.SelectOption(label="Role Update", description="Whitelist a member with role update permission", value="rlup"),
            discord.SelectOption(label="Role Delete", description="Whitelist a member with role delete permission", value="rldl"),
            discord.SelectOption(label="Mention Everyone", description="Whitelist a member with mention everyone permission", value="meneve"),
            discord.SelectOption(label="Manage Webhook", description="Whitelist a member with manage webhook permission", value="mngweb")
        ]

        select = discord.ui.Select(placeholder="Choose Your Options", min_values=1, max_values=len(options), options=options, custom_id="wl")
        button = discord.ui.Button(label="Add This User To All Categories", style=discord.ButtonStyle.primary, custom_id="catWl")

        view = discord.ui.View()
        view.add_item(select)
        view.add_item(button)

        embed = discord.Embed(
            title=ctx.guild.name,
            color=0x000000,
            description=(
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Ban**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Kick**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Prune**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Bot Add**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Server Update**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Member Update**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Channel Create**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Channel Delete**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Channel Update**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Role Create**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Role Delete**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Role Update**\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Mention** @everyone\n"
                "<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **Webhook Management**"
                
            )
        )
        embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
        embed.add_field(name="**Target**", value=f"<@!{member.id}>", inline=True)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_footer(text="Developed by Yuna Development™")

        msg = await ctx.send(embed=embed, view=view)

        def check(interaction):
            return interaction.user.id == ctx.author.id and interaction.message.id == msg.id

        try:
            interaction = await self.bot.wait_for("interaction", check=check, timeout=60.0)
            if interaction.data["custom_id"] == "catWl":
                
                await self.db.execute(
                    "UPDATE whitelisted_users SET ban = ?, kick = ?, prune = ?, botadd = ?, serverup = ?, memup = ?, chcr = ?, chdl = ?, chup = ?, rlcr = ?, rldl = ?, rlup = ?, meneve = ?, mngweb = ?, mngstemo = ? WHERE guild_id = ? AND user_id = ?",
                    (True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, ctx.guild.id, member.id)
                )
                await self.db.commit()
                from core.cache.security_cache import security_cache
                security_cache.invalidate_guild(ctx.guild.id)
                await security_cache.warm_guild(ctx.guild.id)
                from utils.settings_manager import sync_all_settings
                sync_all_settings()

                
                embed = discord.Embed(
                    title=ctx.guild.name,
                    color=0x000000,
                    description=(
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Ban**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Kick**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Prune**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Bot Add**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Server Update**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Member Update**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Channel Create**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Channel Delete**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Channel Update**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Role Create**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Role Delete**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Role Update**\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Mention** @everyone\n"
                        "<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **Webhook Management**"
                        
                    )
                )
                embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
                embed.add_field(name="**Target**", value=f"<@!{member.id}>", inline=True)
                embed.set_thumbnail(url=self.bot.user.avatar.url)
                embed.set_footer(text="Developed by Yuna Development™")

                await interaction.response.edit_message(embed=embed, view=None)
            else:
                
                fields = {
                    'ban': 'Ban',
                    'kick': 'Kick',
                    'prune': 'Prune',
                    'botadd': 'Bot Add',
                    'serverup': 'Server Update',
                    'memup': 'Member Update',
                    'chcr': 'Channel Create',
                    'chdl': 'Channel Delete',
                    'chup': 'Channel Update',
                    'rlcr': 'Role Create',
                    'rldl': 'Role Delete',
                    'rlup': 'Role Update',
                    'meneve': 'Mention Everyone',
                    'mngweb': 'Manage Webhooks'
                }

                
                embed_description = "\n".join(f"<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **{name}**" for key, name in fields.items())

                
                await self.db.execute(
                    "UPDATE whitelisted_users SET ban = 0, kick = 0, prune = 0, botadd = 0, serverup = 0, memup = 0, chcr = 0, chdl = 0, chup = 0, rlcr = 0, rldl = 0, rlup = 0, meneve = 0, mngweb = 0, mngstemo = 0 WHERE guild_id = ? AND user_id = ?",
                    (ctx.guild.id, member.id)
                )

                for value in interaction.data["values"]:
                    await self.db.execute(
                        f"UPDATE whitelisted_users SET {value} = ? WHERE guild_id = ? AND user_id = ?",
                        (True, ctx.guild.id, member.id)
                    )
                    embed_description = embed_description.replace(f"<:antinuke_cross1:1276219010781810799><:antinuke_tick2:1276215848687898785> : **{fields[value]}**", f"<:antinuke_cross2:1276218117206577202><:antinuke_tick1:1276216939407999036> : **{fields[value]}**")

                await self.db.commit()
                from core.cache.security_cache import security_cache
                security_cache.invalidate_guild(ctx.guild.id)
                await security_cache.warm_guild(ctx.guild.id)
                from utils.settings_manager import sync_all_settings
                sync_all_settings()

                
                embed = discord.Embed(
                    title=ctx.guild.name,
                    color=0x000000,
                    description=embed_description
                )
                embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
                embed.add_field(name="**Target**", value=f"<@!{member.id}>", inline=True)
                embed.set_thumbnail(url=self.bot.user.avatar.url)
                embed.set_footer(text="Developed by Yuna Development™")

                await interaction.response.edit_message(embed=embed, view=None)
        except TimeoutError:
            await msg.edit(view=None)


    @commands.hybrid_command(name='whitelisted', aliases=['wlist'], help="Shows the list of whitelisted users.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelisted(self, ctx):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x000000,
                description="❌ | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        pre=ctx.prefix

        is_owner = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        if not is_owner:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=0x000000,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            antinuke = await cursor.fetchone()

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0x000000,
                description=(
                    f"**{ctx.guild.name} security settings <:MOD:1548704219517821089>\n"
                    "Ohh NO! looks like your server doesn't enabled security\n\n"
                    "Current Status : <:disable:1548686459865792583>\n\n"
                    f"To enable use `{pre}antinuke enable` **"
                )
            )
            return await ctx.send(embed=embed)


        async with self.db.execute(
            "SELECT user_id FROM whitelisted_users WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchall()

        # Fetch whitelisted roles
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS whitelisted_roles (
                guild_id INTEGER, role_id INTEGER, added_by INTEGER, PRIMARY KEY (guild_id, role_id)
            )
        """)
        async with self.db.execute(
            "SELECT role_id FROM whitelisted_roles WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            role_data = await cursor.fetchall()

        if not data and not role_data:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                color=0x000000,
                description="No whitelisted users or roles found."
            )
            return await ctx.send(embed=embed)

        whitelisted_users = [self.bot.get_user(user_id[0]) for user_id in data]
        whitelisted_users_str = ", ".join(f"<@!{user.id}>" for user in whitelisted_users if user) if whitelisted_users else "*None*"

        whitelisted_roles = [ctx.guild.get_role(r[0]) for r in role_data if r[0]]
        whitelisted_roles_str = ", ".join(r.mention for r in whitelisted_roles if r) if whitelisted_roles else "*None*"

        embed = discord.Embed(
            color=0x000000,
            title=f"__Whitelisted Configuration for {ctx.guild.name}__"
        )
        embed.add_field(name=f"🛡️ Whitelisted Users ({len([u for u in whitelisted_users if u])})", value=whitelisted_users_str, inline=False)
        embed.add_field(name=f"👑 Whitelisted Roles ({len([r for r in whitelisted_roles if r])})", value=whitelisted_roles_str, inline=False)
        await ctx.send(embed=embed)


    @commands.hybrid_command(name="whitelistreset", aliases=['wlreset'], help="Resets the whitelisted users.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelistreset(self, ctx):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x000000,
                description="❌ | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        pre=ctx.prefix

        is_owner = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        if not is_owner:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=0x000000,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            antinuke = await cursor.fetchone()

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0x000000,
                description=(
                    f"**{ctx.guild.name} Security Settings <:MOD:1548704219517821089>\n"
                    "Ohh NO! looks like your server doesn't enabled security\n\n"
                    "Current Status : <:disable:1548686459865792583>\n\n"
                    f"To enable use `{pre}antinuke enable` **"
                )
            )
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT user_id FROM whitelisted_users WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchall()


        if not data:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                color=0x000000,
                description="No whitelisted users found."
            )
            return await ctx.send(embed=embed)

        await self.db.execute("DELETE FROM whitelisted_users WHERE guild_id = ?", (ctx.guild.id,))
        await self.db.commit()
        try:
            from services.whitelist_panel import WhitelistPanelService
            asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "All Staff Users Reset", ctx.guild.name, ctx.author))
        except Exception:
            pass
        embed = discord.Embed(title="<a:tick:1558726958802800660> Success",
            color=0x000000,
            description=f"Removed all whitelisted members from {ctx.guild.name}"
        )
        await ctx.send(embed=embed)

    async def handle_evy1_whitelist(self, ctx, args_str: str = ""):
        """Handles @everyone and @here channel whitelist management."""
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS wlevy1 (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            )
        ''')
        await self.db.commit()

        args = args_str.strip().split() if args_str else []
        sub = args[0].lower() if args else ""

        # Case 1: add #channel or #channel
        if sub in ["add", "set", "enable"] or (ctx.message.channel_mentions and sub not in ["remove", "rem", "delete", "del", "list", "show", "reset", "clear"]):
            target_channel = None
            if ctx.message.channel_mentions:
                target_channel = ctx.message.channel_mentions[0]
            elif len(args) > 1 and args[1].isdigit():
                target_channel = ctx.guild.get_channel(int(args[1]))
            elif len(args) == 1 and args[0].isdigit():
                target_channel = ctx.guild.get_channel(int(args[0]))
            else:
                target_channel = ctx.channel

            if not target_channel:
                return await ctx.send(embed=discord.Embed(
                    color=0xFF0000,
                    description="❌ | Please specify or mention a valid text channel! Example: `wl evy1 add #general`"
                ))

            await self.db.execute(
                "INSERT OR REPLACE INTO wlevy1 (guild_id, channel_id) VALUES (?, ?)",
                (ctx.guild.id, target_channel.id)
            )
            await self.db.commit()

            embed = discord.Embed(
                color=0x2ECC71,
                description=(
                    f"✅ **@everyone & @here Channel Whitelist Added**\n\n"
                    f"📍 **Whitelisted Channel:** {target_channel.mention}\n"
                    f"👥 All server members can now use `@everyone` and `@here` mentions in this channel without restrictions!"
                )
            )
            return await ctx.send(embed=embed)

        # Case 2: remove #channel / rem #channel
        elif sub in ["remove", "rem", "delete", "del", "disable"]:
            target_channel = None
            if ctx.message.channel_mentions:
                target_channel = ctx.message.channel_mentions[0]
            elif len(args) > 1 and args[1].isdigit():
                target_channel = ctx.guild.get_channel(int(args[1]))
            else:
                target_channel = ctx.channel

            if not target_channel:
                return await ctx.send(embed=discord.Embed(
                    color=0xFF0000,
                    description="❌ | Please specify or mention a whitelisted channel to remove!"
                ))

            await self.db.execute(
                "DELETE FROM wlevy1 WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, target_channel.id)
            )
            await self.db.commit()

            embed = discord.Embed(
                color=0x2ECC71,
                description=f"✅ **Removed {target_channel.mention} from the `@everyone` & `@here` channel whitelist.**"
            )
            return await ctx.send(embed=embed)

        # Case 3: reset / clear
        elif sub in ["reset", "clear"]:
            await self.db.execute("DELETE FROM wlevy1 WHERE guild_id = ?", (ctx.guild.id,))
            await self.db.commit()
            embed = discord.Embed(
                color=0x2ECC71,
                description="✅ **Cleared all `@everyone` & `@here` whitelisted channels for this server.**"
            )
            return await ctx.send(embed=embed)

        # Case 4: list / show or default
        else:
            async with self.db.execute("SELECT channel_id FROM wlevy1 WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

            if not rows:
                embed = discord.Embed(
                    color=0x3498DB,
                    title="📢 @everyone / @here Whitelisted Channels",
                    description=(
                        "No channels are currently whitelisted for `@everyone` / `@here` mentions.\n\n"
                        "**Commands:**\n"
                        f"• `{ctx.prefix}wl evy1 add #channel` — Whitelist a channel\n"
                        f"• `{ctx.prefix}wl evy1 remove #channel` — Remove a channel\n"
                        f"• `{ctx.prefix}wl evy1 reset` — Clear all whitelisted channels"
                    )
                )
                return await ctx.send(embed=embed)

            channel_mentions = []
            for r in rows:
                ch = ctx.guild.get_channel(r[0])
                if ch:
                    channel_mentions.append(ch.mention)
                else:
                    channel_mentions.append(f"<#{r[0]}>")

            embed = discord.Embed(
                color=0x3498DB,
                title="📢 @everyone / @here Whitelisted Channels",
                description=(
                    f"The following channels allow all members to mention `@everyone` & `@here`:\n\n"
                    + "\n".join([f"• {m}" for m in channel_mentions]) +
                    f"\n\n**Usage:**\n`{ctx.prefix}wl evy1 add #channel` | `{ctx.prefix}wl evy1 remove #channel`"
                )
            )
            return await ctx.send(embed=embed)

    @commands.command(
        name="wlevy1",
        aliases=["wleveryone", "wlev1", "wl_evy1", "wlevy"],
        help="Whitelists a channel so @everyone and @here mentions are allowed for all members."
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def wlevy1_cmd(self, ctx, *, args: str = ""):
        prefix = ctx.prefix
        is_owner = is_server_owner_or_extra_owner(ctx.guild, ctx.author)
        is_admin = ctx.author.guild_permissions.administrator if hasattr(ctx.author, "guild_permissions") else False
        if not is_owner and not is_admin:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Access Denied",
                color=0x000000,
                description="Only Server Owner, Admin or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        await self.handle_evy1_whitelist(ctx, args)
