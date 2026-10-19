def is_privilege_escalation(actor_top_role: int, target_top_role: int) -> bool:
    """
    Evaluates Discord's integer-based position hierarchy.
    Returns True if an actor attempts to modify a target equal to or higher than themselves.
    """
    if actor_top_role <= 0:
        return True  # Bottom-tier roles have no authority to escalate
    return actor_top_role <= target_top_role


def is_owner_targeted(target_is_owner: bool) -> bool:
    """Ensures structural invariability protecting the guild owner."""
    return target_is_owner
