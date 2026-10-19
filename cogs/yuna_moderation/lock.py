import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from typing import Union

class LockUnlockView(ui.View):
    def __init__(self, channel, author, ctx):
        super().__init__(timeout=120)
        self.channel = channel
        self.author = author
        self.ctx = ctx  
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if getattr(item, 'label', None) != "Delete":
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Unlock", style=discord.ButtonStyle.success)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        except discord.Forbidden:
            from utils.permission_handler import handle_missing_permission
            return await handle_missing_permission(interaction, action="Unlock channel", permission="manage_channels", channel=self.channel)

        embed = discord.Embed(
            description=f"<:YunaChannel:1297340969137471650> **Channel**: {self.channel.mention}\n<:YunaReason:1295595129809141812> **Status**: Unlocked\n<a:arrow:1557834336571494480> **Reason:** Unlock request by {self.author}",
            color=0x000000
        )
        embed.add_field(name="<:Yuna_staff:1228227884481515613> **Moderator:**", value=self.ctx.author.mention, inline=False)
        embed.set_author(name=f"Successfully Unlocked {self.channel.name}", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")

        for item in self.children:
            if getattr(item, 'label', None) != "Delete":
                item.disabled = True

        if not interaction.response.is_done():
            await interaction.response.send_message(f"{self.channel.mention} has been unlocked.", ephemeral=True)

        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:Yuna_bin:1254336650075701308>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except Exception:
            pass


class Lock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="lock",
        help="Locks a channel to prevent sending messages.",
        usage="lock [channel]",
        aliases=["lockchannel"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock_command(self, ctx, channel: Union[discord.TextChannel, discord.VoiceChannel] = None):
        channel = channel or ctx.channel 
        author_icon = ctx.author.display_avatar.url

        if channel.permissions_for(ctx.guild.default_role).send_messages is False:
            embed = discord.Embed(
                description=f"**<:YunaChannel:1297340969137471650> Channel**: {channel.mention}\n<:YunaReason:1295595129809141812> **Status**: Already Locked",
                color=self.color
            )
            embed.set_author(name=f"{channel.name} is Already Locked", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=author_icon)
            view = LockUnlockView(channel=channel, author=ctx.author, ctx=ctx)  
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            return

        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        except discord.Forbidden:
            from utils.permission_handler import handle_missing_permission
            return await handle_missing_permission(ctx, action="Lock channel", permission="manage_channels", channel=channel)
        except Exception as e:
            return await ctx.reply(f"<:Yuna_cross:1227866668152393789> An error occurred: {e}")

        embed = discord.Embed(
            description=f"<:YunaChannel:1297340969137471650> **Channel**: {channel.mention}\n<:YunaReason:1295595129809141812> **Status**: Locked\n<a:arrow:1557834336571494480> **Reason:** Lock request by {ctx.author}",
            color=self.color
        )
        embed.add_field(name="<:Yuna_staff:1228227884481515613> **Moderator:**", value=ctx.author.mention, inline=False)
        embed.set_author(name=f"Successfully Locked {channel.name}", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=author_icon)
        view = LockUnlockView(channel=channel, author=ctx.author, ctx=ctx)  
        message = await ctx.send(embed=embed, view=view)
        view.message = message
