import discord
from discord.ext import commands
import aiosqlite
import logging
from typing import Optional

from utils.Tools import *
from utils.config import OWNER_IDS
from utils.emojis import ANIMATED_ENABLED, STATIC_DISABLED, ANIMATED_SETTINGS, STATIC_MOD, ANIMATED_TICK

logger = logging.getLogger("yuna.antiraid.cmd")
DB_PATH = "db/anti.db"


class AntiRaidCommands(commands.Cog):
    """Configuration command suite for Anti-Raid & Join-Gate Shield."""

    def __init__(self, bot):
        self.bot = bot

    def _get_antiraid_cog(self):
        return self.bot.get_cog("AntiRaid")

    async def _update_db(self, guild_id: int, **kwargs):
        set_clauses = [f"{k} = ?" for k in kwargs.keys()]
        values = list(kwargs.values()) + [guild_id]

        async with aiosqlite.connect(DB_PATH) as db:
            # Upsert
            await db.execute(f"""
                INSERT INTO antiraid (guild_id, {', '.join(kwargs.keys())})
                VALUES (?, {', '.join(['?'] * len(kwargs))})
                ON CONFLICT(guild_id) DO UPDATE SET {', '.join(set_clauses)}
            """, [guild_id] + list(kwargs.values()) + list(kwargs.values()))
            await db.commit()

        cog = self._get_antiraid_cog()
        if cog:
            cog.update_cache(guild_id, kwargs)

    @commands.group(name="antiraid", aliases=["raidshield", "joingate"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antiraid(self, ctx: commands.Context):
        """Displays the Anti-Raid & Join-Gate Shield dashboard."""
        cog = self._get_antiraid_cog()
        cfg = cog.get_config(ctx.guild.id) if cog else {
            "enabled": False, "massjoin_enabled": True, "threshold_count": 5,
            "threshold_seconds": 10, "action": "kick", "min_age_hours": 24,
            "avatar_filter": False, "quarantine_role_id": None
        }

        embed = discord.Embed(
            title="🛡️ __**YUNA Supreme • Anti-Raid & Join-Gate Shield**__",
            description=(
                f"Autonomous perimeter defense protecting **{ctx.guild.name}** against mass bot joins, "
                f"token raids, and malicious burner accounts.\n"
            ),
            color=0x2b2d31
        )

        status_str = "🟢 **Active & Armed**" if cfg.get("enabled") else "🔴 **Disabled**"
        action_str = f"`{cfg.get('action', 'kick').upper()}`"

        quarantine_role = ctx.guild.get_role(cfg.get("quarantine_role_id")) if cfg.get("quarantine_role_id") else None
        quarantine_str = quarantine_role.mention if quarantine_role else "*None set*"

        mass_join_str = (
            f"Active (`{cfg.get('threshold_count', 5)}` joins in `{cfg.get('threshold_seconds', 10)}s`)"
            if cfg.get("massjoin_enabled") else "Disabled"
        )
        min_age_str = f"`{cfg.get('min_age_hours', 24)} hours`" if cfg.get("min_age_hours", 0) > 0 else "Disabled"
        avatar_str = "Enabled (No default avatars)" if cfg.get("avatar_filter") else "Disabled"

        embed.add_field(name="Shield Status", value=status_str, inline=True)
        embed.add_field(name="Enforcement Action", value=action_str, inline=True)
        embed.add_field(name="Quarantine Role", value=quarantine_str, inline=True)

        embed.add_field(name="Mass-Join Velocity", value=mass_join_str, inline=False)
        embed.add_field(name="Min Account Age", value=min_age_str, inline=True)
        embed.add_field(name="Default Avatar Filter", value=avatar_str, inline=True)

        pre = ctx.prefix
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{pre}antiraid enable` / `disable` — Toggle entire shield\n"
                f"`{pre}antiraid action <kick|ban|quarantine>` — Set raid punishment\n"
                f"`{pre}antiraid massjoin <count> <seconds>` — Configure velocity limits\n"
                f"`{pre}antiraid minage <hours>` — Set minimum account age (0 to disable)\n"
                f"`{pre}antiraid avatar <on|off>` — Block default avatars\n"
                f"`{pre}antiraid quarantine <@role>` — Assign isolation role"
            ),
            inline=False
        )
        embed.set_footer(text=f"Yuna Supreme Anti-Raid V2 • Sub-15ms Gateway Interception", icon_url=getattr(self.bot.user.display_avatar, "url", None))
        await ctx.send(embed=embed)

    @antiraid.command(name="enable", aliases=["on"])
    @commands.has_permissions(administrator=True)
    async def antiraid_enable(self, ctx: commands.Context):
        """Enables the Anti-Raid & Join-Gate shield."""
        await self._update_db(ctx.guild.id, enabled=True)
        embed = discord.Embed(
            description=f"✅ **Anti-Raid & Join-Gate Shield has been enabled!**\nYour server is now protected against mass token raids and burner accounts.",
            color=0x00FF7F
        )
        await ctx.send(embed=embed)

    @antiraid.command(name="disable", aliases=["off"])
    @commands.has_permissions(administrator=True)
    async def antiraid_disable(self, ctx: commands.Context):
        """Disables the Anti-Raid & Join-Gate shield."""
        await self._update_db(ctx.guild.id, enabled=False)
        embed = discord.Embed(
            description=f"⚠️ **Anti-Raid & Join-Gate Shield has been disabled.**",
            color=0xFF4500
        )
        await ctx.send(embed=embed)

    @antiraid.command(name="action")
    @commands.has_permissions(administrator=True)
    async def antiraid_action(self, ctx: commands.Context, action: str):
        """Sets enforcement action: kick, ban, or quarantine."""
        action = action.lower()
        if action not in ["kick", "ban", "quarantine"]:
            return await ctx.send("❌ Valid actions are: `kick`, `ban`, or `quarantine`.")

        await self._update_db(ctx.guild.id, action=action)
        await ctx.send(f"✅ Raid enforcement action updated to **`{action.upper()}`**.")

    @antiraid.command(name="massjoin", aliases=["velocity"])
    @commands.has_permissions(administrator=True)
    async def antiraid_massjoin(self, ctx: commands.Context, count: int, seconds: int):
        """Sets mass-join detection velocity threshold (e.g. 5 joins in 10s)."""
        if count < 2 or count > 50:
            return await ctx.send("❌ Count must be between 2 and 50.")
        if seconds < 3 or seconds > 60:
            return await ctx.send("❌ Seconds window must be between 3 and 60 seconds.")

        await self._update_db(ctx.guild.id, threshold_count=count, threshold_seconds=seconds, massjoin_enabled=True)
        await ctx.send(f"✅ Mass-join velocity threshold set to **{count} joins within {seconds} seconds**.")

    @antiraid.command(name="minage", aliases=["age"])
    @commands.has_permissions(administrator=True)
    async def antiraid_minage(self, ctx: commands.Context, hours: int):
        """Sets minimum account age in hours (e.g. 24 for 1 day, 0 to disable)."""
        if hours < 0 or hours > 720:
            return await ctx.send("❌ Hours must be between 0 (disabled) and 720 (30 days).")

        await self._update_db(ctx.guild.id, min_age_hours=hours)
        if hours == 0:
            await ctx.send("✅ Minimum account age verification has been **disabled**.")
        else:
            await ctx.send(f"✅ Accounts younger than **{hours} hours** ({hours/24:.1f} days) will be intercepted on join.")

    @antiraid.command(name="avatar", aliases=["defaultavatar"])
    @commands.has_permissions(administrator=True)
    async def antiraid_avatar(self, ctx: commands.Context, toggle: str):
        """Toggles blocking accounts with default avatars: on / off."""
        toggle = toggle.lower()
        if toggle in ["on", "enable", "true", "yes"]:
            enabled = True
        elif toggle in ["off", "disable", "false", "no"]:
            enabled = False
        else:
            return await ctx.send("❌ Specify `on` or `off`.")

        await self._update_db(ctx.guild.id, avatar_filter=enabled)
        state_str = "enabled (default avatars will be intercepted)" if enabled else "disabled"
        await ctx.send(f"✅ Default avatar filter is now **{state_str}**.")

    @antiraid.command(name="quarantine", aliases=["jailrole"])
    @commands.has_permissions(administrator=True)
    async def antiraid_quarantine(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Configures or clears the quarantine role."""
        if role is None:
            await self._update_db(ctx.guild.id, quarantine_role_id=None)
            return await ctx.send("✅ Quarantine role cleared.")

        if role >= ctx.guild.me.top_role:
            return await ctx.send("❌ That role is equal to or higher than my highest role. Please move my role above it.")

        await self._update_db(ctx.guild.id, quarantine_role_id=role.id)
        await ctx.send(f"✅ Quarantine role set to {role.mention}.")
