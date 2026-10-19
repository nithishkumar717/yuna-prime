import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *

class BanView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.message = None  
        self.color = discord.Color.from_rgb(0, 0, 0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:Yuna_bin:1254336650075701308>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class AlreadyUnbannedView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=60)
        self.user = user
        self.author = author
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    @ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:Yuna_bin:1254336650075701308>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class ReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Ban Reason")
        self.user = user
        self.author = author
        self.view = view
        self.reason_input = ui.TextInput(label="Reason for Banning", placeholder="Provide a reason for banning or leave it blank for no reason.", required = False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        try:
            await self.user.send(f"<a:Yuna_WarnFlash:1272569018183843874> You have been Banned from **{self.author.guild.name}** by **{self.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        embed = discord.Embed(description=f"**<:YunaUser:1294654665895579721> Target User:** [{self.user}](https://discord.com/users/{self.user.id})\n<:YunaMention:1294654604998475856> **User Mention:** {self.user.mention}\n**<:YunaDM:1295595078122999915> DM Sent:** {dm_status}\n**<:YunaReason:1295595129809141812> Reason:** {reason}", color=0x000000)
        embed.set_author(name=f"Successfully Banned {self.user.name}", icon_url=self.user.avatar.url if self.user.avatar else self.user.default_avatar.url)
        embed.add_field(name="<:YunaMod:1295601558985379852> Moderator:", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"Requested by {self.author}", icon_url=self.author.avatar.url if self.author.avatar else self.author.default_avatar.url)
        embed.timestamp = discord.utils.utcnow()

        try:
            await interaction.guild.ban(self.user, reason=f"Ban requested by {self.author}")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        try:
            await interaction.response.edit_message(embed=embed, view=self.view)
            for item in self.view.children:
                item.disabled = True
            await interaction.message.edit(view=self.view)
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass
            

class Unban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.hybrid_group(
        name="unban",
        help="Unbans a user from the Server or unban all banned members.",
        usage="unban <member|all>",
        aliases=["forgive", "pardon"],
        invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User = None, *, reason=None):
        if ctx.invoked_subcommand is None:
            if user is None:
                return await ctx.send_help(ctx.command)

            bans = [entry async for entry in ctx.guild.bans()]
            if not any(ban_entry.user.id == user.id for ban_entry in bans):
                embed = discord.Embed(description="**Requested User is not banned in this server.**", color=self.color)
                embed.add_field(name="__Ban__:", value="Click on the `Ban` button to ban the mentioned user.")
                embed.set_author(name=f"{user.name} is Not Banned!", icon_url=self.get_user_avatar(user))
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
                view = AlreadyUnbannedView(user=user, author=ctx.author)
                message = await ctx.send(embed=embed, view=view)
                view.message = message 
                return

            try:
                await user.send(f"<:Ztick:1222750301233090600> You have been unbanned from **{ctx.guild.name}** by **{ctx.author}**. Reason: {reason or 'No reason provided'}")
                dm_status = "Yes"
            except discord.Forbidden:
                dm_status = "No"
            except discord.HTTPException:
                dm_status = "No"

            await ctx.guild.unban(user, reason=f"Unban requested by {ctx.author} for reason: {reason or 'No reason provided'}")

            reasonn = reason or "No reason provided"
            embed = discord.Embed(description=f"**<:YunaUser:1294654665895579721> Target User:** [{user}](https://discord.com/users/{user.id})\n**<:YunaMention:1294654604998475856> User Mention:** {user.mention}\n**<:YunaDM:1295595078122999915> DM Sent:** {dm_status}\n**<:YunaReason:1295595129809141812> Reason:** {reasonn}", color=self.color)
            embed.set_author(name=f"Successfully Unbanned {user.name}", icon_url=self.get_user_avatar(user))
            embed.add_field(name="<:YunaMod:1295601558985379852> Moderator:", value=ctx.author.mention, inline=False)
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            embed.timestamp = discord.utils.utcnow()

            view = BanView(user=user, author=ctx.author)
            message = await ctx.send(embed=embed, view=view)
            view.message = message

    @unban.command(
        name="all",
        help="Unbans all banned members in the guild",
        aliases=["everyone"],
        with_app_command=True
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban_all(self, ctx):
        bans = [entry async for entry in ctx.guild.bans()]
        if not bans:
            return await ctx.reply("<:Yuna_cross:1227866668152393789> | There are no banned members in this server.", mention_author=False)

        button = ui.Button(label="Confirm", style=discord.ButtonStyle.green, emoji="<a:tick:1558726958802800660>")
        button1 = ui.Button(label="Cancel", style=discord.ButtonStyle.red, emoji="<:Yuna_cross:1227866668152393789>")

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.ban_members:
                    await interaction.response.edit_message(
                        content="Unbanning all banned members...", embed=None, view=None)
                    unbanned_count = 0
                    unbanned_list = []
                    async for entry in interaction.guild.bans(limit=None):
                        try:
                            await interaction.guild.unban(
                                user=entry.user,
                                reason=f"Unban All command executed by: {ctx.author}"
                            )
                            unbanned_count += 1
                            unbanned_list.append(f"• {entry.user.name} (`{entry.user.id}`)")
                            await asyncio.sleep(0.35)
                        except discord.HTTPException as e:
                            if e.status == 429:
                                retry_after = float(e.response.headers.get('Retry-After', 2.0))
                                await asyncio.sleep(retry_after)
                        except Exception:
                            pass

                    embed = discord.Embed(
                        title="Unban All Completed",
                        description=f"<a:tick:1558726958802800660> Successfully unbanned **{unbanned_count}** member(s).",
                        color=self.color
                    )
                    if unbanned_list:
                        accounts_str = "\n".join(unbanned_list[:40])
                        if len(unbanned_list) > 40:
                            accounts_str += f"\n*...and {len(unbanned_list) - 40} more accounts.*"
                        embed.add_field(name="📜 Unbanned Accounts", value=accounts_str, inline=False)
                    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))

                    try:
                        await interaction.edit_original_response(content=None, embed=embed)
                    except Exception:
                        await interaction.channel.send(embed=embed)
                else:
                    await interaction.response.edit_message(
                        content="<:Yuna_cross:1227866668152393789> I am missing `Ban Members` permission in this guild.",
                        embed=None,
                        view=None
                    )
            else:
                await interaction.response.send_message(
                    "You are not allowed to interact with this button!",
                    ephemeral=True
                )

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(
                    content="Cancelled unbanning members.", embed=None, view=None)
            else:
                await interaction.response.send_message(
                    "You are not allowed to interact with this button!",
                    ephemeral=True
                )

        button.callback = button_callback
        button1.callback = button1_callback

        view = ui.View(timeout=60)
        view.add_item(button)
        view.add_item(button1)

        embed = discord.Embed(
            color=self.color,
            description=f"**Are you sure you want to unban all `{len(bans)}` banned members in this server?**"
        )
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))

        await ctx.send(embed=embed, view=view)
