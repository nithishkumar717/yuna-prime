import discord
from discord.ext import commands
import aiosqlite
from datetime import timedelta
import asyncio

from cogs.yuna_automod.cache import automod_cache

class AntiMassMention(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mass_mention_threshold = 5

    async def is_automod_enabled(self, guild_id):
        return await automod_cache.is_automod_enabled(guild_id)

    async def is_anti_mass_mention_enabled(self, guild_id):
        return await automod_cache.is_rule_enabled(guild_id, "Anti mass mention")

    async def get_ignored_channels(self, guild_id):
        return await automod_cache.get_ignored_channels(guild_id)

    async def get_ignored_roles(self, guild_id):
        return await automod_cache.get_ignored_roles(guild_id)

    async def get_threshold(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT threshold FROM automod_thresholds WHERE guild_id = ? AND event = 'Anti mass mention'", (guild_id,))
            result = await cursor.fetchone()
            return result[0] if (result and result[0]) else 5

    async def get_punishment(self, guild_id):
        return await automod_cache.get_punishment(guild_id, "Anti mass mention")


    async def log_action(self, guild, user, channel, action, reason):
        async with aiosqlite.connect("db/automod.db") as db:
            cursor = await db.execute("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
            log_channel_id = await cursor.fetchone()

        if log_channel_id and log_channel_id[0]:
            log_channel = guild.get_channel(log_channel_id[0])
            if log_channel:
                embed = discord.Embed(title="Automod Log: Anti Mass Mention", color=0xff0000)
                embed.add_field(name="User", value=user.mention, inline=False)
                embed.add_field(name="Action Taken", value=action, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Channel", value=channel.mention, inline=False)
                embed.set_footer(text=f"User ID: {user.id}")
                await log_channel.send(embed=embed)

    async def check_mentions(self, message: discord.Message) -> bool:
        from cogs.yuna_automod.executor import execute_automod_action, get_threshold
        mention_count = max(
            message.content.count("<@"),
            len(getattr(message, "mentions", [])) + len(getattr(message, "role_mentions", []))
        )
        threshold = await get_threshold(message.guild.id, 'Anti mass mention', 5)
        if mention_count >= threshold:
            await execute_automod_action(self.bot, message.guild, message.author, message.channel, message, 'Anti mass mention', f'Mass Mention ({mention_count} mentions)')
            return True
        return False

    async def on_message(self, message):
        # Centralized in cogs.yuna_automod.pipeline
        pass

    @commands.Cog.listener()
    async def on_rate_limit(self, message):
        await asyncio.sleep(10)

