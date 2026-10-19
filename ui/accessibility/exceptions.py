"""Accessibility-related exceptions."""

from ui.foundation.exceptions import UIError


class AccessibilityError(UIError):
    """Base exception for accessibility-related issues."""
    pass


class ContrastError(AccessibilityError):
    """Raised when WCAG contrast requirements aren't met."""
    pass


class AriaError(AccessibilityError):
    """Raised when ARIA attributes are invalid."""
    pass


class ValidationError(AccessibilityError):
    """Raised when accessibility validation fails."""
    pass
