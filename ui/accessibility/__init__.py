"""Accessibility & Responsive Layouts package for Volume VIII."""

from ui.accessibility.exceptions import (
    AccessibilityError,
    ContrastError,
    AriaError,
    ValidationError,
)
from ui.accessibility.contrast import (
    ContrastValidator,
    WCAGLevel,
)
from ui.accessibility.responsive import (
    Breakpoint,
    ResponsiveHelper,
    BREAKPOINT_WIDTHS,
)
from ui.accessibility.aria import (
    ARIAHelper,
    ARIARole,
)
from ui.accessibility.keyboard import (
    KeyboardHelper,
    KeyCode,
)
from ui.accessibility.motion import (
    MotionPreferences,
)
from ui.accessibility.validator import (
    AccessibilityAudit,
)
from ui.accessibility.rtl import (
    RTLHelper,
)
from ui.accessibility.report import (
    AccessibilityReportGenerator,
)

__all__ = [
    "AccessibilityError",
    "ContrastError",
    "AriaError",
    "ValidationError",
    "ContrastValidator",
    "WCAGLevel",
    "Breakpoint",
    "ResponsiveHelper",
    "BREAKPOINT_WIDTHS",
    "ARIAHelper",
    "ARIARole",
    "KeyboardHelper",
    "KeyCode",
    "MotionPreferences",
    "AccessibilityAudit",
    "RTLHelper",
    "AccessibilityReportGenerator",
]

