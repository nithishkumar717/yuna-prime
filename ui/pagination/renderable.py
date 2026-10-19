"""Abstract base class for any UI component that can be paginated.

All paginated pages must implement three rendering methods returning the
appropriate representation for each transport target.
"""

from abc import ABC, abstractmethod
from typing import Any


class RenderablePage(ABC):
    """Interface that page objects must implement to be used with the paginator.

    Implementations may be concrete UI components such as ``EmbedBuilder``,
    ``FormBuilder`` or future chart/card components.
    """

    @abstractmethod
    def render_embed(self) -> Any:
        """Return a Discord embed (or a compatible object) representing the page.
        """
        raise NotImplementedError

    @abstractmethod
    def render_html(self) -> str:
        """Return an HTML string representing the page.
        """
        raise NotImplementedError

    @abstractmethod
    def render_text(self) -> str:
        """Return a plain‑text representation of the page (for CLI output).
        """
        raise NotImplementedError
