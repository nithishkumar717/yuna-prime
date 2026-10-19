"""WCAG 2.1 contrast ratio validation utilities."""

from __future__ import annotations

from typing import Tuple, Union
from enum import Enum

from ui.accessibility.exceptions import ContrastError


class WCAGLevel(Enum):
    """WCAG 2.1 compliance levels."""
    AA = "AA"
    AAA = "AAA"


class ContrastValidator:
    """Validates WCAG 2.1 contrast ratios between foreground/background colors."""

    @staticmethod
    def hex_to_rgb(hex_color: Union[str, int]) -> Tuple[int, int, int]:
        """Convert hex color (str or int) to RGB tuple (0-255, 0-255, 0-255)."""
        if isinstance(hex_color, int):
            r = (hex_color >> 16) & 0xFF
            g = (hex_color >> 8) & 0xFF
            b = hex_color & 0xFF
            return (r, g, b)

        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        elif len(hex_color) != 6:
            raise ContrastError(f"Invalid hex color: {hex_color}")
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        except ValueError:
            raise ContrastError(f"Invalid hex color: {hex_color}")

    @staticmethod
    def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
        """Calculate relative luminance per WCAG 2.1."""
        r, g, b = rgb
        rsRGB = r / 255.0
        gsRGB = g / 255.0
        bsRGB = b / 255.0

        rLum = rsRGB / 12.92 if rsRGB <= 0.03928 else ((rsRGB + 0.055) / 1.055) ** 2.4
        gLum = gsRGB / 12.92 if gsRGB <= 0.03928 else ((gsRGB + 0.055) / 1.055) ** 2.4
        bLum = bsRGB / 12.92 if bsRGB <= 0.03928 else ((bsRGB + 0.055) / 1.055) ** 2.4

        return 0.2126 * rLum + 0.7152 * gLum + 0.0722 * bLum

    @classmethod
    def calculate_contrast_ratio(
        cls,
        foreground: Union[str, int],
        background: Union[str, int],
    ) -> float:
        """Calculate WCAG contrast ratio between foreground and background colors."""
        rgbFg = cls.hex_to_rgb(foreground)
        rgbBg = cls.hex_to_rgb(background)

        lumFg = cls._relative_luminance(rgbFg)
        lumBg = cls._relative_luminance(rgbBg)

        if lumFg > lumBg:
            return (lumFg + 0.05) / (lumBg + 0.05)
        else:
            return (lumBg + 0.05) / (lumFg + 0.05)

    @classmethod
    def validate_contrast(
        cls,
        foreground: Union[str, int],
        background: Union[str, int],
        level: WCAGLevel = WCAGLevel.AA,
        is_large_text: bool = False,
    ) -> bool:
        """Validate that contrast meets specified WCAG level requirements."""
        ratio = cls.calculate_contrast_ratio(foreground, background)

        if level == WCAGLevel.AA:
            return ratio >= 4.5 if not is_large_text else ratio >= 3.0
        elif level == WCAGLevel.AAA:
            return ratio >= 7.0 if not is_large_text else ratio >= 4.5

        return False
