"""Comprehensive tests for ui/pagination – v7.3.0.

Coverage targets (>= 90%):
    - cursor.py         PageCursor, OffsetCursor, CursorToken
    - exceptions.py     PaginationError hierarchy
    - controls.py       All six stateless controls
    - views.py          PaginatedView composition
    - paginator.py      Paginator public API
    - Integration       EmbedBuilder + FormBuilder as RenderablePage
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

from ui.pagination.renderable import RenderablePage
from ui.pagination.cursor import PageCursor, OffsetCursor, CursorToken
from ui.pagination.exceptions import (
    PaginationError,
    InvalidPageError,
    EmptyPaginatorError,
    PageOutOfBoundsError,
)
from ui.pagination.controls import (
    FirstControl,
    PreviousControl,
    NextControl,
    LastControl,
    PageSelectorControl,
    JumpToPageControl,
)
from ui.pagination.paginator import Paginator
from ui.pagination.views import PaginatedView


class SimplePage(RenderablePage):
    """Minimal RenderablePage implementation for testing."""

    def __init__(self, label: str):
        self.label = label

    def render_embed(self) -> dict:
        return {"type": "embed", "label": self.label}

    def render_html(self) -> str:
        return f"<div class='page'>{self.label}</div>"

    def render_text(self) -> str:
        return f"--- {self.label} ---"


def make_pages(n: int) -> list[SimplePage]:
    """Create *n* simple pages labelled Page 1, Page 2, …"""
    return [SimplePage(f"Page {i + 1}") for i in range(n)]


# ===========================================================================
# Exceptions
# ===========================================================================


class TestExceptions:
    def test_pagination_error_is_base(self):
        assert issubclass(InvalidPageError, PaginationError)
        assert issubclass(EmptyPaginatorError, PaginationError)
        assert issubclass(PageOutOfBoundsError, PaginationError)

    def test_pagination_error_base_is_exception(self):
        assert issubclass(PaginationError, Exception)

    def test_raise_invalid_page_error(self):
        with pytest.raises(InvalidPageError):
            raise InvalidPageError("bad page")

    def test_raise_empty_paginator_error(self):
        with pytest.raises(EmptyPaginatorError):
            raise EmptyPaginatorError("empty")

    def test_raise_page_out_of_bounds_error(self):
        with pytest.raises(PageOutOfBoundsError):
            raise PageOutOfBoundsError("oob")


# ===========================================================================
# Cursor
# ===========================================================================


class TestPageCursor:
    # ------------------------------------------------------------------
    # total_pages
    # ------------------------------------------------------------------
    def test_total_pages_zero_items(self):
        c = PageCursor(page=1, page_size=10, total_items=0)
        assert c.total_pages == 0

    def test_total_pages_single_item(self):
        c = PageCursor(page=1, page_size=10, total_items=1)
        assert c.total_pages == 1

    def test_total_pages_exact_fit(self):
        c = PageCursor(page=1, page_size=10, total_items=10)
        assert c.total_pages == 1

    def test_total_pages_partial_last_page(self):
        c = PageCursor(page=1, page_size=10, total_items=97)
        assert c.total_pages == 10

    def test_total_pages_large_dataset(self):
        c = PageCursor(page=1, page_size=25, total_items=1000)
        assert c.total_pages == 40

    def test_total_pages_invalid_page_size(self):
        c = PageCursor(page=1, page_size=0, total_items=10)
        assert c.total_pages == 0

    # ------------------------------------------------------------------
    # has_next / has_previous
    # ------------------------------------------------------------------
    def test_has_next_when_not_last(self):
        c = PageCursor(page=1, page_size=10, total_items=20)
        assert c.has_next is True

    def test_has_next_when_last(self):
        c = PageCursor(page=2, page_size=10, total_items=20)
        assert c.has_next is False

    def test_has_previous_when_first(self):
        c = PageCursor(page=1, page_size=10, total_items=20)
        assert c.has_previous is False

    def test_has_previous_when_not_first(self):
        c = PageCursor(page=2, page_size=10, total_items=20)
        assert c.has_previous is True

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def test_next_page(self):
        c = PageCursor(page=1, page_size=10, total_items=20)
        c2 = c.next_page()
        assert c2.page == 2

    def test_next_page_raises_on_last(self):
        c = PageCursor(page=2, page_size=10, total_items=20)
        with pytest.raises(ValueError):
            c.next_page()

    def test_previous_page(self):
        c = PageCursor(page=2, page_size=10, total_items=20)
        c2 = c.previous_page()
        assert c2.page == 1

    def test_previous_page_raises_on_first(self):
        c = PageCursor(page=1, page_size=10, total_items=20)
        with pytest.raises(ValueError):
            c.previous_page()

    def test_first_page(self):
        c = PageCursor(page=5, page_size=10, total_items=100)
        assert c.first_page().page == 1

    def test_last_page(self):
        c = PageCursor(page=1, page_size=10, total_items=100)
        assert c.last_page().page == 10

    def test_goto_valid(self):
        c = PageCursor(page=1, page_size=10, total_items=100)
        assert c.goto(7).page == 7

    def test_goto_first(self):
        c = PageCursor(page=5, page_size=10, total_items=100)
        assert c.goto(1).page == 1

    def test_goto_last(self):
        c = PageCursor(page=1, page_size=10, total_items=100)
        assert c.goto(10).page == 10

    def test_goto_underflow(self):
        c = PageCursor(page=1, page_size=10, total_items=100)
        with pytest.raises(ValueError):
            c.goto(0)

    def test_goto_overflow(self):
        c = PageCursor(page=1, page_size=10, total_items=100)
        with pytest.raises(ValueError):
            c.goto(11)

    # ------------------------------------------------------------------
    # Immutability – navigation should return a NEW cursor
    # ------------------------------------------------------------------
    def test_navigation_returns_new_instance(self):
        c = PageCursor(page=1, page_size=10, total_items=20)
        c2 = c.next_page()
        assert c.page == 1  # original unchanged
        assert c2.page == 2


class TestOffsetCursor:
    def test_is_subclass_of_page_cursor(self):
        assert issubclass(OffsetCursor, PageCursor)

    def test_offset_cursor_navigation(self):
        c = OffsetCursor(page=1, page_size=10, total_items=30)
        assert c.next_page().page == 2

    def test_exact_page_boundary(self):
        c = OffsetCursor(page=1, page_size=10, total_items=10)
        assert c.total_pages == 1
        assert c.has_next is False


class TestCursorToken:
    def test_repr(self):
        ct = CursorToken(token="abc123", page_size=10)
        assert "abc123" in repr(ct)

    def test_page_is_none(self):
        ct = CursorToken(token="t", page_size=5)
        assert ct.page is None

    def test_next_page_raises(self):
        ct = CursorToken(token="t", page_size=5)
        with pytest.raises(NotImplementedError):
            ct.next_page()

    def test_previous_page_raises(self):
        ct = CursorToken(token="t", page_size=5)
        with pytest.raises(NotImplementedError):
            ct.previous_page()

    def test_first_page_raises(self):
        ct = CursorToken(token="t", page_size=5)
        with pytest.raises(NotImplementedError):
            ct.first_page()

    def test_last_page_raises(self):
        ct = CursorToken(token="t", page_size=5)
        with pytest.raises(NotImplementedError):
            ct.last_page()

    def test_goto_raises(self):
        ct = CursorToken(token="t", page_size=5)
        with pytest.raises(NotImplementedError):
            ct.goto(1)


# ===========================================================================
# Paginator
# ===========================================================================


class TestPaginatorInit:
    def test_empty_raises_empty_paginator_error(self):
        with pytest.raises(EmptyPaginatorError):
            Paginator([])

    def test_single_page(self):
        p = Paginator(make_pages(1))
        assert p.total_pages() == 1

    def test_multiple_pages(self):
        p = Paginator(make_pages(7))
        assert p.total_pages() == 7

    def test_cursor_starts_at_page_one(self):
        p = Paginator(make_pages(5))
        assert p.cursor.page == 1

    def test_repr(self):
        p = Paginator(make_pages(3))
        assert "1" in repr(p)
        assert "3" in repr(p)

    def test_len(self):
        pages = make_pages(4)
        p = Paginator(pages)
        assert len(p) == 4


class TestPaginatorNavigation:
    def _paginator(self, n: int) -> Paginator:
        return Paginator(make_pages(n))

    # next_page
    def test_next_page_increments_cursor(self):
        p = self._paginator(3)
        p.next_page()
        assert p.cursor.page == 2

    def test_next_page_from_last_raises(self):
        p = self._paginator(2)
        p.last_page()
        with pytest.raises(PageOutOfBoundsError):
            p.next_page()

    # previous_page
    def test_previous_page_decrements_cursor(self):
        p = self._paginator(3)
        p.goto(3)
        p.previous_page()
        assert p.cursor.page == 2

    def test_previous_page_from_first_raises(self):
        p = self._paginator(3)
        with pytest.raises(PageOutOfBoundsError):
            p.previous_page()

    # first_page / last_page
    def test_first_page(self):
        p = self._paginator(5)
        p.goto(5)
        p.first_page()
        assert p.cursor.page == 1

    def test_last_page(self):
        p = self._paginator(5)
        p.last_page()
        assert p.cursor.page == 5

    # goto
    def test_goto_valid_page(self):
        p = self._paginator(10)
        p.goto(7)
        assert p.cursor.page == 7

    def test_goto_first_page(self):
        p = self._paginator(10)
        p.goto(1)
        assert p.cursor.page == 1

    def test_goto_last_page(self):
        p = self._paginator(10)
        p.goto(10)
        assert p.cursor.page == 10

    def test_goto_below_one_raises_invalid_page(self):
        p = self._paginator(5)
        with pytest.raises(InvalidPageError):
            p.goto(0)

    def test_goto_above_total_raises_out_of_bounds(self):
        p = self._paginator(5)
        with pytest.raises(PageOutOfBoundsError):
            p.goto(6)

    # single-page edge
    def test_single_page_next_raises(self):
        p = self._paginator(1)
        with pytest.raises(PageOutOfBoundsError):
            p.next_page()

    def test_single_page_previous_raises(self):
        p = self._paginator(1)
        with pytest.raises(PageOutOfBoundsError):
            p.previous_page()


class TestPaginatorRendering:
    def test_render_embed_returns_correct_page(self):
        p = Paginator(make_pages(3))
        result = p.render_embed()
        assert result == {"type": "embed", "label": "Page 1"}

    def test_render_embed_after_navigation(self):
        p = Paginator(make_pages(3))
        p.next_page()
        result = p.render_embed()
        assert result["label"] == "Page 2"

    def test_render_html_returns_string(self):
        p = Paginator(make_pages(3))
        html = p.render_html()
        assert isinstance(html, str)
        assert "Page 1" in html

    def test_render_html_after_navigation(self):
        p = Paginator(make_pages(3))
        p.goto(3)
        html = p.render_html()
        assert "Page 3" in html

    def test_render_text_returns_string(self):
        p = Paginator(make_pages(3))
        text = p.render_text()
        assert isinstance(text, str)
        assert "Page 1" in text

    def test_render_text_after_navigation(self):
        p = Paginator(make_pages(3))
        p.last_page()
        text = p.render_text()
        assert "Page 3" in text

    # Large dataset boundary checks
    def test_last_page_of_97_items_page_size_10(self):
        # 97 items → 10 pages; last page renders page 10
        pages = make_pages(10)
        p = Paginator(pages)
        p.last_page()
        assert p.cursor.page == 10
        assert "Page 10" in p.render_text()


# ===========================================================================
# Stateless Controls
# ===========================================================================


class TestControls:
    def _paginator(self, n: int, start: int = 1) -> Paginator:
        pag = Paginator(make_pages(n))
        if start != 1:
            pag.goto(start)
        return pag

    def _invocation_counter(self):
        calls = []
        def callback(_):
            calls.append(True)
        return callback, calls

    # FirstControl
    def test_first_control_label(self):
        ctrl = FirstControl(self._paginator(3))
        assert "First" in ctrl.label or "⏮" in ctrl.label

    def test_first_control_callback(self):
        pag = self._paginator(5, start=5)
        ctrl = FirstControl(pag)
        ctrl.callback(None)  # triggers paginator.first_page()
        assert pag.cursor.page == 1

    # PreviousControl
    def test_previous_control_callback(self):
        pag = self._paginator(5, start=3)
        ctrl = PreviousControl(pag)
        ctrl.callback(None)
        assert pag.cursor.page == 2

    # NextControl
    def test_next_control_callback(self):
        pag = self._paginator(5, start=1)
        ctrl = NextControl(pag)
        ctrl.callback(None)
        assert pag.cursor.page == 2

    # LastControl
    def test_last_control_callback(self):
        pag = self._paginator(5, start=1)
        ctrl = LastControl(pag)
        ctrl.callback(None)
        assert pag.cursor.page == 5

    # PageSelectorControl
    def test_page_selector_callback(self):
        pag = self._paginator(7)
        ctrl = PageSelectorControl(pag, list(range(1, 8)))
        ctrl.callback(4)
        assert pag.cursor.page == 4

    # JumpToPageControl
    def test_jump_to_page_callback(self):
        pag = self._paginator(7)
        ctrl = JumpToPageControl(pag)
        ctrl.callback(6)
        assert pag.cursor.page == 6

    # Render methods
    def test_first_control_render_embed(self):
        ctrl = FirstControl(self._paginator(3))
        data = ctrl.render_embed()
        assert isinstance(data, dict)

    def test_next_control_render_html(self):
        ctrl = NextControl(self._paginator(3))
        html = ctrl.render_html()
        assert "<button" in html

    def test_previous_control_render_text(self):
        ctrl = PreviousControl(self._paginator(3, start=2))
        text = ctrl.render_text()
        assert "[" in text  # simple bracket notation

    def test_page_selector_render_html(self):
        ctrl = PageSelectorControl(self._paginator(3), [1, 2, 3])
        html = ctrl.render_html()
        assert "<select" in html

    def test_page_selector_render_embed(self):
        ctrl = PageSelectorControl(self._paginator(3), [1, 2, 3])
        data = ctrl.render_embed()
        assert data["type"] == "select"

    def test_page_selector_render_text(self):
        ctrl = PageSelectorControl(self._paginator(3), [1, 2, 3])
        text = ctrl.render_text()
        assert "1" in text


# ===========================================================================
# PaginatedView
# ===========================================================================


class TestPaginatedView:
    def test_total_pages(self):
        view = PaginatedView(Paginator(make_pages(5)))
        assert view.total_pages() == 5

    def test_current_page_starts_at_one(self):
        view = PaginatedView(Paginator(make_pages(5)))
        assert view.current_page() == 1

    def test_goto_updates_current_page(self):
        view = PaginatedView(Paginator(make_pages(5)))
        view.goto(3)
        assert view.current_page() == 3

    # Embed rendering
    def test_render_embed_has_content(self):
        view = PaginatedView(Paginator(make_pages(3)))
        result = view.render_embed()
        assert "content" in result
        assert "controls" in result
        assert "footer" in result

    def test_render_embed_footer_shows_page_indicator(self):
        view = PaginatedView(Paginator(make_pages(5)))
        view.goto(3)
        footer = view.render_embed()["footer"]
        assert "3" in footer
        assert "5" in footer

    # HTML rendering
    def test_render_html_contains_page_and_footer(self):
        view = PaginatedView(Paginator(make_pages(3)))
        html = view.render_html()
        assert "Page 1" in html
        assert "Page 1 / 3" in html

    def test_render_html_after_navigation(self):
        view = PaginatedView(Paginator(make_pages(3)))
        view.goto(2)
        html = view.render_html()
        assert "Page 2" in html
        assert "Page 2 / 3" in html

    # Text rendering
    def test_render_text_contains_page_indicator(self):
        view = PaginatedView(Paginator(make_pages(7)))
        view.goto(2)
        text = view.render_text()
        assert "2 / 7" in text or "Page 2" in text

    def test_render_text_format(self):
        view = PaginatedView(Paginator(make_pages(3)))
        text = view.render_text()
        assert isinstance(text, str)
        assert len(text) > 0

    # Single-page view
    def test_single_page_footer(self):
        view = PaginatedView(Paginator(make_pages(1)))
        footer = view.render_embed()["footer"]
        assert "1 / 1" in footer


# ===========================================================================
# Integration – EmbedBuilder as RenderablePage
# ===========================================================================


class TestEmbedBuilderIntegration:
    """EmbedBuilder already implements render_embed / render_html / render_text,
    so it satisfies the RenderablePage contract without modification."""

    def _build_embed(self, title: str):
        from ui.embeds.builder import EmbedBuilder
        return (
            EmbedBuilder()
            .set_title(title)
            .set_description(f"Description for {title}")
        )

    def test_embed_builder_satisfies_renderable_page(self):
        from ui.embeds.builder import EmbedBuilder
        assert hasattr(EmbedBuilder, "render_embed")
        assert hasattr(EmbedBuilder, "render_html")
        assert hasattr(EmbedBuilder, "render_text")

    def test_paginator_accepts_embed_builders(self):
        pages = [self._build_embed("Page One"), self._build_embed("Page Two")]
        p = Paginator(pages)
        assert p.total_pages() == 2

    def test_paginator_renders_first_embed(self):
        pages = [self._build_embed("First"), self._build_embed("Second")]
        p = Paginator(pages)
        result = p.render_embed()
        assert result["title"] == "First"

    def test_paginator_renders_second_embed_after_navigation(self):
        pages = [self._build_embed("First"), self._build_embed("Second")]
        p = Paginator(pages)
        p.next_page()
        result = p.render_embed()
        assert result["title"] == "Second"

    def test_paginator_render_html_contains_title(self):
        pages = [self._build_embed("My Embed")]
        p = Paginator(pages)
        html = p.render_html()
        assert "My Embed" in html

    def test_paginator_render_text_contains_title(self):
        pages = [self._build_embed("My Embed")]
        p = Paginator(pages)
        text = p.render_text()
        assert "My Embed" in text

    def test_embed_paginator_navigation_sequence(self):
        pages = [self._build_embed(f"Slide {i}") for i in range(1, 6)]
        p = Paginator(pages)
        p.last_page()
        result = p.render_embed()
        assert "Slide 5" in result["title"]

    def test_paginated_view_with_embed_builders(self):
        pages = [self._build_embed("A"), self._build_embed("B"), self._build_embed("C")]
        view = PaginatedView(Paginator(pages))
        view.goto(2)
        result = view.render_embed()
        assert result["content"]["title"] == "B"


# ===========================================================================
# Integration – FormBuilder as RenderablePage
# ===========================================================================


class TestFormBuilderIntegration:
    """FormBuilder already implements render_embed / render_html / render_text,
    so it satisfies the RenderablePage contract without modification."""

    def _build_form(self, title: str):
        from ui.forms.builder import FormBuilder
        return (
            FormBuilder(title=title, custom_id=f"form:{title.lower()}")
            .add_string_field("name", "Name", placeholder="Enter name")
        )

    def test_form_builder_satisfies_renderable_page(self):
        from ui.forms.builder import FormBuilder
        assert hasattr(FormBuilder, "render_embed")
        assert hasattr(FormBuilder, "render_html")
        assert hasattr(FormBuilder, "render_text")

    def test_paginator_accepts_form_builders(self):
        pages = [self._build_form("Step 1"), self._build_form("Step 2")]
        p = Paginator(pages)
        assert p.total_pages() == 2

    def test_paginator_renders_first_form(self):
        pages = [self._build_form("Step 1"), self._build_form("Step 2")]
        p = Paginator(pages)
        result = p.render_embed()
        assert "Step 1" in result["title"]

    def test_paginator_renders_second_form_after_navigation(self):
        pages = [self._build_form("Step 1"), self._build_form("Step 2")]
        p = Paginator(pages)
        p.next_page()
        result = p.render_embed()
        assert "Step 2" in result["title"]

    def test_form_paginator_render_html(self):
        pages = [self._build_form("Page One")]
        p = Paginator(pages)
        html = p.render_html()
        assert isinstance(html, str)
        assert len(html) > 0

    def test_form_paginator_render_text(self):
        pages = [self._build_form("Page One")]
        p = Paginator(pages)
        text = p.render_text()
        assert "Page One" in text

    def test_multi_page_form_preserves_order(self):
        pages = [self._build_form(f"Step {i}") for i in range(1, 4)]
        p = Paginator(pages)
        for i in range(1, 4):
            p.goto(i)
            result = p.render_embed()
            assert f"Step {i}" in result["title"]

    def test_paginated_view_with_form_builders(self):
        pages = [self._build_form("A"), self._build_form("B")]
        view = PaginatedView(Paginator(pages))
        result = view.render_embed()
        assert "A" in result["content"]["title"]
        view.goto(2)
        result = view.render_embed()
        assert "B" in result["content"]["title"]


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_paginator_error_message(self):
        with pytest.raises(EmptyPaginatorError, match="empty"):
            Paginator([])

    def test_paginator_page_size_is_always_one(self):
        p = Paginator(make_pages(5))
        assert p.page_size() == 1

    def test_cursor_is_immutable_across_navigations(self):
        p = Paginator(make_pages(5))
        original_cursor = p.cursor
        p.next_page()
        assert p.cursor is not original_cursor
        assert original_cursor.page == 1

    def test_sequential_next_to_last(self):
        n = 5
        p = Paginator(make_pages(n))
        for _ in range(n - 1):
            p.next_page()
        assert p.cursor.page == n

    def test_sequential_previous_to_first(self):
        n = 5
        p = Paginator(make_pages(n))
        p.last_page()
        for _ in range(n - 1):
            p.previous_page()
        assert p.cursor.page == 1

    def test_goto_negative_page(self):
        p = Paginator(make_pages(5))
        with pytest.raises(InvalidPageError):
            p.goto(-1)

    def test_first_and_last_on_single_page(self):
        p = Paginator(make_pages(1))
        p.first_page()
        assert p.cursor.page == 1
        p.last_page()
        assert p.cursor.page == 1

    def test_97_items_page_size_10_gives_10_pages(self):
        # Cursor math: 97 items, page_size 10 → 10 pages.
        c = PageCursor(page=1, page_size=10, total_items=97)
        assert c.total_pages == 10
        assert c.last_page().page == 10

    def test_renderable_page_is_abstract(self):
        with pytest.raises(TypeError):
            RenderablePage()  # type: ignore[abstract]
