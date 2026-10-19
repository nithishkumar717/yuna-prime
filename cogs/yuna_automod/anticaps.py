import discord
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import timedelta
from cogs.yuna_automod.cache import automod_cache

class AntiCaps(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.caps_threshold = 70
        self.mute_duration = 2 * 60

    async def is_automod_enabled(self, guild_id):
        return await automod_cache.is_automod_enabled(guild_id)

    async def is_anti_caps_enabled(self, guild_id):
        return await automod_cache.is_rule_enabled(guild_id, "Anti caps")

    async def get_ignored_channels(self, guild_id):
        return await automod_cache.get_ignored_channels(guild_id)

    async def get_ignored_roles(self, guild_id):
        return await automod_cache.get_ignored_roles(guild_id)

    async def get_punishment(self, guild_id):
        return await automod_cache.get_punishment(guild_id, "Anti caps")

    async def log_action(self, guild, user, channel, action, reason):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
            log_channel_id = await cursor.fetchone()

        if log_channel_id and log_channel_id[0]:
            log_channel = guild.get_channel(log_channel_id[0])
            if log_channel:
                embed = discord.Embed(title="Automod Log: Anti-Caps", color=0xff0000)
                embed.add_field(name="User", value=user.mention, inline=False)
                embed.add_field(name="Action", value=action, inline=False)
                embed.add_field(name="Channel", value=channel.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"User ID: {user.id}")
                avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
                embed.set_thumbnail(url=avatar_url)
                embed.timestamp=discord.utils.utcnow()
                await log_channel.send(embed=embed)

    async def check_caps(self, message: discord.Message) -> bool:
        letters = [c for c in message.content if c.isalpha()]
        if len(letters) < 6:
            return False

        from cogs.yuna_automod.executor import execute_automod_action, get_threshold
        threshold = await get_threshold(message.guild.id, 'Anti caps', 70)

        caps_count = sum(1 for c in letters if c.isupper())
        caps_percentage = (caps_count / len(letters)) * 100

        if caps_percentage >= threshold:
            await execute_automod_action(self.bot, message.guild, message.author, message.channel, message, 'Anti caps', f'Excessive Caps ({caps_percentage:.1f}%)')
            return True
        return False

    async def on_message(self, message):
        # Centralized in cogs.yuna_automod.pipeline
        pass

    @commands.Cog.listener()
    async def on_rate_limit(self, message):
        await asyncio.sleep(10)

