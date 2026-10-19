"""Extended typography scale for the Theme & Branding Engine.

Extends the foundation ``TypographyStyle`` with a complete heading hierarchy,
line-height tokens, letter-spacing tokens, and additional font weights.
"""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel


class BrandTypography(BaseModel):
    """Full typography scale extending the foundation ``TypographyStyle``.

    All size/spacing values are CSS strings (e.g. ``"1.5rem"``).
    """

    # -----------------------------------------------------------------
    # Font family
    # -----------------------------------------------------------------
    font_family: str = "'Inter', system-ui, -apple-system, sans-serif"
    font_family_mono: str = "'JetBrains Mono', 'Fira Code', Consolas, monospace"

    # -----------------------------------------------------------------
    # Font size scale
    # -----------------------------------------------------------------
    font_size_xs: str = "0.75rem"    # 12px
    font_size_sm: str = "0.875rem"   # 14px
    font_size_base: str = "1.0rem"   # 16px
    font_size_lg: str = "1.125rem"   # 18px
    font_size_xl: str = "1.25rem"    # 20px
    font_size_2xl: str = "1.5rem"    # 24px
    font_size_3xl: str = "1.875rem"  # 30px

    # Heading hierarchy
    font_size_h1: str = "2.25rem"    # 36px
    font_size_h2: str = "1.875rem"   # 30px
    font_size_h3: str = "1.5rem"     # 24px
    font_size_h4: str = "1.25rem"    # 20px

    # -----------------------------------------------------------------
    # Font weights
    # -----------------------------------------------------------------
    weight_light: int = 300
    weight_normal: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600
    weight_bold: int = 700
    weight_extrabold: int = 800

    # -----------------------------------------------------------------
    # Line heights
    # -----------------------------------------------------------------
    line_height_tight: str = "1.25"
    line_height_snug: str = "1.375"
    line_height_normal: str = "1.5"
    line_height_relaxed: str = "1.625"
    line_height_loose: str = "2.0"

    # -----------------------------------------------------------------
    # Letter spacing
    # -----------------------------------------------------------------
    letter_spacing_tight: str = "-0.025em"
    letter_spacing_normal: str = "0em"
    letter_spacing_wide: str = "0.025em"
    letter_spacing_wider: str = "0.05em"
    letter_spacing_widest: str = "0.1em"

    def to_css_dict(self) -> Dict[str, str]:
        """Return a complete CSS variable mapping for this typography scale."""
        return {
            "--font-family": self.font_family,
            "--font-family-mono": self.font_family_mono,
            # sizes
            "--font-size-xs": self.font_size_xs,
            "--font-size-sm": self.font_size_sm,
            "--font-size-base": self.font_size_base,
            "--font-size-lg": self.font_size_lg,
            "--font-size-xl": self.font_size_xl,
            "--font-size-2xl": self.font_size_2xl,
            "--font-size-3xl": self.font_size_3xl,
            # headings
            "--font-size-h1": self.font_size_h1,
            "--font-size-h2": self.font_size_h2,
            "--font-size-h3": self.font_size_h3,
            "--font-size-h4": self.font_size_h4,
            # weights
            "--font-weight-light": str(self.weight_light),
            "--font-weight-normal": str(self.weight_normal),
            "--font-weight-medium": str(self.weight_medium),
            "--font-weight-semibold": str(self.weight_semibold),
            "--font-weight-bold": str(self.weight_bold),
            "--font-weight-extrabold": str(self.weight_extrabold),
            # line heights
            "--line-height-tight": self.line_height_tight,
            "--line-height-snug": self.line_height_snug,
            "--line-height-normal": self.line_height_normal,
            "--line-height-relaxed": self.line_height_relaxed,
            "--line-height-loose": self.line_height_loose,
            # letter spacing
            "--letter-spacing-tight": self.letter_spacing_tight,
            "--letter-spacing-normal": self.letter_spacing_normal,
            "--letter-spacing-wide": self.letter_spacing_wide,
            "--letter-spacing-wider": self.letter_spacing_wider,
            "--letter-spacing-widest": self.letter_spacing_widest,
        }
