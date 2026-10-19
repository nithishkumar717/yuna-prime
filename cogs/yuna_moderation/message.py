import discord
from discord import app_commands
from discord.ext import commands
import re
from typing import *
from collections import Counter
from utils.Tools import *
from typing import Union


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
      deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate, bulk=True)
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
    

class Message(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.color = 0x000000


  @commands.hybrid_group(name="clean", invoke_without_command=True, fallback="all", aliases=["purge", "clear"], help="Clears the messages")
  @app_commands.allowed_installs(guilds=True, users=False)
  @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def clean(self, ctx, amount: int = 5):
        if isinstance(self, commands.Context):
            amount = ctx if isinstance(ctx, int) else 5
            ctx = self

        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)

        return await do_removal(ctx, amount, lambda e: True)



  @clean.command(help="Clears the messages having embeds")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def embeds(self, ctx, search: int = 100):
        if isinstance(self, commands.Context):
            search = ctx if isinstance(ctx, int) else 100
            ctx = self
        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)
        await do_removal(ctx, search, lambda e: len(getattr(e, "embeds", [])))


  @clean.command(help="Clears the messages having files")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def files(self, ctx, search: int = 100):
        if isinstance(self, commands.Context):
            search = ctx if isinstance(ctx, int) else 100
            ctx = self
        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)
        await do_removal(ctx, search, lambda e: len(getattr(e, "attachments", [])))

  @clean.command(help="Clears the messages having images")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def images(self, ctx, search: int = 100):
        if isinstance(self, commands.Context):
            search = ctx if isinstance(ctx, int) else 100
            ctx = self
        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)
        await do_removal(ctx, search, lambda e: len(getattr(e, "embeds", [])) or len(getattr(e, "attachments", [])))


  @clean.command(help="Clears the messages of bots")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def bots(self, ctx, search: int = 100, prefix: str = None):
        if isinstance(self, commands.Context):
            search = ctx if isinstance(ctx, int) else 100
            ctx = self
        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)
        await do_removal(ctx, search, lambda e: (getattr(e, "webhook_id", None) is None and getattr(getattr(e, "author", None), "bot", False)) or (prefix and getattr(e, "content", "").startswith(prefix)))


  @clean.command(help="Clears the messages of a specific user")
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def user(self, ctx, member: discord.Member, search: int = 100):
        if isinstance(self, commands.Context):
            member = ctx
            ctx = self
        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)
        await do_removal(ctx, search, lambda e: getattr(e, "author", None) == member)



  @clean.command(help="Clears the messages containing a specifix string")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def contains(self, ctx, *, string: str):
        if isinstance(self, commands.Context):
            string = ctx
            ctx = self
        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)
        if len(string) < 3:
            await ctx.error("The substring length must be at least 3 characters.")
        else:
            await do_removal(ctx, 100, lambda e: string in getattr(e, "content", ""))


  @clean.command(name="emoji", aliases=["emojis"], help="Clears the messages having emojis")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _emoji(self, ctx, search: int = 100):
        if isinstance(self, commands.Context):
            search = ctx if isinstance(ctx, int) else 100
            ctx = self
        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)
            
        custom_emoji = re.compile(r"<a?:[a-zA-Z0-9\_]+:([0-9]+)>")

        def predicate(m):
            return bool(custom_emoji.search(getattr(m, "content", "")))

        await do_removal(ctx, search, predicate)

  @clean.command(name="reactions", help="Clears the reaction from the messages")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _reactions(self, ctx, search: int = 100):
        if isinstance(self, commands.Context):
            search = ctx if isinstance(ctx, int) else 100
            ctx = self
        is_slash = getattr(ctx, "interaction", None) is not None
        if not is_slash:
            if getattr(ctx, "message", None):
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.defer(ephemeral=True)

        if search > 100:
            search = 100
        if search <= 0:
            return await ctx.send("Amount must be between 1 and 100.")

        total_reactions = 0
        
        before_val = None if is_slash else getattr(ctx, "message", None)
        async for message in ctx.channel.history(limit=search, before=before_val):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                try:
                    await message.clear_reactions()
                except Exception:
                    pass

        await ctx.send(f"<a:tick:1558726958802800660> | Successfully removed {total_reactions} reactions.")
            



  @commands.command(name="purgebots",
                    aliases=["cleanup", "pb", "clearbot", "clearbots"],
                    help="Clear recently bot messages in channel")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _purgebot(self, ctx, prefix=None, search=100):

    await ctx.message.delete()

    def predicate(m):
        return (getattr(m, "webhook_id", None) is None and getattr(getattr(m, "author", None), "bot", False)) or (prefix and getattr(m, "content", "").startswith(prefix))
      
    await do_removal(ctx, search, predicate)


  @commands.command(name="purgeuser",
                    aliases=["clearuser"],
                    help="Clear recent messages of a user in channel")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def purguser(self, ctx, member: discord.Member, search=100):
      
      await ctx.message.delete()
      await do_removal(ctx, search, lambda e: getattr(e, "author", None) == member)
