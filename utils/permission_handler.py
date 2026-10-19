"""
Yuna V7 — Smart Missing Permission Notification System
Centralized, production-ready Missing Permission Handler across the entire Yuna Discord bot.

Features:
- Automatic permission & action detection
- Tailored administrator fix instructions (distinguishing server roles vs channel overwrites vs role hierarchy)
- Standardized warning embed format
- Intelligent delivery hierarchy (Channel -> User DM -> Server Mod/Audit Log -> Internal DB)
- Anti-spam cooldown protection to prevent notification loops
- Strictly avoids false positives (network glitches, rate limits, deleted resources)
"""

import time
import asyncio
from typing import Optional, Union, Dict, Tuple, Any, List, Set
from dataclasses import dataclass, field

import sys
import discord
from discord import app_commands
from discord.ext import commands


def _safe_log(msg: str):
    """Safely outputs log messages to stdout without failing on Windows terminal charmap encodings."""
    try:
        print(msg, flush=True)
    except (UnicodeEncodeError, Exception):
        try:
            encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
            safe_msg = str(msg).encode(encoding, errors="replace").decode(encoding, errors="replace")
            print(safe_msg, flush=True)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Discord Permission Display Name Mapping
# ---------------------------------------------------------------------------
DISCORD_PERM_NAMES: Dict[str, str] = {
    "add_reactions": "Add Reactions",
    "administrator": "Administrator",
    "attach_files": "Attach Files",
    "ban_members": "Ban Members",
    "change_nickname": "Change Nickname",
    "connect": "Connect",
    "create_events": "Create Events",
    "create_expressions": "Create Expressions",
    "create_instant_invite": "Create Instant Invite",
    "create_private_threads": "Create Private Threads",
    "create_public_threads": "Create Public Threads",
    "deafen_members": "Deafen Members",
    "embed_links": "Embed Links",
    "kick_members": "Kick Members",
    "manage_channels": "Manage Channels",
    "manage_emojis": "Manage Emojis and Stickers",
    "manage_emojis_and_stickers": "Manage Emojis and Stickers",
    "manage_events": "Manage Events",
    "manage_expressions": "Manage Expressions",
    "manage_guild": "Manage Server",
    "manage_messages": "Manage Messages",
    "manage_nicknames": "Manage Nicknames",
    "manage_permissions": "Manage Permissions",
    "manage_roles": "Manage Roles",
    "manage_threads": "Manage Threads",
    "manage_webhooks": "Manage Webhooks",
    "mention_everyone": "Mention Everyone",
    "moderate_members": "Moderate Members",
    "move_members": "Move Members",
    "mute_members": "Mute Members",
    "priority_speaker": "Priority Speaker",
    "read_message_history": "Read Message History",
    "read_messages": "View Channel",
    "request_to_speak": "Request to Speak",
    "send_messages": "Send Messages",
    "send_messages_in_threads": "Send Messages in Threads",
    "send_tts_messages": "Send TTS Messages",
    "send_voice_messages": "Send Voice Messages",
    "speak": "Speak",
    "stream": "Video / Stream",
    "use_application_commands": "Use Application Commands",
    "use_embedded_activities": "Use Embedded Activities",
    "use_external_emojis": "Use External Emojis",
    "use_external_sounds": "Use External Sounds",
    "use_external_stickers": "Use External Stickers",
    "use_soundboard": "Use Soundboard",
    "use_voice_activation": "Use Voice Activity",
    "view_audit_log": "View Audit Log",
    "view_channel": "View Channel",
    "view_guild_insights": "View Server Insights",
    "view_creator_monetization_analytics": "View Creator Monetization Analytics",
    "set_voice_channel_status": "Set Voice Channel Status",
}

# ---------------------------------------------------------------------------
# Command / Feature to Expected Action & Permission Mapping
# ---------------------------------------------------------------------------
COMMAND_ACTION_MAP: Dict[str, Tuple[str, str, str]] = {
    # Moderation commands
    "ban": ("Ban member", "Ban Members", "ban_members"),
    "unban": ("Unban member", "Ban Members", "ban_members"),
    "softban": ("Softban member", "Ban Members", "ban_members"),
    "kick": ("Kick member", "Kick Members", "kick_members"),
    "mute": ("Timeout member", "Moderate Members", "moderate_members"),
    "unmute": ("Remove timeout", "Moderate Members", "moderate_members"),
    "timeout": ("Timeout member", "Moderate Members", "moderate_members"),
    "untimeout": ("Remove timeout", "Moderate Members", "moderate_members"),
    "warn": ("Warn member", "Moderate Members", "moderate_members"),

    # Message management
    "purge": ("Delete messages", "Manage Messages", "manage_messages"),
    "clear": ("Delete messages", "Manage Messages", "manage_messages"),
    "clean": ("Delete messages", "Manage Messages", "manage_messages"),
    "snipe": ("Read message history", "Read Message History", "read_message_history"),
    "pin": ("Pin messages", "Manage Messages", "manage_messages"),
    "unpin": ("Unpin messages", "Manage Messages", "manage_messages"),

    # Channel management
    "lock": ("Lock channel", "Manage Channels", "manage_channels"),
    "unlock": ("Unlock channel", "Manage Channels", "manage_channels"),
    "hide": ("Hide channel", "Manage Channels", "manage_channels"),
    "unhide": ("Unhide channel", "Manage Channels", "manage_channels"),
    "slowmode": ("Modify channel settings", "Manage Channels", "manage_channels"),
    "channel": ("Create or modify channels", "Manage Channels", "manage_channels"),
    "clone": ("Clone channel", "Manage Channels", "manage_channels"),

    # Role management
    "role": ("Assign or remove roles", "Manage Roles", "manage_roles"),
    "giverole": ("Assign roles", "Manage Roles", "manage_roles"),
    "takerole": ("Remove roles", "Manage Roles", "manage_roles"),
    "addrole": ("Assign roles", "Manage Roles", "manage_roles"),
    "removerole": ("Remove roles", "Manage Roles", "manage_roles"),
    "autorole": ("Configure autoroles", "Manage Roles", "manage_roles"),
    "customrole": ("Manage custom roles", "Manage Roles", "manage_roles"),

    # Nicknames
    "nick": ("Change nickname", "Manage Nicknames", "manage_nicknames"),
    "nickname": ("Change nickname", "Manage Nicknames", "manage_nicknames"),
    "autonick": ("Change nicknames", "Manage Nicknames", "manage_nicknames"),
    "setnick": ("Change nickname", "Manage Nicknames", "manage_nicknames"),

    # Voice management
    "join": ("Connect to voice", "Connect", "connect"),
    "leave": ("Disconnect from voice", "Connect", "connect"),
    "play": ("Connect and stream in voice", "Connect", "connect"),
    "vcmove": ("Move members between voice channels", "Move Members", "move_members"),
    "vckick": ("Disconnect member from voice", "Move Members", "move_members"),
    "vcmute": ("Mute member in voice", "Mute Members", "mute_members"),
    "vcdeafen": ("Deafen member in voice", "Deafen Members", "deafen_members"),
    "tempvc": ("Manage temporary voice channels", "Manage Channels", "manage_channels"),
    "vcstatus": ("Set voice channel status", "Set Voice Channel Status", "set_voice_channel_status"),

    # Webhooks, Invites & Logging
    "webhook": ("Manage webhooks", "Manage Webhooks", "manage_webhooks"),
    "invitetracker": ("Create or modify channels", "Manage Channels", "manage_channels"),
    "logs": ("Manage logging channels and webhooks", "Manage Webhooks", "manage_webhooks"),
    "invite": ("Create invites", "Create Instant Invite", "create_instant_invite"),

    # Emojis & Stickers
    "steal": ("Manage emojis and stickers", "Manage Emojis and Stickers", "manage_emojis_and_stickers"),
    "addemoji": ("Manage emojis and stickers", "Manage Emojis and Stickers", "manage_emojis_and_stickers"),
    "react": ("Add reactions", "Add Reactions", "add_reactions"),
    "autoreact": ("Add reactions", "Add Reactions", "add_reactions"),

    # Server administration
    "backup": ("Manage server settings", "Manage Server", "manage_guild"),
}


def format_perm_name(perm_key: str) -> str:
    """Returns the clean human-readable name of a Discord permission."""
    key = str(perm_key).lower().replace(" ", "_")
    if key in DISCORD_PERM_NAMES:
        return DISCORD_PERM_NAMES[key]
    return key.replace("_", " ").title()


def generate_fix_instructions(
    permission_name: str,
    denial_source: str = "unknown",
    channel_name: Optional[str] = None
) -> str:
    """Generates tailored administrator remediation instructions."""
    if denial_source == "role_hierarchy":
        return (
            "Ask a server administrator to move Yuna's highest role above the target member's "
            "highest role in **Server Settings → Roles**."
        )
    elif denial_source == "channel_overwrites" and channel_name:
        return (
            f"Ask a server administrator to enable Yuna's `{permission_name}` permission in "
            f"**#{channel_name}**'s channel permission settings (channel overwrite)."
        )
    elif denial_source == "server_roles":
        return (
            f"Ask a server administrator to grant Yuna the `{permission_name}` permission in "
            f"**Server Settings → Roles**."
        )
    else:
        chan_context = f" or enable it for Yuna's role in #{channel_name}'s permission settings" if channel_name else ", or enable it for Yuna's role in the relevant channel's permission settings"
        return (
            f"Ask a server administrator to grant Yuna the `{permission_name}` permission in "
            f"**Server Settings → Roles**{chan_context}."
        )


def build_permission_embed(
    action: str,
    permission_name: str,
    where: str,
    user: Union[discord.User, discord.Member],
    how_to_fix: str,
    bot_user: Optional[discord.ClientUser] = None
) -> discord.Embed:
    """Builds the standardized Yuna Missing Permission embed."""
    description = (
        "I couldn't complete your requested action because I don't have the required permission.\n\n"
        f"**Action:** {action}\n"
        f"**Missing Permission:** `{permission_name}`\n"
        f"**Where:** {where}\n"
        f"**Requested By:** {user.mention}\n\n"
        "**How to Fix**\n"
        f"{how_to_fix}\n\n"
        "Once the permission is granted, try the command again.\n\n"
        "*Error Reference: MISSING_PERMISSIONS*"
    )
    embed = discord.Embed(
        title="⚠️ Yuna Missing Permission",
        description=description,
        color=0xFEE75C  # Discord warning amber
    )
    if bot_user and getattr(bot_user, "display_avatar", None):
        embed.set_thumbnail(url=bot_user.display_avatar.url)
    embed.set_footer(text="Yuna Permission System • MISSING_PERMISSIONS")
    return embed


def build_permission_text(
    action: str,
    permission_name: str,
    where: str,
    user: Union[discord.User, discord.Member],
    how_to_fix: str
) -> str:
    """Plain text fallback when the bot lacks Embed Links permission."""
    return (
        "⚠️ **Yuna Missing Permission**\n\n"
        "I couldn't complete your requested action because I don't have the required permission.\n\n"
        f"**Action:** {action}\n"
        f"**Missing Permission:** `{permission_name}`\n"
        f"**Where:** {where}\n"
        f"**Requested By:** {user.mention}\n\n"
        "**How to Fix**\n"
        f"{how_to_fix}\n\n"
        "Once the permission is granted, try the command again.\n\n"
        "*Error Reference: MISSING_PERMISSIONS*"
    )


def build_aggregated_permission_embed(
    guild: discord.Guild,
    channels: List[Union[discord.abc.GuildChannel, Any]],
    action: str,
    permission_name: str,
    bot_user: Optional[discord.ClientUser] = None,
    recipient_title: str = "Server Administrator"
) -> discord.Embed:
    """
    Builds the consolidated, aggregated explanatory DM embed for server owners/administrators
    grouping all unique affected channels in a single server.
    """
    guild_name = guild.name if guild else "Unknown Server"

    is_vc = False
    if channels:
        for ch in channels:
            if isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                is_vc = True
                break
    if not is_vc and ("voice" in action.lower() or "vc" in action.lower()):
        is_vc = True

    if len(channels) <= 1:
        title = "⚠️ Yuna Missing Permission"
        if is_vc:
            intro = "Yuna detected that it cannot update voice channel status in your server because of permission restrictions."
            channel_heading = "Affected Voice Channel"
            retry_step = "Retry setting the voice channel status."
        else:
            intro = f"Yuna detected that it cannot {action.lower()} in a channel in your server because of permission restrictions."
            channel_heading = "Affected Channel"
            retry_step = "Retry the action once permissions are updated."
    else:
        title = "⚠️ Yuna Missing Permissions"
        if is_vc:
            intro = "Yuna detected that it cannot update voice channel statuses in several channels in your server because of permission restrictions."
            channel_heading = "Affected Voice Channels"
            retry_step = "Retry setting the voice channel statuses."
        else:
            intro = f"Yuna detected that it cannot {action.lower()} in several channels in your server because of permission restrictions."
            channel_heading = "Affected Channels"
            retry_step = "Retry the action once permissions are updated."

    raw_perm = str(permission_name or "").strip()
    if not raw_perm or raw_perm.lower() in ("unknown", "none"):
        perm_display = "Check bot permissions"
    else:
        perm_display = f"`{raw_perm}`"

    channel_lines = []
    display_limit = 25
    for idx, ch in enumerate(channels[:display_limit], 1):
        cname = getattr(ch, "name", str(ch))
        clean_name = str(cname).replace("`", "")
        channel_lines.append(f"{idx}. `{clean_name}`")

    if len(channels) > display_limit:
        remaining = len(channels) - display_limit
        channel_lines.append(f"*... and {remaining} more channels*")

    channel_list_text = "\n".join(channel_lines) if channel_lines else "1. `(No specific channel)`"

    how_to_fix = (
        "**How to Fix:**\n"
        "1. Check Yuna's role permissions in your Discord server.\n"
        f"2. Check channel-specific permission overrides for the affected {'voice ' if is_vc else ''}channels.\n"
        "3. Grant the verified permission needed for this action.\n"
        f"4. {retry_step}"
    )

    description = (
        f"Hello, {recipient_title}!\n\n"
        f"{intro}\n\n"
        f"**Server:** {guild_name}\n\n"
        f"**Failed Action:** {action}\n\n"
        f"**Required Permission:** {perm_display} — verify the exact requirement against the actual Discord API operation.\n\n"
        f"**{channel_heading}:**\n\n"
        f"{channel_list_text}\n\n"
        f"{how_to_fix}\n\n"
        "**Error Reference:** `MISSING_PERMISSIONS`"
    )

    embed = discord.Embed(
        title=title,
        description=description,
        color=0xFEE75C  # Discord warning amber
    )
    if bot_user and getattr(bot_user, "display_avatar", None):
        embed.set_thumbnail(url=bot_user.display_avatar.url)
    embed.set_footer(text=f"Automated Alert • {guild_name} • MISSING_PERMISSIONS")
    return embed


def build_aggregated_permission_text(
    guild: discord.Guild,
    channels: List[Union[discord.abc.GuildChannel, Any]],
    action: str,
    permission_name: str,
    recipient_title: str = "Server Administrator"
) -> str:
    """Plain text fallback for server owner/administrator aggregated DM alert."""
    guild_name = guild.name if guild else "Unknown Server"

    is_vc = False
    if channels:
        for ch in channels:
            if isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                is_vc = True
                break
    if not is_vc and ("voice" in action.lower() or "vc" in action.lower()):
        is_vc = True

    if len(channels) <= 1:
        title = "⚠️ Yuna Missing Permission"
        if is_vc:
            intro = "Yuna detected that it cannot update voice channel status in your server because of permission restrictions."
            channel_heading = "Affected Voice Channel"
            retry_step = "Retry setting the voice channel status."
        else:
            intro = f"Yuna detected that it cannot {action.lower()} in a channel in your server because of permission restrictions."
            channel_heading = "Affected Channel"
            retry_step = "Retry the action once permissions are updated."
    else:
        title = "⚠️ Yuna Missing Permissions"
        if is_vc:
            intro = "Yuna detected that it cannot update voice channel statuses in several channels in your server because of permission restrictions."
            channel_heading = "Affected Voice Channels"
            retry_step = "Retry setting the voice channel statuses."
        else:
            intro = f"Yuna detected that it cannot {action.lower()} in several channels in your server because of permission restrictions."
            channel_heading = "Affected Channels"
            retry_step = "Retry the action once permissions are updated."

    raw_perm = str(permission_name or "").strip()
    if not raw_perm or raw_perm.lower() in ("unknown", "none"):
        perm_display = "Check bot permissions"
    else:
        perm_display = f"`{raw_perm}`"

    channel_lines = []
    display_limit = 25
    for idx, ch in enumerate(channels[:display_limit], 1):
        cname = getattr(ch, "name", str(ch))
        clean_name = str(cname).replace("`", "")
        channel_lines.append(f"{idx}. `{clean_name}`")

    if len(channels) > display_limit:
        remaining = len(channels) - display_limit
        channel_lines.append(f"*... and {remaining} more channels*")

    channel_list_text = "\n".join(channel_lines) if channel_lines else "1. `(No specific channel)`"

    how_to_fix = (
        "**How to Fix:**\n"
        "1. Check Yuna's role permissions in your Discord server.\n"
        f"2. Check channel-specific permission overrides for the affected {'voice ' if is_vc else ''}channels.\n"
        "3. Grant the verified permission needed for this action.\n"
        f"4. {retry_step}"
    )

    return (
        f"**{title}**\n\n"
        f"Hello, {recipient_title}!\n\n"
        f"{intro}\n\n"
        f"**Server:** {guild_name}\n\n"
        f"**Failed Action:** {action}\n\n"
        f"**Required Permission:** {perm_display} — verify the exact requirement against the actual Discord API operation.\n\n"
        f"**{channel_heading}:**\n\n"
        f"{channel_list_text}\n\n"
        f"{how_to_fix}\n\n"
        "**Error Reference:** `MISSING_PERMISSIONS`"
    )


def build_owner_permission_embed(
    guild: discord.Guild,
    channel: Optional[discord.abc.GuildChannel],
    action: str,
    permission_name: str,
    bot_user: Optional[discord.ClientUser] = None,
    recipient_title: str = "Server Owner"
) -> discord.Embed:
    """Single channel wrapper delegating to build_aggregated_permission_embed for backward compatibility."""
    return build_aggregated_permission_embed(
        guild=guild,
        channels=[channel] if channel else [],
        action=action,
        permission_name=permission_name,
        bot_user=bot_user,
        recipient_title=recipient_title
    )


def build_owner_permission_text(
    guild: discord.Guild,
    channel: Optional[discord.abc.GuildChannel],
    action: str,
    permission_name: str,
    recipient_title: str = "Server Owner"
) -> str:
    """Single channel text wrapper delegating to build_aggregated_permission_text for backward compatibility."""
    return build_aggregated_permission_text(
        guild=guild,
        channels=[channel] if channel else [],
        action=action,
        permission_name=permission_name,
        recipient_title=recipient_title
    )


class ScanSessionState:
    COLLECTING = "COLLECTING"
    FINALIZED = "FINALIZED"
    DISPATCHING = "DISPATCHING"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


@dataclass
class PermissionFailureRecord:
    guild_id: int
    action: str
    permission: str
    channel_id: int
    channel_name: str
    channel: Optional[Union[discord.abc.GuildChannel, Any]] = None
    timestamp: float = field(default_factory=time.time)
    details: Optional[str] = None


class _StubChannel:
    """Fallback stub channel representation preserving ID, name, and guild."""
    def __init__(self, channel_id: int, channel_name: str, guild: Optional[discord.Guild] = None):
        self.id = channel_id
        self.name = channel_name
        self.guild = guild

    def __str__(self):
        return self.name


class ScanSession:
    """
    An explicit, awaited lifecycle context for collecting permission failures during bulk scans.
    Guarantees the strict workflow:
      Step 1: FETCH AND CHECK EVERYTHING (complete scan of all channels)
      Step 2: COLLECT ALL RESULTS (await all checks, deduplicate, preserve names/ids)
      Step 3: FINALIZE THE COMPLETE SUMMARY (verify complete list of unique affected channels)
      Step 4: SEND ONE CONSOLIDATED DM (never premature partial DMs)
    """
    def __init__(
        self,
        handler: "PermissionHandler",
        guild: discord.Guild,
        action: str,
        permission: Optional[str] = None,
        server_cooldown_seconds: float = 3600.0
    ):
        self.handler = handler
        self.guild = guild
        self.action = action
        self.permission = permission or "manage_messages"
        self.perm_name = format_perm_name(self.permission)
        self.server_cooldown_seconds = server_cooldown_seconds
        self.state: str = ScanSessionState.COLLECTING
        self._failures: Dict[int, PermissionFailureRecord] = {}  # channel_id -> Record (deduplicated)
        self._lock = asyncio.Lock()
        self._finalized_channels: List[Union[discord.abc.GuildChannel, Any]] = []

    @property
    def action_key(self) -> str:
        return self.action.lower().strip() if self.action else "*"

    @property
    def server_key(self) -> Tuple[int, str]:
        return (self.guild.id, self.action_key)

    async def record_failure(
        self,
        channel: Optional[Union[discord.abc.GuildChannel, Any]] = None,
        channel_id: Optional[int] = None,
        channel_name: Optional[str] = None,
        permission: Optional[str] = None,
        details: Optional[str] = None
    ) -> bool:
        """Records a detected permission failure synchronously into the active scan session."""
        async with self._lock:
            if self.state != ScanSessionState.COLLECTING:
                return False

            cid = getattr(channel, "id", None) or channel_id or 0
            cname = getattr(channel, "name", None) or channel_name or str(cid)
            perm = permission or self.permission

            # Deduplicate by channel_id, preserving insertion order
            if cid not in self._failures:
                self._failures[cid] = PermissionFailureRecord(
                    guild_id=self.guild.id,
                    action=self.action,
                    permission=perm,
                    channel_id=cid,
                    channel_name=str(cname),
                    channel=channel,
                    timestamp=time.time(),
                    details=details
                )
            return True

    async def __aenter__(self) -> "ScanSession":
        await self.handler.register_scan_session(self)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                await self.finalize_and_dispatch()
            else:
                async with self._lock:
                    self.state = ScanSessionState.CANCELLED
        finally:
            await self.handler.unregister_scan_session(self)

    async def finalize_and_dispatch(self) -> bool:
        """
        Step 3: FINALIZE THE COMPLETE SUMMARY
        Step 4: SEND ONE DM
        Transitions state: COLLECTING -> FINALIZED -> DISPATCHING -> SENT.
        """
        async with self._lock:
            if self.state != ScanSessionState.COLLECTING:
                return False
            self.state = ScanSessionState.FINALIZED

            # If no failures occurred during the scan, no DM is dispatched
            if not self._failures:
                return False

            # Build finalized list of unique channels preserving order
            channels: List[Union[discord.abc.GuildChannel, Any]] = []
            for r in self._failures.values():
                if r.channel:
                    channels.append(r.channel)
                else:
                    ch_obj = self.guild.get_channel(r.channel_id) if hasattr(self.guild, "get_channel") else None
                    if not ch_obj:
                        ch_obj = _StubChannel(r.channel_id, r.channel_name, self.guild)
                    channels.append(ch_obj)

            self._finalized_channels = channels
            self.state = ScanSessionState.DISPATCHING

        success = await self.handler._dispatch_scan_session(self, channels)
        async with self._lock:
            self.state = ScanSessionState.SENT if success else ScanSessionState.FINALIZED
        return success


class PermissionHandler:
    """
    Centralized coordinator for missing permission detection, tailored explanations,
    anti-spam cooldowns, and intelligent multi-tier delivery.
    """

    def __init__(self):
        # Anti-spam cooldown cache: (guild_id, channel_id, permission_name) -> timestamp
        self._cooldown_cache: Dict[Tuple[int, int, str], float] = {}
        # Strictly filtered 1-time owner DM notification set: (guild_id, channel_id, permission_name)
        self._owner_notified: Set[Tuple[int, int, str]] = set()
        # Server-level aggregated notification tracking: (guild_id, action_normalized) -> timestamp
        self._server_notified: Dict[Tuple[int, str], float] = {}
        # (guild_id, action_normalized) -> set of channel IDs included in the notification
        self._server_notified_channels: Dict[Tuple[int, str], Set[int]] = {}
        # (guild_id, action_normalized) -> pending batch dict
        self._pending_batches: Dict[Tuple[int, str], Dict[str, Any]] = {}
        # Active scan sessions: (guild_id, action_normalized) -> ScanSession
        self._active_scan_sessions: Dict[Tuple[int, str], ScanSession] = {}
        # Concurrency safety: per-server lock to prevent race conditions during DM dispatch
        self._server_locks: Dict[Tuple[int, str], asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    def is_cooling_down(self, guild_id: int, channel_id: int, permission_name: str, cooldown_seconds: float = 60.0) -> bool:
        """Prevents repeated duplicate notifications for the same unresolved permission issue."""
        now = time.time()
        key = (guild_id, channel_id, permission_name)
        last_time = self._cooldown_cache.get(key, 0.0)
        if (now - last_time) < cooldown_seconds:
            return True
        self._cooldown_cache[key] = now

        # Prune expired entries
        if len(self._cooldown_cache) > 250:
            self._cooldown_cache = {k: v for k, v in self._cooldown_cache.items() if (now - v) < 300.0}
        return False

    def detect_permission_details(
        self,
        error: Any,
        ctx_or_interaction: Union[commands.Context, discord.Interaction],
        action: Optional[str] = None,
        permission: Optional[str] = None,
        channel: Optional[discord.abc.GuildChannel] = None
    ) -> Tuple[str, str, str, str, str]:
        """
        Detects (action, permission_name, where, denial_source, how_to_fix)
        by inspecting the error, command invocation context, guild permissions,
        and channel permission overwrites.
        """
        guild = getattr(ctx_or_interaction, "guild", None)
        target_channel = channel or getattr(ctx_or_interaction, "channel", None)
        bot_member = guild.me if guild else None

        # Resolve command name
        cmd_obj = getattr(ctx_or_interaction, "command", None)
        cmd_name = ""
        if cmd_obj:
            cmd_name = getattr(cmd_obj, "name", "") or ""
            if not cmd_name and hasattr(cmd_obj, "qualified_name"):
                cmd_name = cmd_obj.qualified_name.split()[0]
        cmd_name = cmd_name.lower().strip()

        # Step 1: Handle explicit BotMissingPermissions check failures
        if isinstance(error, (commands.BotMissingPermissions, app_commands.BotMissingPermissions)):
            missing_perms = getattr(error, "missing_permissions", [])
            first_perm = missing_perms[0] if missing_perms else "manage_messages"
            perm_attr = str(first_perm).lower()
            perm_name = format_perm_name(perm_attr)

            if not action:
                if cmd_name in COMMAND_ACTION_MAP:
                    action = COMMAND_ACTION_MAP[cmd_name][0]
                else:
                    action = f"Execute command `{cmd_name or 'action'}`"

            where = f"#{target_channel.name}" if hasattr(target_channel, "name") else (guild.name if guild else "Server")
            how_to_fix = generate_fix_instructions(perm_name, "server_roles")
            return action, perm_name, where, "server_roles", how_to_fix

        # Step 2: Handle explicit caller overrides
        if permission:
            perm_name = format_perm_name(permission)
            act = action or (COMMAND_ACTION_MAP.get(cmd_name, (f"Execute `{cmd_name}`", "", ""))[0] if cmd_name else "Complete requested action")
            where = f"#{target_channel.name}" if hasattr(target_channel, "name") else (guild.name if guild else "Server")
            how_to_fix = generate_fix_instructions(perm_name, "unknown", getattr(target_channel, "name", None))
            return act, perm_name, where, "unknown", how_to_fix

        # Step 3: Analyze discord.Forbidden based on command / feature
        detected_action = action
        detected_perm_attr = None
        detected_perm_name = None

        if cmd_name in COMMAND_ACTION_MAP:
            mapping_act, mapping_perm_name, mapping_attr = COMMAND_ACTION_MAP[cmd_name]
            if not detected_action:
                detected_action = mapping_act
            detected_perm_attr = mapping_attr
            detected_perm_name = mapping_perm_name

        # Verify against bot permissions to distinguish server roles vs channel overwrites vs hierarchy
        denial_source = "unknown"
        if bot_member and detected_perm_attr:
            # Check server-wide base permission
            has_guild_perm = getattr(bot_member.guild_permissions, detected_perm_attr, None)
            
            # Check channel-specific overwrite permission
            has_chan_perm = None
            if target_channel and hasattr(target_channel, "permissions_for"):
                chan_perms = target_channel.permissions_for(bot_member)
                has_chan_perm = getattr(chan_perms, detected_perm_attr, None)

            if has_guild_perm is False:
                denial_source = "server_roles"
            elif has_chan_perm is False:
                denial_source = "channel_overwrites"
            elif has_guild_perm is True and has_chan_perm in (True, None):
                # Likely role hierarchy issue (e.g. banning/muting higher role member)
                if detected_perm_attr in ("manage_roles", "ban_members", "kick_members", "moderate_members"):
                    denial_source = "role_hierarchy"

        # Fallback inspection across fundamental permissions if no specific command mapping was found
        if not detected_perm_name and bot_member:
            if target_channel and hasattr(target_channel, "permissions_for"):
                chan_perms = target_channel.permissions_for(bot_member)
                if not chan_perms.send_messages:
                    detected_action = detected_action or "Send messages"
                    detected_perm_name = "Send Messages"
                    denial_source = "channel_overwrites" if bot_member.guild_permissions.send_messages else "server_roles"
                elif not chan_perms.embed_links:
                    detected_action = detected_action or "Send embeds"
                    detected_perm_name = "Embed Links"
                    denial_source = "channel_overwrites" if bot_member.guild_permissions.embed_links else "server_roles"
                elif not chan_perms.manage_messages and cmd_name in ("purge", "clear", "clean"):
                    detected_action = detected_action or "Delete messages"
                    detected_perm_name = "Manage Messages"
                    denial_source = "channel_overwrites" if bot_member.guild_permissions.manage_messages else "server_roles"

        # Final default fallback
        detected_action = detected_action or (f"Execute `{cmd_name}`" if cmd_name else "Complete requested action")
        detected_perm_name = detected_perm_name or "Manage Server"

        where = f"#{target_channel.name}" if hasattr(target_channel, "name") else (guild.name if guild else "Server")
        how_to_fix = generate_fix_instructions(detected_perm_name, denial_source, getattr(target_channel, "name", None))

        return detected_action, detected_perm_name, where, denial_source, how_to_fix

    async def deliver_notification(
        self,
        ctx_or_interaction: Union[commands.Context, discord.Interaction],
        embed: discord.Embed,
        text_content: str,
        user: Union[discord.User, discord.Member],
        guild: Optional[discord.Guild] = None,
        channel: Optional[discord.abc.Messageable] = None
    ) -> bool:
        """
        Intelligent multi-tier notification delivery:
        1. Context / Interaction command channel (Ephemeral or Public Reply)
        2. Direct Message to invoking user
        3. Server Admin / Audit Log Channel
        4. Internal bot error logs DB
        """
        bot_member = guild.me if guild else None

        # Level 1A: Deliver directly through Discord Interaction if active
        if isinstance(ctx_or_interaction, discord.Interaction):
            try:
                if not ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
                    return True
                else:
                    await ctx_or_interaction.followup.send(embed=embed, ephemeral=True)
                    return True
            except (discord.Forbidden, discord.HTTPException):
                pass

        if hasattr(ctx_or_interaction, "interaction") and ctx_or_interaction.interaction:
            inter = ctx_or_interaction.interaction
            try:
                if not inter.response.is_done():
                    await inter.response.send_message(embed=embed, ephemeral=True)
                    return True
                else:
                    await inter.followup.send(embed=embed, ephemeral=True)
                    return True
            except (discord.Forbidden, discord.HTTPException):
                pass

        # Level 1B: Deliver to the command channel
        target_channel = channel or getattr(ctx_or_interaction, "channel", None)
        if target_channel and guild and bot_member and hasattr(target_channel, "permissions_for"):
            perms = target_channel.permissions_for(bot_member)
            if perms.send_messages:
                try:
                    if perms.embed_links:
                        if hasattr(ctx_or_interaction, "reply"):
                            await ctx_or_interaction.reply(embed=embed, mention_author=False)
                        else:
                            await target_channel.send(embed=embed)
                    else:
                        if hasattr(ctx_or_interaction, "reply"):
                            await ctx_or_interaction.reply(content=text_content, mention_author=False)
                        else:
                            await target_channel.send(content=text_content)
                    return True
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # Level 2: Fallback to Direct Message (DM) to the invoking user
        if user and not getattr(user, "bot", False):
            try:
                await user.send(embed=embed)
                return True
            except (discord.Forbidden, discord.HTTPException):
                pass

        # Level 3: Fallback to Server Audit / Moderation log channel
        if guild and bot_member:
            try:
                for ch in guild.text_channels:
                    ch_lower = ch.name.lower()
                    if any(k in ch_lower for k in ("audit", "mod-log", "modlog", "admin-log", "yuna-log")):
                        ch_perms = ch.permissions_for(bot_member)
                        if ch_perms.send_messages:
                            if ch_perms.embed_links:
                                await ch.send(embed=embed)
                            else:
                                await ch.send(content=text_content)
                            return True
            except Exception:
                pass

        # Level 4: Final internal fallback to error logs database
        try:
            from utils.error_logs_db import record_bot_error
            cmd_name = str(getattr(ctx_or_interaction, "command", "Unknown"))
            record_bot_error(
                error_type="MissingPermissions",
                source=cmd_name,
                guild=guild,
                user=user,
                channel=target_channel,
                details=f"Missing Permission Notification: {embed.description[:500]}"
            )
        except Exception:
            pass

        return False

    async def handle_command_error(
        self,
        ctx_or_interaction: Union[commands.Context, discord.Interaction],
        error: Any
    ) -> bool:
        """
        Central entry point for command error handlers.
        Returns True if the error was a recognized missing permission and handled,
        or False if it was unrelated.
        """
        # Unwrap error to root cause
        real_error = getattr(error, "original", error)
        while hasattr(real_error, "original") and getattr(real_error, "original", None) is not None:
            real_error = real_error.original

        # Strictly filter for genuine bot permission errors
        is_bot_missing = isinstance(real_error, (commands.BotMissingPermissions, app_commands.BotMissingPermissions))
        is_forbidden = isinstance(real_error, discord.Forbidden)

        if not (is_bot_missing or is_forbidden):
            return False

        # If it's a Forbidden error, verify it's a genuine permission/access failure (not DM closed, etc.)
        if is_forbidden:
            err_code = getattr(real_error, "code", None)
            # Code 50007 is "Cannot send messages to this user" (user DM closed), not a bot guild permission error
            if err_code == 50007:
                return False
            # Filter out non-permission Discord errors
            if err_code is not None and err_code not in (50013, 50001, 0):
                return False

        user = getattr(ctx_or_interaction, "user", None) or getattr(ctx_or_interaction, "author", None)
        guild = getattr(ctx_or_interaction, "guild", None)
        channel = getattr(ctx_or_interaction, "channel", None)
        bot = getattr(ctx_or_interaction, "client", None) or getattr(ctx_or_interaction, "bot", None)
        bot_user = bot.user if bot else None

        # Detect action and missing permission
        action, perm_name, where, denial_source, how_to_fix = self.detect_permission_details(
            real_error,
            ctx_or_interaction
        )

        guild_id = guild.id if guild else 0
        channel_id = channel.id if channel else 0

        # Anti-spam cooldown check: avoid sending repeated notifications for the same unresolved issue
        if self.is_cooling_down(guild_id, channel_id, perm_name, cooldown_seconds=60.0):
            return True

        embed = build_permission_embed(
            action=action,
            permission_name=perm_name,
            where=where,
            user=user,
            how_to_fix=how_to_fix,
            bot_user=bot_user
        )
        text_content = build_permission_text(
            action=action,
            permission_name=perm_name,
            where=where,
            user=user,
            how_to_fix=how_to_fix
        )

        await self.deliver_notification(
            ctx_or_interaction=ctx_or_interaction,
            embed=embed,
            text_content=text_content,
            user=user,
            guild=guild,
            channel=channel
        )
        return True

    async def handle_missing_permission(
        self,
        ctx_or_interaction: Union[commands.Context, discord.Interaction],
        action: str,
        permission: Optional[str] = None,
        channel: Optional[discord.abc.GuildChannel] = None
    ) -> bool:
        """
        Direct programmatic entry point for cogs, events, and background workers
        when catching discord.Forbidden on a known action.
        """
        user = getattr(ctx_or_interaction, "user", None) or getattr(ctx_or_interaction, "author", None)
        guild = getattr(ctx_or_interaction, "guild", None)
        target_channel = channel or getattr(ctx_or_interaction, "channel", None)
        bot = getattr(ctx_or_interaction, "client", None) or getattr(ctx_or_interaction, "bot", None)
        bot_user = bot.user if bot else None

        # Detect details
        act, perm_name, where, denial_source, how_to_fix = self.detect_permission_details(
            None,
            ctx_or_interaction,
            action=action,
            permission=permission,
            channel=target_channel
        )

        guild_id = guild.id if guild else 0
        channel_id = target_channel.id if target_channel else 0

        if self.is_cooling_down(guild_id, channel_id, perm_name, cooldown_seconds=60.0):
            return True

        embed = build_permission_embed(
            action=act,
            permission_name=perm_name,
            where=where,
            user=user,
            how_to_fix=how_to_fix,
            bot_user=bot_user
        )
        text_content = build_permission_text(
            action=act,
            permission_name=perm_name,
            where=where,
            user=user,
            how_to_fix=how_to_fix
        )

        return await self.deliver_notification(
            ctx_or_interaction=ctx_or_interaction,
            embed=embed,
            text_content=text_content,
            user=user,
            guild=guild,
            channel=target_channel
        )

    def _get_server_lock(self, key: Tuple[int, str]) -> asyncio.Lock:
        if key not in self._server_locks:
            self._server_locks[key] = asyncio.Lock()
        return self._server_locks[key]

    async def register_scan_session(self, session: ScanSession):
        """Registers an active scan session to intercept all permission failures for this guild & action."""
        async with self._lock:
            self._active_scan_sessions[session.server_key] = session

    async def unregister_scan_session(self, session: ScanSession):
        """Unregisters an active scan session upon completion."""
        async with self._lock:
            if self._active_scan_sessions.get(session.server_key) is session:
                self._active_scan_sessions.pop(session.server_key, None)

    def scan_session(
        self,
        guild: discord.Guild,
        action: str,
        permission: Optional[str] = None,
        server_cooldown_seconds: float = 3600.0
    ) -> ScanSession:
        """Factory for creating an explicit scan session context manager."""
        return ScanSession(
            handler=self,
            guild=guild,
            action=action,
            permission=permission,
            server_cooldown_seconds=server_cooldown_seconds
        )

    async def report_permission_failure(
        self,
        guild: discord.Guild,
        action: str,
        permission: Optional[str] = None,
        channel: Optional[discord.abc.GuildChannel] = None,
        error: Optional[Any] = None
    ) -> bool:
        """
        Generic entry point to report a permission failure.
        Routes to an active scan session if present, or batches via notify_server_owner_once.
        """
        perm = permission or "manage_messages"
        return await self.notify_server_owner_once(
            guild=guild,
            action=action,
            permission=perm,
            channel=channel
        )

    async def _delayed_flush(self, key: Tuple[int, str], delay: float):
        try:
            await asyncio.sleep(delay)
            await self._dispatch_server_notification(key)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[PERMISSION NOTIFIER ERROR] Error in delayed flush: {e}", flush=True)

    async def flush_server_batch(self, guild_id: int, action: str) -> bool:
        """Immediately flushes any pending aggregated batch for the given guild and action."""
        action_key = action.lower().strip()
        key = (guild_id, action_key)
        async with self._lock:
            batch = self._pending_batches.get(key)
            if not batch:
                return False
            task = batch.get("task")
            if task and not task.done():
                task.cancel()
        return await self._dispatch_server_notification(key)

    async def notify_server_owner_once(
        self,
        guild: discord.Guild,
        action: str,
        permission: str,
        channel: Optional[discord.abc.GuildChannel] = None,
        debounce_seconds: float = 10.0,
        server_cooldown_seconds: float = 3600.0
    ) -> bool:
        """
        Sends EXACTLY ONE consolidated DM per server to the server owner and administrators
        containing all unique affected channels over a configurable collection window (default 10s).
        Deduplicates repeated failures for the same channel and prevents DM spam loops.
        If an explicit ScanSession is active for this server and action, the failure is recorded
        directly into the scan session without spawning any premature timer.
        """
        if not guild:
            return False

        perm_name = format_perm_name(permission)
        channel_id = getattr(channel, "id", 0)
        action_key = action.lower().strip()
        server_key = (guild.id, action_key)
        now = time.time()

        # 1. Check if an active scan session is capturing failures for this server & action
        async with self._lock:
            active_session = self._active_scan_sessions.get(server_key)
            if not active_session:
                active_session = self._active_scan_sessions.get((guild.id, "*"))

        if active_session:
            await active_session.record_failure(channel=channel, permission=permission)
            return True

        # 2. Outside a scan session: check persistent DB tracking to strictly prevent spamming
        from utils.permission_db import can_send_permission_dm, get_permission_send_count
        if not can_send_permission_dm(guild.id, action_key, max_sends=1):
            db_count = get_permission_send_count(guild.id, action_key)
            ch_name = getattr(channel, "name", "channel") if channel else "channel"
            where = f"#{ch_name} in {guild.name}" if channel else guild.name
            _safe_log(f"[PERMISSION NOTIFIER] Suppressed DM to server owner for action '{action}' on {where}: strictly limited to 1 send on DM (already sent {db_count} time(s) according to DB).")
            return False

        # 3. Apply server-level cooldown and dynamic debounce batching
        async with self._lock:
            last_sent = self._server_notified.get(server_key, 0.0)
            if (now - last_sent) < server_cooldown_seconds:
                notified_channels = self._server_notified_channels.get(server_key, set())
                # If this channel was already included in the previous alert, suppress!
                if channel_id in notified_channels or channel_id == 0:
                    ch_name = getattr(channel, "name", "channel") if channel else "channel"
                    where = f"#{ch_name} in {guild.name}" if channel else guild.name
                    _safe_log(f"[PERMISSION NOTIFIER] Suppressed duplicate DM for action '{action}' on {where}: server authorities already notified within cooldown.")
                    return False

            # Add to active batch if one exists
            if server_key in self._pending_batches:
                batch = self._pending_batches[server_key]
                if channel:
                    batch["channels"][channel.id] = channel

                # Dynamic extending debounce: reset timer on new arrivals (up to max 60s)
                task = batch.get("task")
                if task and not task.done():
                    task.cancel()

                if debounce_seconds <= 0.0:
                    pass
                else:
                    max_batch_window = 60.0
                    elapsed = now - batch.get("created_at", now)
                    remaining = max(1.0, max_batch_window - elapsed)
                    actual_delay = min(debounce_seconds, remaining)
                    batch["task"] = asyncio.create_task(self._delayed_flush(server_key, actual_delay))
                    return True
            else:
                # Create a new pending batch
                batch = {
                    "guild": guild,
                    "action": action,
                    "permission": permission,
                    "perm_name": perm_name,
                    "channels": {channel.id: channel} if channel else {},
                    "created_at": now,
                    "task": None
                }
                self._pending_batches[server_key] = batch
                if debounce_seconds > 0.0:
                    task = asyncio.create_task(self._delayed_flush(server_key, debounce_seconds))
                    batch["task"] = task
                    return True

        # If debounce_seconds <= 0.0, dispatch immediately
        return await self._dispatch_server_notification(server_key)

    async def _dispatch_scan_session(
        self,
        session: ScanSession,
        channels: List[Union[discord.abc.GuildChannel, Any]]
    ) -> bool:
        """
        Dispatches exactly ONE consolidated DM for a completed ScanSession.
        Ensures concurrency locking, deduplication, server cooldown, DB tracking gate,
        owner + admin delivery, and preservation of exact console log formatting.
        """
        if not session.guild or not channels:
            return False

        server_key = session.server_key
        guild = session.guild
        action = session.action
        perm_name = session.perm_name
        now = time.time()
        channel_ids = {getattr(ch, "id", 0) for ch in channels if getattr(ch, "id", 0)}

        first_ch = channels[0] if channels else None
        first_name = getattr(first_ch, "name", "channel") if first_ch else "channel"
        where = f"#{first_name} (+{len(channels)-1} channels) in {guild.name}" if len(channels) > 1 else (f"#{first_name} in {guild.name}" if channels else guild.name)

        # Persistent database gate: strictly allow sending only once on DM to prevent spamming
        from utils.permission_db import can_send_permission_dm, get_permission_send_count
        if not can_send_permission_dm(guild.id, action, max_sends=1):
            db_count = get_permission_send_count(guild.id, action)
            _safe_log(f"[PERMISSION NOTIFIER] Suppressed DM to server owner for action '{action}' on {where}: strictly limited to 1 send on DM (already sent {db_count} time(s) according to DB).")
            return False

        server_lock = self._get_server_lock(server_key)
        async with server_lock:
            async with self._lock:
                last_sent = self._server_notified.get(server_key, 0.0)
                if (now - last_sent) < session.server_cooldown_seconds:
                    notified_channels = self._server_notified_channels.get(server_key, set())
                    # If all channels were already notified within cooldown, suppress
                    if channel_ids and channel_ids.issubset(notified_channels):
                        _safe_log(f"[PERMISSION NOTIFIER] Suppressed duplicate DM for action '{action}' on {where}: server authorities already notified within cooldown.")
                        return False

            success = await self._send_consolidated_alert(
                guild=guild,
                action=action,
                perm_name=perm_name,
                channels=channels
            )

            if success:
                async with self._lock:
                    self._server_notified[server_key] = now
                    existing = self._server_notified_channels.get(server_key, set())
                    self._server_notified_channels[server_key] = existing.union(channel_ids)
                    for ch_id in channel_ids:
                        self._owner_notified.add((guild.id, ch_id, perm_name))

            return success

    async def _dispatch_server_notification(self, server_key: Tuple[int, str]) -> bool:
        """Flushes and sends the consolidated DM for a pending batch."""
        server_lock = self._get_server_lock(server_key)
        async with server_lock:
            async with self._lock:
                batch = self._pending_batches.pop(server_key, None)
                if not batch:
                    return False

                guild = batch["guild"]
                action = batch["action"]
                perm_name = batch["perm_name"]
                channel_map = batch.get("channels", {})
                channels = list(channel_map.values())
                now = time.time()

            first_ch = channels[0] if channels else None
            first_name = getattr(first_ch, "name", "channel") if first_ch else "channel"
            where = f"#{first_name} (+{len(channels)-1} channels) in {guild.name}" if len(channels) > 1 else (f"#{first_name} in {guild.name}" if channels else guild.name)

            # Persistent database gate: strictly allow sending only once on DM to prevent spamming
            from utils.permission_db import can_send_permission_dm, get_permission_send_count
            if not can_send_permission_dm(guild.id, action, max_sends=1):
                db_count = get_permission_send_count(guild.id, action)
                _safe_log(f"[PERMISSION NOTIFIER] Suppressed DM to server owner for action '{action}' on {where}: strictly limited to 1 send on DM (already sent {db_count} time(s) according to DB).")
                return False

            success = await self._send_consolidated_alert(
                guild=guild,
                action=action,
                perm_name=perm_name,
                channels=channels
            )

            if success:
                async with self._lock:
                    self._server_notified[server_key] = now
                    self._server_notified_channels[server_key] = set(channel_map.keys())
                    for ch_id in channel_map.keys():
                        self._owner_notified.add((guild.id, ch_id, perm_name))

            return success

    async def _send_consolidated_alert(
        self,
        guild: discord.Guild,
        action: str,
        perm_name: str,
        channels: List[Union[discord.abc.GuildChannel, Any]]
    ) -> bool:
        """Formats and delivers the consolidated missing permission alert to server authorities."""
        try:
            # 1. Resolve owner robustly (cache -> fetch_member -> fetch_user)
            owner = getattr(guild, "owner", None)
            owner_id = getattr(guild, "owner_id", 0)

            if not owner and owner_id:
                if hasattr(guild, "get_member"):
                    owner = guild.get_member(owner_id)
                if not owner and hasattr(guild, "fetch_member"):
                    try:
                        owner = await guild.fetch_member(owner_id)
                    except Exception:
                        pass

            if not owner and owner_id:
                # Fallback to fetching user via bot client so we can always send the DM
                client = getattr(guild, "_state", None)
                bot_client = getattr(client, "_get_client", lambda: None)() if client else None
                if not bot_client and hasattr(guild, "me") and guild.me:
                    me_state = getattr(guild.me, "_state", None)
                    bot_client = getattr(me_state, "_get_client", lambda: None)() if me_state else None
                if not bot_client and channels:
                    ch_state = getattr(channels[0], "_state", None)
                    bot_client = getattr(ch_state, "_get_client", lambda: None)() if ch_state else None

                if bot_client and hasattr(bot_client, "fetch_user"):
                    try:
                        owner = await bot_client.fetch_user(owner_id)
                    except Exception:
                        pass

            owner_id = owner.id if owner else owner_id

            # 2. Resolve administrators (chunk guild if necessary with strict non-blocking timeout)
            if hasattr(guild, "chunk") and not getattr(guild, "chunked", True):
                try:
                    await asyncio.wait_for(guild.chunk(), timeout=3.0)
                except Exception:
                    pass

            admins: List[discord.Member] = []
            if hasattr(guild, "members") and guild.members:
                for m in guild.members:
                    if getattr(m, "bot", False) or m.id == owner_id:
                        continue
                    perms = getattr(m, "guild_permissions", None)
                    if perms and perms.administrator:
                        if m not in admins:
                            admins.append(m)

            for role in getattr(guild, "roles", []):
                if getattr(role, "permissions", None) and role.permissions.administrator:
                    for m in getattr(role, "members", []):
                        if getattr(m, "bot", False) or m.id == owner_id:
                            continue
                        if m not in admins:
                            admins.append(m)

            admins.sort(key=lambda m: getattr(getattr(m, "top_role", None), "position", 0), reverse=True)
            target_admins = admins[:5]

            # Format where for log preservation
            if channels:
                first_ch = channels[0]
                first_name = getattr(first_ch, "name", "channel")
                if len(channels) == 1:
                    where = f"#{first_name} in {guild.name}"
                else:
                    where = f"#{first_name} (+{len(channels)-1} channels) in {guild.name}"
            else:
                where = guild.name

            bot_user = None
            if hasattr(guild, "me") and guild.me:
                bot_user = getattr(guild.me, "_state", None)
                bot_user = getattr(bot_user, "user", None) or getattr(guild.me, "user", None)

            notified_any = False

            # 3. Notify owner
            if owner:
                owner_embed = build_aggregated_permission_embed(
                    guild=guild,
                    channels=channels,
                    action=action,
                    permission_name=perm_name,
                    bot_user=bot_user,
                    recipient_title="Server Owner"
                )
                if hasattr(guild, "icon") and guild.icon:
                    owner_embed.set_author(name=f"Automated Alert • {guild.name}", icon_url=guild.icon.url)
                else:
                    owner_embed.set_author(name=f"Automated Alert • {guild.name}")

                try:
                    await owner.send(embed=owner_embed)
                    _safe_log(f"[PERMISSION NOTIFIER] Sent 1-time missing permission DM to server owner for action '{action}' on {where}.")
                    notified_any = True
                except discord.Forbidden:
                    try:
                        text_content = build_aggregated_permission_text(
                            guild=guild,
                            channels=channels,
                            action=action,
                            permission_name=perm_name,
                            recipient_title="Server Owner"
                        )
                        await owner.send(content=text_content)
                        _safe_log(f"[PERMISSION NOTIFIER] Sent 1-time missing permission DM to server owner for action '{action}' on {where}.")
                        notified_any = True
                    except (discord.Forbidden, discord.HTTPException) as dm_err:
                        _safe_log(f"[PERMISSION NOTIFIER] Could not DM server owner (DMs closed or blocked: {dm_err}) for action '{action}' on {where}.")
                except discord.HTTPException as http_err:
                    _safe_log(f"[PERMISSION NOTIFIER] HTTP error DMing server owner ({http_err}) for action '{action}' on {where}.")
            else:
                _safe_log(f"[PERMISSION NOTIFIER] Could not resolve server owner for guild '{guild.name}' ({guild.id}) for action '{action}' on {where}.")

            # 4. Notify administrators
            admin_sent_count = 0
            for admin in target_admins:
                admin_embed = build_aggregated_permission_embed(
                    guild=guild,
                    channels=channels,
                    action=action,
                    permission_name=perm_name,
                    bot_user=bot_user,
                    recipient_title="Server Administrator"
                )
                if hasattr(guild, "icon") and guild.icon:
                    admin_embed.set_author(name=f"Automated Alert • {guild.name}", icon_url=guild.icon.url)
                else:
                    admin_embed.set_author(name=f"Automated Alert • {guild.name}")

                try:
                    await admin.send(embed=admin_embed)
                    admin_sent_count += 1
                    notified_any = True
                except discord.Forbidden:
                    try:
                        text_content = build_aggregated_permission_text(
                            guild=guild,
                            channels=channels,
                            action=action,
                            permission_name=perm_name,
                            recipient_title="Server Administrator"
                        )
                        await admin.send(content=text_content)
                        admin_sent_count += 1
                        notified_any = True
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                except discord.HTTPException:
                    pass

            if admin_sent_count > 0:
                _safe_log(f"[PERMISSION NOTIFIER] Sent 1-time missing permission DM to {admin_sent_count} administrator(s) for action '{action}' on {where}.")

            if notified_any:
                try:
                    from utils.permission_db import record_permission_dm_sent
                    new_db_count = record_permission_dm_sent(
                        guild_id=guild.id,
                        guild_name=guild.name,
                        action=action,
                        permission=perm_name,
                        recipient_id=owner_id,
                        recipient_type="owner",
                        channels=channels,
                        details=where
                    )
                    _safe_log(f"[PERMISSION NOTIFIER] Saved to DB: send_count={new_db_count} for guild '{guild.name}' ({guild.id}) action '{action}'.")
                except Exception as db_err:
                    _safe_log(f"[PERMISSION NOTIFIER ERROR] Could not save send count to DB: {db_err}")

            return notified_any
        except Exception as e:
            _safe_log(f"[PERMISSION NOTIFIER ERROR] {e}")
            return False

    def clear_owner_notification(
        self,
        guild_id: int,
        channel_id: int,
        permission: str,
        action: Optional[str] = None
    ):
        """Clears the 1-DM sent state once permission has been restored, allowing future notification if revoked again."""
        perm_name = format_perm_name(permission)
        dedup_key = (guild_id, channel_id, perm_name)
        self._owner_notified.discard(dedup_key)

        matched_keys = [k for k in self._server_notified.keys() if k[0] == guild_id]
        if matched_keys:
            for key in matched_keys:
                if action and key[1] != action.lower().strip():
                    continue
                notified_chans = self._server_notified_channels.get(key, set())
                notified_chans.discard(channel_id)
                if not notified_chans:
                    self._server_notified.pop(key, None)
                    self._server_notified_channels.pop(key, None)
                    try:
                        from utils.permission_db import reset_permission_dm_tracking
                        reset_permission_dm_tracking(guild_id, key[1])
                    except Exception:
                        pass
        else:
            # If in-memory state is empty (e.g. after bot restart), still reset persistent DB tracking
            try:
                from utils.permission_db import reset_permission_dm_tracking
                reset_permission_dm_tracking(guild_id, action)
            except Exception:
                pass

    def clear_server_notification(
        self,
        guild_id: int,
        action: Optional[str] = None
    ):
        """Clears server-level notification state completely."""
        if action:
            action_key = action.lower().strip()
            key = (guild_id, action_key)
            self._server_notified.pop(key, None)
            self._server_notified_channels.pop(key, None)
            try:
                from utils.permission_db import reset_permission_dm_tracking
                reset_permission_dm_tracking(guild_id, action_key)
            except Exception:
                pass
        else:
            for k in list(self._server_notified.keys()):
                if k[0] == guild_id:
                    self._server_notified.pop(k, None)
                    self._server_notified_channels.pop(k, None)
            try:
                from utils.permission_db import reset_permission_dm_tracking
                reset_permission_dm_tracking(guild_id, None)
            except Exception:
                pass

    def get_send_count(self, guild_id: int, action: str) -> int:
        """Returns the persistent DB send count for a given guild and action."""
        try:
            from utils.permission_db import get_permission_send_count
            return get_permission_send_count(guild_id, action)
        except Exception:
            return 0

    def can_send(self, guild_id: int, action: str, max_sends: int = 1) -> bool:
        """Returns True if the action has been sent less than max_sends times."""
        try:
            from utils.permission_db import can_send_permission_dm
            return can_send_permission_dm(guild_id, action, max_sends=max_sends)
        except Exception:
            return True


# Global singleton instance
permission_handler = PermissionHandler()


async def handle_missing_permission(
    ctx_or_interaction: Union[commands.Context, discord.Interaction],
    action: str,
    permission: Optional[str] = None,
    channel: Optional[discord.abc.GuildChannel] = None
) -> bool:
    """Convenience helper to dispatch a missing permission notification."""
    return await permission_handler.handle_missing_permission(
        ctx_or_interaction=ctx_or_interaction,
        action=action,
        permission=permission,
        channel=channel
    )


async def notify_server_owner_once(
    guild: discord.Guild,
    action: str,
    permission: str,
    channel: Optional[discord.abc.GuildChannel] = None,
    debounce_seconds: float = 10.0,
    server_cooldown_seconds: float = 3600.0
) -> bool:
    """Convenience helper to dispatch a strictly filtered 1-time consolidated DM alert to the server owner."""
    return await permission_handler.notify_server_owner_once(
        guild=guild,
        action=action,
        permission=permission,
        channel=channel,
        debounce_seconds=debounce_seconds,
        server_cooldown_seconds=server_cooldown_seconds
    )


async def flush_server_batch(
    guild_id: int,
    action: str
) -> bool:
    """Convenience helper to immediately flush any pending aggregated batch."""
    return await permission_handler.flush_server_batch(guild_id=guild_id, action=action)


def scan_session(
    guild: discord.Guild,
    action: str,
    permission: Optional[str] = None,
    server_cooldown_seconds: float = 3600.0
) -> ScanSession:
    """Convenience helper to create an explicit scan session context manager."""
    return permission_handler.scan_session(
        guild=guild,
        action=action,
        permission=permission,
        server_cooldown_seconds=server_cooldown_seconds
    )


async def report_permission_failure(
    guild: discord.Guild,
    action: str,
    permission: Optional[str] = None,
    channel: Optional[discord.abc.GuildChannel] = None,
    error: Optional[Any] = None
) -> bool:
    """Convenience helper to report a permission failure."""
    return await permission_handler.report_permission_failure(
        guild=guild,
        action=action,
        permission=permission,
        channel=channel,
        error=error
    )


notify_server_authorities_once = notify_server_owner_once


def get_permission_send_count(guild_id: int, action: str) -> int:
    """Returns the persistent DB send count for a given guild and action."""
    return permission_handler.get_send_count(guild_id=guild_id, action=action)


def can_send_permission_dm(guild_id: int, action: str, max_sends: int = 1) -> bool:
    """Returns True if the DM can be sent (send_count < max_sends)."""
    return permission_handler.can_send(guild_id=guild_id, action=action, max_sends=max_sends)


def reset_permission_dm_tracking(guild_id: int, action: Optional[str] = None):
    """Resets the persistent DB send count when permissions are restored."""
    try:
        from utils.permission_db import reset_permission_dm_tracking as _reset_db
        _reset_db(guild_id=guild_id, action=action)
    except Exception:
        pass

