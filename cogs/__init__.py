from __future__ import annotations
from core import BotBase
from colorama import Fore, Style, init

# ==============================================================================
# SECURITY COMMAND SUITE
# ==============================================================================
from .yuna_commands.help import Help
from .yuna_commands.antinuke import Antinuke
from .yuna_commands.anti_wl import Whitelist
from .yuna_commands.anti_unwl import Unwhitelist
from .yuna_commands.extraown import Extraowner
from .yuna_commands.whitelist_bot import BotWhitelist
from .yuna_commands.automod import Automod
from .yuna_commands.antiraid import AntiRaidCommands
from .yuna_commands.security_filters import SecurityFilterCommands
from .yuna_commands.nightmode import Nightmode
from .yuna_commands.emergency import Emergency
from .yuna_commands.security_dashboard import SecurityDashboard
from .yuna_commands.audit_tools import AuditTools
from .yuna_commands.server_logs import ServerLogs
from .yuna_commands.blacklist import Blacklist
from .yuna_commands.owner import Owner
from .yuna_commands.gitpull import GitPull
from .yuna_commands.backup import ServerBackup
from .yuna_commands.ping import Ping

# ==============================================================================
# GUIDE HELPERS (SECURITY FOCUSED)
# ==============================================================================
from .yuna_extra_commands.antinuke import _antinuke
from .yuna_extra_commands.automod import _automod
from .yuna_extra_commands.moderation import _moderation

# ==============================================================================
# CORE SECURITY EVENTS & HANDLERS
# ==============================================================================
from .yuna_events.Errors import Errors
from .yuna_events.autoblacklist import AutoBlacklist
from .yuna_events.on_guild import Guild

# ==============================================================================
# ANTINUKE V2 & ANTI-RAID REAL-TIME LISTENERS
# ==============================================================================
from .yuna_antinuke.antiraid import AntiRaid
from .yuna_antinuke.anti_member_update import AntiMemberUpdate
from .yuna_antinuke.antiban import AntiBan
from .yuna_antinuke.antibotadd import AntiBotAdd
from .yuna_antinuke.antichcr import AntiChannelCreate
from .yuna_antinuke.antichdl import AntiChannelDelete
from .yuna_antinuke.antichup import AntiChannelUpdate
from .yuna_antinuke.antieveryone import AntiEveryone
from .yuna_antinuke.antiguild import AntiGuildUpdate
from .yuna_antinuke.antiIntegration import AntiIntegration
from .yuna_antinuke.antikick import AntiKick
from .yuna_antinuke.antiprune import AntiPrune
from .yuna_antinuke.antirlcr import AntiRoleCreate
from .yuna_antinuke.antirldl import AntiRoleDelete
from .yuna_antinuke.antirlup import AntiRoleUpdate
from .yuna_antinuke.antiwebhook import AntiWebhookUpdate
from .yuna_antinuke.antiwebhookcr import AntiWebhookCreate
from .yuna_antinuke.antiwebhookdl import AntiWebhookDelete
from .yuna_antinuke.audit_stream_antinuke import AuditStreamAntiNuke

# ==============================================================================
# AUTOMOD REAL-TIME LISTENERS
# ==============================================================================
from .yuna_automod.antispam import AntiSpam
from .yuna_automod.anticaps import AntiCaps
from .yuna_automod.antilink import AntiLink
from .yuna_automod.anti_invites import AntiInvite
from .yuna_automod.anti_mass_mention import AntiMassMention
from .yuna_automod.anti_emoji_spam import AntiEmojiSpam

# ==============================================================================
# MODERATION COMMAND SUITE
# ==============================================================================
from .yuna_moderation.ban import Ban
from .yuna_moderation.unban import Unban
from .yuna_moderation.timeout import Mute
from .yuna_moderation.unmute import Unmute
from .yuna_moderation.lock import Lock
from .yuna_moderation.unlock import Unlock
from .yuna_moderation.hide import Hide
from .yuna_moderation.unhide import Unhide
from .yuna_moderation.kick import Kick
from .yuna_moderation.warn import Warn
from .yuna_moderation.role import Role
from .yuna_moderation.message import Message
from .yuna_moderation.moderation import Moderation
from .yuna_moderation.topcheck import TopCheck
from .yuna_moderation.snipe import Snipe


async def setup(bot: BotBase):
    """Registers dedicated security, antinuke, automod, and moderation modules."""
    cogs_to_load = [
        # Help & Info
        Help,
        # Core Security & Access Control
        Antinuke, Whitelist, Unwhitelist, Extraowner, BotWhitelist,
        AntiRaidCommands, Automod, Nightmode, Emergency, SecurityDashboard, AuditTools,
        SecurityFilterCommands,
        ServerLogs, Blacklist, Owner, GitPull, ServerBackup, Ping,
        
        # Security Guides
        _antinuke, _automod, _moderation,
        
        # System & Gateway Events
        Errors, AutoBlacklist, Guild,
        
        # Anti-Nuke V2 & Anti-Raid Gateway Listeners
        AntiRaid,
        AntiMemberUpdate, AntiBan, AntiBotAdd, AntiChannelCreate, AntiChannelDelete,
        AntiChannelUpdate, AntiEveryone, AntiGuildUpdate, AntiIntegration, AntiKick,
        AntiPrune, AntiRoleCreate, AntiRoleDelete, AntiRoleUpdate, AntiWebhookUpdate,
        AntiWebhookCreate, AntiWebhookDelete, AuditStreamAntiNuke,
        
        # AutoMod Event Listeners
        AntiSpam, AntiCaps, AntiLink, AntiInvite, AntiMassMention, AntiEmojiSpam,
        
        # Moderation Commands
        Ban, Unban, Mute, Unmute, Lock, Unlock, Hide, Unhide, Kick, Warn,
        Role, Message, Moderation, TopCheck, Snipe
    ]

    loaded = 0
    failed = 0
    for cog_class in cogs_to_load:
        if cog_class is None:
            continue
        cog_name = getattr(cog_class, '__name__', str(cog_class))
        if bot.get_cog(cog_name):
            continue
        try:
            await bot.add_cog(cog_class(bot))
            print(Fore.GREEN + Style.BRIGHT + f"[SUPREME COG] Loaded: {cog_name}")
            loaded += 1
        except Exception as e:
            print(Fore.RED + Style.BRIGHT + f"[SUPREME COG WARNING] Skipped {cog_name}: {e}")
            failed += 1

    print(Fore.CYAN + Style.BRIGHT + f"[YUNA SUPREME] Modules Processed: ({loaded} loaded, {failed} failed).")
