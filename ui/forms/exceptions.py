from ui.foundation.exceptions import UIError


class FormValidationError(UIError):
    """Base exception for form schema configuration and input validation errors."""
    pass


class FormSubmissionError(FormValidationError):
    """Raised when submitting invalid input data to a Form schema."""
    pass
