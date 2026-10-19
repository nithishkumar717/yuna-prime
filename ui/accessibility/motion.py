"""Reduced-motion preference utilities for accessibility."""

from __future__ import annotations


class MotionPreferences:
    """Tracks reduced-motion preferences (respects user accessibility settings)."""

    _reduced_motion: bool = False

    @classmethod
    def set_reduced_motion(cls, enabled: bool) -> None:
        """Set whether reduced-motion mode is enabled."""
        cls._reduced_motion = enabled

    @classmethod
    def is_reduced_motion(cls) -> bool:
        """Get whether reduced-motion mode is currently enabled."""
        return cls._reduced_motion

    @classmethod
    def should_animate(cls) -> bool:
        """Determine whether animations should be played (opposite of is_reduced_motion)."""
        return not cls._reduced_motion
