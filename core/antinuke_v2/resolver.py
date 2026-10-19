"""Anti-Nuke V2 Engine — Actor and Role Resolver.

Guarantees that an uncached member holding a whitelisted role is never falsely banned.
Resolves actors through local cache, the whitelisted role-member index, and bounded-timeout
REST fetches before any destructive containment decision can be reached.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Tuple

from core.antinuke_v2.role_index import WhitelistedRoleMemberIndex

logger = logging.getLogger("antinuke.v2.resolver")


class ActorResolver:
    """Asynchronous actor resolver with bounded timeouts for uncached Discord members."""

    @staticmethod
    async def resolve_actor(
        guild: Any,
        actor_id: int,
        role_index: WhitelistedRoleMemberIndex,
        timeout: float = 0.5,
    ) -> Tuple[Optional[Any], bool]:
        """Resolves an actor and updates the role-member index.
        
        Args:
            guild: Discord Guild object
            actor_id: The ID of the actor to resolve
            role_index: In-memory WhitelistedRoleMemberIndex
            timeout: Maximum seconds to wait for REST fetch (bounded)
            
        Returns:
            (resolved_member_or_none, is_resolved_boolean)
            - If is_resolved is False, the actor could not be verified within timeout,
              preventing destructive false bans.
        """
        guild_id = getattr(guild, "id", None)
        if guild_id is None or not actor_id:
            return None, False

        # 1. Check local discord.py member cache first (0 ms)
        if hasattr(guild, "get_member"):
            member = guild.get_member(actor_id)
            if member is not None:
                roles = getattr(member, "roles", [])
                role_ids = {r.id for r in roles} if roles else set()
                role_index.update_member(guild_id, actor_id, role_ids)
                return member, True

        # 2. Check WhitelistedRoleMemberIndex (0 ms)
        if role_index.has_whitelisted_role(guild_id, actor_id):
            return None, True

        # 3. Asynchronous resolution with strict bounded timeout
        if hasattr(guild, "fetch_member"):
            try:
                fetched_member = await asyncio.wait_for(
                    guild.fetch_member(actor_id),
                    timeout=timeout
                )
                if fetched_member is not None:
                    roles = getattr(fetched_member, "roles", [])
                    role_ids = {r.id for r in roles} if roles else set()
                    role_index.update_member(guild_id, actor_id, role_ids)
                    logger.debug(
                        "[ActorResolver] Successfully resolved uncached member %s in guild %s",
                        actor_id, guild_id
                    )
                    return fetched_member, True
            except asyncio.TimeoutError:
                logger.warning(
                    "[ActorResolver] Timed out (%ss) resolving uncached member %s in guild %s",
                    timeout, actor_id, guild_id
                )
                return None, False
            except Exception as e:
                logger.warning(
                    "[ActorResolver] Could not fetch uncached member %s in guild %s: %s",
                    actor_id, guild_id, e
                )
                return None, False

        return None, False
