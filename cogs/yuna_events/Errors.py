import discord
from discord import app_commands
from discord.ext import commands
from core import BotBase, Cog, Context
from utils.Tools import get_ignore_data
from utils.permission_handler import permission_handler

class Errors(Cog):
  def __init__(self, client: BotBase):
    self.client = client
    # Hook slash command error logging and user-facing interaction response
    if hasattr(client, "tree"):
      orig_tree_error = getattr(client.tree, "on_error", None)
      async def _tree_error_handler(interaction: discord.Interaction, error: Exception):
        try:
          from utils.error_logs_db import record_bot_error
          cmd_name = interaction.command.name if interaction.command else "slash_command"
          record_bot_error(
            error=error,
            error_type="SlashError",
            source=f"/{cmd_name}",
            guild=interaction.guild,
            user=interaction.user,
            channel=interaction.channel
          )
        except Exception:
          pass

        # Respond to interaction so the user never sees "The application did not respond"
        try:
          real_err = getattr(error, 'original', error)
          while hasattr(real_err, 'original') and getattr(real_err, 'original', None) is not None:
            real_err = real_err.original

          if isinstance(real_err, (discord.NotFound, discord.Forbidden)) or getattr(real_err, 'code', None) in (10062, 10008, 50027):
            return

          embed = None
          if isinstance(real_err, app_commands.CommandOnCooldown):
            embed = discord.Embed(
              color=0x000000,
              description=f"Whoa, slow down there! You can run the command again in **{real_err.retry_after:.2f}** seconds."
            )
            embed.set_author(name="Cooldown", icon_url=client.user.avatar.url if client.user.avatar else client.user.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1251052632949395538.png")
          elif isinstance(real_err, (app_commands.MissingPermissions, commands.MissingPermissions)):
            missing = [str(p).replace("_", " ").replace("guild", "server").title() for p in real_err.missing_permissions]
            fmt = ", and ".join([", ".join(missing[:-1]), missing[-1]]) if len(missing) > 2 else " and ".join(missing)
            embed = discord.Embed(
              color=0x000000,
              description=f"You lack the **{fmt}** Permission to run this command!"
            )
            embed.set_author(name="Missing Permissions", icon_url=client.user.avatar.url if client.user.avatar else client.user.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1227625594511163537.png")
          elif isinstance(real_err, (app_commands.BotMissingPermissions, commands.BotMissingPermissions)) or isinstance(real_err, discord.Forbidden):
            if await permission_handler.handle_command_error(interaction, real_err):
              return
            embed = None
          elif isinstance(real_err, (app_commands.CheckFailure, commands.CheckFailure)):
            embed = discord.Embed(
              color=0x000000,
              description="<:Yuna_cross:1227866668152393789> You cannot use this command here or you lack permission."
            )
          elif isinstance(real_err, (app_commands.TransformerError, commands.BadArgument)):
            embed = discord.Embed(
              color=0x000000,
              description=f"<:Yuna_cross:1227866668152393789> Invalid argument provided for `/{cmd_name}`. Please check the command options."
            )
          else:
            embed = discord.Embed(
              color=0x000000,
              description=f"<:Yuna_cross:1227866668152393789> An unexpected error occurred while executing `/{cmd_name}`. This incident has been logged for administrators."
            )
            embed.set_footer(text=f"Logged as {type(real_err).__name__}")

          if embed:
            if not interaction.response.is_done():
              await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
              await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
          pass

        if orig_tree_error:
          await orig_tree_error(interaction, error)
      client.tree.on_error = _tree_error_handler

  async def send_error(self, ctx: Context, content=None, embed=None, delete_after=None, ephemeral=True):
    try:
      if ctx.interaction:
        if ctx.interaction.response.is_done():
          msg = await ctx.interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral, wait=True)
          if delete_after and msg and not ephemeral:
            try:
              await msg.delete(delay=delete_after)
            except Exception:
              pass
        else:
          await ctx.interaction.response.send_message(content=content, embed=embed, ephemeral=ephemeral, delete_after=delete_after)
      else:
        await ctx.reply(content=content, embed=embed, delete_after=delete_after, mention_author=False)
    except Exception:
      try:
        await ctx.send(content=content, embed=embed)
      except Exception:
        pass

  @commands.Cog.listener()
  async def on_command_error(self, ctx: Context, error):
    if ctx.command is None:
      return

    # Fully unwrap HybridCommandError and CommandInvokeError to root cause
    real_error = getattr(error, 'original', error)
    while hasattr(real_error, 'original') and getattr(real_error, 'original', None) is not None:
      real_error = real_error.original

    if isinstance(real_error, commands.CommandNotFound):
      return

    if isinstance(real_error, commands.MissingRequiredArgument):
      await ctx.send_help(ctx.command)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(real_error, commands.NotOwner):
      embed = discord.Embed(
        color=0x000000,
        description="<:Yuna_cross:1227866668152393789> Only the **Bot Owner** can use this command!"
      )
      await self.send_error(ctx, embed=embed, delete_after=6)
      return

    if isinstance(real_error, (commands.CheckFailure, app_commands.CheckFailure)):
      if not ctx.guild:
        embed = discord.Embed(color=0x000000, description="<:Yuna_cross:1227866668152393789> You cannot use my commands in DMs / outside of a server.")
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await self.send_error(ctx, embed=embed, delete_after=10)
        return

      # Silently block blacklisted users and guilds
      try:
        import aiosqlite
        async with aiosqlite.connect('db/block.db') as db:
          cursor = await db.execute("SELECT 1 FROM user_blacklist WHERE user_id = ?", (str(ctx.author.id),))
          if await cursor.fetchone():
            return
          cursor = await db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (str(ctx.guild.id),))
          if await cursor.fetchone():
            return
      except Exception:
        pass

      data = await get_ignore_data(ctx.guild.id)
      ch = data["channel"]
      iuser = data["user"]
      cmd = data["command"]
      buser = data["bypassuser"]

      if str(ctx.author.id) in buser:
        return

      if str(ctx.channel.id) in ch:
        await self.send_error(ctx, content=f"{ctx.author.mention} This **channel** is on the **ignored** list. Please try my commands in another channel.", delete_after=8)
        return

      if str(ctx.author.id) in iuser:
        await self.send_error(ctx, content=f"{ctx.author.mention} You are set as an **ignored user** for this guild. Please try my commands or modules in a different guild.", delete_after=8)
        return

      cmd_obj = getattr(ctx, "command", None)
      command_name = (getattr(cmd_obj, "name", "") or "").strip().lower()
      raw_aliases = getattr(cmd_obj, "aliases", None) or getattr(getattr(cmd_obj, "wrapped", None), "aliases", None) or []
      aliases = [str(alias).strip().lower() for alias in raw_aliases]
      if command_name in cmd or any(alias in cmd for alias in aliases):
        await self.send_error(ctx, content=f"{ctx.author.mention} This **command is ignored** in this guild. Please use other commands or try this command in a different guild", delete_after=8)
        return

      # Generic check failure fallback
      embed = discord.Embed(color=0x000000, description="<:Yuna_cross:1227866668152393789> You cannot use this command here or you lack permission.")
      await self.send_error(ctx, embed=embed, delete_after=8)
      return

    if isinstance(real_error, commands.NoPrivateMessage):
      embed = discord.Embed(color=0x000000, description="<:Yuna_cross:1227866668152393789> You cannot use my commands in DMs / outside of a server.")
      embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
      embed.set_thumbnail(url=ctx.author.display_avatar.url)
      await self.send_error(ctx, embed=embed, delete_after=10)
      return

    if isinstance(real_error, commands.TooManyArguments):
      await ctx.send_help(ctx.command)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(real_error, (commands.CommandOnCooldown, app_commands.CommandOnCooldown)):
      embed = discord.Embed(color=0x000000, description=f"{ctx.author.mention} Whoa, slow down there! You can run the command again in **{real_error.retry_after:.2f}** seconds.")
      embed.set_author(name="Cooldown", icon_url=self.client.user.avatar.url if self.client.user.avatar else self.client.user.default_avatar.url)
      embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1251052632949395538.png")
      embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      await self.send_error(ctx, embed=embed, delete_after=10)
      return

    if isinstance(real_error, commands.MaxConcurrencyReached):
      embed = discord.Embed(color=0x000000, description=f"{ctx.author.mention} This command is already in progress. Please let it finish and try again afterward.")
      embed.set_author(name="Command in Progress.", icon_url=self.client.user.avatar.url if self.client.user.avatar else self.client.user.default_avatar.url)
      embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1251052632949395538.png")
      embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      await self.send_error(ctx, embed=embed, delete_after=10)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(real_error, (commands.MissingPermissions, app_commands.MissingPermissions)):
      missing = [str(perm).replace("_", " ").replace("guild", "server").title() for perm in real_error.missing_permissions]
      fmt = "{}, and {}".format(", ".join(missing[:-1]), missing[-1]) if len(missing) > 2 else " and ".join(missing)
      embed = discord.Embed(color=0x000000, description=f"You lack the **{fmt}** Permission to run the **{ctx.command.name}** command!")
      embed.set_author(name="Missing Permissions", icon_url=self.client.user.avatar.url if self.client.user.avatar else self.client.user.default_avatar.url)
      embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1227625594511163537.png")
      embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      await self.send_error(ctx, embed=embed, delete_after=7)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(real_error, (commands.BotMissingPermissions, app_commands.BotMissingPermissions)):
      await permission_handler.handle_command_error(ctx, real_error)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(real_error, (commands.BadArgument, app_commands.TransformerError)):
      await ctx.send_help(ctx.command)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(real_error, discord.Forbidden):
      if await permission_handler.handle_command_error(ctx, real_error):
        ctx.command.reset_cooldown(ctx)
        return
      return

    if isinstance(real_error, discord.NotFound):
      return

    if isinstance(real_error, discord.HTTPException):
      if getattr(real_error, 'code', None) in (10062, 10008, 50027):
        return

    # Persist unhandled runtime & command code errors to Admin Error Logs database
    try:
      from utils.error_logs_db import record_bot_error
      cmd_name = ctx.command.qualified_name if ctx.command else (ctx.invoked_with or "unknown_command")
      is_slash = getattr(ctx, "interaction", None) is not None
      cmd_display = f"/{cmd_name}" if is_slash else f"${cmd_name}"
      record_bot_error(
        error=real_error if isinstance(real_error, Exception) else error,
        error_type="CommandError",
        source=cmd_display,
        guild=ctx.guild,
        user=ctx.author,
        channel=ctx.channel
      )
      try:
        embed = discord.Embed(
          color=0x000000,
          description=f"<:Yuna_cross:1227866668152393789> An unexpected error occurred while executing **{cmd_display}**. This incident has been logged for administrators."
        )
        embed.set_footer(text=f"Logged as {type(real_error).__name__}")
        await self.send_error(ctx, embed=embed, delete_after=10)
      except Exception:
        pass
    except Exception as log_ex:
      print(f"[Errors Cog] Error logging failed: {log_ex}", flush=True)

  @commands.Cog.listener()
  async def on_error(self, event_method, *args, **kwargs):
    """Captures unhandled exceptions from event listeners (on_message, on_guild_join, etc.)."""
    try:
      import sys
      from utils.error_logs_db import record_bot_error
      exc_info = sys.exc_info()
      if exc_info and exc_info[1]:
        record_bot_error(
          error=exc_info[1],
          error_type="EventError",
          source=f"on_{event_method}"
        )
    except Exception as ex:
      print(f"[Errors Cog] Global on_error logging failed: {ex}", flush=True)
