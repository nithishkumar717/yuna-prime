from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseUIComponent(ABC):
    """Abstract base class for all multi-target UI components in Yuna Framework."""

    @abstractmethod
    def render_embed(self) -> Dict[str, Any]:
        """Renders component as a structured Discord Embed dictionary payload."""
        pass

    @abstractmethod
    def render_html(self) -> str:
        """Renders component as a styled Web Dashboard HTML element."""
        pass

    @abstractmethod
    def render_text(self) -> str:
        """Renders component as a clean plain-text fallback representation."""
        pass
