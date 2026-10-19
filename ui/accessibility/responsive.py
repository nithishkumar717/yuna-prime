"""Responsive design helpers and breakpoints."""

from __future__ import annotations

from enum import Enum
from typing import Dict


class Breakpoint(Enum):
    """Standard responsive breakpoints (Bootstrap-inspired)."""
    XS = "xs"
    SM = "sm"
    MD = "md"
    LG = "lg"
    XL = "xl"
    XXL = "xxl"


BREAKPOINT_WIDTHS: Dict[Breakpoint, int] = {
    Breakpoint.XS: 0,
    Breakpoint.SM: 576,
    Breakpoint.MD: 768,
    Breakpoint.LG: 992,
    Breakpoint.XL: 1200,
    Breakpoint.XXL: 1400,
}


class ResponsiveHelper:
    """Utility class for responsive design calculations and helpers."""

    @staticmethod
    def get_breakpoint_for_width(width: int) -> Breakpoint:
        """Determine which breakpoint corresponds to a given screen width."""
        for bp in reversed(Breakpoint):
            if width >= BREAKPOINT_WIDTHS[bp]:
                return bp
        return Breakpoint.XS

    @staticmethod
    def is_mobile(width: int) -> bool:
        """Check if width is considered a mobile screen."""
        return width < BREAKPOINT_WIDTHS[Breakpoint.MD]

    @staticmethod
    def is_tablet(width: int) -> bool:
        """Check if width is considered a tablet screen."""
        return (BREAKPOINT_WIDTHS[Breakpoint.MD] <= width 
                < BREAKPOINT_WIDTHS[Breakpoint.LG])

    @staticmethod
    def is_desktop(width: int) -> bool:
        """Check if width is considered a desktop screen."""
        return width >= BREAKPOINT_WIDTHS[Breakpoint.LG]

    @staticmethod
    def generate_media_queries() -> Dict[Breakpoint, str]:
        """Generate CSS media query strings for all breakpoints."""
        queries: Dict[Breakpoint, str] = {}
        widths = list(BREAKPOINT_WIDTHS.items())
        for i, (bp, min_w) in enumerate(widths):
            if i < len(widths) - 1:
                next_bp, next_min = widths[i + 1]
                queries[bp] = f"@media (min-width: {min_w}px) and (max-width: {next_min - 1}px)"
            else:
                queries[bp] = f"@media (min-width: {min_w}px)"
        return queries
