from .velocity import JoinTracker
from .account_age_analyzer import AccountAgeAnalyzer


class RaidDetector:
    """Orchestrates composite signals to map Raid Confidence."""

    def __init__(self) -> None:
        self.tracker = JoinTracker(window_seconds=10, threshold=5)
        self.age_analyzer = AccountAgeAnalyzer()

    def process_join(
        self, guild_id: int, account_age_days: int, current_time: float = 0.0
    ) -> bool:
        """Returns True if a Raid is actively confirmed based on multi-signal consensus."""

        # Signal 1: Global Influx Velocity
        velocity_breach = self.tracker.track_and_check(guild_id, current_time)

        # Signal 2: Target Cohort Metadata
        metadata_suspicious = self.age_analyzer.is_suspicious(account_age_days)

        # Architectural constraint: Velocity alone does not equal a Raid (could be an influencer linking the discord)
        # It must be mathematically paired with hostile behavioral bounds (e.g. freshly generated bot swarms)
        if velocity_breach and metadata_suspicious:
            return True

        return False
