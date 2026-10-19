class BaselineAnalyzer:
    """Evaluates if the current action volume violates historical bounds."""

    def is_anomalous(self, current_volume: int, historical_average: int) -> bool:
        if historical_average == 0 and current_volume > 10:
            return True
        if historical_average > 0 and current_volume > historical_average * 3:
            return True
        return False
