"""Animation and transition token model.

``AnimationToken`` provides CSS animation/transition design tokens for use in
the HTML dashboard. These tokens have no meaning for Discord or CLI targets.

All values are CSS strings consumable directly in stylesheets or inline styles.
"""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel


class AnimationToken(BaseModel):
    """CSS transition and animation timing tokens.

    Rendering target: **HTML dashboard only**.
    Discord and CLI renderers should ignore this model.
    """

    # -----------------------------------------------------------------
    # Duration scale
    # -----------------------------------------------------------------
    duration_instant: str = "75ms"
    duration_fast: str = "150ms"
    duration_normal: str = "250ms"
    duration_slow: str = "400ms"
    duration_slower: str = "600ms"

    # -----------------------------------------------------------------
    # Easing curves (Material Design / CSS spec conventions)
    # -----------------------------------------------------------------
    easing_linear: str = "linear"
    easing_ease: str = "ease"
    easing_ease_in: str = "cubic-bezier(0.4, 0, 1, 1)"
    easing_ease_out: str = "cubic-bezier(0, 0, 0.2, 1)"
    easing_ease_in_out: str = "cubic-bezier(0.4, 0, 0.2, 1)"
    easing_bounce: str = "cubic-bezier(0.34, 1.56, 0.64, 1)"
    easing_spring: str = "cubic-bezier(0.175, 0.885, 0.32, 1.275)"

    # -----------------------------------------------------------------
    # Composite transition presets (duration + easing)
    # -----------------------------------------------------------------
    @property
    def transition_fast(self) -> str:
        return f"{self.duration_fast} {self.easing_ease_out}"

    @property
    def transition_normal(self) -> str:
        return f"{self.duration_normal} {self.easing_ease_in_out}"

    @property
    def transition_slow(self) -> str:
        return f"{self.duration_slow} {self.easing_ease_in_out}"

    @property
    def transition_bounce(self) -> str:
        return f"{self.duration_slow} {self.easing_bounce}"

    def to_css_dict(self) -> Dict[str, str]:
        """Return a CSS variable mapping for `:root {}` injection."""
        return {
            "--duration-instant": self.duration_instant,
            "--duration-fast": self.duration_fast,
            "--duration-normal": self.duration_normal,
            "--duration-slow": self.duration_slow,
            "--duration-slower": self.duration_slower,
            "--easing-linear": self.easing_linear,
            "--easing-ease": self.easing_ease,
            "--easing-ease-in": self.easing_ease_in,
            "--easing-ease-out": self.easing_ease_out,
            "--easing-ease-in-out": self.easing_ease_in_out,
            "--easing-bounce": self.easing_bounce,
            "--easing-spring": self.easing_spring,
            "--transition-fast": self.transition_fast,
            "--transition-normal": self.transition_normal,
            "--transition-slow": self.transition_slow,
            "--transition-bounce": self.transition_bounce,
        }
