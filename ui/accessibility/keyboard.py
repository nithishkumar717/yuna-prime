"""Keyboard navigation and accessibility utilities."""

from __future__ import annotations

from enum import Enum


class KeyCode(Enum):
    """Common keyboard key codes for accessibility navigation."""
    TAB = "Tab"
    ENTER = "Enter"
    SPACE = " "
    ESCAPE = "Escape"
    UP = "ArrowUp"
    DOWN = "ArrowDown"
    LEFT = "ArrowLeft"
    RIGHT = "ArrowRight"
    HOME = "Home"
    END = "End"
    PAGE_UP = "PageUp"
    PAGE_DOWN = "PageDown"


class KeyboardHelper:
    """Utility class for keyboard navigation support."""

    @staticmethod
    def is_navigation_key(key: str) -> bool:
        """Check if a key is a navigation key (arrow keys, tab, home/end, page up/down)."""
        return key in {
            KeyCode.TAB.value,
            KeyCode.UP.value,
            KeyCode.DOWN.value,
            KeyCode.LEFT.value,
            KeyCode.RIGHT.value,
            KeyCode.HOME.value,
            KeyCode.END.value,
            KeyCode.PAGE_UP.value,
            KeyCode.PAGE_DOWN.value,
        }

    @staticmethod
    def is_action_key(key: str) -> bool:
        """Check if a key is an action key (Enter, Space)."""
        return key in {KeyCode.ENTER.value, KeyCode.SPACE.value}
