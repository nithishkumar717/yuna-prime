# A static registry of Discord permissions capable of causing systemic structural damage.
DANGEROUS_PERMISSIONS = {
    "administrator",
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
}


def is_dangerous_role(role) -> bool:
    """Returns True if the role has any dangerous administrative/nuke permissions or is a protected system role."""
    if not role:
        return False
    if getattr(role, "name", "") in ["Yuna Supreme™", "Yuna Supreme"]:
        return True
    p = getattr(role, "permissions", None)
    if not p:
        return False
    return any([
        getattr(p, "administrator", False),
        getattr(p, "manage_guild", False),
        getattr(p, "manage_roles", False),
        getattr(p, "manage_channels", False),
        getattr(p, "ban_members", False),
        getattr(p, "kick_members", False),
        getattr(p, "manage_webhooks", False),
    ])

