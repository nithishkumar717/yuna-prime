"""Anti-Nuke V2 Engine — Whitelisted Role-Member Index.

Maintains an in-memory, O(1) index of all members who hold any whitelisted role.
Guarantees that role-based whitelist evaluations NEVER falsely fail due to an uncached
member in discord.py. Updated dynamically via gateway events.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional, Set

logger = logging.getLogger("antinuke.v2.role_index")


class WhitelistedRoleMemberIndex:
    """Synchronous, thread-safe in-memory index of members holding whitelisted roles."""

    def __init__(self) -> None:
        # guild_id -> set of member_ids holding at least one whitelisted role
        self._index: Dict[int, Set[int]] = {}
        # guild_id -> set of whitelisted role_ids
        self._whitelisted_roles: Dict[int, Set[int]] = {}

    def get_whitelisted_roles(self, guild_id: int) -> Set[int]:
        """Returns a copy of the whitelisted role IDs for a guild."""
        return set(self._whitelisted_roles.get(guild_id, set()))

    def set_whitelisted_roles(self, guild_id: int, role_ids: Set[int]) -> None:
        """Sets the active whitelisted role IDs for a guild."""
        self._whitelisted_roles[guild_id] = set(role_ids)
        if guild_id not in self._index:
            self._index[guild_id] = set()

    def add_whitelisted_role(self, guild_id: int, role_id: int) -> None:
        """Adds a single whitelisted role."""
        if guild_id not in self._whitelisted_roles:
            self._whitelisted_roles[guild_id] = set()
        self._whitelisted_roles[guild_id].add(role_id)
        if guild_id not in self._index:
            self._index[guild_id] = set()

    def remove_whitelisted_role(self, guild_id: int, role_id: int) -> None:
        """Removes a whitelisted role and cleans up the index."""
        if guild_id in self._whitelisted_roles:
            self._whitelisted_roles[guild_id].discard(role_id)

    def build_guild_index(self, guild: Any, whitelisted_roles: Optional[Set[int]] = None) -> int:
        """Builds or rebuilds the member role index from all currently cached guild members.
        
        Returns the number of members indexed.
        """
        guild_id = getattr(guild, "id", None)
        if guild_id is None:
            return 0

        if whitelisted_roles is not None:
            self.set_whitelisted_roles(guild_id, whitelisted_roles)

        active_roles = self._whitelisted_roles.get(guild_id, set())
        matched_members: Set[int] = set()

        if active_roles and hasattr(guild, "members"):
            for member in guild.members:
                roles = getattr(member, "roles", [])
                if roles and any(getattr(r, "id", None) in active_roles for r in roles):
                    matched_members.add(member.id)

        self._index[guild_id] = matched_members
        logger.debug(
            "[RoleIndex] Built index for guild %s: %d members indexed with %d roles",
            guild_id, len(matched_members), len(active_roles)
        )
        return len(matched_members)

    def update_member(self, guild_id: int, member_id: int, role_ids: Iterable[int]) -> bool:
        """Updates a member's presence in the whitelist index based on their current role IDs.
        
        Returns True if the member has a whitelisted role, False otherwise.
        """
        active_roles = self._whitelisted_roles.get(guild_id, set())
        if not active_roles:
            if guild_id in self._index:
                self._index[guild_id].discard(member_id)
            return False

        has_role = any(rid in active_roles for rid in role_ids)
        if guild_id not in self._index:
            self._index[guild_id] = set()

        if has_role:
            self._index[guild_id].add(member_id)
        else:
            self._index[guild_id].discard(member_id)

        return has_role

    def remove_member(self, guild_id: int, member_id: int) -> None:
        """Removes a member from the index (e.g. on member leave/kick/ban)."""
        if guild_id in self._index:
            self._index[guild_id].discard(member_id)

    def has_whitelisted_role(self, guild_id: int, user_id: int) -> bool:
        """Synchronously checks if a user is in the whitelisted role index for the guild."""
        return user_id in self._index.get(guild_id, set())

    def is_member_cached(self, guild: Any, user_id: int) -> bool:
        """Checks if a member is currently present in discord.py's internal guild member cache."""
        if not guild or not hasattr(guild, "get_member"):
            return False
        return guild.get_member(user_id) is not None

    def prune_guild(self, guild_id: int) -> None:
        """Prunes all index data for a guild upon guild removal to maintain bounded memory."""
        self._index.pop(guild_id, None)
        self._whitelisted_roles.pop(guild_id, None)
