"""Discord Components V2 layout used for honeypot warning messages."""

import discord

HONEYPOT_REACTIONS = ("🍯", "🚫", "⚠️", "👀", "🔒")


def build_honeypot_warning_view(warning: str) -> discord.ui.LayoutView:
    """Turn the dashboard's multiline warning text into an orange V2 card."""
    lines = warning.splitlines()
    first_content_line = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first_content_line is None:
        heading = "🍯 **DO NOT POST HERE**"
        body = "This channel is a honeypot trap. Any message here triggers automatic moderation."
    else:
        heading = lines[first_content_line].strip()
        body = "\n".join(lines[first_content_line + 1:]).strip()
        if not heading.startswith("#"):
            heading = f"## {heading}"

    view = discord.ui.LayoutView(timeout=None)
    card = discord.ui.Container(accent_color=0xF39C12)
    card.add_item(discord.ui.TextDisplay(heading))
    if body:
        card.add_item(discord.ui.Separator())
        card.add_item(discord.ui.TextDisplay(body))
    view.add_item(card)
    return view


async def add_honeypot_reactions(message: discord.Message) -> None:
    """Add several quick reactions to the pinned honeypot warning."""
    existing = {str(reaction.emoji) for reaction in message.reactions}
    for emoji in HONEYPOT_REACTIONS:
        if emoji in existing:
            continue
        try:
            await message.add_reaction(emoji)
        except (discord.Forbidden, discord.HTTPException):
            # Keep trying the remaining reactions if one cannot be added.
            continue
