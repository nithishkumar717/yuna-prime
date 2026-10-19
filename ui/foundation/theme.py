from typing import Dict
from pydantic import BaseModel, Field
from .colors import ColorPalette
from .typography import TypographyStyle
from .spacing import SpacingToken
from .exceptions import InvalidThemeError


class ThemeConfig(BaseModel):
    """Encapsulates a complete design token bundle (colors, typography, spacing)."""
    name: str
    colors: ColorPalette = Field(default_factory=ColorPalette)
    typography: TypographyStyle = Field(default_factory=TypographyStyle)
    spacing: SpacingToken = Field(default_factory=SpacingToken)

    def export_css_variables(self) -> str:
        tokens: Dict[str, str] = {}
        tokens.update(self.colors.to_css_dict())
        tokens.update(self.typography.to_css_dict())
        tokens.update(self.spacing.to_css_dict())

        rules = [f"  {k}: {v};" for k, v in tokens.items()]
        return ":root {\n" + "\n".join(rules) + "\n}"


class ThemeEngine:
    """Centralized theme engine managing active presentation tokens and custom theme registries."""

    _themes: Dict[str, ThemeConfig] = {}
    _active_theme_name: str = "yuna_dark"

    @classmethod
    def _init_defaults(cls) -> None:
        if not cls._themes:
            # Yuna Dark Theme (Default)
            dark = ThemeConfig(
                name="yuna_dark",
                colors=ColorPalette(
                    primary=0x5865F2,
                    secondary=0x4E5D94,
                    neutral_dark=0x1E1F22,
                    neutral_light=0xF2F3F5
                )
            )

            # Yuna Light Theme
            light = ThemeConfig(
                name="yuna_light",
                colors=ColorPalette(
                    primary=0x5865F2,
                    secondary=0x7289DA,
                    neutral_dark=0xF2F3F5,
                    neutral_light=0x1E1F22
                )
            )

            # High Contrast Theme
            contrast = ThemeConfig(
                name="high_contrast",
                colors=ColorPalette(
                    primary=0xFFFFFF,
                    secondary=0x000000,
                    success=0x00FF00,
                    warning=0xFFFF00,
                    danger=0xFF0000
                )
            )

            cls.register_theme(dark)
            cls.register_theme(light)
            cls.register_theme(contrast)

    @classmethod
    def register_theme(cls, theme: ThemeConfig) -> None:
        cls._themes[theme.name.lower()] = theme

    @classmethod
    def get_theme(cls, name: str) -> ThemeConfig:
        cls._init_defaults()
        t = cls._themes.get(name.lower())
        if not t:
            raise InvalidThemeError(f"Theme '{name}' is not registered.")
        return t

    @classmethod
    def set_active_theme(cls, name: str) -> None:
        theme = cls.get_theme(name)
        cls._active_theme_name = theme.name.lower()

    @classmethod
    def get_active_theme(cls) -> ThemeConfig:
        return cls.get_theme(cls._active_theme_name)

    @classmethod
    def clear(cls) -> None:
        cls._themes.clear()
        cls._active_theme_name = "yuna_dark"
