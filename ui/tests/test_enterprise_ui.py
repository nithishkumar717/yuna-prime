"""End-to-end tests for Volume VIII – Enterprise UI Library Stable (v8.0.0)."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from ui.embeds.builder import EmbedBuilder
from ui.pagination.paginator import Paginator
from ui.pagination.renderable import RenderablePage
from ui.dashboard.renderer import DashboardRenderer
from ui.dashboard.adapters import (
    EmbedToCardAdapter,
    PaginatorToHtmlAdapter,
)
from ui.accessibility.validator import AccessibilityAudit
from ui.accessibility.contrast import WCAGLevel
from ui.themes import ThemeRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_registry():
    ThemeRegistry.reset()
    yield
    ThemeRegistry.reset()


# Helpers (not test classes)
def _create_test_page(title: str) -> RenderablePage:
    class _TP(RenderablePage):
        def render_embed(self):
            return {"title": title, "description": "Test page"}
        def render_html(self):
            return f"<div><h3>{title}</h3></div>"
        def render_text(self):
            return title
    return _TP()


@pytest.fixture
def test_paginator():
    return Paginator([
        _create_test_page("Page 1"),
        _create_test_page("Page 2"),
        _create_test_page("Page 3"),
    ])


@pytest.fixture
def test_embed():
    return (
        EmbedBuilder()
        .set_title("Enterprise Test")
        .set_description("E2E test")
        .set_color("primary")
    )


# ===========================================================================
# End-to-End Tests
# ===========================================================================
class TestEnterpriseUI:
    def test_multi_theme_embed_rendering(self):
        from ui.foundation.theme import ThemeEngine
        for theme_name in ["yuna_dark", "yuna_light", "high_contrast"]:
            ThemeEngine.set_active_theme(theme_name)
            embed = EmbedBuilder().set_title(f"{theme_name} Test").render_embed()
            assert embed["title"] == f"{theme_name} Test"

    def test_embed_to_dashboard(self, test_embed):
        adapter = EmbedToCardAdapter(test_embed)
        html = adapter.to_html()
        assert "Enterprise Test" in html

    def test_paginator_to_dashboard(self, test_paginator):
        adapter = PaginatorToHtmlAdapter(test_paginator)
        html = adapter.to_html()
        assert "Page 1" in html

    def test_dashboard_css_generation(self):
        renderer = DashboardRenderer()
        css = renderer.generate_css()
        assert "--color-primary" in css
        assert "Inter" in css

    def test_accessibility_audit_all_themes(self):
        from ui.foundation.theme import ThemeEngine
        for theme_name in ["yuna_dark", "yuna_light", "high_contrast"]:
            ThemeEngine.set_active_theme(theme_name)
            audit = AccessibilityAudit.audit_theme(theme_name, WCAGLevel.AA)
            assert audit["theme_name"] == theme_name