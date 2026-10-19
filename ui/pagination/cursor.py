"""Cursor abstractions for pagination.

Provides offset‑based pagination (PageCursor, OffsetCursor) and a placeholder
CursorToken for future token‑based implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PageCursor:
    """Represents the current position in a paginated collection.

    Attributes
    ----------
    page: int
        1‑based index of the current page.
    page_size: int
        Number of items per page.
    total_items: int
        Total number of items in the collection.
    """

    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        """Calculate the total number of pages based on ``total_items`` and ``page_size``.
        """
        if self.page_size <= 0:
            return 0
        return (self.total_items + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    def next_page(self) -> "PageCursor":
        if not self.has_next:
            raise ValueError("Already at last page")
        return PageCursor(self.page + 1, self.page_size, self.total_items)

    def previous_page(self) -> "PageCursor":
        if not self.has_previous:
            raise ValueError("Already at first page")
        return PageCursor(self.page - 1, self.page_size, self.total_items)

    def first_page(self) -> "PageCursor":
        return PageCursor(1, self.page_size, self.total_items)

    def last_page(self) -> "PageCursor":
        return PageCursor(self.total_pages, self.page_size, self.total_items)

    def goto(self, page: int) -> "PageCursor":
        if page < 1 or page > self.total_pages:
            raise ValueError("Page out of bounds")
        return PageCursor(page, self.page_size, self.total_items)


# Alias for clarity – currently offset based.
class OffsetCursor(PageCursor):
    """Concrete implementation used today; identical to ``PageCursor`` but kept for
    future API stability when token‑based cursors are introduced.
    """

    pass


class CursorToken:
    """Placeholder for future token‑based cursor implementations.

    The class stores an opaque token string that can be passed to APIs that
    support cursor pagination (e.g., GraphQL connections). It implements the same
    navigation interface as ``PageCursor`` but raises ``NotImplementedError`` for
    now.
    """

    def __init__(self, token: str, page_size: int, total_items: Optional[int] = None):
        self.token = token
        self.page_size = page_size
        self.total_items = total_items or 0
        # ``page`` is unknown for token‑based cursors – we keep it optional.
        self.page = None

    def __repr__(self) -> str:
        return f"CursorToken(token={self.token!r}, page_size={self.page_size})"

    # All navigation methods raise to signal unimplemented functionality.
    def next_page(self, *_, **__) -> "CursorToken":  # pragma: no cover
        raise NotImplementedError("Token‑based pagination not implemented yet")

    def previous_page(self, *_, **__) -> "CursorToken":  # pragma: no cover
        raise NotImplementedError("Token‑based pagination not implemented yet")

    def first_page(self, *_, **__) -> "CursorToken":  # pragma: no cover
        raise NotImplementedError("Token‑based pagination not implemented yet")

    def last_page(self, *_, **__) -> "CursorToken":  # pragma: no cover
        raise NotImplementedError("Token‑based pagination not implemented yet")

    def goto(self, *_, **__) -> "CursorToken":  # pragma: no cover
        raise NotImplementedError("Token‑based pagination not implemented yet")
