from typing import Dict
from pydantic import BaseModel


class SpacingToken(BaseModel):
    """Layout spacing tokens and CSS variable mapping."""
    xs: str = "4px"
    sm: str = "8px"
    md: str = "16px"
    lg: str = "24px"
    xl: str = "32px"
    xxl: str = "48px"

    def to_css_dict(self) -> Dict[str, str]:
        return {
            "--spacing-xs": self.xs,
            "--spacing-sm": self.sm,
            "--spacing-md": self.md,
            "--spacing-lg": self.lg,
            "--spacing-xl": self.xl,
            "--spacing-xxl": self.xxl
        }
