"""Central icon registry for semantic icon access across render targets.

Components ask for an icon by semantic role rather than hardcoding emoji or
HTML. Discord targets get emoji; HTML targets can map to SVGs or icon fonts.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict


class IconRole(str, Enum):
    """Semantic icon roles for consistent cross-target rendering."""

    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    INFO = "info"
    SECURITY = "security"
    AI = "ai"
    MODERATION = "moderation"
    DATABASE = "database"
    SETTINGS = "settings"
    HELP = "help"
    HOME = "home"
    USER = "user"
    CHANNEL = "channel"
    SERVER = "server"


class IconRegistry:
    """Semantic icon registry with target-specific mappings.

    Usage
    -----
    registry = IconRegistry()
    emoji = registry.get_discord(IconRole.SUCCESS)
    svg_id = registry.get_html(IconRole.SUCCESS)
    """

    def __init__(self) -> None:
        self._discord: Dict[IconRole, str] = {}
        self._html: Dict[IconRole, str] = {}
        self._fallbacks: Dict[IconRole, str] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Set up default emoji mappings for Discord."""
        self.register_discord(IconRole.SUCCESS, "✅")
        self.register_discord(IconRole.WARNING, "⚠️")
        self.register_discord(IconRole.DANGER, "❌")
        self.register_discord(IconRole.INFO, "ℹ️")
        self.register_discord(IconRole.SECURITY, "🛡️")
        self.register_discord(IconRole.AI, "🤖")
        self.register_discord(IconRole.MODERATION, "🔨")
        self.register_discord(IconRole.DATABASE, "🗄️")
        self.register_discord(IconRole.SETTINGS, "⚙️")
        self.register_discord(IconRole.HELP, "❓")
        self.register_discord(IconRole.HOME, "🏠")
        self.register_discord(IconRole.USER, "👤")
        self.register_discord(IconRole.CHANNEL, "#️⃣")
        self.register_discord(IconRole.SERVER, "🖥️")

        self.register_html(IconRole.SUCCESS, "check-circle")
        self.register_html(IconRole.WARNING, "alert-triangle")
        self.register_html(IconRole.DANGER, "x-circle")
        self.register_html(IconRole.INFO, "info-circle")
        self.register_html(IconRole.SECURITY, "shield")
        self.register_html(IconRole.AI, "bot")
        self.register_html(IconRole.MODERATION, "gavel")
        self.register_html(IconRole.DATABASE, "database")
        self.register_html(IconRole.SETTINGS, "settings")
        self.register_html(IconRole.HELP, "help-circle")
        self.register_html(IconRole.HOME, "home")
        self.register_html(IconRole.USER, "user")
        self.register_html(IconRole.CHANNEL, "hash")
        self.register_html(IconRole.SERVER, "server")

        for role in IconRole:
            self._fallbacks[role] = f"[{role.value}]"

    def register_discord(self, role: IconRole, emoji: str) -> None:
        """Register a Discord emoji for an icon role."""
        self._discord[role] = emoji

    def register_html(self, role: IconRole, icon_id: str) -> None:
        """Register an HTML icon identifier (e.g., SVG ID or font icon class)."""
        self._html[role] = icon_id

    def get_discord(self, role: IconRole) -> str:
        """Return the Discord emoji for a role, or fallback placeholder."""
        return self._discord.get(role, self._fallbacks[role])

    def get_html(self, role: IconRole) -> str:
        """Return the HTML icon identifier for a role, or fallback placeholder."""
        return self._html.get(role, self._fallbacks[role])

    def get_fallback(self, role: IconRole) -> str:
        """Return a text fallback for an icon role."""
        return self._fallbacks[role]
