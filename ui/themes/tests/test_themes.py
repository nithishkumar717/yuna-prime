"""Comprehensive tests for ui/themes – v7.4.0 Theme & Branding Engine.

Coverage targets (>= 90%):
    exceptions.py       BrandingError hierarchy
    palette.py          BrandPalette, SemanticColorRole, inheritance, factories
    typography.py       BrandTypography, CSS dict
    animations.py       AnimationToken, CSS dict, composite properties
    branding.py         BrandProfile, validation, multi-target rendering, factories
    assets.py           BrandAssetRegistry CRUD, fallback, manifest
    registry.py         ThemeRegistry registration, inheritance, guild overrides,
                        CSS manifest, asset manifest, backward compat
    Integration         EmbedBuilder and Paginator consuming theme data
    Backward compat     ThemeEngine.get_active_theme() still works after ThemeRegistry
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from ui.themes.exceptions import (
    BrandingError,
    ThemeInheritanceError,
    AssetNotFoundError,
    InvalidBrandProfileError,
)
from ui.themes.palette import BrandPalette, SemanticColorRole
from ui.themes.typography import BrandTypography
from ui.themes.animations import AnimationToken
from ui.themes.branding import BrandProfile
from ui.themes.assets import BrandAssetRegistry
from ui.themes.registry import ThemeRegistry
from ui.foundation.theme import ThemeConfig, ThemeEngine
from ui.foundation.colors import ColorPalette
from ui.foundation.exceptions import UIError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset ThemeRegistry and ThemeEngine before each test for isolation."""
    ThemeRegistry.reset()
    yield
    ThemeRegistry.reset()


def _make_config(name: str, primary: int = 0x5865F2) -> ThemeConfig:
    return ThemeConfig(name=name, colors=ColorPalette(primary=primary))


# ===========================================================================
# Exceptions
# ===========================================================================


class TestExceptions:
    def test_branding_error_extends_ui_error(self):
        assert issubclass(BrandingError, UIError)

    def test_inheritance_error_is_branding_error(self):
        assert issubclass(ThemeInheritanceError, BrandingError)

    def test_asset_not_found_is_branding_error(self):
        assert issubclass(AssetNotFoundError, BrandingError)

    def test_invalid_brand_profile_is_branding_error(self):
        assert issubclass(InvalidBrandProfileError, BrandingError)

    def test_raise_branding_error(self):
        with pytest.raises(BrandingError):
            raise BrandingError("test")

    def test_raise_theme_inheritance_error(self):
        with pytest.raises(ThemeInheritanceError):
            raise ThemeInheritanceError("bad parent")

    def test_raise_asset_not_found(self):
        with pytest.raises(AssetNotFoundError):
            raise AssetNotFoundError("missing asset")

    def test_raise_invalid_brand_profile(self):
        with pytest.raises(InvalidBrandProfileError):
            raise InvalidBrandProfileError("bad profile")


# ===========================================================================
# BrandPalette & SemanticColorRole
# ===========================================================================


class TestBrandPalette:
    def test_default_values(self):
        p = BrandPalette()
        assert p.primary == 0x5865F2

    def test_extends_color_palette(self):
        from ui.foundation.colors import ColorPalette
        assert issubclass(BrandPalette, ColorPalette)

    def test_additional_tokens_present(self):
        p = BrandPalette()
        assert hasattr(p, "surface")
        assert hasattr(p, "on_surface")
        assert hasattr(p, "accent")
        assert hasattr(p, "muted")

    def test_to_css_dict_includes_extended_tokens(self):
        p = BrandPalette()
        css = p.to_css_dict()
        assert "--color-surface" in css
        assert "--color-on-surface" in css
        assert "--color-accent" in css
        assert "--color-muted" in css

    def test_to_css_dict_includes_base_tokens(self):
        p = BrandPalette()
        css = p.to_css_dict()
        assert "--color-primary" in css
        assert "--color-danger" in css

    def test_resolve_semantic_role_primary(self):
        p = BrandPalette()
        assert p.resolve(SemanticColorRole.PRIMARY) == p.primary

    def test_resolve_semantic_role_accent(self):
        p = BrandPalette()
        assert p.resolve(SemanticColorRole.ACCENT) == p.accent

    def test_resolve_semantic_role_success(self):
        p = BrandPalette()
        assert p.resolve(SemanticColorRole.SUCCESS) == p.success

    # ------------------------------------------------------------------
    # Inheritance
    # ------------------------------------------------------------------
    def test_inherit_from_parent_fills_defaults(self):
        parent = BrandPalette(accent=0xABCDEF)
        child = BrandPalette()  # all defaults
        merged = child.inherit_from(parent)
        assert merged.accent == 0xABCDEF  # parent fills the gap

    def test_inherit_from_child_overrides_parent(self):
        parent = BrandPalette(accent=0xABCDEF)
        child = BrandPalette(accent=0x123456)  # child explicitly differs
        merged = child.inherit_from(parent)
        assert merged.accent == 0x123456  # child wins

    def test_inherit_does_not_mutate_parent(self):
        parent = BrandPalette(accent=0xABCDEF)
        child = BrandPalette()
        _ = child.inherit_from(parent)
        assert parent.accent == 0xABCDEF  # unchanged

    def test_inherit_does_not_mutate_child(self):
        parent = BrandPalette(accent=0xABCDEF)
        child = BrandPalette()
        original_child_accent = child.accent
        _ = child.inherit_from(parent)
        assert child.accent == original_child_accent  # unchanged

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------
    def test_yuna_dark_factory(self):
        p = BrandPalette.yuna_dark()
        assert p.primary == 0x5865F2
        assert p.surface == 0x2B2D31

    def test_yuna_light_factory(self):
        p = BrandPalette.yuna_light()
        assert p.surface == 0xFFFFFF

    def test_high_contrast_factory(self):
        p = BrandPalette.high_contrast()
        assert p.primary == 0xFFFFFF
        assert p.danger == 0xFF0000


class TestSemanticColorRole:
    def test_all_roles_defined(self):
        roles = {r.value for r in SemanticColorRole}
        assert "primary" in roles
        assert "danger" in roles
        assert "surface" in roles
        assert "accent" in roles

    def test_is_string_enum(self):
        assert SemanticColorRole.PRIMARY == "primary"


# ===========================================================================
# BrandTypography
# ===========================================================================


class TestBrandTypography:
    def test_default_font_family(self):
        t = BrandTypography()
        assert "Inter" in t.font_family

    def test_has_mono_font_family(self):
        t = BrandTypography()
        assert t.font_family_mono != ""

    def test_heading_hierarchy_h1_to_h4(self):
        t = BrandTypography()
        assert t.font_size_h1 != t.font_size_h2
        assert t.font_size_h2 != t.font_size_h3
        assert t.font_size_h3 != t.font_size_h4

    def test_to_css_dict_includes_headings(self):
        css = BrandTypography().to_css_dict()
        for h in ["--font-size-h1", "--font-size-h2", "--font-size-h3", "--font-size-h4"]:
            assert h in css

    def test_to_css_dict_includes_line_heights(self):
        css = BrandTypography().to_css_dict()
        assert "--line-height-normal" in css
        assert "--line-height-tight" in css
        assert "--line-height-loose" in css

    def test_to_css_dict_includes_letter_spacing(self):
        css = BrandTypography().to_css_dict()
        assert "--letter-spacing-normal" in css
        assert "--letter-spacing-wide" in css

    def test_to_css_dict_includes_weights(self):
        css = BrandTypography().to_css_dict()
        assert "--font-weight-semibold" in css
        assert "--font-weight-extrabold" in css

    def test_css_dict_values_are_strings(self):
        css = BrandTypography().to_css_dict()
        for k, v in css.items():
            assert isinstance(v, str), f"{k} should be a string"


# ===========================================================================
# AnimationToken
# ===========================================================================


class TestAnimationToken:
    def test_default_durations(self):
        a = AnimationToken()
        assert a.duration_fast == "150ms"
        assert a.duration_normal == "250ms"

    def test_composite_transition_fast(self):
        a = AnimationToken()
        assert a.duration_fast in a.transition_fast
        assert a.easing_ease_out in a.transition_fast

    def test_composite_transition_normal(self):
        a = AnimationToken()
        assert a.duration_normal in a.transition_normal

    def test_composite_transition_bounce(self):
        a = AnimationToken()
        assert a.easing_bounce in a.transition_bounce

    def test_to_css_dict_includes_durations(self):
        css = AnimationToken().to_css_dict()
        assert "--duration-fast" in css
        assert "--duration-normal" in css
        assert "--duration-slow" in css

    def test_to_css_dict_includes_easings(self):
        css = AnimationToken().to_css_dict()
        assert "--easing-ease-out" in css
        assert "--easing-bounce" in css
        assert "--easing-spring" in css

    def test_to_css_dict_includes_composites(self):
        css = AnimationToken().to_css_dict()
        assert "--transition-fast" in css
        assert "--transition-normal" in css
        assert "--transition-bounce" in css

    def test_css_values_are_non_empty_strings(self):
        css = AnimationToken().to_css_dict()
        for k, v in css.items():
            assert isinstance(v, str) and v, f"{k} has empty value"


# ===========================================================================
# BrandProfile
# ===========================================================================


class TestBrandProfile:
    # ------------------------------------------------------------------
    # Construction and validation
    # ------------------------------------------------------------------
    def test_valid_construction(self):
        bp = BrandProfile(name="test", display_name="Test Brand", accent_color=0x5865F2)
        assert bp.name == "test"

    def test_empty_name_raises(self):
        with pytest.raises(InvalidBrandProfileError):
            BrandProfile(name="", display_name="Test", accent_color=0x5865F2)

    def test_blank_name_raises(self):
        with pytest.raises(InvalidBrandProfileError):
            BrandProfile(name="   ", display_name="Test", accent_color=0x5865F2)

    def test_empty_display_name_raises(self):
        with pytest.raises(InvalidBrandProfileError):
            BrandProfile(name="test", display_name="", accent_color=0x5865F2)

    def test_accent_color_too_high_raises(self):
        with pytest.raises(InvalidBrandProfileError):
            BrandProfile(name="t", display_name="T", accent_color=0x1000000)

    def test_accent_color_negative_raises(self):
        with pytest.raises(InvalidBrandProfileError):
            BrandProfile(name="t", display_name="T", accent_color=-1)

    def test_accent_color_zero_valid(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x000000)
        assert bp.accent_color == 0

    def test_accent_color_max_valid(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0xFFFFFF)
        assert bp.accent_color == 0xFFFFFF

    def test_optional_fields_default_to_none(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2)
        assert bp.logo_url is None
        assert bp.banner_url is None
        assert bp.tagline is None

    def test_dark_mode_default(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2)
        assert bp.dark_mode is True

    # ------------------------------------------------------------------
    # Multi-target rendering
    # ------------------------------------------------------------------
    def test_render_embed_contains_title(self):
        bp = BrandProfile(name="t", display_name="My Brand", accent_color=0x5865F2)
        embed = bp.render_embed()
        assert embed["title"] == "My Brand"

    def test_render_embed_contains_accent_color(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0xABCDEF)
        assert bp.render_embed()["color"] == 0xABCDEF

    def test_render_embed_contains_tagline_as_description(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2, tagline="Hello!")
        assert bp.render_embed()["description"] == "Hello!"

    def test_render_embed_no_description_without_tagline(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2)
        assert "description" not in bp.render_embed()

    def test_render_embed_contains_thumbnail_when_logo_set(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2,
                          logo_url="https://example.com/logo.png")
        assert "thumbnail" in bp.render_embed()

    def test_render_html_contains_display_name(self):
        bp = BrandProfile(name="t", display_name="My Brand", accent_color=0x5865F2)
        assert "My Brand" in bp.render_html()

    def test_render_html_contains_accent_hex(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2)
        assert "#5865F2" in bp.render_html()

    def test_render_html_contains_logo_img_when_set(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2,
                          logo_url="https://example.com/logo.png")
        assert "<img" in bp.render_html()

    def test_render_html_no_img_without_logo(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2)
        assert "<img" not in bp.render_html()

    def test_render_text_contains_name(self):
        bp = BrandProfile(name="test_brand", display_name="Test", accent_color=0x5865F2)
        assert "test_brand" in bp.render_text()

    def test_render_text_contains_hex(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2)
        assert "#5865F2" in bp.render_text()

    def test_render_text_contains_tagline(self):
        bp = BrandProfile(name="t", display_name="T", accent_color=0x5865F2,
                          tagline="My tagline")
        assert "My tagline" in bp.render_text()

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------
    def test_yuna_dark_factory(self):
        bp = BrandProfile.yuna_dark()
        assert bp.name == "yuna_dark"
        assert bp.dark_mode is True

    def test_yuna_light_factory(self):
        bp = BrandProfile.yuna_light()
        assert bp.dark_mode is False

    def test_high_contrast_factory(self):
        bp = BrandProfile.high_contrast()
        assert bp.accent_color == 0xFFFFFF


# ===========================================================================
# BrandAssetRegistry
# ===========================================================================


class TestBrandAssetRegistry:
    def _registry(self) -> BrandAssetRegistry:
        return BrandAssetRegistry()

    # ------------------------------------------------------------------
    # Registration & retrieval
    # ------------------------------------------------------------------
    def test_register_and_get(self):
        r = self._registry()
        r.register(None, "logo", "https://example.com/logo.png")
        assert r.get(None, "logo") == "https://example.com/logo.png"

    def test_get_returns_none_when_not_set(self):
        r = self._registry()
        assert r.get(None, "logo") is None

    def test_get_or_default_guild_specific(self):
        r = self._registry()
        r.register(42, "logo", "https://guild.com/logo.png")
        assert r.get_or_default(42, "logo") == "https://guild.com/logo.png"

    def test_get_or_default_falls_back_to_global(self):
        r = self._registry()
        r.register(None, "logo", "https://global.com/logo.png")
        assert r.get_or_default(99, "logo") == "https://global.com/logo.png"

    def test_guild_override_takes_precedence_over_global(self):
        r = self._registry()
        r.register(None, "logo", "https://global.com/logo.png")
        r.register(42, "logo", "https://guild.com/logo.png")
        assert r.get_or_default(42, "logo") == "https://guild.com/logo.png"

    def test_get_or_default_returns_fallback_when_nothing_set(self):
        r = self._registry()
        result = r.get_or_default(99, "logo", fallback="https://default.com/logo.png")
        assert result == "https://default.com/logo.png"

    def test_get_or_default_returns_none_fallback(self):
        r = self._registry()
        assert r.get_or_default(99, "logo") is None

    def test_require_raises_when_not_found(self):
        r = self._registry()
        with pytest.raises(AssetNotFoundError):
            r.require(99, "logo")

    def test_require_returns_url_when_found(self):
        r = self._registry()
        r.register(None, "logo", "https://example.com/logo.png")
        assert r.require(99, "logo") == "https://example.com/logo.png"

    def test_invalid_asset_type_raises(self):
        r = self._registry()
        with pytest.raises(ValueError):
            r.register(None, "wallpaper", "https://example.com/wp.png")

    def test_all_asset_types_valid(self):
        r = self._registry()
        for atype in ["logo", "banner", "icon", "thumbnail", "favicon"]:
            r.register(None, atype, f"https://example.com/{atype}.png")
            assert r.get(None, atype) is not None

    # ------------------------------------------------------------------
    # Removal
    # ------------------------------------------------------------------
    def test_remove_specific_asset(self):
        r = self._registry()
        r.register(None, "logo", "https://example.com/logo.png")
        r.remove(None, "logo")
        assert r.get(None, "logo") is None

    def test_remove_is_noop_when_not_present(self):
        r = self._registry()
        r.remove(None, "logo")  # no error

    def test_clear_removes_all_guild_assets(self):
        r = self._registry()
        r.register(42, "logo", "https://example.com/logo.png")
        r.register(42, "banner", "https://example.com/banner.png")
        r.clear(42)
        assert r.get(42, "logo") is None
        assert r.get(42, "banner") is None

    def test_clear_does_not_remove_other_guilds(self):
        r = self._registry()
        r.register(42, "logo", "https://example.com/logo.png")
        r.register(99, "logo", "https://other.com/logo.png")
        r.clear(42)
        assert r.get(99, "logo") == "https://other.com/logo.png"

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------
    def test_list_assets_includes_global_defaults(self):
        r = self._registry()
        r.register(None, "logo", "https://global.com/logo.png")
        assets = r.list_assets(99)
        assert assets.get("logo") == "https://global.com/logo.png"

    def test_list_assets_guild_overrides_global(self):
        r = self._registry()
        r.register(None, "logo", "https://global.com/logo.png")
        r.register(42, "logo", "https://guild.com/logo.png")
        assets = r.list_assets(42)
        assert assets["logo"] == "https://guild.com/logo.png"

    def test_len(self):
        r = self._registry()
        r.register(None, "logo", "url")
        r.register(42, "banner", "url2")
        assert len(r) == 2


# ===========================================================================
# ThemeRegistry
# ===========================================================================


class TestThemeRegistryDefaults:
    def test_list_themes_includes_builtins(self):
        themes = ThemeRegistry.list_themes()
        assert "yuna_dark" in themes
        assert "yuna_light" in themes
        assert "high_contrast" in themes

    def test_resolve_config_returns_theme_config(self):
        config = ThemeRegistry.resolve_config()
        assert isinstance(config, ThemeConfig)

    def test_resolve_brand_returns_brand_profile(self):
        brand = ThemeRegistry.resolve_brand()
        assert isinstance(brand, BrandProfile)

    def test_resolve_palette_returns_brand_palette(self):
        palette = ThemeRegistry.resolve_palette()
        assert isinstance(palette, BrandPalette)


class TestThemeRegistryRegistration:
    def test_register_custom_theme(self):
        config = _make_config("custom_theme")
        ThemeRegistry.register(config)
        assert "custom_theme" in ThemeRegistry.list_themes()

    def test_register_syncs_to_theme_engine(self):
        config = _make_config("synced_theme")
        ThemeRegistry.register(config)
        t = ThemeEngine.get_theme("synced_theme")
        assert t.name == "synced_theme"

    def test_register_with_brand_profile(self):
        config = _make_config("branded_theme")
        brand = BrandProfile(name="branded_theme", display_name="Branded", accent_color=0xABCDEF)
        ThemeRegistry.register(config, brand=brand)
        node = ThemeRegistry.get_node("branded_theme")
        assert node.brand.display_name == "Branded"

    def test_register_with_custom_palette(self):
        config = _make_config("pal_theme")
        palette = BrandPalette(accent=0x112233)
        ThemeRegistry.register(config, palette=palette)
        node = ThemeRegistry.get_node("pal_theme")
        assert node.palette.accent == 0x112233


class TestThemeRegistryInheritance:
    def test_child_inherits_parent_palette_defaults(self):
        parent_config = _make_config("parent_theme")
        parent_palette = BrandPalette(accent=0xAABBCC)
        ThemeRegistry.register(parent_config, palette=parent_palette)

        child_config = _make_config("child_theme")
        child_palette = BrandPalette()  # all defaults – should inherit parent accent
        ThemeRegistry.register(child_config, palette=child_palette, parent="parent_theme")

        child_node = ThemeRegistry.get_node("child_theme")
        assert child_node.palette.accent == 0xAABBCC

    def test_child_overrides_parent_token(self):
        parent_config = _make_config("parent2")
        parent_palette = BrandPalette(accent=0xAABBCC)
        ThemeRegistry.register(parent_config, palette=parent_palette)

        child_config = _make_config("child2")
        child_palette = BrandPalette(accent=0x112233)  # explicit override
        ThemeRegistry.register(child_config, palette=child_palette, parent="parent2")

        child_node = ThemeRegistry.get_node("child2")
        assert child_node.palette.accent == 0x112233

    def test_unregistered_parent_raises(self):
        config = _make_config("orphan")
        with pytest.raises(ThemeInheritanceError):
            ThemeRegistry.register(config, parent="nonexistent_parent")

    def test_self_inheritance_raises(self):
        config = _make_config("self_theme")
        ThemeRegistry.register(config)
        config2 = _make_config("self_theme")
        with pytest.raises(ThemeInheritanceError):
            ThemeRegistry.register(config2, parent="self_theme")


class TestThemeRegistryGuildOverrides:
    def test_set_and_get_guild_theme(self):
        ThemeRegistry.set_guild_theme(12345, "yuna_light")
        assert ThemeRegistry.get_guild_theme_name(12345) == "yuna_light"

    def test_resolve_uses_guild_override(self):
        ThemeRegistry.set_guild_theme(12345, "yuna_light")
        brand = ThemeRegistry.resolve_brand(guild_id=12345)
        assert brand.name == "yuna_light"

    def test_resolve_without_guild_uses_global(self):
        brand = ThemeRegistry.resolve_brand(guild_id=None)
        assert brand.name == "yuna_dark"  # default active theme

    def test_resolve_unset_guild_uses_global(self):
        brand = ThemeRegistry.resolve_brand(guild_id=99999)
        assert brand.name == "yuna_dark"

    def test_clear_guild_theme(self):
        ThemeRegistry.set_guild_theme(12345, "yuna_light")
        ThemeRegistry.clear_guild_theme(12345)
        assert ThemeRegistry.get_guild_theme_name(12345) is None

    def test_set_guild_theme_invalid_raises(self):
        from ui.foundation.exceptions import InvalidThemeError
        with pytest.raises(InvalidThemeError):
            ThemeRegistry.set_guild_theme(99, "does_not_exist")


class TestThemeRegistryCssManifest:
    def test_export_css_manifest_returns_root_block(self):
        css = ThemeRegistry.export_css_manifest("yuna_dark")
        assert ":root {" in css
        assert "}" in css

    def test_css_manifest_includes_color_tokens(self):
        css = ThemeRegistry.export_css_manifest("yuna_dark")
        assert "--color-primary" in css
        assert "--color-surface" in css

    def test_css_manifest_includes_typography_tokens(self):
        css = ThemeRegistry.export_css_manifest("yuna_dark")
        assert "--font-family" in css
        assert "--font-size-h1" in css

    def test_css_manifest_includes_spacing_tokens(self):
        css = ThemeRegistry.export_css_manifest("yuna_dark")
        assert "--spacing-md" in css

    def test_css_manifest_includes_animation_tokens(self):
        css = ThemeRegistry.export_css_manifest("yuna_dark")
        assert "--duration-fast" in css
        assert "--easing-bounce" in css

    def test_css_manifest_invalid_theme_raises(self):
        from ui.foundation.exceptions import InvalidThemeError
        with pytest.raises(InvalidThemeError):
            ThemeRegistry.export_css_manifest("nonexistent_theme")

    def test_css_manifest_defaults_to_active_theme(self):
        css = ThemeRegistry.export_css_manifest()
        assert ":root {" in css


class TestThemeRegistryAssetManifest:
    def test_export_asset_manifest_returns_dict(self):
        manifest = ThemeRegistry.export_asset_manifest()
        assert isinstance(manifest, dict)

    def test_asset_manifest_contains_all_types(self):
        manifest = ThemeRegistry.export_asset_manifest()
        for atype in ["logo", "banner", "icon", "thumbnail", "favicon"]:
            assert atype in manifest

    def test_asset_manifest_reflects_registered_assets(self):
        ThemeRegistry.assets().register(None, "logo", "https://example.com/logo.png")
        manifest = ThemeRegistry.export_asset_manifest()
        assert manifest["logo"] == "https://example.com/logo.png"

    def test_asset_manifest_guild_override(self):
        ThemeRegistry.assets().register(None, "logo", "https://global.com/logo.png")
        ThemeRegistry.assets().register(42, "logo", "https://guild.com/logo.png")
        manifest = ThemeRegistry.export_asset_manifest(guild_id=42)
        assert manifest["logo"] == "https://guild.com/logo.png"


class TestThemeRegistryIntrospection:
    def test_get_node_valid(self):
        node = ThemeRegistry.get_node("yuna_dark")
        assert node.config.name == "yuna_dark"

    def test_get_node_invalid_raises(self):
        from ui.foundation.exceptions import InvalidThemeError
        with pytest.raises(InvalidThemeError):
            ThemeRegistry.get_node("does_not_exist")


# ===========================================================================
# Backward Compatibility – ThemeEngine still works
# ===========================================================================


class TestBackwardCompatibility:
    def test_theme_engine_get_active_theme_returns_config(self):
        # ThemeRegistry._init_defaults populates ThemeEngine
        ThemeRegistry.list_themes()  # triggers init
        config = ThemeEngine.get_active_theme()
        assert isinstance(config, ThemeConfig)

    def test_theme_engine_register_still_works(self):
        extra = _make_config("extra_theme")
        ThemeEngine.register_theme(extra)
        t = ThemeEngine.get_theme("extra_theme")
        assert t.name == "extra_theme"

    def test_embed_builder_get_active_theme_unaffected(self):
        """EmbedBuilder uses ThemeEngine.get_active_theme() – must not break."""
        from ui.embeds.builder import EmbedBuilder
        ThemeRegistry.list_themes()  # ensure init
        embed = EmbedBuilder().set_title("Test").set_description("Check").render_embed()
        assert "color" in embed

    def test_form_builder_get_active_theme_unaffected(self):
        """FormBuilder uses ThemeEngine.get_active_theme() – must not break."""
        from ui.forms.builder import FormBuilder
        ThemeRegistry.list_themes()
        form = FormBuilder(title="Test", custom_id="test:compat")
        form.add_string_field("key", "Label")
        result = form.render_embed()
        assert "color" in result


# ===========================================================================
# Integration – EmbedBuilder consuming theme palette
# ===========================================================================


class TestEmbedBuilderThemeIntegration:
    def test_embed_uses_theme_primary_color(self):
        from ui.embeds.builder import EmbedBuilder
        ThemeRegistry.list_themes()
        embed = EmbedBuilder().set_title("Themed Embed").render_embed()
        active_theme = ThemeEngine.get_active_theme()
        assert embed["color"] == active_theme.colors.primary

    def test_embed_with_custom_color_ignores_theme(self):
        from ui.embeds.builder import EmbedBuilder
        embed = EmbedBuilder().set_title("T").set_color(0xFF0000).render_embed()
        assert embed["color"] == 0xFF0000


# ===========================================================================
# Integration – Paginator with themed footer
# ===========================================================================


class TestPaginatorThemeIntegration:
    def _make_simple_page(self, label: str):
        from ui.pagination.renderable import RenderablePage

        class SimplePage(RenderablePage):
            def __init__(self, lbl: str):
                self.lbl = lbl
            def render_embed(self):
                return {"label": self.lbl}
            def render_html(self):
                return f"<div>{self.lbl}</div>"
            def render_text(self):
                return self.lbl

        return SimplePage(label)

    def test_paginator_works_after_theme_registry_init(self):
        from ui.pagination.paginator import Paginator
        ThemeRegistry.list_themes()  # triggers init
        pages = [self._make_simple_page(f"Page {i}") for i in range(1, 4)]
        p = Paginator(pages)
        assert p.total_pages() == 3

    def test_paginated_view_footer_uses_page_numbers(self):
        from ui.pagination.paginator import Paginator
        from ui.pagination.views import PaginatedView
        ThemeRegistry.list_themes()
        pages = [self._make_simple_page(f"P{i}") for i in range(1, 4)]
        view = PaginatedView(Paginator(pages))
        view.goto(2)
        footer = view.render_embed()["footer"]
        assert "2" in footer
        assert "3" in footer
