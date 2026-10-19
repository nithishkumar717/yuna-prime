"""Paginator orchestration layer.

The ``Paginator`` owns the list of ``RenderablePage`` objects and a
``PageCursor`` that tracks the current page index. It provides navigation
methods that mutate the cursor and delegate rendering to the current page.
It is deliberately transport‑agnostic – rendering is performed by the page
itself via ``render_embed``, ``render_html`` and ``render_text``.
"""

from __future__ import annotations

from typing import Any, Sequence

from .renderable import RenderablePage
from .cursor import PageCursor
from .exceptions import EmptyPaginatorError, InvalidPageError, PageOutOfBoundsError


class Paginator:
    """Public API for pagination.

    Parameters
    ----------
    pages: List[RenderablePage]
        Pre‑constructed renderable pages. Each entry must implement the
        ``RenderablePage`` interface.
    """

    def __init__(self, pages: Sequence[RenderablePage]):
        if not pages:
            raise EmptyPaginatorError("Paginator cannot be instantiated with an empty page list.")
        self._pages: Sequence[RenderablePage] = pages
        # For now each page is a separate entry – page_size of 1.
        total_items = len(pages)
        self.cursor: PageCursor = PageCursor(page=1, page_size=1, total_items=total_items)

    # ---------------------------------------------------------------------
    # Navigation helpers – these mutate ``self.cursor`` and raise appropriate
    # pagination errors when navigation is out of bounds.
    # ---------------------------------------------------------------------
    def _validate_page_number(self, page: int) -> None:
        if page < 1:
            raise InvalidPageError("Page number must be >= 1.")
        if page > self.total_pages():
            raise PageOutOfBoundsError(f"Page {page} exceeds total pages {self.total_pages()}.")

    def next_page(self) -> None:
        if not self.cursor.has_next:
            raise PageOutOfBoundsError("Already at the last page.")
        self.cursor = self.cursor.next_page()

    def previous_page(self) -> None:
        if not self.cursor.has_previous:
            raise PageOutOfBoundsError("Already at the first page.")
        self.cursor = self.cursor.previous_page()

    def first_page(self) -> None:
        self.cursor = self.cursor.first_page()

    def last_page(self) -> None:
        self.cursor = self.cursor.last_page()

    def goto(self, page: int) -> None:
        self._validate_page_number(page)
        self.cursor = self.cursor.goto(page)

    # ---------------------------------------------------------------------
    # Rendering delegations – simply forward to the current page.
    # ---------------------------------------------------------------------
    def _current_page_obj(self) -> RenderablePage:
        # ``self.cursor.page`` is 1‑based.
        index = self.cursor.page - 1
        return self._pages[index]

    def render_embed(self) -> Any:
        return self._current_page_obj().render_embed()

    def render_html(self) -> str:
        return self._current_page_obj().render_html()

    def render_text(self) -> str:
        return self._current_page_obj().render_text()

    # ---------------------------------------------------------------------
    # Convenience helpers.
    # ---------------------------------------------------------------------
    def total_pages(self) -> int:
        return len(self._pages)

    def page_size(self) -> int:
        # Size per page is constant (1) as each entry is a full page.
        return 1

    def __len__(self) -> int:
        return len(self._pages)

    def __repr__(self) -> str:
        return f"Paginator(page={self.cursor.page}, total_pages={self.total_pages()})"

__all__ = ["Paginator"]
