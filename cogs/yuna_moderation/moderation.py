import discord
import re
from typing import *
from collections import Counter
from utils.Tools import *
from discord.ext import commands
from discord.ui import Button, View
from typing import Union
import aiohttp


time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}


def convert(argument):
  args = argument.lower()
  matches = re.findall(time_regex, args)
  time = 0
  for key, value in matches:
    try:
      time += time_dict[value] * float(key)
    except KeyError:
      raise commands.BadArgument(
        f"{value} is an invalid time key! h|m|s|d are valid arguments")
    except ValueError:
      raise commands.BadArgument(f"{key} is not a number!")
  return round(time)

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
        from utils.permission_handler import handle_missing_permission
        return await handle_missing_permission(ctx, action="Delete messages", permission="manage_messages", channel=ctx.channel)
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
        await ctx.send(f"<a:tick:1558726958802800660> | Successfully removed {count_deleted} messages.", delete_after=7)
    else:
        await ctx.send(to_send, delete_after=7)




class Moderation(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.color = 0x000000
    self.sniped = {}

  def convert(self, time):
    pos = ["s", "m", "h", "d"]

    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24}
    unit = time[-1]
    if unit not in pos:
      return -1
    try:
      val = int(time[:-1])
    except:
      return -2
    return val * time_dict[unit]



  @commands.command()
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  async def enlarge(self, ctx,  emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
    url = emoji.url
    await ctx.send(url)




  @commands.hybrid_command(name="unlockall",
                    help="Unlocks all channels in the Guild.",
                    usage="unlockall")
  @blacklist_check()
  @ignore_check()
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 15, commands.BucketType.channel)
  async def unlockall(self, ctx):
      if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          button = Button(label="Confirm",
                    style=discord.ButtonStyle.green,
                    emoji="<a:tick:1558726958802800660>")
          button1 = Button(label="Cancel",
                     style=discord.ButtonStyle.red,
                     emoji="<:Yuna_cross:1227866668152393789>")
          async def button_callback(interaction: discord.Interaction):
              a = 0
              if interaction.user == ctx.author:
                  if interaction.guild.me.guild_permissions.manage_roles:
                      embed1 = discord.Embed(
                     color=self.color,
                    description=f"Unlocking all channels in {ctx.guild.name} .")
                      await interaction.response.edit_message(
                       embed=embed1, view=None)
                      channels = list(interaction.guild.channels)
                      from core.discord.request_manager import request_manager, Priority
                      coro_funcs = [
                          lambda ch=c: ch.set_permissions(
                              ctx.guild.default_role,
                              overwrite=discord.PermissionOverwrite(send_messages=True, read_messages=True),
                              reason=f"Unlockall Command Executed By: {ctx.author}"
                          ) for c in channels
                      ]
                      await request_manager.enqueue_bulk(
                          priority=Priority.P1_HIGH,
                          base_task_id=f"unlockall_{ctx.guild.id}",
                          coro_funcs=coro_funcs,
                          guild_id=ctx.guild.id
                      )
                      await interaction.channel.send(
                              content=f"<a:tick:1558726958802800660> | Successfully Unlocked {len(channels)} Channels")   
                      return
                  else:
                    await interaction.response.edit_message(
                         content=
                           "<:Yuna_notify:1227866804630720565> | It seems I'm missing the necessary permissions. Please grant me the `manage roles` permissions and try again.",
                              embed=None,
                                  view=None)
              else:
                await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)

          async def button1_callback(interaction: discord.Interaction):   
              if interaction.user == ctx.author:  
                  embed2 = discord.Embed(
                     color=self.color,
                    description="Cancelled, I won't proceed with unlocking any channel.")
                  await interaction.response.edit_message(
                      embed=embed2, view=None)   
              else:
                  await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)
          embed = discord.Embed(
                  color=self.color,
                 description=f'**Do you really want to unlock all channels in {ctx.guild.name}**')
          view = View()
          button.callback = button_callback
          button1.callback = button1_callback
          view.add_item(button)
          view.add_item(button1)
          embed.set_footer(text="Please click either 'Confirm' or 'Cancel' to proceed. You have 30 seconds to decide!")
          await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=30)     


      else:
          embed5 = discord.Embed(title="<:Denied:1294218790082711553> Access Denied",
                description="Your role should be above my top role.",
                color=0x000000)
          embed5.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
          await ctx.send(embed=embed5, mention_author=False)  



  @commands.hybrid_command(name="lockall",
                    help="locks all the channels in Guild.",
                    usage="lockall")
  @blacklist_check()
  @ignore_check()
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 15, commands.BucketType.channel)
  async def lockall(self, ctx):
      if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          button = Button(label="Confirm",
                    style=discord.ButtonStyle.green,
                    emoji="<a:tick:1558726958802800660>")
          button1 = Button(label="Cancel",
                     style=discord.ButtonStyle.red,
                     emoji="<:Yuna_cross:1227866668152393789>")
          async def button_callback(interaction: discord.Interaction):
              if interaction.user == ctx.author:
                  if interaction.guild.me.guild_permissions.manage_roles:
                      embed1 = discord.Embed(
                     color=self.color,
                    description=f"Locking all channels in {ctx.guild.name}...")
                      await interaction.response.edit_message(
                       embed=embed1, view=None)
                      channels = list(interaction.guild.channels)
                      from core.discord.request_manager import request_manager, Priority
                      coro_funcs = [
                          lambda ch=c: ch.set_permissions(
                              ctx.guild.default_role,
                              overwrite=discord.PermissionOverwrite(send_messages=False, read_messages=True),
                              reason=f"Lockall command executed by: {ctx.author}"
                          ) for c in channels
                      ]
                      await request_manager.enqueue_bulk(
                          priority=Priority.P1_HIGH,
                          base_task_id=f"lockall_{ctx.guild.id}",
                          coro_funcs=coro_funcs,
                          guild_id=ctx.guild.id
                      )
                      await interaction.channel.send(
                              content=f"<a:tick:1558726958802800660> | Successfully locked {len(channels)} Channels")
                      return
                  else:
                    await interaction.response.edit_message(
                         content=
                           "<:Denied:1294218790082711553> | It seems I'm missing the necessary permissions. Please grant me the `manage roles` permissions and try again.",
                              embed=None,
                                  view=None)
              else:
                await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)

          async def button1_callback(interaction: discord.Interaction):   
              if interaction.user == ctx.author:  
                  embed2 = discord.Embed(
                     color=self.color,
                    description="Cancelled, I won't proceed with locking any channel.")
                  await interaction.response.edit_message(
                      embed=embed2, view=None)   
              else:
                  await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)
          embed = discord.Embed(
                  color=self.color,
                 description=f'**Do you really want to lock all channels in {ctx.guild.name}**')
          view = View()
          button.callback = button_callback
          button1.callback = button1_callback
          view.add_item(button)
          view.add_item(button1)
          embed.set_footer(text="Please click either 'Confirm' or 'Cancel' to proceed. You have 30 seconds to decide!")
          await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=30)     

      else:
          denied = discord.Embed(title="<:Denied:1294218790082711553> Access Denied",
              description="Your role should be above my top role.",
              color=0x000000)
          denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                     icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
          await ctx.send(embed=denied, mention_author=False)
          

  @commands.hybrid_command(name="give",
                    help="Gives the mentioned user a role.",
                    usage="give <user> <role>",
                    aliases=["addrole"])
  @blacklist_check()
  @ignore_check()
  @top_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.has_permissions(manage_roles=True)
  @commands.bot_has_permissions(manage_roles= True)
  async def give(self, ctx, member: discord.Member, *, role: discord.Role):
    if not ctx.guild.me.guild_permissions.manage_roles:
        return await ctx.send("<:Denied:1294218790082711553> I don't have permission to manage roles!")

    if role >= ctx.guild.me.top_role:
        error = discord.Embed(
            color=self.color,
            description="I can't manage roles for a user with a higher or equal role!"
        )

        error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=error)

    if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role <= member.top_role:
        error = discord.Embed(
            color=self.color,
            description="You can't manage roles for a user with a higher or equal role than yours!"
        )
        error.set_author(name="Access Denied", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=error)

    try:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Role added by {ctx.author} (ID: {ctx.author.id})")
            success = discord.Embed(
                color=self.color,
                description=f"Successfully **added** role {role.name} to {member.mention}."
            )
            success.set_author(name="Role Added", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
            success.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        else:
            await member.remove_roles(role, reason=f"Role removed by {ctx.author} (ID: {ctx.author.id})")
            success = discord.Embed(
                color=self.color,
                description=f"Successfully **removed** role {role.name} from {member.mention}."
            )
            success.set_author(name="Role Removed", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
            success.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=success)
    except discord.Forbidden:
        from utils.permission_handler import handle_missing_permission
        await handle_missing_permission(ctx, action="Assign or remove roles", permission="manage_roles")
    except Exception as e:
        error = discord.Embed(
            color=self.color,
            description=f"<:Denied:1294218790082711553> An unexpected error occurred: {str(e)}"
        )
        await ctx.send(embed=error)



  @commands.hybrid_command(name="hideall", help="Hides all the channels .",
                    usage="hideall")
  @blacklist_check()
  @ignore_check()
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 15, commands.BucketType.channel)
  async def hideall(self, ctx):
      if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          button = Button(label="Confirm",
                    style=discord.ButtonStyle.green,
                    emoji="<a:tick:1558726958802800660>")
          button1 = Button(label="Cancel",
                     style=discord.ButtonStyle.red,
                     emoji="<:Yuna_cross:1227866668152393789>")
          async def button_callback(interaction: discord.Interaction):
              a = 0
              if interaction.user == ctx.author:
                  if interaction.guild.me.guild_permissions.manage_roles:
                      embed1 = discord.Embed(
                     color=self.color,
                    description=f"Hiding all channels in {ctx.guild.name} ...")
                      await interaction.response.edit_message(
                       embed=embed1, view=None)
                      for channel in interaction.guild.channels:
                           try:
                               await channel.set_permissions(ctx.guild.default_role, view_channel=False,
                                          reason="Hideall Executed by: {}".format(ctx.author))
                               a += 1  
                               await asyncio.sleep(0.35)
                           except discord.HTTPException as e:
                               if e.status == 429:
                                   retry_after = float(e.response.headers.get('Retry-After', 2.0))
                                   await asyncio.sleep(retry_after)
                           except Exception as e:
                               print(e)
                      await interaction.channel.send(
                              content=f"<a:tick:1558726958802800660> | Successfully Hidden {a} Channel(s) .")
                      return
                  else:
                    await interaction.response.edit_message(
                         content=
                           "<:Denied:1294218790082711553> | It seems I'm missing the necessary permissions. Please grant me the `manage channels` permissions and try again.",
                              embed=None,
                                  view=None)
              else:
                await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)

          async def button1_callback(interaction: discord.Interaction):   
              if interaction.user == ctx.author:  
                  embed2 = discord.Embed(
                     color=self.color,
                    description="Cancelled, I won't proceed with hiding any channel.")
                  await interaction.response.edit_message(
                      embed=embed2, view=None)   
              else:
                  await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)
          embed = discord.Embed(
                  color=self.color,
                 description=f'**Do you really want to hide all channels in {ctx.guild.name}**')
          view = View()
          button.callback = button_callback
          button1.callback = button1_callback
          view.add_item(button)
          view.add_item(button1)
          embed.set_footer(text="Please click either 'Confirm' or 'Cancel' to proceed. You have 30 seconds to decide!")
          await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=30)

      else:
          denied = discord.Embed(title="<:Denied:1294218790082711553> Access Denied",
              description="Your role should be above my top role.",
              color=0x000000)
          denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                     icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
          await ctx.send(embed=denied, mention_author=False)

  @commands.hybrid_command(name="unhideall", help="Unhides all the channels in the server.",
                    usage="unhideall")
  @blacklist_check()
  @ignore_check()
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 15, commands.BucketType.channel)
  async def unhideall(self, ctx):
      if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          button = Button(label="Confirm",
                    style=discord.ButtonStyle.green,
                    emoji="<a:tick:1558726958802800660>")
          button1 = Button(label="Cancel",
                     style=discord.ButtonStyle.red,
                     emoji="<:Yuna_cross:1227866668152393789>")
          async def button_callback(interaction: discord.Interaction):
              a = 0
              if interaction.user == ctx.author:
                  if interaction.guild.me.guild_permissions.manage_roles:
                      embed1 = discord.Embed(
                     color=self.color,
                    description=f"Unhiding all channels in {ctx.guild.name} .")
                      await interaction.response.edit_message(
                       embed=embed1, view=None)
                      for channel in interaction.guild.channels:
                           try:
                               await channel.set_permissions(ctx.guild.default_role, view_channel=True,
                                          reason="Unhideall Command Executed By: {}".format(ctx.author))
                               a += 1  
                               await asyncio.sleep(0.35)
                           except discord.HTTPException as e:
                               if e.status == 429:
                                   retry_after = float(e.response.headers.get('Retry-After', 2.0))
                                   await asyncio.sleep(retry_after)
                           except Exception as e:
                               print(e)
                      await interaction.channel.send(
                              content=f"<a:tick:1558726958802800660> | Successfully Unhidden {a} Channel(s) .")
                      return
                  else:
                    await interaction.response.edit_message(
                         content=
                           "<:Denied:1294218790082711553> | It seems I'm missing the necessary permissions. Please grant me the `manage channels` permissions and try again.",
                              embed=None,
                                  view=None)
              else:
                await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)

          async def button1_callback(interaction: discord.Interaction):   
              if interaction.user == ctx.author:  
                  embed2 = discord.Embed(
                     color=self.color,
                    description="Cancelled, I won't proceed with unhiding any channel.")
                  await interaction.response.edit_message(
                      embed=embed2, view=None)   
              else:
                  await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)
          embed = discord.Embed(
                  color=self.color,
                 description=f'**Do you really want to unhide all channels in {ctx.guild.name}**')
          view = View()
          button.callback = button_callback
          button1.callback = button1_callback
          view.add_item(button)
          view.add_item(button1)
          embed.set_footer(text="Please click either 'Confirm' or 'Cancel' to proceed. You have 30 seconds to decide!")
          await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=30)     

      else:
          denied = discord.Embed(title="<:Denied:1294218790082711553> Access Denied",
              description="Your role should be above my top role.",
              color=0x000000)
          denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                     icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
          await ctx.send(embed=denied, mention_author=False)



  @commands.hybrid_command(
        name="prefix",
        aliases=["setprefix", "prefixset"],
        help="Allows you to change the prefix of the bot for this server"
    )
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(administrator=True)
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def _prefix(self, ctx: commands.Context, prefix: str):
      if not prefix:
          await ctx.reply(embed=discord.Embed(title="<:Yuna_cross:1227866668152393789> Error",
                description="Prefix cannot be empty. Please provide a valid prefix.",
                color=self.color
            ))
          return
          
      data = await getConfig(ctx.guild.id)
      if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
          data["prefix"] = str(prefix)
          await updateConfig(ctx.guild.id, data)
          embed1=discord.Embed(title="<a:tick:1558726958802800660> Success",
                description=f"Changed Prefix For this guild to `{prefix}`\n\nNew Prefix for **{ctx.guild.name}** is : `{prefix}`\nUse `{prefix}help` For More.",
                color=self.color
                             )
          await ctx.reply(embed=embed1)
      else:
          denied = discord.Embed(title="<:Denied:1294218790082711553> Access Denied",
              description="Your role should be above my top role.",
              color=0x000000)
          denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                     icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
          await ctx.send(embed=denied, mention_author=False)
        


  @commands.hybrid_command(name="clone", help="Clones a channel. Clones current channel if omitted.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
  @commands.has_permissions(manage_channels=True)
  async def clone(self, ctx: commands.Context, channel: Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel, discord.StageChannel, discord.ForumChannel] = None):
    channel = channel or ctx.channel

    if not ctx.guild.me.guild_permissions.manage_channels:
        error = discord.Embed(
            color=self.color,
            description="I don't have permission to manage channels!"
        )
        error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=error)

    try:
        cloned_channel = await channel.clone(reason=f"Channel cloned by {ctx.author}")
        success = discord.Embed(
            color=self.color,
            description=f"<a:tick:1558726958802800660> | {channel.mention if hasattr(channel, 'mention') else channel.name} has been successfully cloned to {cloned_channel.mention if hasattr(cloned_channel, 'mention') else cloned_channel.name}!"
        )
        success.set_author(name="Success", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
        success.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=success)
    except discord.Forbidden:
        from utils.permission_handler import handle_missing_permission
        await handle_missing_permission(ctx, action="Clone channel", permission="manage_channels", channel=channel)
    except Exception as e:
        error = discord.Embed(
            color=self.color,
            description=f"An error occurred while trying to clone the channel: {str(e)}"
        )
        error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        await ctx.send(embed=error)
        

  @commands.hybrid_command(
      name="nuke",
      help="Nukes a channel by duplicating and deleting the original.",
      usage="nuke [#channel]"
  )
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
  @commands.has_permissions(manage_channels=True)
  async def nuke(self, ctx: commands.Context, channel: Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.ForumChannel] = None):
    channel = channel or ctx.channel

    if not ctx.guild.me.guild_permissions.manage_channels:
        error = discord.Embed(
            color=self.color,
            description="<:Yuna_cross:1227866668152393789> | I don't have permission to manage channels!"
        )
        error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=error)

    if isinstance(channel, discord.CategoryChannel):
        error = discord.Embed(
            color=self.color,
            description="<:Yuna_cross:1227866668152393789> | Cannot nuke an entire category channel!"
        )
        return await ctx.send(embed=error)

    if ctx.guild.rules_channel and channel.id == ctx.guild.rules_channel.id:
        error = discord.Embed(
            color=self.color,
            description="<:Yuna_cross:1227866668152393789> | Cannot nuke the Community Rules channel!"
        )
        return await ctx.send(embed=error)

    if ctx.guild.public_updates_channel and channel.id == ctx.guild.public_updates_channel.id:
        error = discord.Embed(
            color=self.color,
            description="<:Yuna_cross:1227866668152393789> | Cannot nuke the Community Updates channel!"
        )
        return await ctx.send(embed=error)

    if not (is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position or ctx.author.id == ctx.guild.owner_id):
        denied = discord.Embed(
            title="<:Denied:1294218790082711553> Access Denied",
            description="Your role should be above my top role to nuke channels.",
            color=0x000000
        )
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                          icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=denied, mention_author=False)

    try:
        # 1. Capture position and duplicate channel before deleting
        old_position = channel.position
        new_channel = await channel.clone(reason=f"Channel nuked by {ctx.author} ({ctx.author.id})")

        # 2. Match original position
        try:
            await new_channel.edit(position=old_position)
        except Exception:
            pass

        # 3. Delete original channel
        await channel.delete(reason=f"Channel nuked by {ctx.author} ({ctx.author.id})")

        # 4. Send nuke embed in the cloned channel
        nuke_embed = discord.Embed(
            title="<a:tick:1558726958802800660> Channel Nuked",
            description=f"This channel has been successfully nuked by {ctx.author.mention}!",
            color=self.color
        )
        nuke_embed.set_image(url="https://media.tenor.com/7123956693892550567/explosion.gif")
        nuke_embed.set_footer(
            text=f"Nuked by {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        await new_channel.send(embed=nuke_embed)

        # 5. If nuked remotely from another channel, notify the invoking channel as well
        if channel.id != ctx.channel.id:
            success = discord.Embed(
                color=self.color,
                description=f"<a:tick:1558726958802800660> | Successfully nuked **{channel.name}**! New channel: {new_channel.mention}"
            )
            success.set_author(name="Success", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
            success.set_footer(text=f"Requested by {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=success)

    except discord.Forbidden:
        from utils.permission_handler import handle_missing_permission
        await handle_missing_permission(ctx, action="Create or modify channels", permission="manage_channels", channel=ctx.channel)
    except Exception as e:
        error = discord.Embed(
            color=self.color,
            description=f"<:Yuna_cross:1227866668152393789> | An error occurred while nuking the channel: {str(e)}"
        )
        error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        try:
            await ctx.send(embed=error)
        except Exception:
            pass


  @commands.hybrid_command(name="nick",
                           aliases=['setnick'],
                           help="To change someone's nickname.",
                           usage="nick [member]")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(manage_nicknames=True)
  @commands.bot_has_permissions(manage_nicknames=True)
  async def changenickname(self, ctx: commands.Context, member: discord.Member, *, name: str = None):
    
    
    if member == ctx.guild.owner or is_server_owner_or_extra_owner(ctx.guild, member):
        error = discord.Embed(
            color=self.color,
            description="I can't change the nickname of the server owner or extra owner!"
        )
        error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=error)

    
    if member.top_role >= ctx.guild.me.top_role:
        error = discord.Embed(
            color=self.color,
            description="I can't change the nickname of a user with a higher or equal role than mine!"
        )
        error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error.set_footer(text=f"Requested by {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=error)

    
    if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role <= member.top_role:
        error = discord.Embed(
            color=self.color,
            description="You can't change the nickname of a user with a higher or equal role than you!"
        )
        error.set_author(name="Access Denied", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=error)

    try:
        await member.edit(nick=name)
        if name:
            success = discord.Embed(
                color=self.color,
                description=f"Successfully changed nickname of {member.mention} to {name}."
            )
            success.set_author(name="Nickname Updated", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
            success.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        else:
            success = discord.Embed(
                color=self.color,
                description=f"Successfully cleared nickname of {member.mention}."
            )
            success.set_author(name="Nickname Cleared", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
            success.set_footer(text=f"Requested by {ctx.author}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=success)
    except discord.Forbidden:
        from utils.permission_handler import handle_missing_permission
        await handle_missing_permission(ctx, action="Change nickname", permission="manage_nicknames")
    except Exception as e:
        error = discord.Embed(
            color=self.color,
            description=f"<:Denied:1294218790082711553> | An error occurred while trying to change the nickname: {str(e)}"
        )
        await ctx.send(embed=error)
        

  @commands.hybrid_command(name="nuke", help="Nukes a channel", usage="nuke")
  @blacklist_check()
  @ignore_check()
  @top_check()
  @commands.cooldown(1, 7, commands.BucketType.user)
  @commands.has_permissions(manage_channels=True)
  async def _nuke(self, ctx: commands.Context):
    button = Button(label="Confirm",
                    style=discord.ButtonStyle.green,
                    emoji="<a:tick:1558726958802800660>")
    button1 = Button(label="Cancel",
                     style=discord.ButtonStyle.red,
                     emoji="<:Yuna_cross:1227866668152393789>")

    async def button_callback(interaction: discord.Interaction):
      if interaction.user == ctx.author:
        if interaction.guild.me.guild_permissions.manage_channels:
          channel = interaction.channel
          newchannel = await channel.clone()
          await newchannel.edit(position=channel.position)

          await channel.delete()
          embed = discord.Embed(
            description="Channel has been Successfully nuked by **`%s`**" % (ctx.author),
            color=self.color)
          embed.set_author(name="Channel Nuked", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
          embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
          await newchannel.send(embed=embed)
        else:
          await interaction.response.edit_message(
            content=
            "<:Denied:1294218790082711553> | It seems I'm missing the necessary permissions. Please grant me the `manage channel` permissions and try again.",
            embed=None,
            view=None)
      else:
        await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)

    async def button1_callback(interaction: discord.Interaction):
      if interaction.user == ctx.author:
        await interaction.response.edit_message(
          content="Cancelled, I won't proceed with nuking channel.", embed=None, view=None)
      else:
        await interaction.response.send_message("Oops! It looks like that message isn't from you. You need to run the command yourself to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)

    embed = discord.Embed(
      color=self.color, description='**Do you really want to nuke the channel?**')

    view = View()
    button.callback = button_callback
    button1.callback = button1_callback
    view.add_item(button)
    view.add_item(button1)
    embed.set_footer(text="Please click either 'Confirm' or 'Cancel' to proceed. You have 30 seconds to decide!")
    await ctx.reply(embed=embed, view=view, mention_author=False,delete_after=30)



  @commands.hybrid_command(name="slowmode",
                           help="Changes the slowmode",
                           usage="slowmode [seconds]",
                           aliases=["slow"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 2, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  async def _slowmode(self, ctx: commands.Context, seconds: int = 0):
    if seconds > 120:
      embed=discord.Embed(description="Slowmode can not be over 2 minutes",
                            color=self.color)
      embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
      embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      return await ctx.send(embed=embed)
    if seconds == 0:
      await ctx.channel.edit(slowmode_delay=seconds)
      await ctx.send(embed=discord.Embed(
        title="Slowmode", description="Slowmode is disabled", color=self.color))
    else:
      await ctx.channel.edit(slowmode_delay=seconds)
      embed=discord.Embed(description="Successfully Set slowmode to **`%s`**" % (seconds),
                            color=self.color)
      embed.set_author(name="Slowmode Activated", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
      embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      await ctx.send(embed=embed)
      

  @commands.hybrid_command(name="unslowmode",
                           help="Disables slowmode",
                           usage="unslowmode",
                           aliases=["unslow"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 2, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _unslowmode(self, ctx: commands.Context):
    await ctx.channel.edit(slowmode_delay=0)
    embed=discord.Embed(description="Successfully Disabled slowmode", color=self.color)
    embed.set_author(name="Unslowmode", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
    embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    await ctx.send(embed=embed)



  @commands.command(aliases=["deletesticker", "removesticker"], description="Delete the sticker from the server")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_emojis=True)
  @commands.bot_has_permissions(manage_emojis=True)
  async def delsticker(self, ctx: commands.Context, *, name=None):
        if ctx.message.reference is None:
            return await ctx.reply("No replied message found")
        msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if len(msg.stickers) == 0:
            return await ctx.reply("No sticker found")
        try:
            name = ""
            for i in msg.stickers:
                name = i.name
                await ctx.guild.delete_sticker(i)
            await ctx.reply(f"<:Ztick:1222750301233090600> Sucessfully deleted sticker named `{name}`")
        except:
            await ctx.reply("Failed to delete the sticker")


  @commands.command(aliases=["deleteemoji", "removeemoji"], description="Deletes the emoji from the server")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_emojis=True)
  async def delemoji(self, ctx, emoji: str = None):
    init_message = await ctx.reply("<a:loading:1554957482248380416> Processing to delete emojis...", mention_author=False)
    message_content = None

    
    if ctx.message.reference is not None:
        referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        message_content = str(referenced_message.content)
    else:
        message_content = str(ctx.message.content)

    
    if message_content:
        
        emoji_pattern = r"<a?:\w+:(\d+)>"
        found_emojis = re.findall(emoji_pattern, message_content)
        delete_count = 0

        if len(found_emojis) != 0:
            
            if len(found_emojis) > 15:
                await init_message.delete()
                return await ctx.reply("Maximum 15 emojis can be deleted at a time.")

            
            for emoji_id in found_emojis:
                try:
                    emoji_to_delete = await ctx.guild.fetch_emoji(int(emoji_id))
                    await emoji_to_delete.delete(reason=f"Deleted by {ctx.author}")
                    delete_count += 1
                except discord.NotFound:
                    continue  
                except discord.Forbidden:
                    continue  
            await init_message.delete()
            return await ctx.reply(f"<a:tick:1558726958802800660> | Successfully deleted {delete_count}/{len(found_emojis)} emoji(s).")

    
    await init_message.delete()
    return await ctx.reply("No valid emoji found to delete.")



  
  @commands.command(description="Changes the icon for the role.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(administrator=True)
  @commands.bot_has_guild_permissions(manage_roles=True)
  async def roleicon(self, ctx: commands.Context, role: discord.Role, *, icon: Union[discord.Emoji, discord.PartialEmoji, str] = None):
    
    if role.position >= ctx.guild.me.top_role.position:
        error_embed = discord.Embed(
            description=f"{role.mention} is higher than my role. Please move my role above it.",
            color=self.color
        )
        error_embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error_embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        return await ctx.send(embed=error_embed)

    
    if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and ctx.author.top_role.position <= role.position:
        error_embed = discord.Embed(
            description=f"{role.mention} has the same or a higher position than your top role!",
            color=self.color
        )
        error_embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        error_embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        return await ctx.send(embed=error_embed)

    
    if icon is None:
        attachment_found = False
        attachment_url = None
        for attachment in ctx.message.attachments:
            attachment_url = attachment.url
            attachment_found = True

        if attachment_found:
            try:
                async with aiohttp.request("GET", attachment_url) as r:
                    image_data = await r.read()
                await role.edit(display_icon=image_data)
                success_embed = discord.Embed(
                    description=f"Successfully changed the icon of {role.mention}.",
                    color=self.color
                )
                success_embed.set_author(name="Icon Updated", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
                success_embed.set_footer(
                    text=f"Requested by {ctx.author}",
                    icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
                )
                return await ctx.send(embed=success_embed)
            except Exception as e:
                print(e)
                return await ctx.reply("Failed to change the icon of the role.")
        else:
            await role.edit(display_icon=None)
            removal_embed = discord.Embed(
                description=f"Successfully removed the icon from {role.mention}.",
                color=self.color
            )
            removal_embed.set_author(name="Icon Removed", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
            removal_embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            return await ctx.reply(embed=removal_embed, mention_author=False)

    
    if isinstance(icon, discord.Emoji) or isinstance(icon, discord.PartialEmoji):
        emoji_url = f"https://cdn.discordapp.com/emojis/{icon.id}.png"
        try:
            async with aiohttp.request("GET", emoji_url) as r:
                image_data = await r.read()
            await role.edit(display_icon=image_data)
            success_embed = discord.Embed(
                description=f"Successfully changed the icon for {role.mention} to {icon}.",
                color=self.color
            )
            success_embed.set_author(name="Icon Updated", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
            success_embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            return await ctx.reply(embed=success_embed, mention_author=False)
        except Exception as e:
            print(e)
            return await ctx.reply("Failed to change the icon of the role.")

    
    else:
        if not icon.startswith("https://"):
            return await ctx.reply("Please provide a valid link.")
        try:
            async with aiohttp.request("GET", icon) as r:
                image_data = await r.read()
            await role.edit(display_icon=image_data)
            success_embed = discord.Embed(
                description=f"<a:tick:1558726958802800660> | Successfully changed the icon for {role.mention}.",
                color=self.color
            )
            return await ctx.reply(embed=success_embed, mention_author=False)
        except Exception as e:
            print(e)
            return await ctx.reply("An error occurred while changing the icon for the role.")
  
  
      
  @commands.hybrid_command(name="unbanall",
                           help="Unbans Everyone In The Guild!",
                           aliases=['massunban'],
                           usage="Unbanall",
                           with_app_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 30, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(ban_members=True)
  async def unbanall(self, ctx):
    button = Button(label="Confirm",
                    style=discord.ButtonStyle.green,
                    emoji="<a:tick:1558726958802800660>")
    button1 = Button(label="Cancel",
                     style=discord.ButtonStyle.red,
                     emoji="<:Yuna_cross:1227866668152393789>")

    async def button_callback(interaction: discord.Interaction):
      a = 0
      unbanned_list = []
      if interaction.user == ctx.author:
        if interaction.guild.me.guild_permissions.ban_members:
          await interaction.response.edit_message(
            content="Unbanning All Banned Members...", embed=None, view=None)
          async for idk in interaction.guild.bans(limit=None):
            try:
              await interaction.guild.unban(
                user=idk.user,
                reason="Unbanall Command Executed By: {}".format(ctx.author))
              a += 1
              unbanned_list.append(f"• {idk.user.name} (`{idk.user.id}`)")
              await asyncio.sleep(0.35)
            except discord.HTTPException as e:
              if e.status == 429:
                retry_after = float(e.response.headers.get('Retry-After', 2.0))
                await asyncio.sleep(retry_after)
            except Exception:
              pass

          embed = discord.Embed(
            title="Unban All Completed",
            description=f"<a:tick:1558726958802800660> Successfully unbanned **{a}** member(s).",
            color=self.color
          )
          if unbanned_list:
            accounts_str = "\n".join(unbanned_list[:40])
            if len(unbanned_list) > 40:
              accounts_str += f"\n*...and {len(unbanned_list) - 40} more accounts.*"
            embed.add_field(name="📜 Unbanned Accounts", value=accounts_str, inline=False)
          embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url if ctx.author and ctx.author.display_avatar else None)

          try:
            await interaction.edit_original_response(content=None, embed=embed)
          except Exception:
            await interaction.channel.send(embed=embed)
        else:
          await interaction.response.edit_message(
            content=
            "I am missing `ban members` in this Guil.",
            embed=None,
            view=None)
      else:
        await interaction.response.send_message("Uh oh! That message doesn't belong to you.\nYou must run this command to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)

    async def button1_callback(interaction: discord.Interaction):
      if interaction.user == ctx.author:
        await interaction.response.edit_message(
          content="Cancelled, I will Not unban anyone.", embed=None, view=None)
      else:
        await interaction.response.send_message("Uh oh! That message doesn't belong to you.\nYou must run this command to interact with it.",
                                                embed=None,
                                                view=None,
                                                ephemeral=True)

    embed = discord.Embed(
      color=self.color,
      description='**Are you sure you want to unban all members in this guild?**')

    view = View()
    button.callback = button_callback
    button1.callback = button1_callback
    view.add_item(button)
    view.add_item(button1)
    await ctx.reply(embed=embed, view=view, mention_author=False)
  
  @commands.hybrid_command(name="audit",
                           help="See recents audit log action in the server .")
  @blacklist_check()
  @ignore_check()
  @commands.has_permissions(view_audit_log=True)
  @commands.bot_has_permissions(view_audit_log=True)
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  async def auditlog(self, ctx, limit: int):
    if limit >= 31:
      await ctx.reply(
        "Action rejected, you are not allowed to fetch more than `30` entries.",
        mention_author=False)
      return
    idk = []
    str = ""
    async for entry in ctx.guild.audit_logs(limit=limit):
      idk.append(f'''User: `{entry.user}`
Action: `{entry.action}`
Target: `{entry.target}`
Reason: `{entry.reason}`\n\n''')
    for n in idk:
      str += n
    str = str.replace("AuditLogAction.", "")
    embed = discord.Embed(title=f"Audit Logs Of {ctx.guild.name}",
                          description=f">>> {str}",
                          color=0x000000)
    embed.set_footer(text=f"Audit Log Actions For {ctx.guild.name}")
    await ctx.reply(embed=embed, mention_author=False)
      
