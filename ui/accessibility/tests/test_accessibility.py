"""Comprehensive tests for ui/accessibility – v7.6.0 Accessibility & Responsive Layouts."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
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
)
from ui.accessibility.aria import ARIARole, ARIAHelper
from ui.accessibility.keyboard import KeyCode, KeyboardHelper
from ui.accessibility.motion import MotionPreferences
from ui.accessibility.validator import AccessibilityAudit
from ui.foundation.exceptions import UIError
from ui.themes import ThemeRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_registry():
    ThemeRegistry.reset()
    yield
    ThemeRegistry.reset()


@pytest.fixture(autouse=True)
def reset_motion_prefs():
    MotionPreferences._reduced_motion = False
    yield
    MotionPreferences._reduced_motion = False


# ===========================================================================
# Exceptions
# ===========================================================================
class TestExceptions:
    def test_accessibility_error_extends_ui_error(self):
        assert issubclass(AccessibilityError, UIError)

    def test_contrast_error_is_accessibility_error(self):
        assert issubclass(ContrastError, AccessibilityError)

    def test_aria_error_is_accessibility_error(self):
        assert issubclass(AriaError, AccessibilityError)

    def test_validation_error_is_accessibility_error(self):
        assert issubclass(ValidationError, AccessibilityError)


# ===========================================================================
# Contrast Validator
# ===========================================================================
class TestContrastValidator:
    def test_hex_to_rgb_int(self):
        r, g, b = ContrastValidator.hex_to_rgb(0xFFFFFF)
        assert r == 255 and g == 255 and b == 255

    def test_hex_to_rgb_str(self):
        r, g, b = ContrastValidator.hex_to_rgb("#FFFFFF")
        assert r == 255 and g == 255 and b == 255

    def test_calculate_contrast_ratio(self):
        ratio = ContrastValidator.calculate_contrast_ratio(0x000000, 0xFFFFFF)
        assert ratio > 20  # perfect contrast

    def test_validate_contrast_aa(self):
        result = ContrastValidator.validate_contrast(
            0x000000, 0xFFFFFF, WCAGLevel.AA
        )
        assert result

    def test_validate_contrast_aaa(self):
        result = ContrastValidator.validate_contrast(
            0x000000, 0xFFFFFF, WCAGLevel.AAA
        )
        assert result


# ===========================================================================
# Responsive
# ===========================================================================
class TestResponsive:
    def test_get_breakpoint_for_width(self):
        assert ResponsiveHelper.get_breakpoint_for_width(0) == Breakpoint.XS
        assert ResponsiveHelper.get_breakpoint_for_width(800) == Breakpoint.MD

    def test_is_mobile(self):
        assert ResponsiveHelper.is_mobile(600)
        assert not ResponsiveHelper.is_mobile(800)

    def test_generate_media_queries(self):
        queries = ResponsiveHelper.generate_media_queries()
        assert Breakpoint.XS in queries


# ===========================================================================
# ARIA
# ===========================================================================
class TestARIA:
    def test_attributes(self):
        attrs = ARIAHelper.attributes(
            role=ARIARole.BUTTON,
            label="Click Me",
            pressed=True,
        )
        assert attrs["role"] == "button"
        assert attrs["aria-label"] == "Click Me"
        assert attrs["aria-pressed"] == "true"


# ===========================================================================
# Keyboard
# ===========================================================================
class TestKeyboard:
    def test_is_navigation_key(self):
        assert KeyboardHelper.is_navigation_key(KeyCode.UP.value)
        assert KeyboardHelper.is_navigation_key(KeyCode.TAB.value)
        assert not KeyboardHelper.is_navigation_key(KeyCode.ENTER.value)

    def test_is_action_key(self):
        assert KeyboardHelper.is_action_key(KeyCode.ENTER.value)
        assert KeyboardHelper.is_action_key(KeyCode.SPACE.value)


# ===========================================================================
# Motion Preferences
# ===========================================================================
class TestMotionPreferences:
    def test_set_and_get(self):
        assert not MotionPreferences.is_reduced_motion()
        assert MotionPreferences.should_animate()
        MotionPreferences.set_reduced_motion(True)
        assert MotionPreferences.is_reduced_motion()
        assert not MotionPreferences.should_animate()


# ===========================================================================
# Accessibility Audit
# ===========================================================================
class TestAccessibilityAudit:
    def test_audit_theme(self):
        result = AccessibilityAudit.audit_theme(level=WCAGLevel.AA)
        assert "theme_name" in result
        assert "passes" in result

    def test_audit_specific_theme(self):
        result = AccessibilityAudit.audit_theme(theme_name="high_contrast", level=WCAGLevel.AAA)
        assert result["theme_name"] == "high_contrast"
        assert result["wcag_level"] == "AAA"
        assert len(result["passes"]) > 0

    def test_audit_invalid_theme_raises_error(self):
        from ui.foundation.exceptions import InvalidThemeError
        with pytest.raises(InvalidThemeError):
            AccessibilityAudit.audit_theme(theme_name="non_existent_theme")


# ===========================================================================
# RTL Helper
# ===========================================================================
class TestRTLHelper:
    def test_is_rtl_language(self):
        from ui.accessibility.rtl import RTLHelper
        assert RTLHelper.is_rtl_language("ar")
        assert RTLHelper.is_rtl_language("ar-EG")
        assert RTLHelper.is_rtl_language("he")
        assert not RTLHelper.is_rtl_language("en")
        assert not RTLHelper.is_rtl_language("en-US")
        assert not RTLHelper.is_rtl_language("")

    def test_get_dir_attribute(self):
        from ui.accessibility.rtl import RTLHelper
        assert RTLHelper.get_dir_attribute("ar") == "rtl"
        assert RTLHelper.get_dir_attribute("en") == "ltr"

    def test_mirror_alignment(self):
        from ui.accessibility.rtl import RTLHelper
        assert RTLHelper.mirror_alignment("left") == "right"
        assert RTLHelper.mirror_alignment("right") == "left"
        assert RTLHelper.mirror_alignment("start") == "end"
        assert RTLHelper.mirror_alignment("end") == "start"
        assert RTLHelper.mirror_alignment("ltr") == "rtl"
        assert RTLHelper.mirror_alignment("center") == "center"

    def test_mirror_icon(self):
        from ui.accessibility.rtl import RTLHelper
        assert RTLHelper.mirror_icon("←") == "→"
        assert RTLHelper.mirror_icon("→") == "←"
        assert RTLHelper.mirror_icon("chevron-left") == "chevron-right"
        assert RTLHelper.mirror_icon("foo") == "foo"


# ===========================================================================
# Accessibility Report Generator
# ===========================================================================
class TestAccessibilityReportGenerator:
    def test_generate_text_report(self):
        from ui.accessibility.report import AccessibilityReportGenerator
        
        audit_results = AccessibilityAudit.audit_theme(theme_name="high_contrast")
        report = AccessibilityReportGenerator.generate_text_report(audit_results)
        
        assert "ACCESSIBILITY AUDIT REPORT: Theme 'high_contrast'" in report
        assert "WCAG Compliance Target: Level AA" in report
        assert "Audit Summary:" in report

    def test_generate_markdown_report(self):
        from ui.accessibility.report import AccessibilityReportGenerator
        
        audit_results = AccessibilityAudit.audit_theme(theme_name="high_contrast")
        report = AccessibilityReportGenerator.generate_markdown_report(audit_results)
        
        assert "# Accessibility Audit Report: Theme `high_contrast`" in report
        assert "Passed Checks" in report

    def test_verify_ci_compliance(self):
        from ui.accessibility.report import AccessibilityReportGenerator
        
        passing_results = {
            "theme_name": "pass",
            "issues": [],
            "passes": [{"type": "contrast"}]
        }
        failing_results = {
            "theme_name": "fail",
            "issues": [{"severity": "error", "message": "Contrast failed"}],
            "passes": []
        }
        
        assert AccessibilityReportGenerator.verify_ci_compliance(passing_results)
        assert not AccessibilityReportGenerator.verify_ci_compliance(failing_results)