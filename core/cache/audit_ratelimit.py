"""
Shared per-guild audit log rate limiter for antinuke cogs.

Prevents multiple antinuke cogs from hammering Discord's audit log API
simultaneously when events cascade (e.g., autorole + autonick + antinuke
all reacting to the same member join).

Usage in antinuke cogs:
    from core.cache.audit_ratelimit import guarded_audit_fetch

    entry = await guarded_audit_fetch(guild, action, target_id)
"""
import asyncio
import time
import discord
import datetime
import pytz
from typing import Optional

# Per-guild semaphore: max 1 concurrent audit log fetch per guild
_guild_semaphores: dict[int, asyncio.Semaphore] = {}

# Per-guild last fetch timestamp to enforce minimum gap between fetches
_guild_last_fetch: dict[int, float] = {}

# Minimum seconds between audit log API calls for the same guild
_MIN_FETCH_GAP = 1.5


def _get_semaphore(guild_id: int) -> asyncio.Semaphore:
    if guild_id not in _guild_semaphores:
        _guild_semaphores[guild_id] = asyncio.Semaphore(1)
    return _guild_semaphores[guild_id]


from core.services.audit_log_service import audit_log_service


async def guarded_audit_fetch(
    guild: discord.Guild,
    action: discord.AuditLogAction,
    target_id: Optional[int] = None,
    max_retries: int = 6,
    max_age_seconds: float = 30.0
) -> Optional[discord.AuditLogEntry]:
    """
    Fetch audit log entries with centralized sliding-window caching,
    in-flight coalescing, and Discord API rate-limit protection.
    """
    return await audit_log_service.get_entry(
        guild=guild,
        action=action,
        target_id=target_id,
        max_retries=max_retries,
        max_age_seconds=max_age_seconds
    )


async def guarded_webhook_audit_fetch(
    guild: discord.Guild,
    channel: Optional[discord.abc.GuildChannel] = None,
    max_age_seconds: float = 10.0
) -> Optional[discord.AuditLogEntry]:
    """
    Fetch and resolve webhook creation, deletion, or update audit entries
    with a single fast REST request and 1.5s caching.
    """
    return await audit_log_service.get_webhook_entry(
        guild=guild,
        channel=channel,
        max_age_seconds=max_age_seconds
    )
