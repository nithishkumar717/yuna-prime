import discord
from discord import Permissions
from typing import Union
from core.cache.security_cache import security_cache

_orig_member_guild_permissions = discord.Member.guild_permissions.fget
_orig_channel_permissions_for = discord.abc.GuildChannel.permissions_for

def _hooked_member_guild_permissions(self: discord.Member) -> Permissions:
    try:
        if self.guild and hasattr(self.guild, "id"):
            if self.id == self.guild.owner_id or security_cache.is_extra_owner(self.guild.id, self.id):
                return Permissions.all()
    except Exception:
        pass
    return _orig_member_guild_permissions(self)

def _hooked_channel_permissions_for(self: discord.abc.GuildChannel, obj: Union[discord.Member, discord.Role], /) -> Permissions:
    try:
        if hasattr(obj, "id") and hasattr(self, "guild") and self.guild:
            if obj.id == self.guild.owner_id or security_cache.is_extra_owner(self.guild.id, obj.id):
                return Permissions.all()
    except Exception:
        pass
    return _orig_channel_permissions_for(self, obj)

_hook_applied = False

def apply_extra_owner_permissions_hook():
    """Dynamically patches discord.Member.guild_permissions and discord.abc.GuildChannel.permissions_for
    so that assigned Extra Owners seamlessly receive discord.Permissions.all() within discord.py.
    
    This ensures that all command checks decorated with has_permissions
    (such as administrator=True, manage_roles=True, ban_members=True, kick_members=True, etc.)
    instantly pass for Extra Owners without modifying individual command decorators.
    """
    global _hook_applied
    if _hook_applied:
        return
    discord.Member.guild_permissions = property(_hooked_member_guild_permissions)
    discord.abc.GuildChannel.permissions_for = _hooked_channel_permissions_for
    _hook_applied = True
