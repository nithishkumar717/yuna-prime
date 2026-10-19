from .profile import BehaviorProfile


class SequenceAnalyzer:
    """Detects exact multi-action hostile execution chains."""

    # Example Malicious Chain: create a webhook, modify a role, delete a channel
    HOSTILE_CHAINS = [["webhook_create", "role_modify", "channel_delete"]]

    def detect_hostile_chain(self, profile: BehaviorProfile) -> bool:
        if len(profile.event_buffer) < 3:
            return False

        recent_actions = [e[1] for e in profile.event_buffer[-3:]]

        for chain in self.HOSTILE_CHAINS:
            if recent_actions == chain:
                return True

        return False
