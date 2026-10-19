"""Exceptions for the Theme & Branding Engine.

Hierarchy:
    BrandingError (extends UIError)
    ├── ThemeInheritanceError
    ├── AssetNotFoundError
    └── InvalidBrandProfileError
"""

from ui.foundation.exceptions import UIError


class BrandingError(UIError):
    """Base class for all theme and branding related errors."""
    pass


class ThemeInheritanceError(BrandingError):
    """Raised when a theme inheritance chain is invalid (e.g. circular reference)."""
    pass


class AssetNotFoundError(BrandingError):
    """Raised when a requested brand asset cannot be resolved."""
    pass


class InvalidBrandProfileError(BrandingError):
    """Raised when a BrandProfile is constructed with invalid parameters."""
    pass
