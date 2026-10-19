"""Theme & Branding Engine public API.

Exports
-------
ThemeRegistry   Central theme management authority
BrandProfile    Visual identity descriptor
BrandPalette    Extended color palette with semantic roles and inheritance
BrandTypography Extended typography scale
AnimationToken  HTML dashboard animation / transition tokens
BrandAssetRegistry  Per-guild brand asset store
SemanticColorRole   Enum of semantic color roles
IconRole            Enum of semantic icon roles
IconRegistry        Central icon registry
CSSGenerator        CSS generation from theme tokens
BrandingError       Exception hierarchy
ThemeInheritanceError
AssetNotFoundError
InvalidBrandProfileError
"""

from .registry import ThemeRegistry
from .branding import BrandProfile
from .palette import BrandPalette, SemanticColorRole
from .typography import BrandTypography
from .animations import AnimationToken
from .assets import BrandAssetRegistry
from .icons import IconRole, IconRegistry
from .css import CSSGenerator
from .exceptions import (
    BrandingError,
    ThemeInheritanceError,
    AssetNotFoundError,
    InvalidBrandProfileError,
)

__all__ = [
    "ThemeRegistry",
    "BrandProfile",
    "BrandPalette",
    "SemanticColorRole",
    "BrandTypography",
    "AnimationToken",
    "BrandAssetRegistry",
    "IconRole",
    "IconRegistry",
    "CSSGenerator",
    "BrandingError",
    "ThemeInheritanceError",
    "AssetNotFoundError",
    "InvalidBrandProfileError",
]
