import discord
from discord.ext import commands
from discord import app_commands
from difflib import get_close_matches
from core.Bot import BotBase
from core.Cog import Cog
from utils.Tools import getConfig
import importlib
from utils import help as vhelp
importlib.reload(vhelp)
from utils import Paginator, FieldPagePaginator
import asyncio
from utils.Tools import *

color = 0x2B2D31


def build_help_embed(prefix: str = "$", command_count: int = 0, slash_count: int = 0, author_name: str = "User") -> discord.Embed:
    embed = discord.Embed(
        title="🛡️ Yuna Supreme ~ Security & Moderation Center",
        description="*Dedicated Autonomous Protection & Ultra-Low-Latency Containment*\n──────────────────────────────",
        color=color
    )
    from utils.support_utils import get_support_url
    support_url = get_support_url()
    embed.add_field(
        name="System Stats & Info",
        value=f"• **Prefix:** `{prefix}`\n• **Prefix Commands:** `{command_count}`\n• **Slash Commands:** `{slash_count}`\n• **Engine:** Anti-Nuke V2 TurboBan (Sub-15ms Dispatch)\n**[Support Server]({support_url})**",
        inline=False
    )
    embed.add_field(
        name="How to use me?",
        value=f">>> `{prefix}help <command/module>` to view details!\n*Example:* `{prefix}help antinuke` or `{prefix}help automod`",
        inline=False
    )
    embed.add_field(
        name="Security & Moderation Domains",
        value=(
            "• **Security & Anti-Nuke** • Autonomous Anti-Nuke V2, TurboBan, Whitelists, Bot Guard & Emergency Lockdown.\n"
            "• **AutoMod** • Real-time filtering of spam, malicious links, invites, mass mentions & blacklisted words.\n"
            "• **Moderation** • High-precision member discipline, channel locks, purge filters & honeypot traps.\n"
            "• **Logs & Audits** • Forensic audit trails, event routing and instant security notifications."
        ),
        inline=False
    )
    return embed


class HelpCommand(commands.HelpCommand):

  async def send_ignore_message(self, ctx, ignore_type: str):

    if ignore_type == "channel":
      await ctx.reply("🌸 This channel is ignored~", mention_author=False)
    elif ignore_type == "command":
      await ctx.reply(f"{ctx.author.mention} 🌸 This Command, Channel, or You have been ignored here~", delete_after=6)
    elif ignore_type == "user":
      await ctx.reply("🌸 You are ignored~", mention_author=False)


  async def on_help_command_error(self, ctx, error):
    errors = [
      commands.CommandOnCooldown, commands.CommandNotFound,
      discord.HTTPException, commands.CommandInvokeError
    ]
    if type(error) not in errors:
      await self.context.reply(f"🌸 Uh oh! Unknown Error Occurred:\n{error.original}",
                               mention_author=False)
    else:
      if type(error) == commands.CommandOnCooldown:
        return

    return await super().on_help_command_error(ctx, error)

  
  async def command_not_found(self, string: str) -> None:
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
        return

    if not check_ignore:
        await self.send_ignore_message(ctx, "command")
        return

    from utils.config import OWNER_IDS
    is_owner = ctx.author.id in OWNER_IDS or (await ctx.bot.is_owner(ctx.author) if hasattr(ctx.bot, "is_owner") else False)

    cmds = [str(cmd) for cmd in self.context.bot.walk_commands() if not cmd.hidden or is_owner]
    matches = get_close_matches(string, cmds)

    embed = discord.Embed(
        title="🌸 Command Not Found",
        description=f"Uh oh! I couldn't find a command named `{string}`.",
        color=0x2B2D31
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1275364856631005256.png")
    bot_icon = self.context.bot.user.display_avatar.url if self.context.bot.user else None
    embed.set_author(name=f"Hi {self.context.author.display_name}!", icon_url=bot_icon)
    embed.set_footer(text=f"Requested By {ctx.author} • Yuna Companion",
                       icon_url=ctx.author.display_avatar.url)
    if matches:
        match_list = "\n".join([f"🌸 `{match}`" for match in matches])
        embed.add_field(name="🌸 Did you mean:", value=match_list, inline=True)

    await ctx.reply(embed=embed)

  
  async def send_bot_help(self, mapping):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    importlib.reload(vhelp)
    view = vhelp.SaaSView(ctx)
    await ctx.reply(view=view, mention_author=False)

  async def send_command_help(self, command):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    if command.hidden:
      from utils.config import OWNER_IDS
      is_owner = ctx.author.id in OWNER_IDS or (await ctx.bot.is_owner(ctx.author) if hasattr(ctx.bot, "is_owner") else False)
      if not is_owner:
        if command.name == "np" or (getattr(command, "root_parent", None) and getattr(command.root_parent, "name", None) == "np"):
          from utils.support_utils import get_support_url
          support_url = get_support_url(ctx.bot)
          embed = discord.Embed(
              title="🎁 Claim Lifetime Free No-Prefix Access",
              description=(
                  "Want to run Yuna commands effortlessly without typing a prefix?\n\n"
                  "✨ **Lifetime Free Beta Program**\n"
                  f"➜ Join our **[Official Support Server]({support_url})**\n"
                  "➜ Head over to the `#claim-no-prefix` channel\n"
                  "➜ Click **🎁 Claim Free No-Prefix (Lifetime)** for instant 1-click activation!\n\n"
                  "*(Works globally across every Discord server where Yuna is present!)*"
              ),
              color=color
          )
          avatar = ctx.bot.user.display_avatar.url if ctx.bot.user else None
          if avatar:
              embed.set_thumbnail(url=avatar)
          embed.set_footer(text=f"Requested by {ctx.author.display_name} • Free Testing Beta", icon_url=ctx.author.display_avatar.url)
          view = discord.ui.View()
          view.add_item(discord.ui.Button(
              label="👉 Claim Now",
              style=discord.ButtonStyle.link,
              url=support_url,
              emoji="🎁"
          ))
          return await ctx.reply(embed=embed, view=view, mention_author=False)
        await self.send_error_message(command.qualified_name)
        return
    
    sonu = f">>> {command.help}" if command.help else '>>> No Help Provided...'
    embed = discord.Embed(
        title=f"🌸 `{command.qualified_name.title()}` Command",
        description=
        f"""```xml
<[] = optional | ‹› = required\nDon't type these while using Commands>```\n{sonu}""",
        color=color)
    alias = ' | '.join(command.aliases)

    embed.add_field(name="🌸 **Aliases**",
                      value=f"`{alias}`" if command.aliases else "No Aliases",
                      inline=False)
    embed.add_field(name="🌸 **Usage**",
                      value=f"`{self.context.prefix}{command.signature}`\n")
    embed.set_author(name=f"Requested by {self.context.author.display_name}",
                       icon_url=self.context.bot.user.display_avatar.url)
    await self.context.reply(embed=embed, mention_author=False)


  def get_command_signature(self, command: commands.Command) -> str:
    parent = command.full_parent_name
    if len(command.aliases) > 0:
      aliases = ' | '.join(command.aliases)
      fmt = f'[{command.name} | {aliases}]'
      if parent:
        fmt = f'{parent}'
      alias = f'[{command.name} | {aliases}]'
    else:
      alias = command.name if not parent else f'{parent} {command.name}'
    return f'{alias} {command.signature}'

  def common_command_formatting(self, embed_like, command):
    embed_like.title = self.get_command_signature(command)
    if command.description:
      embed_like.description = f'{command.description}\n\n{command.help}'
    else:
      embed_like.description = command.help or 'No help found...'

  async def send_group_help(self, group):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
        return

    if not check_ignore:
        await self.send_ignore_message(ctx, "command")
        return

    if group.name == "np":
      from utils.config import OWNER_IDS
      is_owner = ctx.author.id in OWNER_IDS or (await ctx.bot.is_owner(ctx.author) if hasattr(ctx.bot, "is_owner") else False)
      if not is_owner:
        from utils.support_utils import get_support_url
        support_url = get_support_url(ctx.bot)
        embed = discord.Embed(
            title="🎁 Claim Lifetime Free No-Prefix Access",
            description=(
                "Want to run Yuna commands effortlessly without typing a prefix?\n\n"
                "✨ **Lifetime Free Beta Program**\n"
                f"➜ Join our **[Official Support Server]({support_url})**\n"
                "➜ Head over to the `#claim-no-prefix` channel\n"
                "➜ Click **🎁 Claim Free No-Prefix (Lifetime)** for instant 1-click activation!\n\n"
                "*(Works globally across every Discord server where Yuna is present!)*"
            ),
            color=color
        )
        avatar = ctx.bot.user.display_avatar.url if ctx.bot.user else None
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text=f"Requested by {ctx.author.display_name} • Free Testing Beta", icon_url=ctx.author.display_avatar.url)
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="👉 Claim Now",
            style=discord.ButtonStyle.link,
            url=support_url,
            emoji="🎁"
        ))
        return await ctx.reply(embed=embed, view=view, mention_author=False)

    entries = [
        (
            f"➜ `{self.context.prefix}{cmd.qualified_name}`\n",
            f"{cmd.short_doc if cmd.short_doc else ''}\n\u200b"
        )
        for cmd in group.commands
    ]

    count = len(group.commands)

    embeds = FieldPagePaginator(
        entries=entries,
        title=f"{group.qualified_name.title()} [{count}]",
        description="< > Duty | [ ] Optional\n",
        per_page=4
    ).get_pages()

    paginator = Paginator(ctx, embeds)
    await paginator.paginate()
    
  async def send_cog_help(self, cog):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return


    entries = [(
      f"➜ `{self.context.prefix}{cmd.qualified_name}`",
      f"{cmd.short_doc if cmd.short_doc else ''}"
      f"\n\u200b",
    ) for cmd in cog.get_commands()]
    embeds = FieldPagePaginator(
      entries=entries,
      title=f"{cog.qualified_name.title()} ({len(cog.get_commands())})",
      description="< > Duty | [ ] Optional\n\n",
      color=color,
      per_page=4).get_pages()
    paginator = Paginator(ctx, embeds)
    await paginator.paginate()


class Help(Cog, name="help"):

  def __init__(self, client: BotBase):
    self.client = client
    self._original_help_command = client.help_command
    # Set up the help command, but don't give it a name so it doesn't conflict
    client.help_command = HelpCommand()
    client.help_command.cog = self
    # Remove the automatically created help command
    client.remove_command("help")

  async def cog_unload(self):
    self.help_command = self._original_help_command

  @commands.hybrid_command(name="help", aliases=['h'], description="Shows help about bot, a command or a category")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  async def hybrid_help(self, ctx: commands.Context, *, command: str = None):
    self.client.help_command.context = ctx
    if command:
      command_clean = command.strip().lower()

      # 1. Direct Command / Alias Check
      cmd = self.client.get_command(command)
      if cmd:
        if isinstance(cmd, commands.Group):
          return await self.client.help_command.send_group_help(cmd)
        return await self.client.help_command.send_command_help(cmd)

      # 2. Category Cog Matching (Case-Insensitive & Alias-Aware)
      target_cog = None

      # Check registered cogs by exact or normalized name
      for name, cog in self.client.cogs.items():
        clean_name = name.lower().lstrip('_')
        if command_clean in (name.lower(), clean_name):
          target_cog = cog
          break
        if "help_custom" in dir(cog):
          _, label, _ = cog.help_custom()
          clean_label = label.lower().replace("commands", "").strip()
          if command_clean in (label.lower(), clean_label):
            target_cog = cog
            break

      # Common category alias dictionary
      if not target_cog:
        category_map = {
          "security": "_antinuke",
          "antinuke": "_antinuke",
          "anti": "_antinuke",
          "automod": "_automod",
          "music": "_music",
          "mod": "_moderation",
          "moderation": "_moderation",
          "general": "_general",
          "stats": "_general",
          "fun": "_fun",
          "games": "_games",
          "game": "_games",
          "extra": "_extra",
          "utility": "_extra",
          "giveaway": "_giveaway",
          "gaway": "_giveaway",
          "voice": "_voice",
          "vc": "_voice",
          "welcome": "_welcome",
          "welcomer": "_welcome",
          "server": "_server",
          "ignore": "_ignore",
          "billing": "_billing",
          "store": "_billing",
          "payments": "_billing",
          "payment": "_billing",
          "invoices": "_billing",
          "invoice": "_billing",
        }
        if command_clean in category_map:
          target_cog = self.client.get_cog(category_map[command_clean])

      if target_cog:
        if "help_custom" in dir(target_cog):
          emoji, label, desc = target_cog.help_custom()
          embed = discord.Embed(
            title=f"{emoji} 𝒀𝒖𝒏𝒂 ~ {label}",
            description=f"*{desc}*\n🎀 ───────────────────────────── 🎀",
            color=color
          )
          for c in target_cog.get_commands():
            if c.name.startswith("__") and c.name.endswith("__"):
              embed.description = f"*{desc}*\n🎀 ───────────────────────────── 🎀\n\n{c.help or c.description or ''}"
            else:
              params = "".join([f" <{p}>" for p in c.clean_params])
              embed.add_field(
                name=f"🌸 `{ctx.prefix}{c.name}{params}`",
                value=f"{c.help or 'No description'}\n\u200b",
                inline=False
              )
          user_icon = ctx.author.display_avatar.url
          embed.set_author(name=f"Hi {ctx.author.display_name}! 💕", icon_url=user_icon)
          embed.set_footer(text=f"Requested by {ctx.author} • Yuna Companion", icon_url=user_icon)
          return await ctx.reply(embed=embed, mention_author=False)
        else:
          return await self.client.help_command.send_cog_help(target_cog)

      # 3. Fuzzy search for close command matches
      await self.client.help_command.command_not_found(command)
    else:
      # Send interactive Home Center with Dropdown & Pagination
      mapping = {}
      for cog in self.client.cogs.values():
        if cog_commands := await self.client.help_command.filter_commands(cog.get_commands(), sort=True):
          mapping[cog] = cog_commands
      await self.client.help_command.send_bot_help(mapping)


    
