"""
Yuna Discord Bot - Gateway Mobile Client Manager
Enables or disables the Discord Mobile Client status indicator (phone badge 📱)
by safely intercepting the WebSocket IDENTIFY handshake packet without modifying
or duplicating discord.py internal connection/sharding/presence logic.
"""

from __future__ import annotations
import os
import sys
import logging
import discord
import discord.gateway

logger = logging.getLogger("yuna.gateway.mobile")

_original_identify = discord.gateway.DiscordWebSocket.identify
_mobile_status_active = False


def is_mobile_status_enabled() -> bool:
    """Checks whether Discord mobile client status is configured to ON in environment variables."""
    val = os.getenv("DISCORD_MOBILE_STATUS", "on").strip().lower()
    return val in ("true", "1", "yes", "on", "enable", "enabled")


def get_mobile_platform_name() -> str:
    """Returns the configured mobile platform string (default: Discord Android)."""
    platform = os.getenv("DISCORD_MOBILE_PLATFORM", "Discord Android").strip()
    if not platform:
        platform = "Discord Android"
    return platform


def setup_mobile_status() -> bool:
    """
    Applies the Discord mobile gateway patch if DISCORD_MOBILE_STATUS is enabled.
    Can be safely called before or during bot initialization.
    """
    global _mobile_status_active

    if not is_mobile_status_enabled():
        # If disabled or turned off in .env, ensure original identify is restored
        if _mobile_status_active:
            discord.gateway.DiscordWebSocket.identify = _original_identify
            _mobile_status_active = False
            print("[DISCORD CLIENT] [DESKTOP] Mobile status disabled. Standard desktop client mode active.", flush=True)
        return False

    if _mobile_status_active:
        return True

    platform_name = get_mobile_platform_name()
    target_os = "android" if "android" in platform_name.lower() else "ios"

    async def mobile_identify(self):
        """Intercepts outgoing payload during IDENTIFY to inject mobile device properties."""
        original_send = self.send_as_json

        async def intercept_send(payload):
            if isinstance(payload, dict) and payload.get("op") == self.IDENTIFY:
                props = payload.setdefault("d", {}).setdefault("properties", {})
                props["os"] = target_os
                props["browser"] = platform_name
                props["device"] = platform_name
            return await original_send(payload)

        self.send_as_json = intercept_send
        try:
            return await _original_identify(self)
        finally:
            self.send_as_json = original_send

    discord.gateway.DiscordWebSocket.identify = mobile_identify
    _mobile_status_active = True
    print(f"[DISCORD CLIENT] [MOBILE] Mobile status activated ({platform_name}). Phone badge enabled!", flush=True)
    return True
