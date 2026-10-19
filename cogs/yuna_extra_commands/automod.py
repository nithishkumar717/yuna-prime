from discord.ext import commands


class _automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Automod commands"""

    def help_custom(self):
        emoji = '🌸'
        label = "Automod Commands"
        description = "Advanced spam, link, content and media protection."
        return emoji, label, description

    @commands.group()
    async def __AutoMod__(self, ctx: commands.Context):
        """__**Automod Interactive UI Dashboard**__
`automod` (Opens Full Button & Dropdown Control Panel) , `automod ignore <#channel/@role>` , `automod unignore <#channel/@role>` , `automod logging <#channel>`

__**Smart Threat Filters & External App Spam**__
`antispam <enable/disable>` , `anticaps <enable/disable>` , `antilink <enable/disable>` , `antiinvite <enable/disable>` , `anti_mass_mention <enable/disable>` , `anti_emoji_spam <enable/disable>`

__**Word Blacklist & Bypass Guard**__
`blacklistword` , `blacklistword add <word>` , `blacklistword remove <word>` , `blacklistword config` , `blacklistword reset` , `blacklistword bypass add <#channel/@role>` , `blacklistword bypass remove <#channel/@role>` , `blacklistword bypass show` , `blacklist`"""