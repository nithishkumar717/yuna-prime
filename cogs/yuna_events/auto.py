# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                  ║
# ║   ░█▄░█░█▀▀░█▀▄░█▀▄   ░█░█   ░█░░░▀█▀░█░█░█▀▀                 ║
# ║   ░█░▀█░█▀▀░█▀▄░█░█   ░▄▀▄   ░█░░░░█░░▀▄▀░█▀▀                 ║
# ║   ░▀░░▀░▀▀▀░▀░▀░▀▀░   ░▀░▀   ░▀▀▀░▀█▀░░▀░░▀▀▀                 ║
# ║                                                                  ║
# ║            © 2026 Nerd X Live — All Rights Reserved             ║
# ║                                                                  ║
# ║   discord  ──  https://discord.gg/YzHCx5yQXv                    ║
# ║   github   ──  https://github.com/nithishkumar717/zyuna         ║
# ║                                                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

import discord
from discord.utils import *
try:
    from bot.core import zyuna, Cog
    from bot.utils.Tools import *
    from bot.utils.config import BotName, BRAND_NAME, serverLink, websiteLink
except (ImportError, ModuleNotFoundError):
    from core import zyuna, Cog
    from utils.Tools import *
    from utils.config import BotName, BRAND_NAME, serverLink, websiteLink
from discord.ext import commands
from discord.ui import Button, View

class Autorole(Cog):
    def __init__(self, bot: zyuna):
       self.bot = bot

    @commands.Cog.listener(name="on_guild_join")
    async def send_msg_to_adder(self, guild: discord.Guild):
        async for entry in guild.audit_logs(limit=3):
            if entry.action == discord.AuditLogAction.bot_add:
                try:
                    prefix_data = await getConfig(guild.id)
                    prefix = prefix_data.get("prefix", "$")
                except Exception:
                    prefix = "$"

                bot_name = BRAND_NAME if BRAND_NAME else (self.bot.user.name if self.bot.user else "Zyuna")
                adder_name = entry.user.display_name if entry.user else "there"
                invite_url = f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"
                support_url = serverLink if serverLink else "https://discord.gg/YzHCx5yQXv"

                # Message header content
                content = f"🧙 **Hey ! {adder_name} , I am {bot_name}!**"

                # Modern sleek card embed
                embed = discord.Embed(
                    description=(
                        f"» **Thanks for adding me to {guild.name}!**\n"
                        f"» Type `{prefix}help` or `{prefix}h` to dive in.\n"
                        f"» Fully equipped: Antinuke · Music · Automod & more."
                    ),
                    color=0x474851
                )

                embed.set_footer(text=f"{bot_name}! • Multipurpose • No fillers")

                invite_button = Button(
                    label="Invite Bot",
                    style=discord.ButtonStyle.link,
                    url=invite_url
                )
                support_button = Button(
                    label="Support Server",
                    style=discord.ButtonStyle.link,
                    url=support_url
                )
                view = View()
                view.add_item(invite_button)
                view.add_item(support_button)

                try:
                    await entry.user.send(content=content, embed=embed, view=view)
                except Exception as e:
                    print(f"Failed to send welcome DM: {e}")
