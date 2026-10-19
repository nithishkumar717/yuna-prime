from discord.ext import commands


class _antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Security and Antinuke commands"""

    def help_custom(self):
        emoji = '🛡️'
        label = "Security Commands"
        description = "Advanced anti-nuke, bot guard and server security controls."
        return emoji, label, description

    @commands.group()
    async def __AntiNuke__(self, ctx: commands.Context):
        """__**Master Security UI Control Center**__
`security` (Interactive Panel: Protection Hub [Anti-Nuke & Bot Protection], Extra Owners, Whitelist Hub, Nightmode)

__**Protection Hub (Anti-Nuke & Bot Protection Engine)**__
`antinuke` , `antinuke enable` , `antinuke disable` , `antinuke config` , `antinuke logging <#channel>`
`botprotection` (Enable / Disable Periodic Audit & Rolling Window Filter; Instant Kick / Ban Bot, Ban / Kick / Demote Inviter)

__**Whitelist Hub & Extra Owners**__
`whitelist` (All Access Users & Trusted Staff Roles) , `whitelist add <user/role>` , `whitelist remove <user/role>` , `whitelisted` , `whitelist reset`
`extraowner` , `extraowner set <@user>` , `extraowner view` , `extraowner reset`

__**Whitelisted Bot System (Interactive Bot Protection)**__
`whitelistbot` , `whitelistbot add <bot/ID>` , `whitelistbot remove <bot/ID>` , `whitelistbot list` (Whitelisted vs Unwhitelisted Status) , `whitelistbot reset`
*(Select Menu: Select any bot from server directly via interactive dropdown to whitelist)*

__**Nightmode & Block Guard (12:00 AM – 6:00 AM IST)**__
`nightmode` , `nightmode enable` , `nightmode disable` , `nightmode config` , `nightmode roles` , `nightmode auto enable` , `nightmode auto disable` , `nightmode auto status` , `block <@user/guild_id>` , `unblock <@user/guild_id>` , `blocked`

__**Emergency Situation System**__
`emergency` , `emergency enable` , `emergency disable` , `emergency status` , `emergency role add/remove/list` , `emergency authorise add/remove/list`"""
