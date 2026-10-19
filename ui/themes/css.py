"""CSS generation utilities for the Theme & Branding Engine.

Converts theme tokens to valid CSS with variables, font imports, and semantic
color classes for use in the HTML dashboard.
"""

from __future__ import annotations

from typing import Dict

from .palette import BrandPalette
from .typography import BrandTypography
from .animations import AnimationToken
from ui.foundation.spacing import SpacingToken


class CSSGenerator:
    """Generates CSS from theme tokens.

    Usage
    -----
    generator = CSSGenerator()
    css = generator.generate(
        palette=BrandPalette.yuna_dark(),
        typography=BrandTypography(),
        spacing=SpacingToken(),
        animation=AnimationToken(),
    )
    """

    def __init__(self) -> None:
        self._font_imports: str = """
/* Inter font family */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* JetBrains Mono font family for code */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
""".strip()

    def generate(
        self,
        palette: BrandPalette,
        typography: BrandTypography,
        spacing: SpacingToken,
        animation: AnimationToken,
        include_font_imports: bool = True,
    ) -> str:
        """Generate complete CSS from theme tokens."""
        parts: list[str] = []
        if include_font_imports:
            parts.append(self._font_imports)
        parts.append(self._generate_root_variables(palette, typography, spacing, animation))
        parts.append(self._generate_semantic_classes(palette))
        return "\n\n".join(parts)

    def _generate_root_variables(
        self,
        palette: BrandPalette,
        typography: BrandTypography,
        spacing: SpacingToken,
        animation: AnimationToken,
    ) -> str:
        """Generate :root {} block with all CSS variables."""
        tokens: Dict[str, str] = {}
        tokens.update(palette.to_css_dict())
        tokens.update(typography.to_css_dict())
        tokens.update(spacing.to_css_dict())
        tokens.update(animation.to_css_dict())
        rules = "\n".join(f"  {k}: {v};" for k, v in sorted(tokens.items()))
        return f":root {{\n{rules}\n}}"

    def _generate_semantic_classes(self, palette: BrandPalette) -> str:
        """Generate semantic color utility classes."""
        class_defs: list[str] = []

        # Background colors
        for role in ["primary", "secondary", "surface", "success", "warning", "danger", "info"]:
            color_val = getattr(palette, role, palette.primary)
            class_defs.append(f".bg-{role} {{\n  background-color: #{color_val:06X};\n}}")

        # Text colors
        for role in ["primary", "secondary", "on_surface", "muted", "success", "warning", "danger", "info"]:
            color_val = getattr(palette, role, palette.on_surface)
            class_defs.append(f".text-{role} {{\n  color: #{color_val:06X};\n}}")

        return "\n\n".join(class_defs)
