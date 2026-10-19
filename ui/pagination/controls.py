"""Stateless navigation controls for pagination.

Each control is a lightweight object that knows how to render itself for the
target UI (Discord, HTML, CLI) and stores a callback that will be invoked when
the user activates the control. The paginator owns all state; controls merely
call back into it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

# The type of the callback that a control will invoke. It receives the
# paginator instance and performs the appropriate state transition.
ControlCallback = Callable[[Any], None]


@dataclass(frozen=True)
class _BaseControl:
    """Common base for all pagination controls.

    Subclasses should provide a ``label`` (used for HTML/CLI) and a ``render``
    method that returns a representation appropriate for the target transport.
    The ``callback`` is invoked when the control is activated.
    """

    label: str
    callback: ControlCallback

    def render_embed(self) -> dict:
        """Return a minimal Discord‑style button representation.

        Real Discord integration will replace this dict with an actual
        ``discord.ui.Button`` instance.
        """
        return {
            "type": "button",
            "style": "secondary",
            "label": self.label,
            "disabled": False,
        }

    def render_html(self) -> str:
        """HTML button element.
        """
        return f'<button type="button" class="pagination-control" disabled="false">{self.label}</button>'

    def render_text(self) -> str:
        """Plain‑text representation used in CLI output.
        """
        return f'[{self.label}]'


# Concrete stateless controls – each simply wires the appropriate paginator
# method via the supplied callback.

class FirstControl(_BaseControl):
    def __init__(self, paginator: Any):
        super().__init__(label="⏮️ First", callback=lambda _: paginator.first_page())


class PreviousControl(_BaseControl):
    def __init__(self, paginator: Any):
        super().__init__(label="◀️ Prev", callback=lambda _: paginator.previous_page())


class NextControl(_BaseControl):
    def __init__(self, paginator: Any):
        super().__init__(label="Next ▶️", callback=lambda _: paginator.next_page())


class LastControl(_BaseControl):
    def __init__(self, paginator: Any):
        super().__init__(label="Last ⏭️", callback=lambda _: paginator.last_page())


class PageSelectorControl(_BaseControl):
    """A dropdown / selector control that jumps to a specific page.

    The ``pages`` argument is a list of page numbers that should be selectable.
    The callback receives the chosen page number.
    """

    def __init__(self, paginator: Any, pages: list[int]):
        # The lambda captures the paginator and expects a page number later.
        super().__init__(label="Select Page", callback=lambda page: paginator.goto(page))
        self._available_pages = pages

    def render_embed(self) -> dict:
        # In Discord this would be a ``Select`` component.
        return {
            "type": "select",
            "options": [{"label": str(p), "value": str(p)} for p in self._available_pages],
        }

    def render_html(self) -> str:
        options = "\n".join(
            f'    <option value="{p}">{p}</option>' for p in self._available_pages
        )
        return f'<select class="pagination-selector">\n{options}\n</select>'

    def render_text(self) -> str:
        return f"Select page ({', '.join(map(str, self._available_pages))})"


class JumpToPageControl(_BaseControl):
    """A simple control that, when activated, asks the user for a page number.

    The actual UI frameworks will provide an input dialog. Here we expose a
    generic ``prompt`` method that callers can hook into.
    """

    def __init__(self, paginator: Any):
        super().__init__(label="🔢 Jump", callback=lambda page: paginator.goto(page))

    # The render methods can be identical to ``_BaseControl`` – the UI layer is
    # responsible for converting the click into a concrete page number.

    # No extra implementation needed.

__all__ = [
    "FirstControl",
    "PreviousControl",
    "NextControl",
    "LastControl",
    "PageSelectorControl",
    "JumpToPageControl",
]
