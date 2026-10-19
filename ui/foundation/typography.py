from typing import Dict
from pydantic import BaseModel


class TypographyStyle(BaseModel):
    """Defines font tokens, weights, line heights, and header hierarchy styles."""
    font_family: str = "'Inter', system-ui, -apple-system, sans-serif"
    font_size_xs: str = "0.75rem"
    font_size_sm: str = "0.875rem"
    font_size_base: str = "1.0rem"
    font_size_lg: str = "1.25rem"
    font_size_xl: str = "1.5rem"
    font_size_h1: str = "2.0rem"

    weight_normal: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600
    weight_bold: int = 700

    def to_css_dict(self) -> Dict[str, str]:
        return {
            "--font-family": self.font_family,
            "--font-size-xs": self.font_size_xs,
            "--font-size-sm": self.font_size_sm,
            "--font-size-base": self.font_size_base,
            "--font-size-lg": self.font_size_lg,
            "--font-size-xl": self.font_size_xl,
            "--font-size-h1": self.font_size_h1,
            "--font-weight-normal": str(self.weight_normal),
            "--font-weight-bold": str(self.weight_bold)
        }
