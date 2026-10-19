import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
from typing import Optional, Union
from utils.Tools import ignore_check, blacklist_check
from core.cache.security_cache import security_cache
from services.whitelist_panel import WhitelistPanelService

DB_PATH = 'db/anti.db'

class AddBotModal(discord.ui.Modal, title="Whitelist Trusted Bot"):
    bot_input = discord.ui.TextInput(
        label="Bot ID or Bot Mention",
        placeholder="e.g. 123456789012345678 or @MyBot",
        min_length=15,
        max_length=40,
        required=True
    )

    def __init__(self, cog, guild_id: int, author: discord.Member):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER
        is_owner = interaction.user.id in {self.author.id, interaction.guild.owner_id, PRIMARY_BOT_OWNER} or interaction.user.id in GLOBAL_OWNER_IDS
        if not is_owner:
            return await interaction.response.send_message("You are not authorized to use this control panel.", ephemeral=True)

        raw_val = self.bot_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            target_id = int(raw_val)
        except ValueError:
            return await interaction.response.send_message("Invalid Bot ID provided. Please enter a numerical Discord ID.", ephemeral=True)

        # Check if bot exists
        try:
            bot_user = await self.cog.bot.fetch_user(target_id)
        except Exception:
            return await interaction.response.send_message("Could not find a Discord user or bot with that ID.", ephemeral=True)

        if not bot_user.bot:
            return await interaction.response.send_message(f"**{bot_user.name}** is a human user account! Use $whitelist for human staff.", ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO whitelisted_bots (guild_id, bot_id, added_by)
                VALUES (?, ?, ?)
            """, (self.guild_id, bot_user.id, self.author.id))
            await db.commit()
        security_cache.invalidate_guild(self.guild_id)
        if interaction.guild:
            asyncio.create_task(WhitelistPanelService.on_whitelist_update(interaction.guild, "Security Bot Whitelisted", bot_user, interaction.user))

        embed = discord.Embed(
            title="Bot Whitelisted Successfully",
            description=(
                f"**Bot:** {bot_user.mention} (`{bot_user.name}#{bot_user.discriminator}`)\n"
                f"**Bot ID:** `{bot_user.id}`\n"
                f"**Security Status:** **Trusted** (Permitted to join server with admin access)"
            ),
            color=0xD4AF37
        )
        embed.set_thumbnail(url=bot_user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

class RemoveBotSelect(discord.ui.Select):
    def __init__(self, cog, guild_id: int, bot_list: list):
        self.cog = cog
        self.guild_id = guild_id
        options = []
        for b_id, b_name in bot_list[:25]:
            options.append(discord.SelectOption(
                label=b_name[:100],
                value=str(b_id),
                description=f"ID: {b_id}"
            ))
        super().__init__(placeholder="Select a whitelisted bot to remove...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        bot_id = int(self.values[0])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelisted_bots WHERE guild_id = ? AND bot_id = ?", (self.guild_id, bot_id))
            await db.commit()
        security_cache.invalidate_guild(self.guild_id)
        if interaction.guild:
            asyncio.create_task(WhitelistPanelService.on_whitelist_update(interaction.guild, "Security Bot Removed", f"<@{bot_id}>", interaction.user))

        embed = discord.Embed(
            title="Whitelisted Bot Removed",
            description=f"Bot `<@{bot_id}>` (`{bot_id}`) has been **removed** from the trusted whitelist!\nAnti-Bot Add will now instantly kick this bot if added by non-owners.",
            color=0xFF0044
        )
        await interaction.response.send_message(embed=embed)

class RemoveBotView(discord.ui.View):
    def __init__(self, cog, guild_id: int, bot_list: list):
        super().__init__(timeout=60)
        self.add_item(RemoveBotSelect(cog, guild_id, bot_list))

class AddRoleModal(discord.ui.Modal, title="Whitelist Trusted Role"):
    role_input = discord.ui.TextInput(
        label="Role ID, Role Mention, or Role Name",
        placeholder="e.g. 123456789012345678, @Admin, or Admin",
        min_length=2,
        max_length=50,
        required=True
    )

    def __init__(self, cog, guild_id: int, author: discord.Member):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER
        is_owner = interaction.user.id in {self.author.id, interaction.guild.owner_id, PRIMARY_BOT_OWNER} or interaction.user.id in GLOBAL_OWNER_IDS
        if not is_owner:
            return await interaction.response.send_message("You are not authorized to use this control panel.", ephemeral=True)

        clean_val = self.role_input.value.strip().replace("<@&", "").replace(">", "").replace("!", "").replace("@", "").strip()
        target_role = None
        guild = interaction.guild

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
            return await interaction.response.send_message(f"Could not find role **`{self.role_input.value}`** in this server.", ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER,
                    role_id INTEGER,
                    added_by INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            try:
                await db.execute("ALTER TABLE whitelisted_roles ADD COLUMN added_by INTEGER;")
            except Exception:
                pass
            await db.execute("""
                INSERT OR REPLACE INTO whitelisted_roles (guild_id, role_id, added_by)
                VALUES (?, ?, ?)
            """, (self.guild_id, target_role.id, self.author.id))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.add_whitelisted_role(self.guild_id, target_role.id)
        if interaction.guild:
            asyncio.create_task(WhitelistPanelService.on_whitelist_update(interaction.guild, "Staff Role Whitelisted", target_role, interaction.user))

        embed = discord.Embed(
            title="Role Whitelisted Successfully",
            description=(
                f"**Role:** {target_role.mention} (`{target_role.name}`)\n"
                f"**Role ID:** `{target_role.id}`\n"
                f"**Status:** All members with this role now have **Full Whitelist Immunity**!"
            ),
            color=0xD4AF37
        )
        await interaction.response.send_message(embed=embed)

class RemoveRoleSelect(discord.ui.Select):
    def __init__(self, cog, guild_id: int, role_list: list):
        self.cog = cog
        self.guild_id = guild_id
        options = []
        for r_id, r_name in role_list[:25]:
            options.append(discord.SelectOption(
                label=r_name[:100],
                value=str(r_id),
                description=f"ID: {r_id}"
            ))
        super().__init__(placeholder="Select a whitelisted role to remove...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?", (self.guild_id, role_id))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.remove_whitelisted_role(self.guild_id, role_id)
        if interaction.guild:
            asyncio.create_task(WhitelistPanelService.on_whitelist_update(interaction.guild, "Staff Role Removed", f"<@&{role_id}>", interaction.user))

        embed = discord.Embed(
            title="Whitelisted Role Removed",
            description=f"Role `<@&{role_id}>` (`{role_id}`) has been **removed** from the trusted role whitelist!",
            color=0xFF0044
        )
        await interaction.response.send_message(embed=embed)

class RemoveRoleView(discord.ui.View):
    def __init__(self, cog, guild_id: int, role_list: list):
        super().__init__(timeout=60)
        self.add_item(RemoveRoleSelect(cog, guild_id, role_list))

class BotWhitelistView(discord.ui.View):
    def __init__(self, cog, ctx: commands.Context):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER
        is_owner = interaction.user.id in {self.ctx.author.id, self.ctx.guild.owner_id, PRIMARY_BOT_OWNER} or interaction.user.id in GLOBAL_OWNER_IDS
        if not is_owner:
            await interaction.response.send_message("This panel was requested by another administrator.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Whitelist Bot", style=discord.ButtonStyle.success, row=0)
    async def add_bot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddBotModal(self.cog, self.ctx.guild.id, self.ctx.author))

    @discord.ui.button(label="Whitelist Role", style=discord.ButtonStyle.success, row=0)
    async def add_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddRoleModal(self.cog, self.ctx.guild.id, self.ctx.author))

    @discord.ui.button(label="Remove Bot", style=discord.ButtonStyle.danger, row=1)
    async def remove_bot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT bot_id FROM whitelisted_bots WHERE guild_id = ?", (self.ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message("There are no whitelisted bots in this server yet!", ephemeral=True)

        bot_list = []
        for (b_id,) in rows:
            user = self.cog.bot.get_user(b_id)
            name = f"{user.name}" if user else f"Bot {b_id}"
            bot_list.append((b_id, name))

        view = RemoveBotView(self.cog, self.ctx.guild.id, bot_list)
        await interaction.response.send_message("Select the bot you want to unwhitelist:", view=view, ephemeral=True)

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.danger, row=1)
    async def remove_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER, role_id INTEGER, added_by INTEGER, PRIMARY KEY (guild_id, role_id)
                )
            """)
            async with db.execute("SELECT role_id FROM whitelisted_roles WHERE guild_id = ?", (self.ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message("There are no whitelisted roles in this server yet!", ephemeral=True)

        role_list = []
        for (r_id,) in rows:
            role = self.ctx.guild.get_role(r_id)
            name = f"@{role.name}" if role else f"Role {r_id}"
            role_list.append((r_id, name))

        view = RemoveRoleView(self.cog, self.ctx.guild.id, role_list)
        await interaction.response.send_message("Select the role you want to unwhitelist:", view=view, ephemeral=True)

    @discord.ui.button(label="View Whitelist", style=discord.ButtonStyle.primary, row=1)
    async def list_bots_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog.get_whitelist_embed(self.ctx.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Reset All", style=discord.ButtonStyle.secondary, row=1)
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelisted_bots WHERE guild_id = ?", (self.ctx.guild.id,))
            await db.execute("DELETE FROM whitelisted_roles WHERE guild_id = ?", (self.ctx.guild.id,))
            await db.commit()

        embed = discord.Embed(
            title="Whitelist Reset",
            description="All whitelisted bots and roles have been cleared!",
            color=0xFEE75C
        )
        await interaction.response.send_message(embed=embed)

class BotWhitelist(commands.Cog, name="BotWhitelist"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.color = 0x2B2D31

    async def get_whitelist_embed(self, guild: discord.Guild) -> discord.Embed:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER, role_id INTEGER, added_by INTEGER, PRIMARY KEY (guild_id, role_id)
                )
            """)
            async with db.execute("""
                SELECT bot_id, added_by, added_at 
                FROM whitelisted_bots 
                WHERE guild_id = ?
            """, (guild.id,)) as cursor:
                bot_rows = await cursor.fetchall()

            async with db.execute("""
                SELECT role_id, added_by 
                FROM whitelisted_roles 
                WHERE guild_id = ?
            """, (guild.id,)) as cursor:
                role_rows = await cursor.fetchall()

        embed = discord.Embed(
            title=f"Trusted Whitelist • {guild.name}",
            color=self.color
        )
        
        bot_lines = []
        for idx, (bot_id, added_by, added_at) in enumerate(bot_rows, 1):
            bot_user = self.bot.get_user(bot_id)
            bot_tag = f"**{bot_user.name}**" if bot_user else f"`{bot_id}`"
            bot_lines.append(f"`#{idx}` <@{bot_id}> ({bot_tag}) — Added by <@{added_by}>")

        role_lines = []
        for idx, (role_id, added_by) in enumerate(role_rows, 1):
            role_obj = guild.get_role(role_id)
            role_tag = f"**{role_obj.name}**" if role_obj else f"`{role_id}`"
            role_lines.append(f"`#{idx}` <@&{role_id}> ({role_tag}) — Added by <@{added_by}>")

        desc_parts = []
        if bot_lines:
            desc_parts.append("**Whitelisted Bots:**\n" + "\n".join(bot_lines))
        else:
            desc_parts.append("**Whitelisted Bots:** *None*")

        if role_lines:
            desc_parts.append("**Whitelisted Roles:**\n" + "\n".join(role_lines))
        else:
            desc_parts.append("**Whitelisted Roles:** *None*")

        embed.description = "\n\n".join(desc_parts)
        embed.set_footer(text=f"Total: {len(bot_rows)} Bots, {len(role_rows)} Roles • Yuna Security")
        return embed

    @commands.hybrid_group(
        name="whitelistbot",
        aliases=["botwhitelist", "trustedbot"],
        invoke_without_command=True,
        help="Manage whitelisted bots and roles with interactive buttons."
    )
    @commands.has_permissions(administrator=True)
    @ignore_check()
    @blacklist_check()
    async def whitelistbot(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Yuna ~ Whitelisted Bot & Role Security Panel",
            color=self.color,
            description=(
                "Protect your server from rogue bot raids and unauthorized role actions!\n\n"
                "**Interactive Control Panel:**\n"
                "• Click **`Whitelist Bot`** to add a trusted bot\n"
                "• Click **`Whitelist Role`** to add a trusted role\n"
                "• Click **`Remove Bot`** / **`Remove Role`** to revoke trust\n"
                "• Click **`View Whitelist`** to list all trusted bots & roles\n"
                "• Click **`Reset All`** to clear whitelists\n\n"
                "**Command Syntax:**\n"
                "• `whitelistbot add <@bot / ID>`\n"
                "• `whitelistrole add <@role / ID / name>`\n"
                "• `whitelistbot list` / `whitelistrole list`"
            )
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Yuna Anti-Bot & Role Whitelist Security System")
        view = BotWhitelistView(self, ctx)
        await ctx.send(embed=embed, view=view)

    @whitelistbot.command(name="add", help="Add a bot to the trusted whitelist.")
    @commands.has_permissions(administrator=True)
    async def wb_add(self, ctx: commands.Context, bot: Union[discord.User, discord.Member]):
        bot_user = bot
        if not bot_user.bot:
            return await ctx.send(f"**{bot_user.name}** is a human user account! Use `$whitelist` for human staff.")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO whitelisted_bots (guild_id, bot_id, added_by)
                VALUES (?, ?, ?)
            """, (ctx.guild.id, bot_user.id, ctx.author.id))
            await db.commit()
        security_cache.add_whitelisted_bot(ctx.guild.id, bot_user.id)
        asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Security Bot Whitelisted", bot_user, ctx.author))

        embed = discord.Embed(
            title="Bot Whitelisted Successfully",
            description=(
                f"**Bot:** {bot_user.mention} (`{bot_user.name}`)\n"
                f"**Bot ID:** `{bot_user.id}`\n"
                f"**Security Status:** **Trusted**"
            ),
            color=0xD4AF37
        )
        embed.set_thumbnail(url=bot_user.display_avatar.url)
        await ctx.send(embed=embed)

    @whitelistbot.command(name="remove", aliases=["del", "unwhitelist"], help="Remove a bot from the trusted whitelist.")
    @commands.has_permissions(administrator=True)
    async def wb_remove(self, ctx: commands.Context, bot: Union[discord.User, discord.Member]):
        bot_id = bot.id
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelisted_bots WHERE guild_id = ? AND bot_id = ?", (ctx.guild.id, bot_id))
            await db.commit()
        security_cache.remove_whitelisted_bot(ctx.guild.id, bot_id)
        asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Security Bot Removed", bot, ctx.author))

        embed = discord.Embed(
            title="Whitelisted Bot Removed",
            description=f"Bot `<@{bot_id}>` (`{bot_id}`) has been **removed** from the trusted whitelist!",
            color=0xFF0044
        )
        await ctx.send(embed=embed)

    @whitelistbot.command(name="list", aliases=["show"], help="View all whitelisted bots and roles in the server.")
    @commands.has_permissions(administrator=True)
    async def wb_list(self, ctx: commands.Context):
        embed = await self.get_whitelist_embed(ctx.guild)
        await ctx.send(embed=embed)

    @whitelistbot.command(name="reset", help="Clear all whitelisted bots from the server.")
    @commands.has_permissions(administrator=True)
    async def wb_reset(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelisted_bots WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        security_cache.invalidate_guild(ctx.guild.id)
        asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Security Bots Reset", "All Bots", ctx.author))

        embed = discord.Embed(
            title="Bot Whitelist Reset",
            description="All whitelisted bots have been cleared!",
            color=0xFEE75C
        )
        await ctx.send(embed=embed)

    # ----------------------------------------------------
    # WHITELIST ROLE COMMAND GROUP
    # ----------------------------------------------------
    @commands.hybrid_group(
        name="whitelistrole",
        aliases=["rolewhitelist", "wr", "trustedrole", "wlrole"],
        invoke_without_command=True,
        help="Manage whitelisted roles with interactive buttons."
    )
    @commands.has_permissions(administrator=True)
    @ignore_check()
    @blacklist_check()
    async def whitelistrole(self, ctx: commands.Context):
        embed = await self.get_whitelist_embed(ctx.guild)
        view = BotWhitelistView(self, ctx)
        await ctx.send(embed=embed, view=view)

    @whitelistrole.command(name="add", help="Add a role to the trusted whitelist.")
    @commands.has_permissions(administrator=True)
    async def wr_add(self, ctx: commands.Context, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER, role_id INTEGER, added_by INTEGER, PRIMARY KEY (guild_id, role_id)
                )
            """)
            try:
                await db.execute("ALTER TABLE whitelisted_roles ADD COLUMN added_by INTEGER;")
            except Exception:
                pass
            await db.execute("""
                INSERT OR REPLACE INTO whitelisted_roles (guild_id, role_id, added_by)
                VALUES (?, ?, ?)
            """, (ctx.guild.id, role.id, ctx.author.id))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.add_whitelisted_role(ctx.guild.id, role.id)
        asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Staff Role Whitelisted", role, ctx.author))

        embed = discord.Embed(
            title="Role Whitelisted Successfully",
            description=f"**Role:** {role.mention} (`{role.name}`)\n**Role ID:** `{role.id}`\n**Status:** All members with this role now have **Full Whitelist Immunity**!",
            color=0xD4AF37
        )
        await ctx.send(embed=embed)

    @whitelistrole.command(name="remove", aliases=["del", "unwhitelist"], help="Remove a role from the trusted whitelist.")
    @commands.has_permissions(administrator=True)
    async def wr_remove(self, ctx: commands.Context, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.remove_whitelisted_role(ctx.guild.id, role.id)
        asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Staff Role Removed", role, ctx.author))

        embed = discord.Embed(
            title="Whitelisted Role Removed",
            description=f"Role `{role.name}` (`{role.id}`) has been **removed** from the trusted role whitelist!",
            color=0xFF0044
        )
        await ctx.send(embed=embed)

    @whitelistrole.command(name="list", aliases=["show"], help="View all whitelisted roles in the server.")
    @commands.has_permissions(administrator=True)
    async def wr_list(self, ctx: commands.Context):
        embed = await self.get_whitelist_embed(ctx.guild)
        await ctx.send(embed=embed)

    @whitelistrole.command(name="reset", help="Clear all whitelisted roles from the server.")
    @commands.has_permissions(administrator=True)
    async def wr_reset(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelisted_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        from core.cache.security_cache import security_cache
        security_cache.reset_whitelisted_roles(ctx.guild.id)
        asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Staff Roles Reset", "All Roles", ctx.author))

        embed = discord.Embed(
            title="Role Whitelist Reset",
            description="All whitelisted roles have been cleared!",
            color=0xFEE75C
        )
        await ctx.send(embed=embed)

    # Subcommand alias under whitelistbot
    @whitelistbot.command(name="role", help="Manage whitelisted roles.")
    @commands.has_permissions(administrator=True)
    async def wb_role_alias(self, ctx: commands.Context, action: str = None, role: discord.Role = None):
        if not action:
            return await self.whitelistrole(ctx)
        action_low = action.lower()
        if action_low == "add" and role:
            return await self.wr_add(ctx, role)
        elif action_low in ["remove", "del", "unwhitelist"] and role:
            return await self.wr_remove(ctx, role)
        elif action_low in ["list", "show"]:
            return await self.wr_list(ctx)
        elif action_low == "reset":
            return await self.wr_reset(ctx)
        else:
            return await self.whitelistrole(ctx)

async def setup(bot):
    await bot.add_cog(BotWhitelist(bot))
