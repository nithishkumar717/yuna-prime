"""
Yuna Support Server Management & Auto-Invite Generation Utility
Support Server ID: 1525481611116806185

Automatically fetches, caches, or creates a permanent, non-expiring Discord invite
(max_age=0, max_uses=0) for the official support server. Provides universal access
to the support URL across all commands, buttons, embeds, event notices, and API endpoints.
"""

from __future__ import annotations
import os
import json
import time
from typing import Optional, Dict, Any

import discord

SUPPORT_GUILD_ID: int = 1525481611116806185
DEFAULT_FALLBACK_URL: str = "https://discord.gg/YzHCx5yQXv"

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_FILE = os.path.join(_BASE_DIR, "db", "support_invite.json")

# In-memory cached URL: {"url": str, "timestamp": float}
_CACHE_DATA: Dict[str, Any] = {
    "url": DEFAULT_FALLBACK_URL,
    "timestamp": 0
}


def _load_cached_url() -> str:
    """Loads previously saved permanent invite from disk cache if available."""
    global _CACHE_DATA
    if _CACHE_DATA.get("url") and _CACHE_DATA["url"] != DEFAULT_FALLBACK_URL:
        return _CACHE_DATA["url"]

    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("url"):
                    _CACHE_DATA["url"] = data["url"]
                    _CACHE_DATA["timestamp"] = data.get("timestamp", time.time())
                    return data["url"]
    except Exception:
        pass
    return DEFAULT_FALLBACK_URL


def _save_cached_url(url: str):
    """Persists permanent invite to disk cache."""
    global _CACHE_DATA
    _CACHE_DATA["url"] = url
    _CACHE_DATA["timestamp"] = time.time()
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "guild_id": SUPPORT_GUILD_ID,
                "url": url,
                "timestamp": _CACHE_DATA["timestamp"]
            }, f, indent=2)
    except Exception as e:
        print(f"[SUPPORT_UTILS] Error writing invite cache: {e}")


def get_support_url(bot: Optional[discord.Client] = None) -> str:
    """
    Returns the current official permanent support server invite link synchronously.
    Uses disk-backed memory cache with instant zero-latency return.
    """
    url = _load_cached_url()
    if url and url != DEFAULT_FALLBACK_URL:
        return url

    # If bot reference is provided, check if vanity URL is available
    if bot:
        guild = bot.get_guild(SUPPORT_GUILD_ID)
        if guild and getattr(guild, "vanity_url_code", None):
            v_url = f"https://discord.gg/{guild.vanity_url_code}"
            _save_cached_url(v_url)
            return v_url

    return url or DEFAULT_FALLBACK_URL

get_support_server_url = get_support_url


async def get_or_generate_support_invite(bot: discord.Client, force_refresh: bool = False) -> str:
    """
    Asynchronously finds, validates, or generates a permanent forever invite link (max_age=0, max_uses=0).
    Called automatically on bot ready, guild join, or /api/support-server.
    """
    if not bot:
        return get_support_url()

    now = time.time()
    # Cache for up to 6 hours if not forced
    if not force_refresh and _CACHE_DATA.get("url") and _CACHE_DATA["url"] != DEFAULT_FALLBACK_URL:
        if now - _CACHE_DATA.get("timestamp", 0) < 21600:
            return _CACHE_DATA["url"]

    guild = bot.get_guild(SUPPORT_GUILD_ID)
    if not guild:
        # Guild not in cache, fallback to saved URL
        return get_support_url(bot)

    # 1. Vanity URL Check
    try:
        if getattr(guild, "vanity_url_code", None):
            vanity_url = f"https://discord.gg/{guild.vanity_url_code}"
            _save_cached_url(vanity_url)
            return vanity_url
    except Exception:
        pass

    # 2. Existing Permanent Invites Search
    try:
        bot_member = guild.me or (await guild.fetch_member(bot.user.id) if bot.user else None)
        if bot_member and bot_member.guild_permissions.manage_guild:
            invites = await guild.invites()
            # Prioritize permanent invite created by the bot
            for inv in (invites or []):
                if inv.max_age == 0 and inv.max_uses == 0 and not getattr(inv, "temporary", False):
                    if inv.inviter and bot.user and inv.inviter.id == bot.user.id:
                        _save_cached_url(inv.url)
                        return inv.url

            # Second pass: Any permanent invite in the server
            for inv in (invites or []):
                if inv.max_age == 0 and inv.max_uses == 0 and not getattr(inv, "temporary", False):
                    _save_cached_url(inv.url)
                    return inv.url
    except Exception as e:
        print(f"[SUPPORT_UTILS] Error scanning existing invites: {e}")

    # 3. Auto-generate a new permanent forever invite (max_age=0, max_uses=0)
    try:
        bot_member = guild.me or (await guild.fetch_member(bot.user.id) if bot.user else None)
        if not bot_member:
            return get_support_url(bot)

        # Find best channel for the invite (welcome, rules, general, or first suitable channel)
        preferred_names = ["welcome", "rules", "announcements", "general", "chat", "lounge", "lobby"]
        candidates = []
        for ch in guild.text_channels:
            perms = ch.permissions_for(bot_member)
            if perms.create_instant_invite and perms.view_channel:
                candidates.append(ch)

        target_channel = None
        for pref in preferred_names:
            for ch in candidates:
                if pref in ch.name.lower():
                    target_channel = ch
                    break
            if target_channel:
                break

        if not target_channel and candidates:
            target_channel = candidates[0]

        if target_channel:
            new_inv = await target_channel.create_invite(
                max_age=0,
                max_uses=0,
                temporary=False,
                unique=False,
                reason="Yuna Support Server Invite"
            )
            _save_cached_url(new_inv.url)
            print(f"[SUPPORT_UTILS] Support server invite active in #{target_channel.name}: {new_inv.url}", flush=True)
            return new_inv.url
    except Exception as create_err:
        print(f"[SUPPORT_UTILS] Error auto-generating permanent invite: {create_err}")

    return get_support_url(bot)
