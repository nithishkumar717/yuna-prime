from typing import Dict
from pydantic import BaseModel


class ColorPalette(BaseModel):
    """Encapsulates color tokens with conversion helper methods for Discord Embeds and CSS rendering."""
    primary: int = 0x5865F2
    secondary: int = 0x4E5D94
    success: int = 0x57F287
    warning: int = 0xFEE75C
    danger: int = 0xED4245
    info: int = 0x3498DB
    neutral_dark: int = 0x1E1F22
    neutral_light: int = 0xF2F3F5

    def to_hex_int(self, color_name: str) -> int:
        val = getattr(self, color_name.lower(), self.primary)
        return int(val)

    def to_hex_str(self, color_name: str) -> str:
        hex_int = self.to_hex_int(color_name)
        return f"#{hex_int:06X}"

    def to_css_dict(self) -> Dict[str, str]:
        return {
            "--color-primary": self.to_hex_str("primary"),
            "--color-secondary": self.to_hex_str("secondary"),
            "--color-success": self.to_hex_str("success"),
            "--color-warning": self.to_hex_str("warning"),
            "--color-danger": self.to_hex_str("danger"),
            "--color-info": self.to_hex_str("info"),
            "--color-neutral-dark": self.to_hex_str("neutral_dark"),
            "--color-neutral-light": self.to_hex_str("neutral_light")
        }
