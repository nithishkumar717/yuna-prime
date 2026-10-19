"""
Yuna Auto-Logging System V2 - Webhook & Log Dispatcher Service
Enables high-resolution, rate-limit immune audit logging sent via Discord Webhooks
outside of standard bot messages across all Discord servers.
"""

from __future__ import annotations
import os
import re
import time
import json
import asyncio
import unicodedata
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import discord
import aiosqlite
from services.log_components_v2 import build_log_v2_views
from services.logging_config import extract_setup_channel_ids, merge_dashboard_events

DB_PATH = "db/audit_logs.db"
SNOWFLAKE_TEXT_RE = re.compile(
    r"(?<!<@)(?<!<@!)(?<!<@&)(?<!<#)(?<!\d)\d{17,20}(?!\d|>)"
)


def _hide_embed_ids(embed: discord.Embed) -> discord.Embed:
    """Hide raw Discord snowflakes in visible embed text without breaking mentions."""
    data = embed.to_dict()

    def redact(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        # Keep a readable name but remove user-profile links that expose an ID.
        value = re.sub(
            r"\[([^\]]+)\]\(https?://(?:www\.)?discord(?:app)?\.com/users/\d{17,20}\)",
            r"\1",
            value,
        )
        return SNOWFLAKE_TEXT_RE.sub("[hidden]", value)

    for key in ("title", "description"):
        if key in data:
            data[key] = redact(data[key])
    if isinstance(data.get("author"), dict) and "name" in data["author"]:
        data["author"]["name"] = redact(data["author"]["name"])
    if isinstance(data.get("footer"), dict) and "text" in data["footer"]:
        data["footer"]["text"] = redact(data["footer"]["text"])
    for field in data.get("fields", []):
        for key in ("name", "value"):
            if key in field:
                field[key] = redact(field[key])
    return discord.Embed.from_dict(data)

# Unicode small caps mapping for channel name normalization
SMALL_CAPS: Dict[str, str] = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ',
    'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
    's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
}
REVERSE_SMALL_CAPS: Dict[str, str] = {v: k for k, v in SMALL_CAPS.items()}
REVERSE_SMALL_CAPS.update({
    'ꞯ': 'q', 'ѕ': 's', '×': 'x', 'ⅹ': 'x', 'ᴠ': 'v', 'ᴡ': 'w', 'ʏ': 'y', 'ᴢ': 'z'
})


def normalize_channel_name(name: str) -> str:
    """Normalizes small-caps or stylized channel name to standard ASCII lowercase."""
    step1 = "".join(REVERSE_SMALL_CAPS.get(ch, ch) for ch in name)
    nfkd = unicodedata.normalize('NFKD', step1)
    return "".join(REVERSE_SMALL_CAPS.get(ch, ch) for ch in nfkd).lower()


def _webhook_identity(url: Optional[str]) -> Optional[tuple[str, str]]:
    if not url:
        return None
    match = re.search(r"/api/webhooks/(\d+)/([^/?]+)", str(url))
    return (match.group(1), match.group(2)) if match else None


class LoggerServiceV2:
    """
    Central logging service for Yuna V2 logs.
    Dispatches Components V2 log cards via per-channel webhooks under the 'Yuna Logs'
    category with universal multi-server compatibility and graceful fallbacks.
    """
    _webhook_cache: Dict[int, discord.Webhook] = {}  # channel_id -> Webhook
    _guild_config_cache: Dict[int, Dict[str, Any]] = {}  # guild_id -> categories_map
    _webhook_last_send: Dict[int, float] = {}  # webhook_id -> timestamp

    @classmethod
    def update_guild_cache(cls, guild_id: int, categories_map: Dict[str, Any]):
        """Caches channel and webhook mapping for a guild to allow zero-latency lookup."""
        previous = cls._guild_config_cache.get(guild_id, {})
        preserved_keys = (
            "_customWebhookUrl", "_customWebhookEnabled", "_logRetention",
            "categories", "serverLogsChannel", "modLogsChannel", "perEventEnabled",
            "eventsConfig", "disabledEvents", "channelMappings", "ignoredChannels",
            "ignoredCategories", "ignoredRoles", "displayOldRoles", "displayIds",
            "moderationActions",
        )
        for preserved_key in preserved_keys:
            if preserved_key not in categories_map and preserved_key in previous:
                categories_map[preserved_key] = previous[preserved_key]
        cls._guild_config_cache[guild_id] = categories_map

    @classmethod
    async def get_executor(
        cls,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        target_id: Optional[int] = None
    ) -> Optional[discord.abc.User]:
        """Fetches the responsible moderator/executor from Discord Audit Logs."""
        if not guild or not guild.me or not guild.me.guild_permissions.view_audit_log:
            return None
        try:
            async for entry in guild.audit_logs(limit=3, action=action):
                is_recent = (time.time() - entry.created_at.timestamp()) < 10.0
                if is_recent:
                    if target_id is None or (entry.target and getattr(entry.target, "id", None) == target_id):
                        return entry.user
        except Exception:
            pass
        return None

    @classmethod
    async def resolve_member_departure(
        cls,
        guild: discord.Guild,
        member: discord.abc.User | discord.Member,
    ) -> Tuple[str, Optional[discord.abc.User], str]:
        """
        Determines whether a member left voluntarily, was kicked, or was banned.
        Returns:
            (departure_type, executor, reason)
            departure_type: 'self_left' | 'kicked' | 'banned' | 'unknown'
            executor: Optional[discord.abc.User] (responsible moderator)
            reason: str (departure reason text)
        """
        if not guild or not guild.me:
            return "unknown", None, "Unknown"

        # Permission verification: If bot cannot view audit logs, departure cannot be verified.
        if not getattr(guild.me.guild_permissions, "view_audit_log", False):
            return "unknown", None, "Unknown"

        member_id = member.id
        now_dt = datetime.now(timezone.utc)

        # Retry loop to handle Discord audit log propagation delay.
        # Delays: 0.0s (immediate), 0.5s, 0.7s (up to ~1.2s total wait)
        delays = [0.0, 0.5, 0.7]
        audit_accessible = True

        for attempt, delay in enumerate(delays):
            if delay > 0:
                await asyncio.sleep(delay)

            try:
                # 1. Check for recent ban audit log
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.ban):
                    target_id = getattr(entry.target, "id", None)
                    if target_id == member_id:
                        entry_time = entry.created_at
                        if entry_time.tzinfo is None:
                            entry_time = entry_time.replace(tzinfo=timezone.utc)
                        age = (now_dt - entry_time).total_seconds()
                        if -5.0 <= age <= 15.0:
                            reason = (entry.reason or "").strip() or "No reason provided."
                            return "banned", entry.user, reason

                # 2. Check for recent kick audit log
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.kick):
                    target_id = getattr(entry.target, "id", None)
                    if target_id == member_id:
                        entry_time = entry.created_at
                        if entry_time.tzinfo is None:
                            entry_time = entry_time.replace(tzinfo=timezone.utc)
                        age = (now_dt - entry_time).total_seconds()
                        if -5.0 <= age <= 15.0:
                            reason = (entry.reason or "").strip() or "No reason provided."
                            return "kicked", entry.user, reason

            except (discord.Forbidden, discord.HTTPException):
                audit_accessible = False
                break
            except Exception:
                audit_accessible = False
                break

        if not audit_accessible:
            return "unknown", None, "Unknown"

        # Secondary check: If ban entry exists in guild bans
        try:
            ban_entry = await guild.fetch_ban(member)
            if ban_entry:
                reason = (ban_entry.reason or "").strip() or "No reason provided."
                ban_executor = None
                try:
                    async for entry in guild.audit_logs(limit=25, action=discord.AuditLogAction.ban):
                        if getattr(entry.target, "id", None) == member_id:
                            ban_executor = entry.user
                            if entry.reason:
                                reason = entry.reason.strip()
                            break
                except Exception:
                    pass
                return "banned", ban_executor, reason
        except discord.NotFound:
            pass
        except Exception:
            pass

        # Successfully queried audit logs with retries, no kick/ban found -> voluntary departure
        return "self_left", None, "Voluntarily left the server."

    @classmethod
    async def get_channel_webhook(cls, channel: discord.TextChannel) -> Optional[discord.Webhook]:
        """Fetches cached webhook or resolves/creates 'Yuna Logs Webhook' for the target channel."""
        if channel.id in cls._webhook_cache:
            return cls._webhook_cache[channel.id]

        try:
            webhooks = await channel.webhooks()
            webhook = next((w for w in webhooks if w.name == "Yuna Logs Webhook" or (w.user and w.user.id == channel.guild.me.id)), None)

            if not webhook and channel.permissions_for(channel.guild.me).manage_webhooks:
                avatar_bytes = None
                try:
                    bot_user = channel.guild.me
                    if bot_user and getattr(bot_user, "display_avatar", None):
                        avatar_bytes = await bot_user.display_avatar.read()
                except Exception:
                    pass
                webhook = await channel.create_webhook(
                    name="Yuna Logs Webhook",
                    avatar=avatar_bytes,
                    reason="Yuna Logs V2 Auto-Provision"
                )

            if webhook:
                cls._webhook_cache[channel.id] = webhook
            return webhook
        except Exception:
            return None

    @classmethod
    async def _resolve_guild_config(cls, guild_id: int) -> Dict[str, Any]:
        """Loads categories configuration from cache or DB for the guild."""
        if guild_id in cls._guild_config_cache:
            return cls._guild_config_cache[guild_id]

        try:
            if os.path.exists(DB_PATH):
                async with aiosqlite.connect(DB_PATH, timeout=5.0) as db:
                    async with db.execute(
                        "SELECT webhook_forward_url, webhook_forward_enabled, retention, categories_json FROM server_logs_config WHERE guild_id = ?",
                        (guild_id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            config = json.loads(row[3] or "{}")
                            if not isinstance(config, dict):
                                config = {"categories": config} if isinstance(config, list) else {}
                            setup_channels = extract_setup_channel_ids(config)
                            if setup_channels:
                                config["eventsConfig"] = merge_dashboard_events(
                                    config.get("eventsConfig"),
                                    setup_channels,
                                )
                            config.update({
                                "_customWebhookUrl": row[0] or "",
                                "_customWebhookEnabled": bool(row[1]),
                                "_logRetention": row[2] or "90 Days",
                            })
                            cls._guild_config_cache[guild_id] = config
                            return config
        except Exception:
            pass
        return {}

    @staticmethod
    def _resolve_text_channel(guild: discord.Guild, value: Any) -> Optional[discord.TextChannel]:
        """Resolve a configured channel ID or channel name in this guild."""
        channel_value = str(value or "").strip()
        if not channel_value:
            return None
        if channel_value.isdigit():
            channel = guild.get_channel(int(channel_value))
        else:
            clean_name = channel_value.lstrip("#").lower()
            channel = discord.utils.find(
                lambda item: normalize_channel_name(item.name) == clean_name
                or item.name.lower() == clean_name,
                guild.text_channels,
            )
        return channel if isinstance(channel, discord.TextChannel) else None

    @classmethod
    async def resolve_target_channel(
        cls,
        guild: discord.Guild,
        channel_key: str,
        event_key: Optional[str] = None,
        source_channel: Optional[discord.abc.GuildChannel] = None,
        moderation_action: Optional[str] = None,
    ) -> Tuple[Optional[discord.TextChannel], Optional[str]]:
        """
        Resolves destination TextChannel and optional target Webhook URL for given guild
        and log event/category based on dashboard config, overrides, or dynamic locator.
        """
        if not guild:
            return None, None

        key_lower = channel_key.lower()
        event_key_lower = event_key.lower() if event_key else None
        target_channel: Optional[discord.TextChannel] = None
        target_webhook_url: Optional[str] = None

        guild_config = await cls._resolve_guild_config(guild.id)
        categories_list = None
        per_event_enabled = False
        events_config = {}
        server_logs_channel = ""
        mod_logs_channel = ""
        channel_mappings = []

        if isinstance(guild_config, dict) and "categories" in guild_config:
            categories_list = guild_config.get("categories")
            per_event_enabled = bool(guild_config.get("perEventEnabled", False))
            events_config = guild_config.get("eventsConfig", {})
            server_logs_channel = str(guild_config.get("serverLogsChannel", "")).strip()
            mod_logs_channel = str(guild_config.get("modLogsChannel", "")).strip()
            channel_mappings = guild_config.get("channelMappings", [])
        elif isinstance(guild_config, list):
            categories_list = guild_config

        # Check per-event channel override first if enabled
        if per_event_enabled:
            route_key = event_key_lower or key_lower
            event_ch = events_config.get(route_key) if isinstance(events_config, dict) else None
            if not event_ch and event_key_lower:
                event_ch = events_config.get(key_lower) if isinstance(events_config, dict) else None
            if not event_ch:
                is_mod = bool(moderation_action) or (event_key_lower in {"warn", "softban", "note", "kick", "ban", "unban", "timeout"}) or (key_lower in ("mod", "ban", "automod", "security"))
                if is_mod and mod_logs_channel:
                    event_ch = mod_logs_channel
                elif server_logs_channel:
                    event_ch = server_logs_channel
            if event_ch:
                target_channel = cls._resolve_text_channel(guild, event_ch)

        # Check single server logs channel / mod logs channel if per-event is disabled
        if not target_channel and not per_event_enabled:
            is_moderation_log = bool(moderation_action) or event_key_lower in {
                "ban", "unban", "kick", "timeout"
            } or key_lower in ("mod", "ban", "automod", "security")
            master_ch = mod_logs_channel if is_moderation_log and mod_logs_channel else server_logs_channel
            if master_ch:
                target_channel = cls._resolve_text_channel(guild, master_ch)

        # Source-to-log channel mappings
        if source_channel:
            mapped_source = getattr(source_channel, "parent", None) or source_channel
            source_channel_id = str(getattr(mapped_source, "id", "")) or None
            if source_channel_id and isinstance(channel_mappings, list):
                for mapping in channel_mappings:
                    if not isinstance(mapping, dict):
                        continue
                    if str(mapping.get("sourceChannelId", "")) != source_channel_id:
                        continue
                    mapped_channel = cls._resolve_text_channel(
                        guild, mapping.get("logChannelId", "")
                    )
                    if mapped_channel:
                        target_channel = mapped_channel
                        target_webhook_url = None
                    break

        if not target_channel and categories_list:
            for cat in categories_list:
                cat_id = str(cat.get("id", "")).lower()
                cat_ch = str(cat.get("channel", "")).strip()
                cat_enabled = cat.get("enabled", True)
                if not cat_enabled:
                    if key_lower in cat_id or cat_id in key_lower:
                        return None, None

                if key_lower in cat_id or cat_id in key_lower:
                    if cat_ch:
                        resolved = cls._resolve_text_channel(guild, cat_ch)
                        if isinstance(resolved, discord.TextChannel):
                            target_channel = resolved
                            break

        if not target_channel and isinstance(guild_config, dict) and key_lower in guild_config:
            entry = guild_config[key_lower]
            if isinstance(entry, dict):
                ch_id = entry.get("channel_id")
                if ch_id:
                    resolved = guild.get_channel(int(ch_id))
                    if isinstance(resolved, discord.TextChannel):
                        target_channel = resolved
                        target_webhook_url = entry.get("webhook_url")

        # Dynamic search path: Universal channel locator
        if not target_channel:
            if key_lower == 'joins':
                pat = r'(^|[^a-z0-9])joins?([^a-z0-9]|$)'
            elif key_lower == 'leaves':
                pat = r'(^|[^a-z0-9])(leave|leaves)([^a-z0-9]|$)'
            else:
                pat = rf'(^|[^a-z0-9]){re.escape(key_lower)}([^a-z0-9]|$)'

            candidates: List[tuple[int, discord.TextChannel]] = []
            for ch in guild.text_channels:
                norm_name = normalize_channel_name(ch.name)
                if re.search(pat, norm_name):
                    cat_name = ch.category.name.lower() if ch.category else ""
                    is_yuna_cat = ("yuna" in cat_name and "log" in cat_name) or cat_name in ("yuna logs", "❀ yuna・logs", "🌸 yuna・logs")
                    is_logs_cat = "logs" in cat_name
                    has_yuna_name = any(k in norm_name for k in ("yuna", "❀", "🌸"))
                    has_yuna_topic = getattr(ch, "topic", None) and any(t in ch.topic for t in ("Automated Audit Logs", "Antinuke Security Alerts"))

                    score = (10 if is_yuna_cat else 0) + (5 if has_yuna_topic else 0) + (3 if is_logs_cat else 0) + (2 if has_yuna_name else 0)
                    candidates.append((score, ch))

            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                target_channel = candidates[0][1]

        return target_channel, target_webhook_url

    @classmethod
    async def send_v2_log(
        cls,
        guild: discord.Guild,
        channel_key: str,
        title: str = "",
        description: str = "",
        color: int = 0x2B2D31,
        user: Optional[discord.abc.User] = None,
        executor: Optional[discord.abc.User] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        embed: Optional[discord.Embed] = None,
        view: Optional[discord.ui.LayoutView] = None,
        silent: Optional[bool] = None,
        event_key: Optional[str] = None,
        source_channel: Optional[discord.abc.GuildChannel] = None,
        moderation_action: Optional[str] = None
    ) -> bool:
        """
        Dispatches a structured Components V2 panel to the appropriate logging channel
        under the Yuna Logs category via Webhook across any Discord server.
        """
        if not guild:
            return False

        key_lower = channel_key.lower()
        event_key_lower = event_key.lower() if event_key else None

        # 1. Check in-memory/DB configured channel mapping & ignore rules
        guild_config = await cls._resolve_guild_config(guild.id)
        disabled_events = set()
        ignored_channels = []
        ignored_categories = []
        ignored_roles = []
        display_old_roles = True
        display_ids = True
        moderation_actions = {}

        if isinstance(guild_config, dict):
            disabled_events = {
                str(value).lower()
                for value in guild_config.get("disabledEvents", [])
                if isinstance(value, str)
            }
            ignored_channels = [str(x) for x in guild_config.get("ignoredChannels", [])]
            ignored_categories = [str(x) for x in guild_config.get("ignoredCategories", [])]
            ignored_roles = [str(x) for x in guild_config.get("ignoredRoles", [])]
            display_old_roles = bool(guild_config.get("displayOldRoles", True))
            display_ids = bool(guild_config.get("displayIds", True))
            moderation_actions = guild_config.get("moderationActions", {})

        # Apply event-specific and category switches
        disabled_route_keys = {key_lower}
        if event_key_lower:
            disabled_route_keys.add(event_key_lower)
        if disabled_route_keys.intersection(disabled_events):
            return False

        if moderation_action and isinstance(moderation_actions, dict):
            if not moderation_actions.get(moderation_action.lower(), True):
                return False

        # Check ignored roles against user or executor
        check_user = user or executor
        if check_user and hasattr(check_user, "roles") and ignored_roles:
            for r in getattr(check_user, "roles", []):
                if str(r.id) in ignored_roles:
                    return False

        # Source channel checks
        if source_channel:
            mapped_source = getattr(source_channel, "parent", None) or source_channel
            source_channel_id = str(getattr(mapped_source, "id", "")) or None
            source_category_id = getattr(mapped_source, "category_id", None)
            if source_channel_id and source_channel_id in ignored_channels:
                return False
            if source_category_id and str(source_category_id) in ignored_categories:
                return False

        target_channel, target_webhook_url = await cls.resolve_target_channel(
            guild=guild,
            channel_key=channel_key,
            event_key=event_key,
            source_channel=source_channel,
            moderation_action=moderation_action,
        )

        if not target_channel:
            return False

        # Build the legacy embed-shaped data first, then render it as a Components V2 card.
        if not embed and view is None:
            embed = discord.Embed(
                title=title or f"[{channel_key.upper()} LOG]",
                description=description,
                color=color,
                timestamp=discord.utils.utcnow()
            )
            if user:
                avatar_url = getattr(getattr(user, "display_avatar", None), "url", None)
                embed.set_author(name=f"{title} • {user}", icon_url=avatar_url)

            if fields:
                for f in fields:
                    embed.add_field(
                        name=f.get("name", "\u200b"),
                        value=f.get("value", "\u200b"),
                        inline=f.get("inline", False)
                    )

            if event_key_lower == "leaves" and display_old_roles and user and hasattr(user, "roles"):
                old_roles = [role.mention for role in user.roles if not role.is_default()]
                if old_roles:
                    embed.add_field(
                        name="Roles",
                        value=", ".join(old_roles)[:1024],
                        inline=False,
                    )

            if key_lower == "leaves" or event_key_lower == "leaves":
                footer_text = f"Guild ID: {guild.id}"
            else:
                footer_text = f"Action by: {executor} ({executor.id})" if executor else f"Guild ID: {guild.id}"
            embed.set_footer(
                text=footer_text,
                icon_url=getattr(getattr(guild.me, "display_avatar", None), "url", None) if guild else None
            )

        if not display_ids and embed is not None:
            embed = _hide_embed_ids(embed)

        if view is None and embed is not None:
            rendered_views = build_log_v2_views([embed], channel_key)
            if rendered_views:
                view = rendered_views[0]

        # Determine notification suppression (mute mode):
        # All logs are muted (silent / suppress_notifications) EXCEPT antinuke and security logs.
        if silent is None:
            is_critical_security = key_lower in ("antinuke", "security")
            is_silent = not is_critical_security
        else:
            is_silent = bool(silent)

        allowed_mentions = discord.AllowedMentions.none() if is_silent else discord.AllowedMentions(everyone=True, roles=True, users=True)
        message_kwargs = {
            "silent": is_silent,
            "allowed_mentions": allowed_mentions,
        }
        if view is not None:
            message_kwargs["view"] = view
        elif embed is not None:
            message_kwargs["embed"] = embed

        # 0. Stream to Axiom Cloud in background (0 MB VPS disk usage!)
        try:
            from services.axiom_logger import is_axiom_configured, send_to_axiom
            if is_axiom_configured() and event_key_lower != "message_delete":
                event_data = {
                    "id": f"v2log-{guild.id}-{int(time.time() * 1000)}",
                    "guild_id": str(guild.id),
                    "guild_name": guild.name,
                    "channel_key": channel_key,
                    "event_key": event_key_lower or "",
                    "module": channel_key.upper(),
                    "action": title or f"[{channel_key.upper()} LOG]",
                    "headline": title or ((description[:100] if description else f"[{channel_key.upper()} LOG]")),
                    "details": description,
                    "actor": str(executor) if executor else "Unknown",
                    "actorId": str(executor.id) if executor else "0",
                    "target": str(user) if user else "Server",
                    "targetId": str(user.id) if user else "",
                    "timestamp": discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "createdAt": time.time()
                }
                if event_key_lower in {"joins", "bot_add"}:
                    event_data["items"] = [
                        f"{str(field.get('name') or 'Detail').strip()}: {str(field.get('value') or '').strip()}"
                        for field in (fields or [])
                        if isinstance(field, dict) and str(field.get("value") or "").strip()
                    ]
                    if event_key_lower == "joins":
                        for field in fields or []:
                            if not isinstance(field, dict):
                                continue
                            field_name = str(field.get("name") or "").strip().lower()
                            field_value = str(field.get("value") or "").strip()
                            if field_name == "invited by":
                                event_data["invitedBy"] = field_value
                            elif field_name == "invite code":
                                event_data["inviteCode"] = field_value

                    # For a human join, the joining member is the subject of the event
                    # and provides the most useful identity/avatar in the audit trail.
                    if event_key_lower == "joins" and user:
                        avatar = getattr(getattr(user, "display_avatar", None), "url", "")
                        event_data.update({
                            "headline": f"{user} joined the server",
                            "actor": str(user),
                            "actorId": str(user.id),
                            "actorAvatar": str(avatar) if avatar else "",
                            "target": "Server",
                            "targetId": str(guild.id),
                        })
                elif event_key_lower == "leaves":
                    for field in (fields or []):
                        if isinstance(field, dict) and str(field.get("name", "")).strip().lower() == "departure reason":
                            event_data["departureReason"] = str(field.get("value", "")).strip()

                asyncio.create_task(send_to_axiom([event_data]))
        except Exception:
            pass

        custom_webhook_url = str(guild_config.get("_customWebhookUrl", "")).strip() if isinstance(guild_config, dict) else ""
        custom_webhook_enabled = bool(guild_config.get("_customWebhookEnabled", False)) if isinstance(guild_config, dict) else False
        channel_delivery_succeeded = False
        channel_webhook_url = target_webhook_url

        # 1. Send via the selected channel's webhook.
        try:
            webhook = None
            if target_webhook_url:
                try:
                    client_session = getattr(guild._state, "_get_client", lambda: None)()
                    webhook = discord.Webhook.from_url(target_webhook_url, client=client_session)
                except Exception:
                    webhook = None

            if not webhook:
                webhook = await cls.get_channel_webhook(target_channel)

            if webhook:
                channel_webhook_url = getattr(webhook, "url", None) or channel_webhook_url
                bot_user = guild.me
                username = "Yuna Logs"
                avatar_url = getattr(getattr(bot_user, "display_avatar", None), "url", None) if bot_user else None
                wh_id = getattr(webhook, "id", None) or 0
                now_t = time.time()
                last_t = cls._webhook_last_send.get(wh_id, 0.0)
                if (now_t - last_t) < 0.25:
                    await asyncio.sleep(0.25 - (now_t - last_t))
                cls._webhook_last_send[wh_id] = time.time()
                try:
                    await webhook.send(
                        username=username,
                        avatar_url=avatar_url,
                        **message_kwargs
                    )
                    channel_delivery_succeeded = True
                except Exception:
                    if "view" in message_kwargs and embed is not None:
                        try:
                            fb_kwargs = dict(message_kwargs)
                            fb_kwargs.pop("view", None)
                            fb_kwargs["embed"] = embed
                            await webhook.send(
                                username=username,
                                avatar_url=avatar_url,
                                **fb_kwargs
                            )
                            channel_delivery_succeeded = True
                        except Exception:
                            pass
        except Exception:
            pass

        # Keep the selected channel useful if its webhook delivery fails.
        if not channel_delivery_succeeded:
            try:
                if target_channel.permissions_for(guild.me).send_messages:
                    try:
                        await target_channel.send(**message_kwargs)
                        channel_delivery_succeeded = True
                    except Exception:
                        if "view" in message_kwargs and embed is not None:
                            fb_kwargs = dict(message_kwargs)
                            fb_kwargs.pop("view", None)
                            fb_kwargs["embed"] = embed
                            await target_channel.send(**fb_kwargs)
                            channel_delivery_succeeded = True
            except Exception:
                pass

        # The dashboard's optional webhook is an additional destination. If it
        # points at the same webhook already used for channel delivery, skip it
        # to avoid duplicate log messages.
        custom_webhook_succeeded = False
        same_webhook = (
            _webhook_identity(custom_webhook_url)
            and _webhook_identity(custom_webhook_url) == _webhook_identity(channel_webhook_url)
        )
        if custom_webhook_enabled and custom_webhook_url and not same_webhook:
            try:
                client_session = getattr(guild._state, "_get_client", lambda: None)()
                custom_webhook = discord.Webhook.from_url(custom_webhook_url, client=client_session)
                bot_user = guild.me
                cwh_id = getattr(custom_webhook, "id", None) or 0
                now_t = time.time()
                last_t = cls._webhook_last_send.get(cwh_id, 0.0)
                if (now_t - last_t) < 0.25:
                    await asyncio.sleep(0.25 - (now_t - last_t))
                cls._webhook_last_send[cwh_id] = time.time()
                try:
                    await custom_webhook.send(
                        username="Yuna Logs",
                        avatar_url=getattr(getattr(bot_user, "display_avatar", None), "url", None) if bot_user else None,
                        **message_kwargs,
                    )
                    custom_webhook_succeeded = True
                except Exception:
                    if "view" in message_kwargs and embed is not None:
                        fb_kwargs = dict(message_kwargs)
                        fb_kwargs.pop("view", None)
                        fb_kwargs["embed"] = embed
                        await custom_webhook.send(
                            username="Yuna Logs",
                            avatar_url=getattr(getattr(bot_user, "display_avatar", None), "url", None) if bot_user else None,
                            **fb_kwargs,
                        )
                        custom_webhook_succeeded = True
            except Exception as exc:
                print(f"[SERVER LOG WEBHOOK WARN] Guild {guild.id}: configured forwarding webhook failed: {exc}")

        return channel_delivery_succeeded or custom_webhook_succeeded
