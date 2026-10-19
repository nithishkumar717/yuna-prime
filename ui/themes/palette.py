"""Extended color palette with semantic roles and theme inheritance.

Extends the foundation ``ColorPalette`` with:
- ``SemanticColorRole`` enum for structured role-based color access
- ``BrandPalette`` subclass adding ``surface``, ``on_surface``, ``accent``,
  and ``muted`` tokens and an ``inherit_from()`` composition helper
"""

from __future__ import annotations

from enum import Enum
from typing import Dict


from ui.foundation.colors import ColorPalette


class SemanticColorRole(str, Enum):
    """Named semantic roles for color tokens.

    These names are transport-agnostic and map to concrete hex values at
    render time via ``BrandPalette``.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    INFO = "info"
    NEUTRAL_DARK = "neutral_dark"
    NEUTRAL_LIGHT = "neutral_light"
    SURFACE = "surface"
    ON_SURFACE = "on_surface"
    ACCENT = "accent"
    MUTED = "muted"


class BrandPalette(ColorPalette):
    """Extended color palette with additional semantic tokens and inheritance.

    Additional tokens compared to the base ``ColorPalette``:
    - ``surface``: background surface color (card backgrounds, modal backdrops)
    - ``on_surface``: foreground color drawn on surfaces (text, icons)
    - ``accent``: highlight / CTA color distinct from ``primary``
    - ``muted``: subdued foreground for secondary text and hints

    Inheritance
    -----------
    Call ``inherit_from(parent)`` to produce a new ``BrandPalette`` where any
    token that is *not* overridden in ``self`` falls back to ``parent``'s value.
    Child values always win.
    """

    surface: int = 0x2B2D31
    on_surface: int = 0xDBDEE1
    accent: int = 0x5865F2
    muted: int = 0x80848E

    def inherit_from(self, parent: "BrandPalette") -> "BrandPalette":
        """Return a new ``BrandPalette`` merging parent defaults with child overrides.

        Child (self) values take precedence; parent fills any gaps where the
        child still holds the default value.
        """
        parent_data = parent.model_dump()
        child_data = self.model_dump()
        default_data = BrandPalette().model_dump()

        merged: Dict[str, int] = {}
        for key, child_val in child_data.items():
            # If child still holds the class default, fall back to parent.
            if child_val == default_data[key]:
                merged[key] = parent_data[key]
            else:
                merged[key] = child_val

        return BrandPalette(**merged)

    def resolve(self, role: SemanticColorRole) -> int:
        """Return the hex int for a semantic color role."""
        return getattr(self, role.value, self.primary)

    def to_css_dict(self) -> Dict[str, str]:
        base = super().to_css_dict()
        base.update({
            "--color-surface": f"#{self.surface:06X}",
            "--color-on-surface": f"#{self.on_surface:06X}",
            "--color-accent": f"#{self.accent:06X}",
            "--color-muted": f"#{self.muted:06X}",
        })
        return base

    # ------------------------------------------------------------------
    # Convenience factories
    # ------------------------------------------------------------------
    @classmethod
    def yuna_dark(cls) -> "BrandPalette":
        return cls(
            primary=0x5865F2,
            secondary=0x4E5D94,
            success=0x57F287,
            warning=0xFEE75C,
            danger=0xED4245,
            info=0x3498DB,
            neutral_dark=0x1E1F22,
            neutral_light=0xF2F3F5,
            surface=0x2B2D31,
            on_surface=0xDBDEE1,
            accent=0x5865F2,
            muted=0x80848E,
        )

    @classmethod
    def yuna_light(cls) -> "BrandPalette":
        return cls(
            primary=0x5865F2,
            secondary=0x7289DA,
            success=0x3BA55C,
            warning=0xC27C0E,
            danger=0xED4245,
            info=0x2F7BB6,
            neutral_dark=0xF2F3F5,
            neutral_light=0x1E1F22,
            surface=0xFFFFFF,
            on_surface=0x060607,
            accent=0x5865F2,
            muted=0x4F5660,
        )

    @classmethod
    def high_contrast(cls) -> "BrandPalette":
        return cls(
            primary=0xFFFFFF,
            secondary=0xCCCCCC,
            success=0x00FF00,
            warning=0xFFFF00,
            danger=0xFF0000,
            info=0x00FFFF,
            neutral_dark=0x000000,
            neutral_light=0xFFFFFF,
            surface=0x000000,
            on_surface=0xFFFFFF,
            accent=0xFFFF00,
            muted=0xAAAAAA,
        )
