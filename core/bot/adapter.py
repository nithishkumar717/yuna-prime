import discord
from discord.ext import commands
from core.event_bus import EventDispatcher
from .events import MemberJoinedEvent
from core.logging import get_logger


class DiscordAdapter:
    """Translates Discord events strictly into internal Event Bus events, containing no business logic."""

    def __init__(self, bot: commands.Bot, event_bus: EventDispatcher) -> None:
        self.bot = bot
        self.event_bus = event_bus
        self.logger = get_logger("BOT", "DiscordAdapter")
        self._register_listeners()

    def _register_listeners(self) -> None:
        self.bot.add_listener(self.on_member_join, "on_member_join")

    async def on_member_join(self, member: discord.Member) -> None:
        self.logger.info(
            f"Translating MemberJoinedEvent for {member.id}", event="AdapterTranslation"
        )
        event = MemberJoinedEvent(
            member_id=member.id,
            guild_id=member.guild.id,  # type: ignore
            member_name=member.name,
        )
        await self.event_bus.publish(event)
