"""Performance and benchmarking tests for the Yuna UI Library."""

from __future__ import annotations

import time
import warnings
from ui.themes import ThemeRegistry
from ui.dashboard import DashboardRenderer, DashboardCard, KPIWidget, DataTable
from ui.pagination import Paginator, RenderablePage



class SamplePage(RenderablePage):
    """Minimal RenderablePage implementation for performance testing."""
    def render_embed(self) -> dict:
        return {"title": "Test", "description": "Desc"}
    def render_html(self) -> str:
        return "<div>Test</div>"
    def render_text(self) -> str:
        return "Test"


def test_performance_theme_resolution():
    """Verify that theme resolution and CSS generation is extremely fast."""
    # Warmup
    ThemeRegistry._init_defaults()
    ThemeRegistry.resolve_palette()
    
    start = time.perf_counter()
    iterations = 1000
    for _ in range(iterations):
        ThemeRegistry.resolve_palette()
        ThemeRegistry.resolve_brand()
        ThemeRegistry.export_css_manifest()
    end = time.perf_counter()
    
    duration_ms = (end - start) * 1000
    avg_ms = duration_ms / iterations
    print(f"\n[Theme Resolution Benchmark] Avg: {avg_ms:.4f} ms per iteration")
    
    # Assert average resolution/manifest generation is under 5ms (typically << 1ms)
    assert avg_ms < 5.0


def test_performance_dashboard_rendering():
    """Verify that document and component rendering is extremely fast."""
    renderer = DashboardRenderer()
    card = DashboardCard("Security", "Safe", accent_color="success")
    kpi = KPIWidget("Alerts", 3)
    table = DataTable(["Name", "Value"], [["A", "1"], ["B", "2"]])
    
    start = time.perf_counter()
    iterations = 500
    for _ in range(iterations):
        c_html = card.render_html()
        k_html = kpi.render_html()
        t_html = table.render_html()
        full_content = f"{c_html}{k_html}{t_html}"
        renderer.render_document(full_content, title="Dashboard Performance Test")
    end = time.perf_counter()
    
    duration_ms = (end - start) * 1000
    avg_ms = duration_ms / iterations
    print(f"[Dashboard Rendering Benchmark] Avg: {avg_ms:.4f} ms per full page render")
    
    # Assert average render time is under 10ms (typically << 2ms)
    assert avg_ms < 10.0


def test_performance_pagination_and_navigation():
    """Verify that pagination transitions are fast."""
    pages = [SamplePage() for _ in range(20)]
    paginator = Paginator(pages)
    
    start = time.perf_counter()
    iterations = 1000
    for i in range(iterations):
        paginator.goto(i % 20 + 1)
        _ = paginator.cursor.page
        _ = paginator.cursor.has_next
        _ = paginator.cursor.has_previous
    end = time.perf_counter()

    
    duration_ms = (end - start) * 1000
    avg_ms = duration_ms / iterations
    print(f"[Pagination Benchmark] Avg: {avg_ms:.4f} ms per transition")
    
    # Assert average transition is under 2ms (typically << 0.1ms)
    assert avg_ms < 2.0


def test_deprecation_decorator_emits_warning():
    """Verify that the @deprecated decorator raises a DeprecationWarning."""
    from ui.foundation.deprecation import deprecated

    @deprecated("new_function")
    def old_function():
        return "result"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        res = old_function()
        
        assert res == "result"
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "old_function is deprecated" in str(w[0].message)
        assert "Use new_function instead" in str(w[0].message)
