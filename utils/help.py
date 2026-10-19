import discord
from discord import ui
from typing import Dict, Any, Optional

EMBED_COLOR = 0x2b2d31  # Premium Dark SaaS Color

# Complete & Comprehensive Structured Data for Yuna Supreme Security Help Center
SAAS_HELP_DATA: Dict[str, Dict[str, Any]] = {
    "Security": {
        "desc": "Autonomous Anti-Nuke V2, sub-15ms TurboBan, whitelisting and threat containment.",
        "sections": {
            "Protection Hub": {
                "desc": "Configure Anti-Nuke V2 autonomous defense, rate limits and recovery actions.",
                "commands": [
                    "antinuke", "antinuke enable", "antinuke disable",
                    "antinuke config", "antinuke logging <#channel>", "security", "security status"
                ]
            },
            "Whitelist & Owners": {
                "desc": "Manage trusted staff whitelists and extra server owners with full bypass immunity.",
                "commands": [
                    "whitelist", "whitelist add <@user/@role>", "whitelist remove <@user/@role>",
                    "whitelisted", "whitelist reset", "extraowner", "extraowner set <@user>",
                    "extraowner view", "extraowner reset"
                ]
            },
            "Bot Protection": {
                "desc": "Control unauthorized bot joins and manage verified bot exemptions.",
                "commands": [
                    "whitelistbot", "whitelistbot add <bot/ID>", "whitelistbot remove <bot/ID>",
                    "whitelistbot list", "whitelistbot reset"
                ]
            },
            "Nightmode": {
                "desc": "Automate overnight permissions freeze, role isolation and raid lockdown.",
                "commands": [
                    "nightmode", "nightmode enable", "nightmode disable", "nightmode config",
                    "nightmode roles", "nightmode auto enable", "nightmode auto disable",
                    "nightmode auto status", "block <@user/id>", "unblock <@user/id>", "blocked"
                ]
            },
            "Emergency Lockdown": {
                "desc": "Trigger immediate server isolation, emergency channel lockdown and quarantine rogue staff.",
                "commands": [
                    "emergency", "emergency enable", "emergency disable", "emergency status",
                    "emergency role add/remove/list", "emergency authorise add/remove/list",
                    "emergency quarantine <@user>"
                ]
            }
        }
    },
    "AutoMod": {
        "desc": "Real-time threat filtering: spam, dangerous links, invite exploits and mass mentions.",
        "sections": {
            "Threat Filters": {
                "desc": "Instant automated action against high-frequency spam and malicious exploits.",
                "commands": [
                    "automod", "antispam <enable/disable>", "anticaps <enable/disable>", "antilink <enable/disable>",
                    "antiinvite <enable/disable>", "anti_mass_mention <enable/disable>",
                    "anti_emoji_spam <enable/disable>", "antieveryone <enable/disable>"
                ]
            },
            "Word Filter": {
                "desc": "Manage server blacklisted words, regex filters and channel/role bypasses.",
                "commands": [
                    "blacklistword", "blacklistword add <word>", "blacklistword remove <word>",
                    "blacklistword config", "blacklistword reset",
                    "blacklistword bypass add <#channel/@role>", "blacklistword bypass remove <#channel/@role>",
                    "blacklistword bypass show", "blacklist"
                ]
            },
            "AutoMod Configuration": {
                "desc": "Set punishment rules (mute/kick/ban), exempt channels and configure logging.",
                "commands": [
                    "automod logging <#channel>", "automod ignore <#channel/@role>",
                    "automod unignore <#channel/@role>", "automod punishment <timeout/kick/ban>"
                ]
            }
        }
    },
    "Moderation": {
        "desc": "Advanced staff tools: instant discipline, channel locks, purge filters and honeypot traps.",
        "sections": {
            "Member Discipline": {
                "desc": "Ban, unban, kick, warn, timeout and manage member disciplinary actions.",
                "commands": [
                    "ban <@user> [reason]", "unban <id> [reason]", "kick <@user> [reason]",
                    "mute / timeout <@user> <duration> [reason]", "unmute / untimeout <@user>",
                    "warn <@user> [reason]", "clearwarns <@user>", "nick <@user> [new_nick]",
                    "snipe", "honeypot setup <#channel>"
                ]
            },
            "Channel Management": {
                "desc": "Instant channel lockdowns, hide permissions, slowmode and cloning.",
                "commands": [
                    "lock [#channel]", "unlock [#channel]", "lockall", "unlockall",
                    "hide [#channel]", "unhide [#channel]", "hideall", "unhideall",
                    "slowmode <seconds>", "unslowmode", "nuke", "clone [#channel]"
                ]
            },
            "Message Purge": {
                "desc": "Targeted bulk message deletion with intelligent filtering.",
                "commands": [
                    "clear <amount>", "purge all <amount>", "purge bots <amount>",
                    "purge contains <text> <amount>", "purge embeds <amount>", "purge files <amount>",
                    "purge images <amount>", "purge mentions <amount>", "purge user <@user> <amount>"
                ]
            },
            "Role Management": {
                "desc": "Assign, create, delete, modify and mass-manage server roles.",
                "commands": [
                    "role <@user> <@role>", "role create <name>", "role delete <@role>",
                    "role rename <@role> <name>", "role all <@role>", "role humans <@role>",
                    "role bots <@role>", "massrole add/remove <humans/bots> <@role>", "topcheck <enable/disable>"
                ]
            }
        }
    },
    "Logging": {
        "desc": "Forensic audit logging, real-time security alerts and incident tracing.",
        "sections": {
            "Server Logs": {
                "desc": "Route server events to dedicated audit channels with rich formatted logs.",
                "commands": [
                    "logs setup", "logs config", "logs status", "logs channel <category> <#channel>",
                    "logs reset"
                ]
            },
            "Audit Trail": {
                "desc": "Inspect recent staff actions, track anomaly events and review audit entries.",
                "commands": [
                    "audit [limit]", "audit user <@user>", "audit action <ban/kick/role_delete>"
                ]
            }
        }
    }
}


class CategorySelect(ui.Select):
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(
                label=cat_name,
                value=cat_name,
                description=cat_data["desc"][:100]
            )
            for cat_name, cat_data in SAAS_HELP_DATA.items()
        ]
        super().__init__(
            placeholder="Select a security category...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.invoker:
            return await interaction.response.send_message("This menu belongs to someone else.", ephemeral=True)

        selected_cat = self.values[0]
        self.parent_view.current_category = selected_cat
        self.parent_view.current_section = None
        await self.parent_view.update_view(interaction)


class SectionSelect(ui.Select):
    def __init__(self, parent_view, category_name: str):
        cat_data = SAAS_HELP_DATA.get(category_name, {})
        sections = cat_data.get("sections", {})

        options = [
            discord.SelectOption(
                label=sec_name,
                value=sec_name,
                description=sec_data["desc"][:100]
            )
            for sec_name, sec_data in sections.items()
        ]

        super().__init__(
            placeholder="Select a module section...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.invoker:
            return await interaction.response.send_message("This menu belongs to someone else.", ephemeral=True)

        selected_sec = self.values[0]
        self.parent_view.current_section = selected_sec
        await self.parent_view.update_view(interaction)


class BackButton(ui.Button):
    def __init__(self, parent_view):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.invoker:
            return await interaction.response.send_message("This menu belongs to someone else.", ephemeral=True)

        if self.parent_view.current_section:
            self.parent_view.current_section = None
        elif self.parent_view.current_category:
            self.parent_view.current_category = None

        await self.parent_view.update_view(interaction)


class SaaSView(ui.LayoutView):
    def __init__(self, ctx, initial_category: Optional[str] = None):
        super().__init__(timeout=180.0)
        self.ctx = ctx
        self.invoker = ctx.author
        self.current_category: Optional[str] = initial_category
        self.current_section: Optional[str] = None
        self.build_components()

    def build_components(self):
        self.clear_items()
        container = ui.Container(accent_color=EMBED_COLOR)

        if self.current_category is None:
            # Level 1: Main Security Hub
            from utils.support_utils import get_support_url
            support_url = get_support_url(getattr(self.ctx, 'bot', None))
            prefix = getattr(self.ctx, 'prefix', '$') or '$'
            content = (
                "**🛡️ YUNA SUPREME**\n"
                "Dedicated Security & Moderation Center\n\n"
                "Sub-15ms Anti-Nuke V2 • Autonomous Threat Containment • Enterprise AutoMod\n\n"
                "────────────────────────\n\n"
                f"• **Modules:** `{len(SAAS_HELP_DATA)} Security Domains`\n"
                f"• **Active Prefix:** `{prefix}`\n"
                f"• **Architecture:** Pure Security Isolation (100% Dedicated Rate Limit Bucket)\n"
                f"• **Support:** **[Official Support Server]({support_url})**\n\n"
                "Select a category below to explore security controls.\n\n"
                "────────────────────────\n"
                "YUNA SUPREME • Ultra-Low Latency Defense Core"
            )
            container.add_item(ui.TextDisplay(content))
            row = ui.ActionRow()
            row.add_item(CategorySelect(self))
            container.add_item(row)

        elif self.current_section is None:
            # Level 2: Category Overview
            cat_data = SAAS_HELP_DATA.get(self.current_category, {})
            sections_dict = cat_data.get("sections", {})
            sec_names = "\n".join([f"• **{s}**" for s in sections_dict.keys()])

            content = (
                f"**🛡️ YUNA SUPREME • {self.current_category.upper()}**\n\n"
                f"*{cat_data.get('desc', '')}*\n\n"
                "────────────────────────\n\n"
                f"**Available Modules:**\n{sec_names}\n\n"
                "Select a module from the dropdown below to view exact command usage.\n\n"
                "────────────────────────\n"
                "YUNA SUPREME • Security Core"
            )
            container.add_item(ui.TextDisplay(content))
            row1 = ui.ActionRow()
            row1.add_item(SectionSelect(self, self.current_category))
            container.add_item(row1)

            row2 = ui.ActionRow()
            row2.add_item(BackButton(self))
            container.add_item(row2)

        else:
            # Level 3: Section Detail
            cat_data = SAAS_HELP_DATA.get(self.current_category, {})
            sec_data = cat_data.get("sections", {}).get(self.current_section, {})
            cmds = sec_data.get("commands", [])
            prefix = getattr(self.ctx, 'prefix', '$') or '$'
            cmd_formatted = "\n".join([f"• `{prefix}{c}`" for c in cmds]) if cmds else "`No commands found`"

            content = (
                f"**🛡️ YUNA SUPREME • {self.current_category} / {self.current_section}**\n\n"
                f"*{sec_data.get('desc', '')}*\n\n"
                "────────────────────────\n\n"
                f"**Command Syntax:**\n{cmd_formatted}\n\n"
                "────────────────────────\n"
                "YUNA SUPREME • Security Core"
            )
            container.add_item(ui.TextDisplay(content))
            row = ui.ActionRow()
            row.add_item(BackButton(self))
            container.add_item(row)

        self.add_item(container)

    def build_embed(self) -> discord.Embed:
        prefix = getattr(self.ctx, 'prefix', '$') or '$'
        from utils.support_utils import get_support_url
        support_url = get_support_url(getattr(self.ctx, 'bot', None))

        if self.current_category is None:
            embed = discord.Embed(
                title="🛡️ YUNA SUPREME • Security Center",
                description=(
                    "Dedicated Autonomous Protection & Ultra-Low-Latency Containment.\n\n"
                    "────────────────────────\n\n"
                    f"• **Modules:** `{len(SAAS_HELP_DATA)} Security Domains`\n"
                    f"• **Prefix:** `{prefix}`\n"
                    "• **Engine:** Anti-Nuke V2 TurboBan (Sub-15ms Dispatch)\n"
                    f"• **Support:** **[Official Support Server]({support_url})**\n\n"
                    "Select a category below to explore security controls."
                ),
                color=EMBED_COLOR
            )
            embed.set_footer(text="YUNA SUPREME • Ultra-Low Latency Defense Core")
            return embed

        cat_data = SAAS_HELP_DATA.get(self.current_category, {})

        if self.current_section is None:
            sections_dict = cat_data.get("sections", {})
            sec_names = "\n".join([f"• **{s}**" for s in sections_dict.keys()])

            embed = discord.Embed(
                title=f"🛡️ YUNA SUPREME • {self.current_category}",
                description=(
                    f"*{cat_data.get('desc', '')}*\n\n"
                    "────────────────────────\n\n"
                    f"**Available Modules:**\n{sec_names}\n\n"
                    "Select a module from the dropdown below to view exact command usage."
                ),
                color=EMBED_COLOR
            )
            embed.set_footer(text="YUNA SUPREME • Security Core")
            return embed

        sec_data = cat_data.get("sections", {}).get(self.current_section, {})
        cmds = sec_data.get("commands", [])
        cmd_formatted = "\n".join([f"• `{prefix}{c}`" for c in cmds]) if cmds else "`No commands found`"

        embed = discord.Embed(
            title=f"🛡️ YUNA SUPREME • {self.current_category} / {self.current_section}",
            description=(
                f"*{sec_data.get('desc', '')}*\n\n"
                "────────────────────────\n\n"
                f"**Command Syntax:**\n{cmd_formatted}"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text="YUNA SUPREME • Security Core")
        return embed

    async def update_view(self, interaction: discord.Interaction):
        self.build_components()
        if not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        else:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)


View = SaaSView
