import discord


class PresenceManager:
    """Encapsulates Discord Activity state modifications seamlessly."""

    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot

    async def set_maintenance(self) -> None:
        await self.bot.change_presence(
            status=discord.Status.dnd, activity=discord.Game(name="Maintenance Mode")
        )

    async def set_healthy(self) -> None:
        await self.bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="over the network"
            ),
        )
