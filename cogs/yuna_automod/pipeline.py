"""
Consolidated Automod Pipeline for YUNA.
Runs a single pre-flight immunity, permission, and channel/role check before
evaluating enabled rules in prioritized order:
(antispam -> antilink -> anti_invites -> anticaps -> anti_mass_mention -> anti_emoji_spam).
Aborts immediately when a violation is punished.
"""

import discord
from cogs.yuna_automod.cache import automod_cache

async def process_automod(bot, message: discord.Message) -> bool:
    """
    Evaluates message against all active automod rules in a single fast pass.
    Returns True if a violation was found and handled (message deleted/punished), False otherwise.
    """
    if not message.guild or message.author.id == bot.user.id or message.author.bot:
        return False

    guild = message.guild
    user = message.author
    channel = message.channel
    guild_id = guild.id

    # 1. Check if automod overall is enabled for this guild (<0.001ms RAM check)
    if not await automod_cache.is_automod_enabled(guild_id):
        return False

    # 2. Fast bypass for guild owner and administrators (1 check for all rules)
    if user == guild.owner or (getattr(user, "guild_permissions", None) and user.guild_permissions.administrator):
        return False

    # 3. Check ignored channels & roles (1 check for all rules)
    ignored_channels = await automod_cache.get_ignored_channels(guild_id)
    if channel.id in ignored_channels:
        return False

    if hasattr(user, "roles"):
        ignored_roles = await automod_cache.get_ignored_roles(guild_id)
        if any(role.id in ignored_roles for role in user.roles):
            return False

    # 4. Antispam Check
    antispam_cog = bot.get_cog("antispam")
    if antispam_cog and hasattr(antispam_cog, "check_spam"):
        violated = await antispam_cog.check_spam(message)
        if violated:
            return True

    # 5. Antilink Check
    if await automod_cache.is_rule_enabled(guild_id, "Anti link"):
        antilink_cog = bot.get_cog("antilink")
        if antilink_cog and hasattr(antilink_cog, "check_link"):
            violated = await antilink_cog.check_link(message)
            if violated:
                return True

    # 6. Anti-Invites Check
    if await automod_cache.is_rule_enabled(guild_id, "Anti invites"):
        invites_cog = bot.get_cog("anti_invites")
        if invites_cog and hasattr(invites_cog, "check_invites"):
            violated = await invites_cog.check_invites(message)
            if violated:
                return True

    # 7. Anti-Caps Check
    if await automod_cache.is_rule_enabled(guild_id, "Anti caps"):
        anticaps_cog = bot.get_cog("anticaps")
        if anticaps_cog and hasattr(anticaps_cog, "check_caps"):
            violated = await anticaps_cog.check_caps(message)
            if violated:
                return True

    # 8. Anti-Mass-Mention Check
    if await automod_cache.is_rule_enabled(guild_id, "Anti mass mention"):
        mention_cog = bot.get_cog("anti_mass_mention")
        if mention_cog and hasattr(mention_cog, "check_mentions"):
            violated = await mention_cog.check_mentions(message)
            if violated:
                return True

    # 9. Anti-Emoji-Spam Check
    if await automod_cache.is_rule_enabled(guild_id, "Anti emoji spam"):
        emoji_cog = bot.get_cog("anti_emoji_spam")
        if emoji_cog and hasattr(emoji_cog, "check_emoji"):
            violated = await emoji_cog.check_emoji(message)
            if violated:
                return True

    return False
