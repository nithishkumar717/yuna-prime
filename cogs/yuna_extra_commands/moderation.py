from discord.ext import commands


class _moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Moderation commands"""

    def help_custom(self):
        emoji = '🌸'
        label = "Moderation Commands"
        description = "Manage members, channels, roles and server actions."
        return emoji, label, description

    @commands.group()
    async def __Moderation__(self, ctx: commands.Context):
        """__**Member Discipline**__
`ban <@user> [reason]` , `unban <user_id> [reason]` , `unbanall` , `kick <@user> [reason]` , `warn <@user> [reason]` , `clearwarns <@user>` , `audit [limit]` , `mute <@user> [duration]` , `unmute <@user>` , `timeout <@user> <duration> [reason]` , `untimeout <@user>` , `nick <@user> [new_nick]` , `snipe`

__**Channel Controls & Security**__
`lock [#channel]` , `unlock [#channel]` , `lockall` , `unlockall` , `hide [#channel]` , `unhide [#channel]` , `hideall` , `unhideall` , `slowmode <seconds>` , `unslowmode` , `nuke` , `clone [#channel]`

__**Advanced Purge Utilities**__
`clear <amount>` , `purge all <amount>` , `purge bots <amount>` , `purge contains <text> <amount>` , `purge embeds <amount>` , `purge files <amount>` , `purge images <amount>` , `purge mentions <amount>` , `purge reactions <amount>` , `purge user <@user> <amount>`

__**Role Administration & Topcheck**__
`role <@user> <@role>` , `role create <name>` , `role delete <@role>` , `role rename <@role> <new_name>` , `role all <@role>` , `role humans <@role>` , `role bots <@role>` , `role unverified <@role>` , `role temp <@user> <@role> <time>` , `role icon <@role> <url/emoji>` , `topcheck <enable/disable>`"""