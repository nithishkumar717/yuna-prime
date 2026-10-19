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

"""
Welcome & Server Join Layout Builder using Discord Components V2 (CV2).
Constructs a native Discord LayoutView card hierarchy matching the reference card design:
- Top Greeting Content
- CV2 Container (accent_color=0x2b2d31)
  - Section with TextDisplay and Thumbnail accessory
  - ActionRow with Invite & Support Server buttons
  - Muted Footer TextDisplay
Includes resilient fallback to traditional Embed + View for legacy clients.
"""

from typing import Optional, Union, Tuple
import discord
from discord.ui import (
    LayoutView,
    Container,
    Section,
    Thumbnail,
    TextDisplay,
    ActionRow,
    Button,
    View,
)

try:
    from utils.emoji import ZYUNA_GLOBAL as WELCOME_EMOJI
except Exception:
    WELCOME_EMOJI = "<:zyrox_global:1561460971749380226>"

WELCOME_ACCENT_COLOR = 0x2B2D31
WELCOME_FOOTER_TEXT = "YUNA • High-Performance Multipurpose Architecture"


def build_welcome_greeting_payload(
    guild: discord.Guild,
    adder: Optional[Union[discord.Member, discord.User]],
    bot: discord.Client,
    prefix: str = "$",
    support_url: str = "https://discord.gg/YzHCx5yQXv",
    invite_url: str = "",
) -> Tuple[str, LayoutView, discord.Embed, View]:
    """
    Builds the welcome greeting components.
    
    Returns:
        (content, cv2_view, fallback_embed, fallback_view)
    """
    if not invite_url and bot.user:
        invite_url = (
            f"https://discord.com/oauth2/authorize?client_id={bot.user.id}"
            f"&permissions=8&scope=bot%20applications.commands"
        )

    bot_name = bot.user.name if bot.user else "YUNA"
    adder_name = adder.display_name if adder else "there"
    
    # Outer greeting
    content = f"{WELCOME_EMOJI} **Hey ! {adder_name} , I am {bot_name}!**"

    # User avatar thumbnail resolution
    thumbnail_url = adder.display_avatar.url if adder else (
        bot.user.display_avatar.url if bot.user else (
            guild.icon.url if guild.icon else None
        )
    )

    # Core instruction text
    body_text = (
        f"» Thanks for adding me to {guild.name}!\n"
        f"» Type `{prefix}help` or `{prefix}h` to dive in.\n"
        f"» Fully equipped: Antinuke · Music · Automod & more."
    )

    # ── 1. Components V2 (CV2) LayoutView ──────────────────────────────────────
    cv2_view = LayoutView(timeout=None)
    container = Container(accent_color=WELCOME_ACCENT_COLOR)

    section = Section(TextDisplay(body_text))
    container.add_item(section)
    
    action_row = ActionRow(
        Button(label="Invite Bot", style=discord.ButtonStyle.link, url=invite_url),
        Button(label="Support Server", style=discord.ButtonStyle.link, url=support_url),
    )
    container.add_item(action_row)
    container.add_item(TextDisplay(WELCOME_FOOTER_TEXT))
    
    cv2_view.add_item(container)

    # ── 2. Fallback Embed & Standard View ─────────────────────────────────────
    fallback_embed = discord.Embed(
        description=body_text,
        color=WELCOME_ACCENT_COLOR,
    )
    fallback_embed.set_footer(text=WELCOME_FOOTER_TEXT)

    fallback_view = View(timeout=None)
    fallback_view.add_item(Button(label="Invite Bot", style=discord.ButtonStyle.link, url=invite_url))
    fallback_view.add_item(Button(label="Support Server", style=discord.ButtonStyle.link, url=support_url))

    return content, cv2_view, fallback_embed, fallback_view
