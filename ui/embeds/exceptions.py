from ui.foundation.exceptions import UIError


class EmbedValidationError(UIError):
    """Base exception for embed composition validation errors."""
    pass


class EmbedLimitExceededError(EmbedValidationError):
    """Raised when embed field counts or character limits exceed Discord limits."""
    pass
