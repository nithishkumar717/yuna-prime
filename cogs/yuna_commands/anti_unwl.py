import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *


import asyncio
class Unwhitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        asyncio.create_task(self.initialize_db())

    #@commands.Cog.listener()
    async def initialize_db(self):
        self.db = await aiosqlite.connect('db/anti.db')

    @commands.hybrid_command(name='unwhitelist', aliases=['unwl'], help="Unwhitelist a user from antinuke")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def unwhitelist(self, ctx, *, member_or_role: str = None):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x000000,
                description="❌ | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

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
                    "To enable use `antinuke enable` **"
                )
            )
            return await ctx.send(embed=embed)

        if not member_or_role:
            embed = discord.Embed(
                color=0x000000,
                title="__**Unwhitelist Commands**__",
                description="**Removes user or role from whitelist which means that the antinuke module will now take actions on them if they trigger it.**"
            )
            embed.add_field(name="__**Usage**__", value="<:red_dot:1222796144996777995> `unwhitelist @user / @role`\n<:red_dot:1222796144996777995> `unwl @user`")
            return await ctx.send(embed=embed)

        clean_input = member_or_role.strip()
        if clean_input.lower().startswith("role "):
            clean_input = clean_input[5:].strip()

        # Try converting as Role first
        target_role = None
        try:
            target_role = await commands.RoleConverter().convert(ctx, clean_input)
        except Exception:
            target_role = None

        if target_role:
            await self.db.execute("DELETE FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, target_role.id))
            await self.db.commit()
            security_cache.remove_whitelisted_role(ctx.guild.id, target_role.id)

            try:
                from services.whitelist_panel import WhitelistPanelService
                asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Staff Role Removed", target_role, ctx.author))
            except Exception:
                pass

            embed = discord.Embed(
                title="<a:tick:1558726958802800660> Role Unwhitelisted",
                color=0x000000,
                description=f"Role `{target_role.name}` (`{target_role.id}`) has been **removed** from the whitelist."
            )
            return await ctx.send(embed=embed)

        # Otherwise try converting as Member
        try:
            member = await commands.MemberConverter().convert(ctx, clean_input)
        except Exception:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                color=0x000000,
                description=f"Member or Role `{member_or_role}` not found."
            )
        if is_server_owner_or_extra_owner(ctx.guild, member) or member.id == self.bot.user.id:
            embed = discord.Embed(
                title="<:Yuna_cross:1227866668152393789> Protected Account",
                color=0x000000,
                description="The Server Owner, Bot Owners, and Extra Owners are permanently whitelisted and immune. They cannot be unwhitelisted."
            )
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT * FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id)
        ) as cursor:
            data = await cursor.fetchone()

        if not data:
            embed = discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                color=0x000000,
                description=f"<@{member.id}> is not a whitelisted member."
            )
            return await ctx.send(embed=embed)

        await self.db.execute(
            "DELETE FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id)
        )
        await self.db.commit()
        from core.cache.security_cache import security_cache
        security_cache.remove_whitelist_user(ctx.guild.id, member.id)
        from utils.settings_manager import sync_all_settings
        sync_all_settings()

        try:
            from services.whitelist_panel import WhitelistPanelService
            asyncio.create_task(WhitelistPanelService.on_whitelist_update(ctx.guild, "Staff User Removed", member, ctx.author))
        except Exception:
            pass

        embed = discord.Embed(title="<a:tick:1558726958802800660> Success",
            color=0x000000,
            description=f"User <@!{member.id}> has been removed from the whitelist."
        )
        await ctx.send(embed=embed)
