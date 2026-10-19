import discord
from discord.ext import commands
import aiosqlite
import re
from datetime import timedelta
import asyncio

from cogs.yuna_automod.cache import automod_cache

class AntiEmojiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji_threshold = 5  

    async def is_automod_enabled(self, guild_id):
        return await automod_cache.is_automod_enabled(guild_id)

    async def is_anti_emoji_spam_enabled(self, guild_id):
        return await automod_cache.is_rule_enabled(guild_id, "Anti emoji spam")

    async def get_ignored_channels(self, guild_id):
        return await automod_cache.get_ignored_channels(guild_id)

    async def get_ignored_roles(self, guild_id):
        return await automod_cache.get_ignored_roles(guild_id)

    async def get_threshold(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT threshold FROM automod_thresholds WHERE guild_id = ? AND event = 'Anti emoji spam'", (guild_id,))
            result = await cursor.fetchone()
            return result[0] if (result and result[0]) else 5

    async def get_punishment(self, guild_id):
        return await automod_cache.get_punishment(guild_id, "Anti emoji spam")

    async def log_action(self, guild, user, channel, action, reason):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
            log_channel_id = await cursor.fetchone()

        if log_channel_id and log_channel_id[0]:
            log_channel = guild.get_channel(log_channel_id[0])
            if log_channel:
                embed = discord.Embed(title="Automod Log: Anti Emoji Spam", color=0xff0000)
                embed.add_field(name="User", value=user.mention, inline=False)
                embed.add_field(name="Action", value=action, inline=False)
                embed.add_field(name="Channel", value=channel.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"User ID: {user.id}")
                avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
                embed.set_thumbnail(url=avatar_url)
                embed.timestamp=discord.utils.utcnow()
                await log_channel.send(embed=embed)

    async def check_emoji(self, message: discord.Message) -> bool:
        emoji_pattern = re.compile(
            r"<a?:[a-zA-Z0-9_]+:([0-9]+)>|"  # discord emojis
            r"([\U0001F600-\U0001F64F]|"     # Emoticons 
            r"[\U0001F300-\U0001F5FF]|"     # Miscellaneous Symbols and Pictographs
            r"[\U0001F680-\U0001F6FF]|"     # Transport and Map Symbols
            r"[\U0001F700-\U0001F77F]|"     # Alchemical Symbols
            r"[\U0001F780-\U0001F7FF]|"     # Geometric Shapes Extended
            r"[\U0001F800-\U0001F8FF]|"     # Supplemental Arrows-C
            r"[\U0001F900-\U0001F9FF]|"     # Supplemental Symbols and Pictographs
            r"[\U0001FA00-\U0001FAFF]|"     # Chess Symbols
            r"[\U00002700-\U000027BF]|"     # Miscellaneous Symbols
            r"[\U0001F1E6-\U0001F1FF]|"     # Regional Indicator Symbols
            r"[\U0001F004-\U0001F0CF]|"     # Mahjong Tiles and Playing Cards
            r"[\U0001F9B0-\U0001F9FF]"      # Additional Emoji
            r")"
        )

        from cogs.yuna_automod.executor import execute_automod_action, get_threshold
        emoji_count = len(emoji_pattern.findall(message.content))
        threshold = await get_threshold(message.guild.id, 'Anti emoji spam', 5)

        if emoji_count >= threshold:
            await execute_automod_action(self.bot, message.guild, message.author, message.channel, message, 'Anti emoji spam', f'Emoji Spam ({emoji_count} emojis)')
            return True
        return False

    async def on_message(self, message):
        # Centralized in cogs.yuna_automod.pipeline
        pass

    @commands.Cog.listener()
    async def on_rate_limit(self, message):
        await asyncio.sleep(10)
