import discord
from discord.ext import commands
import asyncio
import aiosqlite
import re
from typing import *
from utils.Tools import *
from discord.ui import Button, View


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


async def add_role_to_autorole(guild_id: int, role_id: int, is_bot: bool = False):
    """Registers the role into YUNA AutoRole so newly joined members receive it."""
    try:
        from core.autorole import get_autorole_service
        service = get_autorole_service()
        config = await service.get_config(guild_id)
        if role_id not in config.role_ids:
            config.role_ids.append(role_id)
            config.enabled = True
            await service.save_full_config(config)
    except Exception as e:
        print(f"[AUTOROLE SYNC ERROR] {e}")


async def remove_role_from_autorole(guild_id: int, role_id: int, is_bot: bool = False):
    """Removes the role from YUNA AutoRole."""
    try:
        from core.autorole import get_autorole_service
        service = get_autorole_service()
        await service.remove_role(guild_id, role_id)
    except Exception as e:
        print(f"[AUTOROLE SYNC ERROR] {e}")


class RoleSelectDropdown(discord.ui.RoleSelect):
    def __init__(self, parent_view: 'RolePanelView'):
        super().__init__(placeholder="Select a role to manage...", min_values=1, max_values=1, row=0)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.author:
            return await interaction.response.send_message("This menu is not for you.", ephemeral=True)
        selected_role = self.values[0]
        self.parent_view.role = selected_role
        self.parent_view.build_buttons()
        embed = self.parent_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class RolePanelView(discord.ui.View):
    def __init__(self, cog: 'Role', author: discord.Member, role: discord.Role = None, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.author = author
        self.role = role
        self.build_buttons()

    def build_buttons(self):
        self.clear_items()
        self.add_item(RoleSelectDropdown(self))

        if self.role:
            # Row 1: Add actions
            add_all_btn = discord.ui.Button(label="Add to All", style=discord.ButtonStyle.success, row=1)
            add_all_btn.callback = self.add_all_callback
            self.add_item(add_all_btn)

            add_humans_btn = discord.ui.Button(label="Add to Humans", style=discord.ButtonStyle.primary, row=1)
            add_humans_btn.callback = self.add_humans_callback
            self.add_item(add_humans_btn)

            add_bots_btn = discord.ui.Button(label="Add to Bots", style=discord.ButtonStyle.primary, row=1)
            add_bots_btn.callback = self.add_bots_callback
            self.add_item(add_bots_btn)

            add_unverified_btn = discord.ui.Button(label="Add to Unverified", style=discord.ButtonStyle.secondary, row=1)
            add_unverified_btn.callback = self.add_unverified_callback
            self.add_item(add_unverified_btn)

            # Row 2: Remove actions & Cancel
            rem_all_btn = discord.ui.Button(label="Remove from All", style=discord.ButtonStyle.danger, row=2)
            rem_all_btn.callback = self.rem_all_callback
            self.add_item(rem_all_btn)

            rem_humans_btn = discord.ui.Button(label="Remove from Humans", style=discord.ButtonStyle.secondary, row=2)
            rem_humans_btn.callback = self.rem_humans_callback
            self.add_item(rem_humans_btn)

            rem_bots_btn = discord.ui.Button(label="Remove from Bots", style=discord.ButtonStyle.secondary, row=2)
            rem_bots_btn.callback = self.rem_bots_callback
            self.add_item(rem_bots_btn)

            cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, row=2)
            cancel_btn.callback = self.cancel_callback
            self.add_item(cancel_btn)
        else:
            cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
            cancel_btn.callback = self.cancel_callback
            self.add_item(cancel_btn)

    def build_embed(self) -> discord.Embed:
        guild = self.author.guild
        total_members = len(guild.members)
        total_humans = sum(1 for m in guild.members if not m.bot)
        total_bots = sum(1 for m in guild.members if m.bot)

        if self.role:
            with_role = sum(1 for m in guild.members if self.role in m.roles)
            without_role = total_members - with_role
            humans_without = sum(1 for m in guild.members if not m.bot and self.role not in m.roles)
            bots_without = sum(1 for m in guild.members if m.bot and self.role not in m.roles)
            unverified_without = sum(1 for m in guild.members if m.avatar is None and self.role not in m.roles)

            description = (
                f"**Target Role:** {self.role.mention} (`{self.role.name}` | ID: `{self.role.id}`)\n"
                f"**Role Position:** {self.role.position} / {guild.me.top_role.position} (Bot Top Role)\n\n"
                f"**Guild Statistics:**\n"
                f"• Total Members: **{total_members}** (Humans: **{total_humans}** | Bots: **{total_bots}**)\n"
                f"• Members with Role: **{with_role}**\n"
                f"• Members needing Role: **{without_role}** (Humans: **{humans_without}** | Bots: **{bots_without}** | Unverified: **{unverified_without}**)\n\n"
                f"**Available Actions:**\n"
                f"Click any button below to perform the action. Added roles will also automatically sync to Auto-Role for newly joined members."
            )
        else:
            description = (
                f"**Guild Statistics:**\n"
                f"• Total Members: **{total_members}** (Humans: **{total_humans}** | Bots: **{total_bots}**)\n\n"
                f"Please select a role from the dropdown menu below to view actions."
            )

        embed = discord.Embed(
            title="Role Management Dashboard",
            description=description,
            color=self.cog.color
        )
        embed.set_footer(
            text=f"Requested by {self.author.display_name} | Yuna Moderation",
            icon_url=self.author.display_avatar.url
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return False
        return True

    async def add_all_callback(self, interaction: discord.Interaction):
        if not self.role:
            return
        members = [m for m in interaction.guild.members if self.role not in m.roles]
        if not members:
            return await interaction.response.send_message(f"All members in the server already have {self.role.mention}.", ephemeral=True)
        await self.cog.safe_batch_modify_roles(
            interaction=interaction,
            role=self.role,
            members=members,
            action="add",
            reason=f"Role All Dashboard Action By: {interaction.user}",
            target_type="members",
            sync_autorole=True
        )

    async def add_humans_callback(self, interaction: discord.Interaction):
        if not self.role:
            return
        members = [m for m in interaction.guild.members if not m.bot and self.role not in m.roles]
        if not members:
            return await interaction.response.send_message(f"All human members already have {self.role.mention}.", ephemeral=True)
        await self.cog.safe_batch_modify_roles(
            interaction=interaction,
            role=self.role,
            members=members,
            action="add",
            reason=f"Role Humans Dashboard Action By: {interaction.user}",
            target_type="humans",
            sync_autorole=True
        )

    async def add_bots_callback(self, interaction: discord.Interaction):
        if not self.role:
            return
        members = [m for m in interaction.guild.members if m.bot and self.role not in m.roles]
        if not members:
            return await interaction.response.send_message(f"All bot members already have {self.role.mention}.", ephemeral=True)
        await self.cog.safe_batch_modify_roles(
            interaction=interaction,
            role=self.role,
            members=members,
            action="add",
            reason=f"Role Bots Dashboard Action By: {interaction.user}",
            target_type="bots",
            sync_autorole=True
        )

    async def add_unverified_callback(self, interaction: discord.Interaction):
        if not self.role:
            return
        members = [m for m in interaction.guild.members if m.avatar is None and self.role not in m.roles]
        if not members:
            return await interaction.response.send_message(f"All unverified members already have {self.role.mention}.", ephemeral=True)
        await self.cog.safe_batch_modify_roles(
            interaction=interaction,
            role=self.role,
            members=members,
            action="add",
            reason=f"Role Unverified Dashboard Action By: {interaction.user}",
            target_type="unverified members",
            sync_autorole=False
        )

    async def rem_all_callback(self, interaction: discord.Interaction):
        if not self.role:
            return
        members = [m for m in interaction.guild.members if self.role in m.roles]
        if not members:
            return await interaction.response.send_message(f"No members currently have {self.role.mention}.", ephemeral=True)
        await self.cog.safe_batch_modify_roles(
            interaction=interaction,
            role=self.role,
            members=members,
            action="remove",
            reason=f"Remove Role All Dashboard Action By: {interaction.user}",
            target_type="members",
            sync_autorole=True
        )

    async def rem_humans_callback(self, interaction: discord.Interaction):
        if not self.role:
            return
        members = [m for m in interaction.guild.members if not m.bot and self.role in m.roles]
        if not members:
            return await interaction.response.send_message(f"No human members have {self.role.mention}.", ephemeral=True)
        await self.cog.safe_batch_modify_roles(
            interaction=interaction,
            role=self.role,
            members=members,
            action="remove",
            reason=f"Remove Role Humans Dashboard Action By: {interaction.user}",
            target_type="humans",
            sync_autorole=True
        )

    async def rem_bots_callback(self, interaction: discord.Interaction):
        if not self.role:
            return
        members = [m for m in interaction.guild.members if m.bot and self.role in m.roles]
        if not members:
            return await interaction.response.send_message(f"No bot members have {self.role.mention}.", ephemeral=True)
        await self.cog.safe_batch_modify_roles(
            interaction=interaction,
            role=self.role,
            members=members,
            action="remove",
            reason=f"Remove Role Bots Dashboard Action By: {interaction.user}",
            target_type="bots",
            sync_autorole=True
        )

    async def cancel_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Action Cancelled",
            description="Role management dashboard closed.",
            color=self.cog.color
        )
        await interaction.response.edit_message(embed=embed, view=None)


class Role(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.color = 0x000000

  async def safe_batch_modify_roles(
      self,
      interaction: discord.Interaction,
      role: discord.Role,
      members: list,
      action: str,  # "add" or "remove"
      reason: str,
      target_type: str = "members",
      sync_autorole: bool = True
  ):
      if not interaction.guild.me.guild_permissions.manage_roles:
          return await interaction.response.edit_message(
              content="I am missing the required Manage Roles permission.",
              embed=None,
              view=None
          )

      if role.position >= interaction.guild.me.top_role.position:
          return await interaction.response.edit_message(
              content="That role is higher than or equal to my highest role in role hierarchy.",
              embed=None,
              view=None
          )

      total = len(members)
      action_verb = "Adding" if action == "add" else "Removing"

      embed_progress = discord.Embed(
          title="<a:loading:1554957482248380416> Processing Role Changes...",
          description=f"{action_verb} {role.mention} for **{total}** {target_type}.",
          color=self.color
      )
      await interaction.response.edit_message(embed=embed_progress, view=None)

      success_count = 0
      failed_count = 0

      for member in members:
          try:
              if action == "add":
                  await member.add_roles(role, reason=reason)
              else:
                  await member.remove_roles(role, reason=reason)
              success_count += 1
          except discord.Forbidden:
              failed_count += 1
          except discord.HTTPException as e:
              if e.status == 429:
                  retry_after = getattr(e, 'retry_after', 2.0)
                  try:
                      retry_after = float(retry_after)
                  except Exception:
                      retry_after = 2.0
                  await asyncio.sleep(retry_after + 0.5)
                  try:
                      if action == "add":
                          await member.add_roles(role, reason=reason)
                      else:
                          await member.remove_roles(role, reason=reason)
                      success_count += 1
                  except Exception:
                      failed_count += 1
              else:
                  failed_count += 1
          except Exception:
              failed_count += 1

          # Safe pacing between modifications
          await asyncio.sleep(0.65)

      # Sync to autorole so newly joined members also get the role (or don't if removed)
      if sync_autorole:
          is_bot_target = (target_type == "bots")
          if action == "add":
              await add_role_to_autorole(interaction.guild.id, role.id, is_bot=is_bot_target)
          else:
              await remove_role_from_autorole(interaction.guild.id, role.id, is_bot=is_bot_target)

      action_done = "added" if action == "add" else "removed"
      failed_note = f"Skipped / Failed: **{failed_count}** (Hierarchy/Forbidden)\n" if failed_count else ""
      autorole_note = (
          "\nAuto-Role Active: Newly joined members will also automatically receive this role upon joining."
          if (sync_autorole and action == "add") else ""
      )
      embed_done = discord.Embed(
          title="Role Operation Complete",
          description=(
              f"Successfully {action_done} {role.mention} for **{success_count}** {target_type}.\n"
              f"{failed_note}"
              f"{autorole_note}"
          ),
          color=self.color
      )
      embed_done.set_footer(
          text=f"Requested by {interaction.user.display_name} | Yuna Moderation",
          icon_url=interaction.user.display_avatar.url
      )
      try:
          await interaction.channel.send(embed=embed_done)
      except Exception:
          pass


  @commands.group(name="role",invoke_without_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.has_permissions(manage_roles=True)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @top_check()
  @blacklist_check()
  async def role(self, ctx, member: discord.Member, *, role: discord.Role):
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


  @role.command(help="Give role to member for particular time")
  @commands.bot_has_permissions(manage_roles=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 7, commands.BucketType.user)
  @commands.has_permissions(manage_roles=True)
  @commands.bot_has_permissions(manage_roles=True)
  async def temp(self, ctx, role: discord.Role, time, *, user: discord.Member):
    if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and role.position >= ctx.author.top_role.position:
        embed = discord.Embed(
              description="You can't manage a role that is higher or equal to your top role!",
              color=self.color
          )
        embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=embed)
          
    else:
      if role.position >= ctx.guild.me.top_role.position:
        embed1 = discord.Embed(
          description=
          f"{role} is higher than my top role, move my role above {role}.",
          color=self.color)
        embed1.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        embed1.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=embed1)
    seconds = convert(time)
    await user.add_roles(role, reason=None)
    success = discord.Embed(
      description=
      f"Successfully added {role.mention} to {user.mention} .",
      color=self.color)
    success.set_author(name="Success", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
    success.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    await ctx.send(embed=success)
    await asyncio.sleep(seconds)
    await user.remove_roles(role)

  
  @role.command(help="Delete a role in the guild")
  @blacklist_check()
  @ignore_check()
  @top_check()
  @commands.cooldown(1, 7, commands.BucketType.user)
  @commands.has_permissions(manage_roles=True)
  @commands.bot_has_permissions(manage_roles=True)
  async def delete(self, ctx, *, role: discord.Role):
    if not is_server_owner_or_extra_owner(ctx.guild, ctx.author) and role.position >= ctx.author.top_role.position:
        embed = discord.Embed(
            description="You cannot delete a role that is higher or equal to your top role!",
            color=self.color
        )
        embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=embed)

    if role.position >= ctx.guild.me.top_role.position:
        embed = discord.Embed(
            description=f"I cannot delete {role} because it is higher than my top role. Please move my role above {role}.",
            color=self.color
        )
        embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=embed)

    if role is None:
        embed = discord.Embed(
            description=f"No role named {role} found in this server.",
            color=self.color
        )
        embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=embed)

    await role.delete()
    
    embed = discord.Embed(
        description=f"Successfully deleted {role}.",
        color=self.color
    )
    embed.set_author(name="Success", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
    embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    await ctx.send(embed=embed)
      
  @role.command(help="Create a role in the guild")
  @blacklist_check()
  @ignore_check()
  @top_check()
  @commands.cooldown(1, 7, commands.BucketType.user)
  @commands.has_permissions(administrator=True)
  @commands.bot_has_permissions(manage_roles=True)
  async def create(self, ctx, *, name):
    embed = discord.Embed(
        description=f"Successfully created a role named {name}.",
        color=self.color
    )
    embed.set_author(name="Success", icon_url="https://cdn.discordapp.com/emojis/1222750301233090600.png")
    embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    await ctx.guild.create_role(name=name, color=discord.Color.default())
    await ctx.send(embed=embed)


  @role.command(help="Renames a role in the server.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.has_permissions(administrator=True)
  @commands.bot_has_permissions(manage_roles=True)
  async def rename(self, ctx, role: discord.Role, *, newname):
    
    if role.position >= ctx.author.top_role.position:
        embed = discord.Embed(
            description=f"You can't manage the role {role.mention} because it is higher or equal to your top role.",
            color=self.color
        )
        embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=embed)

    
    if role.position >= ctx.guild.me.top_role.position:
        embed = discord.Embed(
            description=f"I can't manage the role {role.mention} because it is higher than my top role.",
            color=self.color
        )
        embed.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1204106928675102770.png")
        embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.send(embed=embed)

    await role.edit(name=newname)
    embed = discord.Embed(
        description=f"Role {role.name} has been renamed to {newname}.",
        color=self.color
    )
    embed.set_author(name="Success")
    embed.set_footer(text=f"Requested by {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    await ctx.send(embed=embed)


  @role.command(name="humans", help="Gives role to all humans in the guild")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 15, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def role_humans(self, ctx, *, role: discord.Role):
    if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=discord.Embed(title="Error", description="I cannot assign a role that is higher than or equal to my highest role.", color=self.color))

        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green)
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red)

        members_without_role = [member for member in ctx.guild.members if not member.bot and role not in member.roles]

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await self.safe_batch_modify_roles(
                    interaction=interaction,
                    role=role,
                    members=members_without_role,
                    action="add",
                    reason=f"Role Humans Command Executed By: {ctx.author}",
                    target_type="humans",
                    sync_autorole=True
                )
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=self.color,
                    description=f"Action cancelled. No humans will be assigned the role {role.mention}.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        if len(members_without_role) == 0:
            return await ctx.reply(embed=discord.Embed(description=f"All humans already have the {role.mention} role.", color=self.color))
        else:
            embed = discord.Embed(
                color=self.color,
                description=f"**Are you sure you want to assign {role.mention} to {len(members_without_role)} humans?**\n*This will also register as Auto-Role for newly joined members.*")
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False)

    else:
        denied = discord.Embed(title="Access Denied",
            description="Your role should be above my top role.",
            color=0x000000)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)



  @role.command(name="bots", help="Gives role to all the bots in the guild")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def role_bots(self, ctx, *, role: discord.Role):
    if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=discord.Embed(title="Error", description="I cannot assign a role that is higher than or equal to my highest role.", color=self.color))

        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green)
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red)

        bots_without_role = [member for member in ctx.guild.members if member.bot and role not in member.roles]

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await self.safe_batch_modify_roles(
                    interaction=interaction,
                    role=role,
                    members=bots_without_role,
                    action="add",
                    reason=f"Role Bots Command Executed By: {ctx.author}",
                    target_type="bots",
                    sync_autorole=True
                )
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=self.color,
                    description=f"Action cancelled. No bots will be assigned the role {role.mention}.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        if len(bots_without_role) == 0:
            return await ctx.reply(embed=discord.Embed(description=f"All bots already have the {role.mention} role.", color=self.color))
        else:
            embed = discord.Embed(
                color=self.color,
                description=f"**Are you sure you want to give {role.mention} to {len(bots_without_role)} bots?**\n*This will also register as Auto-Role for newly added bots.*")
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False)

    else:
        denied = discord.Embed(title="Access Denied",
            description="Your role should be above my top role.",
            color=0x000000)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)



  @role.command(name="unverified", help="Gives role to all the unverified members in the guild")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def role_unverified(self, ctx, *, role: discord.Role):
    if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=discord.Embed(title="Error", description="I cannot assign a role that is higher than or equal to my highest role.", color=self.color))

        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green)
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red)

        unverified_members = [member for member in ctx.guild.members if member.avatar is None and role not in member.roles]

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await self.safe_batch_modify_roles(
                    interaction=interaction,
                    role=role,
                    members=unverified_members,
                    action="add",
                    reason=f"Role Unverified Command Executed By: {ctx.author}",
                    target_type="unverified members",
                    sync_autorole=False
                )
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=self.color,
                    description=f"Action cancelled. No unverified members will be assigned the role {role.mention}.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        if len(unverified_members) == 0:
            return await ctx.reply(embed=discord.Embed(description="All unverified members already have the requested role.", color=self.color))

        embed = discord.Embed(
            color=self.color,
            description=f'**Are you sure you want to give {role.mention} to {len(unverified_members)} unverified members in this guild?**')
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    else:
        denied = discord.Embed(title="Access Denied",
            description="Your role should be above my top role.",
            color=0x000000)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)



  @role.command(name="all", aliases=["menu", "panel", "dashboard", "ui"], help="Opens the interactive Role Management UI with buttons.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def role_all(self, ctx, *, role: discord.Role = None):
    if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        if role and role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=discord.Embed(title="Error", description="I cannot manage a role that is higher than or equal to my highest role.", color=self.color))

        view = RolePanelView(cog=self, author=ctx.author, role=role)
        embed = view.build_embed()
        await ctx.reply(embed=embed, view=view, mention_author=False)
    else:
        denied = discord.Embed(title="Access Denied",
            description="Your role should be above my top role.",
            color=0x000000)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)



  @commands.group(name="removerole",invoke_without_command=True,
                 aliases=['rrole'],
                    help="remove a role from all members .")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @blacklist_check()
  @commands.has_permissions(administrator=True)
  async def rrole(self,ctx):
    if ctx.subcommand_passed is None:
      await ctx.send_help(ctx.command)
      ctx.command.reset_cooldown(ctx)


  @rrole.command(name="humans", help="Removes a role from all the humans in the server.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.has_permissions(administrator=True)
  async def rrole_humans(self, ctx, *, role: discord.Role):
    if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=discord.Embed(title="<:Denied:1294218790082711553> Error", description="I cannot remove a role that is higher than or equal to my highest role.", color=self.color))

        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green,
                        emoji="<a:tick:1558726958802800660>")
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red,
                         emoji="<:Yuna_cross:1227866668152393789>")

        humans_with_role = [member for member in ctx.guild.members if not member.bot and role in member.roles]

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await self.safe_batch_modify_roles(
                    interaction=interaction,
                    role=role,
                    members=humans_with_role,
                    action="remove",
                    reason=f"Remove Role Humans Command Executed By: {ctx.author}",
                    target_type="humans",
                    sync_autorole=True
                )
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=self.color,
                    description=f"Action cancelled. {role.mention} will not be removed from any humans.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        if len(humans_with_role) == 0:
            return await ctx.reply(embed=discord.Embed(description=f"| Already no humans have {role.mention}.", color=self.color))
        else:
            embed = discord.Embed(
                color=self.color,
                description=f'**Are you sure you want to remove {role.mention} from {len(humans_with_role)} humans in this guild?**')
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False)
    else:
        denied = discord.Embed(title="<:Denied:1294218790082711553> Access Denied",
            description="Your role should be above my top role.",
            color=0x000000)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)



  @rrole.command(name="bots", help="Removes a role from all the bots in the server.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.has_permissions(administrator=True)
  async def rrole_bots(self, ctx, *, role: discord.Role):
    if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=discord.Embed(title="Error", description="I cannot remove a role that is higher than or equal to my highest role.", color=self.color))

        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green)
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red)

        bots_with_role = [member for member in ctx.guild.members if member.bot and role in member.roles]

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await self.safe_batch_modify_roles(
                    interaction=interaction,
                    role=role,
                    members=bots_with_role,
                    action="remove",
                    reason=f"Remove Role Bots Command Executed By: {ctx.author}",
                    target_type="bots",
                    sync_autorole=True
                )
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=self.color,
                    description=f"Action cancelled. {role.mention} will not be removed from any bots.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        if len(bots_with_role) == 0:
            return await ctx.reply(embed=discord.Embed(description=f"No bots currently have {role.mention}.", color=self.color))
        else:
            embed = discord.Embed(
                color=self.color,
                description=f'**Are you sure you want to remove {role.mention} from {len(bots_with_role)} bots in this guild?**')
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False)
    else:
        denied = discord.Embed(title="Access Denied",
            description="Your role should be above my top role.",
            color=0x000000)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)



  @rrole.command(name="all", help="Removes a role from all members in the server.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.has_permissions(administrator=True)
  async def rrole_all(self, ctx, *, role: discord.Role):
    if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=discord.Embed(title="Error", description="I cannot remove a role that is higher than or equal to my highest role.", color=self.color))

        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green)
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red)

        members_with_role = [member for member in ctx.guild.members if role in member.roles]

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await self.safe_batch_modify_roles(
                    interaction=interaction,
                    role=role,
                    members=members_with_role,
                    action="remove",
                    reason=f"Remove Role All Command Executed By: {ctx.author}",
                    target_type="members",
                    sync_autorole=True
                )
            else:
                await interaction.response.send_message("This action is not for you!",
                                                        ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=self.color,
                    description=f"Action cancelled. {role.mention} will not be removed from anyone.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                await interaction.response.send_message("This action is not for you!",
                                                        ephemeral=True)

        if len(members_with_role) == 0:
            return await ctx.reply(embed=discord.Embed(description=f"No members currently have {role.mention}.", color=self.color))
        else:
            embed = discord.Embed(
                color=self.color,
                description=f'**Are you sure you want to remove {role.mention} from {len(members_with_role)} members in this guild?**')
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False)
    else:
        denied = discord.Embed(title="Access Denied",
            description="Your role should be above my top role.",
            color=0x000000)
        denied.set_footer(text=f"“{ctx.command.qualified_name}” Command executed by {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=denied, mention_author=False)



  @rrole.command(name="unverified", help="Removes a role from all the unverified members in the server.")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 10, commands.BucketType.user)
  @commands.has_permissions(administrator=True)
  async def rrole_unverified(self, ctx, *, role: discord.Role):
    if is_server_owner_or_extra_owner(ctx.guild, ctx.author) or ctx.author.top_role.position > ctx.guild.me.top_role.position:
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.reply(embed=discord.Embed(title="Error", description="I cannot remove a role that is higher than or equal to my highest role.", color=self.color))

        button = Button(label="Confirm",
                        style=discord.ButtonStyle.green)
        button1 = Button(label="Cancel",
                         style=discord.ButtonStyle.red)

        unverified_members = [member for member in ctx.guild.members if member.avatar is None and role in member.roles]

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await self.safe_batch_modify_roles(
                    interaction=interaction,
                    role=role,
                    members=unverified_members,
                    action="remove",
                    reason=f"Remove Role Unverified Command Executed By: {ctx.author}",
                    target_type="unverified members",
                    sync_autorole=False
                )
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                embed2 = discord.Embed(
                    color=self.color,
                    description=f"Action cancelled. {role.mention} will not be removed from any unverified members.")
                await interaction.response.edit_message(embed=embed2, view=None)
            else:
                await interaction.response.send_message(
                    "This action is not for you!",
                    ephemeral=True)

        if len(unverified_members) == 0:
            return await ctx.reply(embed=discord.Embed(description=f"No unverified members currently have {role.mention}.", color=self.color))
        else:
            embed = discord.Embed(
                color=self.color,
                description=f'**Are you sure you want to remove {role.mention} from {len(unverified_members)} unverified members in this guild?**')
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False)
    else:
        denied = discord.Embed(title="Access Denied",
            description="Your role should be above my top role.",
            color=0x000000)
        await ctx.send(embed=denied, mention_author=False)

  
