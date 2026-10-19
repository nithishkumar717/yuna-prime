"""Anti-Nuke V2 Engine — Comprehensive Action Mapper.

Maps Discord gateway audit log actions, entity events, and raw payload types
to standardized V2 protected actions with granular metadata extraction.
"""
from __future__ import annotations

import discord
from typing import Any, Dict, Optional, Tuple

# Comprehensive Protected Action Codes in V2
V2_PROTECTED_ACTIONS = {
    # Channels
    "chcr": "channel_create",
    "chdl": "channel_delete",
    "chup": "channel_update",
    "overwrite_create": "permission_overwrite_create",
    "overwrite_update": "permission_overwrite_update",
    "overwrite_delete": "permission_overwrite_delete",
    # Roles
    "rlcr": "role_create",
    "rldl": "role_delete",
    "rlup": "role_update",
    "memup": "dangerous_role_grant",
    # Members
    "ban": "member_ban",
    "unban": "member_unban",
    "kick": "member_kick",
    "prune": "member_prune",
    "botadd": "bot_add",
    # Guild & Integrations
    "serverup": "guild_update",
    "vanity": "vanity_url_change",
    "mngweb": "webhook_manage",
    "webhook_create": "webhook_create",
    "webhook_update": "webhook_update",
    "webhook_delete": "webhook_delete",
    "integration": "integration_manage",
    # Assets & Invites
    "emocr": "emoji_create",
    "emodl": "emoji_delete",
    "stkcr": "sticker_create",
    "stkdl": "sticker_delete",
    "invdl": "invite_delete",
    # Messages
    "everyone": "mass_mention_everyone",
}

# AuditLogAction Enum to V2 Action Code
AUDIT_ACTION_MAP: Dict[discord.AuditLogAction, str] = {
    # Channel actions
    discord.AuditLogAction.channel_create: "chcr",
    discord.AuditLogAction.channel_delete: "chdl",
    discord.AuditLogAction.channel_update: "chup",
    discord.AuditLogAction.overwrite_create: "overwrite_create",
    discord.AuditLogAction.overwrite_update: "overwrite_update",
    discord.AuditLogAction.overwrite_delete: "overwrite_delete",
    # Role actions
    discord.AuditLogAction.role_create: "rlcr",
    discord.AuditLogAction.role_delete: "rldl",
    discord.AuditLogAction.role_update: "rlup",
    # Member actions
    discord.AuditLogAction.ban: "ban",
    discord.AuditLogAction.unban: "unban",
    discord.AuditLogAction.kick: "kick",
    discord.AuditLogAction.member_prune: "prune",
    discord.AuditLogAction.bot_add: "botadd",
    discord.AuditLogAction.member_role_update: "memup",
    # Guild actions
    discord.AuditLogAction.guild_update: "serverup",
    # Webhooks & Integrations
    discord.AuditLogAction.webhook_create: "webhook_create",
    discord.AuditLogAction.webhook_update: "webhook_update",
    discord.AuditLogAction.webhook_delete: "webhook_delete",
    discord.AuditLogAction.integration_create: "integration",
    discord.AuditLogAction.integration_delete: "integration",
    # Emojis & Stickers
    discord.AuditLogAction.emoji_create: "emocr",
    discord.AuditLogAction.emoji_delete: "emodl",
    discord.AuditLogAction.emoji_update: "emoup",
    discord.AuditLogAction.sticker_create: "stkcr",
    discord.AuditLogAction.sticker_delete: "stkdl",
    discord.AuditLogAction.sticker_update: "stkup",
    # Invites
    discord.AuditLogAction.invite_delete: "invdl",
}


class ActionMapper:
    """Translates audit entries and Discord events into unified V2 action descriptors."""

    @staticmethod
    def normalize_action(action_str: str) -> str:
        """Converts user input or event string into standardized V2 action code."""
        s = action_str.lower().strip().replace(" ", "_").replace("-", "")
        if s in V2_PROTECTED_ACTIONS:
            return s
        for code, friendly in V2_PROTECTED_ACTIONS.items():
            clean_friendly = friendly.lower().replace("_", "")
            if s == clean_friendly or s == code:
                return code
        return action_str.lower().strip()

    @staticmethod
    def map_audit_entry(entry: Any) -> Tuple[Optional[str], Optional[int], Dict[str, Any]]:
        """Maps an AuditLogEntry to (action_code, target_id, extra_metadata).
        
        Detects special sub-cases like Vanity URL changes or dangerous permission grants.
        """
        action = getattr(entry, "action", None)
        if action not in AUDIT_ACTION_MAP:
            return None, None, {}

        action_code = AUDIT_ACTION_MAP[action]
        target_id = getattr(entry, "target_id", None) or getattr(entry, "_target_id", None)
        if target_id is None and hasattr(entry, "target") and hasattr(entry.target, "id"):
            target_id = entry.target.id

        extra: Dict[str, Any] = {}

        # 1. Detect Vanity URL changes in guild_update
        if action == discord.AuditLogAction.guild_update and hasattr(entry, "changes") and entry.changes is not None:
            after_changes = getattr(entry.changes, "after", None)
            if after_changes is not None:
                vanity_val = getattr(after_changes, "vanity_url_code", None)
                if isinstance(vanity_val, str):
                    action_code = "vanity"
                    extra["vanity_url_change"] = True

        # 2. Extract permission changes in role_update
        if action == discord.AuditLogAction.role_update and getattr(entry, "changes", None) is not None:
            after_changes = getattr(entry.changes, "after", None)
            extra["has_permission_changes"] = bool(after_changes and hasattr(after_changes, "permissions"))

        return action_code, target_id, extra

    @staticmethod
    def is_dangerous_role_grant(before: Any, after: Any) -> bool:
        """Checks if a member update gave them Administrator or dangerous permissions."""
        before_roles = set(getattr(before, "roles", []))
        after_roles = set(getattr(after, "roles", []))
        new_roles = after_roles - before_roles
        
        for role in new_roles:
            perms = getattr(role, "permissions", None)
            if perms:
                if perms.administrator or perms.manage_guild or perms.manage_roles or perms.manage_channels:
                    return True
        return False

    @staticmethod
    def is_mass_mention(message: Any) -> bool:
        """Checks if a message contains @everyone or @here mentions."""
        content = getattr(message, "content", "")
        if not content:
            return False
        return "@everyone" in content or "@here" in content or getattr(message, "mention_everyone", False)
