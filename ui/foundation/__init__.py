"""
UI Component Foundation providing design token systems (colors, typography, spacing), multi-target BaseUIComponent rendering interfaces, and central ThemeEngine management.
"""

from .exceptions import UIError, InvalidThemeError, ComponentRenderError
from .colors import ColorPalette
from .typography import TypographyStyle
from .spacing import SpacingToken
from .base_component import BaseUIComponent
from .theme import ThemeConfig, ThemeEngine
from .deprecation import deprecated

__all__ = [
    "UIError",
    "InvalidThemeError",
    "ComponentRenderError",
    "ColorPalette",
    "TypographyStyle",
    "SpacingToken",
    "BaseUIComponent",
    "ThemeConfig",
    "ThemeEngine",
    "deprecated",
]

