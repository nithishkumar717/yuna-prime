"""
Discord Profile Manager for YUNA Bot
Centralized abstraction for interacting with Discord HTTP API for per-server bot profiles.
Uses official endpoint: PATCH /guilds/{guild_id}/members/@me
"""

import base64
import logging
import aiohttp
import discord
from discord.http import Route
from typing import Optional, Dict, Any

from services.profile_storage import detect_mime_type

logger = logging.getLogger("yuna.profile_manager")

class DiscordProfileError(Exception):
    """Custom exception raised when Discord Profile API returns an error."""
    pass

class ProfileRateLimited(DiscordProfileError):
    """Raised when Discord returns HTTP 429 rate limit."""
    pass


class DiscordProfileManager:
    """Manages Discord per-server member profile updates via official Discord HTTP API."""

    def __init__(self, bot: discord.Client):
        self.bot = bot

    def _bytes_to_data_uri(self, image_bytes: bytes, fallback_mime: str = "image/png") -> str:
        """Converts raw image bytes into base64 Data URI with auto-detected MIME type."""
        mime_type = detect_mime_type(image_bytes) or fallback_mime
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    async def modify_global_bot_profile(self, *args, **kwargs):
        """
        PERMANENT SECURITY LOCK:
        Global bot avatar, banner, and profile cannot be modified or deleted
        via bot commands or web dashboard routes.
        """
        raise DiscordProfileError("CRITICAL SECURITY VIOLATION: Global bot profile modifications are permanently blocked.")

    async def update_server_profile(
        self,
        guild_id: int,
        nickname: Optional[str] = None,
        avatar_bytes: Optional[bytes] = None,
        avatar_mime: str = "image/png",
        banner_bytes: Optional[bytes] = None,
        banner_mime: str = "image/png",
        bio: Optional[str] = None,
        reset_avatar: bool = False,
        reset_banner: bool = False,
        reset_bio: bool = False
    ) -> Dict[str, Any]:
        """
        Sends HTTP PATCH request to Discord API to update per-server bot member profile.
        Endpoint: PATCH /guilds/{guild_id}/members/@me

        SAFETY GUARANTEE:
        This endpoint ONLY affects the bot's member profile within the specified guild.
        The bot's main global avatar and banner are 100% safe, immutable, and untouched.
        """
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise DiscordProfileError(f"Invalid guild_id ({guild_id}). Global bot profile modifications are strictly prohibited.")

        payload: Dict[str, Any] = {}

        if nickname is not None:
            # Only set nick in payload if specified (pass "" or None to omit)
            payload["nick"] = nickname

        if reset_avatar:
            # Setting member avatar to None clears the per-server override on Discord,
            # reverting this server to display Yuna's permanent global avatar.
            payload["avatar"] = None
        elif avatar_bytes:
            payload["avatar"] = self._bytes_to_data_uri(avatar_bytes, avatar_mime)

        if reset_banner:
            # Setting member banner to None clears the per-server override on Discord,
            # reverting this server to display Yuna's permanent global banner.
            payload["banner"] = None
        elif banner_bytes:
            payload["banner"] = self._bytes_to_data_uri(banner_bytes, banner_mime)

        if reset_bio:
            # Setting member bio to None clears the per-server bio override on Discord
            payload["bio"] = None
        elif bio is not None:
            payload["bio"] = bio[:190]

        if not payload:
            return {"status": "unchanged", "message": "No fields to update on Discord API"}

        # STRICT ROUTE ASSERTION: Only per-guild member route is ever called
        route = Route("PATCH", "/guilds/{guild_id}/members/@me", guild_id=guild_id)

        guild = self.bot.get_guild(guild_id)
        g_label = f"'{guild.name}' ({guild_id})" if guild else str(guild_id)

        try:
            res = await self.bot.http.request(route, json=payload)
            if guild and guild.me and isinstance(res, dict):
                try:
                    guild.me._update(res)
                except Exception:
                    pass
            logger.info(f"[PROFILE MANAGER] Successfully updated server profile for Guild {g_label}")
            return {"status": "success", "data": res}
        except discord.HTTPException as e:
            if e.status == 429:
                logger.warning(f"[PROFILE MANAGER 429] Rate limited updating guild {g_label}: {e}")
                raise ProfileRateLimited(f"Discord Rate Limited (429): {e}")
            logger.error(f"[PROFILE MANAGER ERROR] Discord HTTP Exception for guild {g_label}: {e}")
            raise DiscordProfileError(f"Discord API Error ({e.status}): {e.text}")
        except Exception as e:
            logger.error(f"[PROFILE MANAGER ERROR] Unexpected error for guild {g_label}: {e}")
            raise DiscordProfileError(f"Failed to update profile: {e}")

    async def reset_server_avatar(self, guild_id: int) -> Dict[str, Any]:
        """
        Resets server-specific avatar back to global profile avatar.
        This only clears the member override in this guild; global avatar remains untouched.
        """
        return await self.update_server_profile(guild_id, reset_avatar=True)

    async def reset_server_banner(self, guild_id: int) -> Dict[str, Any]:
        """
        Resets server-specific banner back to global profile banner.
        Global banner remains untouched.
        """
        return await self.update_server_profile(guild_id, reset_banner=True)

    async def reset_server_bio(self, guild_id: int) -> Dict[str, Any]:
        """
        Resets server-specific bio back to global default.
        """
        return await self.update_server_profile(guild_id, reset_bio=True)

    async def reset_entire_profile(self, guild_id: int) -> Dict[str, Any]:
        """
        Resets nickname, server avatar, server banner, and server bio in this server back to global defaults.
        Global bot profile is never deleted or modified.
        """
        return await self.update_server_profile(guild_id, nickname="", reset_avatar=True, reset_banner=True, reset_bio=True)
