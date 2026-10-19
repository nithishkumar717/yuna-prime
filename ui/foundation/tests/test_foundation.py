import pytest
from typing import Dict, Any
from ui.foundation import (
    ColorPalette,
    TypographyStyle,
    SpacingToken,
    BaseUIComponent,
    ThemeEngine,
    InvalidThemeError
)


class SampleCardComponent(BaseUIComponent):
    """Test UI component implementing multi-target render interface."""

    def __init__(self, title: str, content: str) -> None:
        self.title = title
        self.content = content

    def render_embed(self) -> Dict[str, Any]:
        theme = ThemeEngine.get_active_theme()
        return {
            "title": self.title,
            "description": self.content,
            "color": theme.colors.primary
        }

    def render_html(self) -> str:
        return f"<div class='ui-card'><h2>{self.title}</h2><p>{self.content}</p></div>"

    def render_text(self) -> str:
        return f"=== {self.title} ===\n{self.content}"


@pytest.fixture(autouse=True)
def setup_theme_engine():
    ThemeEngine.clear()
    yield
    ThemeEngine.clear()


def test_color_palette_conversions():
    palette = ColorPalette(primary=0x5865F2, danger=0xED4245)
    assert palette.to_hex_int("primary") == 0x5865F2
    assert palette.to_hex_str("primary") == "#5865F2"
    assert palette.to_hex_str("danger") == "#ED4245"

    css = palette.to_css_dict()
    assert css["--color-primary"] == "#5865F2"
    assert css["--color-danger"] == "#ED4245"


def test_typography_and_spacing_tokens():
    typo = TypographyStyle()
    assert "--font-family" in typo.to_css_dict()

    spacing = SpacingToken(xs="4px", lg="24px")
    css = spacing.to_css_dict()
    assert css["--spacing-xs"] == "4px"
    assert css["--spacing-lg"] == "24px"


def test_multi_target_component_rendering():
    card = SampleCardComponent(title="Security Alert", content="Suspicious login detected.")

    embed = card.render_embed()
    assert embed["title"] == "Security Alert"
    assert embed["color"] == 0x5865F2

    html = card.render_html()
    assert "<div class='ui-card'>" in html

    text = card.render_text()
    assert "=== Security Alert ===" in text


def test_theme_engine_and_active_switching():
    # Retrieve default dark theme
    dark_theme = ThemeEngine.get_active_theme()
    assert dark_theme.name == "yuna_dark"

    # Switch to light theme
    ThemeEngine.set_active_theme("yuna_light")
    active = ThemeEngine.get_active_theme()
    assert active.name == "yuna_light"

    # Test CSS variable export
    css_export = active.export_css_variables()
    assert ":root {" in css_export
    assert "--color-primary" in css_export

    # Error handling for invalid theme
    with pytest.raises(InvalidThemeError):
        ThemeEngine.get_theme("non_existent_theme")
