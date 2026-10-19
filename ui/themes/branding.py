"""BrandProfile — visual identity descriptor for a theme.

A ``BrandProfile`` bundles the human-visible identity of a brand (name,
accent color, logo URL, banner URL, tagline) independently of the token
model (palette, typography, spacing). It implements multi-target rendering
so it can be embedded in embeds, HTML, or CLI output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .exceptions import InvalidBrandProfileError


@dataclass
class BrandProfile:
    """Visual identity descriptor for a theme.

    Parameters
    ----------
    name:
        Machine-readable identifier (e.g. ``"yuna_dark"``).
    display_name:
        Human-readable brand name shown in UI (e.g. ``"Yuna · Dark"``).
    accent_color:
        Primary brand accent color as a Discord-compatible hex int.
    logo_url:
        URL to the brand's primary logo image. Optional.
    banner_url:
        URL to a wide banner image. Optional.
    tagline:
        Short brand tagline or description. Optional.
    dark_mode:
        Whether this profile is intended for dark backgrounds.
    """

    name: str
    display_name: str
    accent_color: int
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    tagline: Optional[str] = None
    dark_mode: bool = True

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidBrandProfileError("BrandProfile name must not be empty.")
        if not self.display_name or not self.display_name.strip():
            raise InvalidBrandProfileError("BrandProfile display_name must not be empty.")
        if not (0x000000 <= self.accent_color <= 0xFFFFFF):
            raise InvalidBrandProfileError(
                f"accent_color {self.accent_color:#08x} is out of valid range."
            )

    # ------------------------------------------------------------------
    # Multi-target rendering
    # ------------------------------------------------------------------
    def render_embed(self) -> Dict[str, Any]:
        """Discord embed representation of this brand profile."""
        embed: Dict[str, Any] = {
            "title": self.display_name,
            "color": self.accent_color,
        }
        if self.tagline:
            embed["description"] = self.tagline
        if self.logo_url:
            embed["thumbnail"] = {"url": self.logo_url}
        if self.banner_url:
            embed["image"] = {"url": self.banner_url}
        embed["fields"] = [
            {"name": "🎨 Accent", "value": f"#{self.accent_color:06X}", "inline": True},
            {"name": "🌙 Dark Mode", "value": str(self.dark_mode), "inline": True},
        ]
        return embed

    def render_html(self) -> str:
        """HTML brand card for dashboard rendering."""
        accent_hex = f"#{self.accent_color:06X}"
        tagline_html = f"<p class='brand-tagline'>{self.tagline}</p>" if self.tagline else ""
        logo_html = (
            f"<img class='brand-logo' src='{self.logo_url}' alt='{self.display_name} logo' />"
            if self.logo_url else ""
        )
        banner_html = (
            f"<img class='brand-banner' src='{self.banner_url}' alt='{self.display_name} banner' />"
            if self.banner_url else ""
        )
        return (
            f"<div class='brand-profile' style='border-color: {accent_hex};'>"
            f"{banner_html}"
            f"<div class='brand-header'>"
            f"{logo_html}"
            f"<h2 class='brand-name' style='color: {accent_hex};'>{self.display_name}</h2>"
            f"</div>"
            f"{tagline_html}"
            f"<span class='brand-accent-chip' style='background: {accent_hex};'>{accent_hex}</span>"
            f"</div>"
        )

    def render_text(self) -> str:
        """Plain-text summary for CLI/debug output."""
        lines = [
            f"Brand: {self.display_name} ({self.name})",
            f"Accent: #{self.accent_color:06X}",
            f"Mode: {'Dark' if self.dark_mode else 'Light'}",
        ]
        if self.tagline:
            lines.append(f"Tagline: {self.tagline}")
        if self.logo_url:
            lines.append(f"Logo: {self.logo_url}")
        if self.banner_url:
            lines.append(f"Banner: {self.banner_url}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Built-in Yuna brand profiles
    # ------------------------------------------------------------------
    @classmethod
    def yuna_dark(cls) -> "BrandProfile":
        return cls(
            name="yuna_dark",
            display_name="Yuna · Dark",
            accent_color=0x5865F2,
            tagline="Intelligent moderation infrastructure.",
            dark_mode=True,
        )

    @classmethod
    def yuna_light(cls) -> "BrandProfile":
        return cls(
            name="yuna_light",
            display_name="Yuna · Light",
            accent_color=0x5865F2,
            tagline="Intelligent moderation infrastructure.",
            dark_mode=False,
        )

    @classmethod
    def high_contrast(cls) -> "BrandProfile":
        return cls(
            name="high_contrast",
            display_name="Yuna · High Contrast",
            accent_color=0xFFFFFF,
            tagline="Accessibility-first presentation.",
            dark_mode=True,
        )
