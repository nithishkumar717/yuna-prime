class AccountAgeAnalyzer:
    """Analyzes cohort age metadata against suspicious bot bounds."""

    def is_suspicious(self, account_age_days: int) -> bool:
        # Accounts under 1 day old joining during a velocity spike are considered extremely suspicious
        return account_age_days < 1
