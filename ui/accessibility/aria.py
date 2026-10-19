"""ARIA attributes and semantic label generation."""

from __future__ import annotations

from typing import Dict, Optional, Any
from enum import Enum


class ARIARole(Enum):
    """Common ARIA roles."""
    ALERT = "alert"
    BUTTON = "button"
    CHECKBOX = "checkbox"
    DIALOG = "dialog"
    LINK = "link"
    MENU = "menu"
    MENU_ITEM = "menuitem"
    NAVIGATION = "navigation"
    PROGRESS_BAR = "progressbar"
    RADIO = "radio"
    SEARCH = "search"
    SLIDER = "slider"
    TAB = "tab"
    TAB_LIST = "tablist"
    TAB_PANEL = "tabpanel"
    TEXTBOX = "textbox"


class ARIAHelper:
    """Helper class for managing ARIA attributes and semantic labels."""

    @staticmethod
    def attributes(
        role: Optional[ARIARole] = None,
        label: Optional[str] = None,
        labelled_by: Optional[str] = None,
        described_by: Optional[str] = None,
        hidden: Optional[bool] = None,
        disabled: Optional[bool] = None,
        required: Optional[bool] = None,
        expanded: Optional[bool] = None,
        pressed: Optional[bool] = None,
        checked: Optional[bool] = None,
        invalid: Optional[bool] = None,
        live: Optional[str] = None,
        controls: Optional[str] = None,
        owns: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build ARIA attributes dictionary from parameters."""
        attrs: Dict[str, Any] = {}
        if role:
            attrs["role"] = role.value
        if label:
            attrs["aria-label"] = label
        if labelled_by:
            attrs["aria-labelledby"] = labelled_by
        if described_by:
            attrs["aria-describedby"] = described_by
        if hidden is not None:
            attrs["aria-hidden"] = "true" if hidden else "false"
        if disabled is not None:
            attrs["aria-disabled"] = "true" if disabled else "false"
        if required is not None:
            attrs["aria-required"] = "true" if required else "false"
        if expanded is not None:
            attrs["aria-expanded"] = "true" if expanded else "false"
        if pressed is not None:
            attrs["aria-pressed"] = "true" if pressed else "false"
        if checked is not None:
            attrs["aria-checked"] = "true" if checked else "false"
        if invalid is not None:
            attrs["aria-invalid"] = "true" if invalid else "false"
        if live:
            attrs["aria-live"] = live
        if controls:
            attrs["aria-controls"] = controls
        if owns:
            attrs["aria-owns"] = owns
        return attrs
