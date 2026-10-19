import discord
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import timedelta
import re

from cogs.yuna_automod.cache import automod_cache

class AntiInvite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.recent_violations = {}
        self.invite_pattern = re.compile(r'(https?://)?(www\.)?(discord\.gg|discordapp\.com/invite|discord\.com/invite)/\S+')

    async def is_automod_enabled(self, guild_id):
        return await automod_cache.is_automod_enabled(guild_id)

    async def is_anti_invites_enabled(self, guild_id):
        return await automod_cache.is_rule_enabled(guild_id, "Anti invites")

    async def get_ignored_channels(self, guild_id):
        return await automod_cache.get_ignored_channels(guild_id)

    async def get_ignored_roles(self, guild_id):
        return await automod_cache.get_ignored_roles(guild_id)

    async def get_punishment(self, guild_id):
        return await automod_cache.get_punishment(guild_id, "Anti invites")

    async def log_action(self, guild, user, channel, action, reason):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
            log_channel_id = await cursor.fetchone()

        if log_channel_id and log_channel_id[0]:
            log_channel = guild.get_channel(log_channel_id[0])
            if log_channel:
                embed = discord.Embed(title="Automod Log: Anti-Invite", color=0xff0000)
                embed.add_field(name="User", value=user.mention, inline=False)
                embed.add_field(name="Action", value=action, inline=False)
                embed.add_field(name="Channel", value=channel.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"User ID: {user.id}")
                avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
                embed.set_thumbnail(url=avatar_url)
                embed.timestamp=discord.utils.utcnow()
                await log_channel.send(embed=embed)

    async def check_invites(self, message: discord.Message) -> bool:
        invite_matches = self.invite_pattern.findall(message.content)
        if not invite_matches:
            return False

        guild = message.guild
        own_invite_codes = set()
        try:
            guild_invs = await guild.invites()
            for inv in guild_invs:
                if hasattr(inv, "code") and inv.code:
                    own_invite_codes.add(inv.code.lower())
        except Exception:
            pass

        external_invites = []
        for raw_match in self.invite_pattern.finditer(message.content):
            full_url = raw_match.group(0)
            code = full_url.rstrip('/').split('/')[-1].lower()
            if code and code not in own_invite_codes:
                external_invites.append(full_url)

        if external_invites:
            from cogs.yuna_automod.executor import execute_automod_action, get_threshold
            guild_id = guild.id
            threshold = await get_threshold(guild_id, 'Anti invites', 1)
            if threshold <= 1 or len(external_invites) >= threshold:
                await execute_automod_action(self.bot, guild, message.author, message.channel, message, 'Anti invites', f'Posting unauthorized Discord invite(s) ({len(external_invites)})')
                return True
            else:
                user_key = (guild_id, message.author.id)
                current_time = message.created_at.timestamp()
                user_violations = self.recent_violations.get(user_key, [])
                user_violations = [t for t in user_violations if current_time - t < 30]
                user_violations.append(current_time)
                self.recent_violations[user_key] = user_violations

                if len(user_violations) >= threshold:
                    self.recent_violations.pop(user_key, None)
                    await execute_automod_action(self.bot, guild, message.author, message.channel, message, 'Anti invites', f'Posting unauthorized Discord invite(s) ({len(user_violations)} violations in 30s)')
                    return True
                else:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return True
        return False

    async def on_message(self, message):
        # Centralized in cogs.yuna_automod.pipeline
        pass

    @commands.Cog.listener()
    async def on_rate_limit(self, message):
        await asyncio.sleep(10)

