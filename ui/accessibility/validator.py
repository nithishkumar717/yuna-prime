"""Accessibility audit and validation utilities."""

from __future__ import annotations

from typing import Dict, Any, Optional
from ui.accessibility.contrast import ContrastValidator, WCAGLevel
from ui.themes import ThemeRegistry


class AccessibilityAudit:
    """Performs accessibility audits on UI components and themes."""

    @staticmethod
    def audit_theme(
        theme_name: Optional[str] = None,
        level: WCAGLevel = WCAGLevel.AA,
    ) -> Dict[str, Any]:
        """Audit a theme for accessibility compliance (contrast, etc.)."""
        if theme_name:
            name = theme_name.lower()
            ThemeRegistry._init_defaults()
            if name in ThemeRegistry._nodes:
                palette = ThemeRegistry._nodes[name].palette
            else:
                from ui.foundation.exceptions import InvalidThemeError
                raise InvalidThemeError(f"Theme '{theme_name}' is not registered.")
        else:
            palette = ThemeRegistry.resolve_palette()

        results: Dict[str, Any] = {
            "theme_name": theme_name or "default",
            "wcag_level": level.value,
            "issues": [],
            "passes": [],
        }


        # Check on_surface against neutral_dark (background)
        contrast1 = ContrastValidator.calculate_contrast_ratio(
            palette.on_surface, palette.neutral_dark
        )
        pass1 = ContrastValidator.validate_contrast(
            palette.on_surface, palette.neutral_dark, level
        )

        if pass1:
            results["passes"].append({
                "type": "contrast",
                "foreground": "on_surface",
                "background": "neutral_dark",
                "ratio": round(contrast1, 2),
            })
        else:
            results["issues"].append({
                "type": "contrast",
                "severity": "error",
                "message": f"on_surface/neutral_dark contrast {round(contrast1, 2)} fails {level.value}",
                "ratio": round(contrast1, 2),
            })

        # Check muted against surface
        contrast2 = ContrastValidator.calculate_contrast_ratio(
            palette.muted, palette.surface
        )
        pass2 = ContrastValidator.validate_contrast(
            palette.muted, palette.surface, level
        )

        if pass2:
            results["passes"].append({
                "type": "contrast",
                "foreground": "muted",
                "background": "surface",
                "ratio": round(contrast2, 2),
            })
        else:
            results["issues"].append({
                "type": "contrast",
                "severity": "error",
                "message": f"muted/surface contrast {round(contrast2, 2)} fails {level.value}",
                "ratio": round(contrast2, 2),
            })

        return results
