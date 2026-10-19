"""ThemeRegistry — central authority for theme management.

Responsibilities
----------------
- Theme registration with optional parent inheritance
- Per-guild theme overrides (in-memory; upgradeable to MongoDB later)
- Active theme resolution (guild-scoped or global)
- Full CSS variable manifest generation
- Brand asset manifest generation
- Backward-compatible delegation to the existing ``ThemeEngine``

Layering
--------
ThemeRegistry (richer management layer)
        │
        ▼ delegates active theme to
ThemeEngine (lightweight runtime accessor in ui.foundation)
        │
        ▼ consumed by
EmbedBuilder / FormBuilder / Paginator / PaginatedView
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ui.foundation.theme import ThemeConfig, ThemeEngine
from ui.foundation.colors import ColorPalette

from .palette import BrandPalette
from .typography import BrandTypography
from .animations import AnimationToken
from .branding import BrandProfile
from .assets import BrandAssetRegistry
from .exceptions import ThemeInheritanceError


class _ThemeNode:
    """Internal representation of a registered theme with its lineage."""

    def __init__(
        self,
        config: ThemeConfig,
        brand: Optional[BrandProfile] = None,
        palette: Optional[BrandPalette] = None,
        typography: Optional[BrandTypography] = None,
        animation: Optional[AnimationToken] = None,
        parent_name: Optional[str] = None,
    ):
        self.config = config
        self.brand = brand or BrandProfile.yuna_dark()
        self.palette = palette or BrandPalette.yuna_dark()
        self.typography = typography or BrandTypography()
        self.animation = animation or AnimationToken()
        self.parent_name = parent_name


class ThemeRegistry:
    """Central management authority for all theme and branding concerns.

    This is a class-level singleton following the same pattern as the existing
    ``ThemeEngine``. It wraps ``ThemeEngine`` so all v7.0–v7.3 consumers
    continue to work unchanged.
    """

    _nodes: Dict[str, _ThemeNode] = {}
    _guild_overrides: Dict[int, str] = {}
    _asset_registry: BrandAssetRegistry = BrandAssetRegistry()
    _initialised: bool = False

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    @classmethod
    def _init_defaults(cls) -> None:
        if cls._initialised:
            return
        cls._initialised = True

        # Register the three built-in themes, mirroring ThemeEngine defaults.
        dark_config = ThemeConfig(
            name="yuna_dark",
            colors=ColorPalette(
                primary=0x5865F2,
                secondary=0x4E5D94,
                neutral_dark=0x1E1F22,
                neutral_light=0xF2F3F5,
            ),
        )
        light_config = ThemeConfig(
            name="yuna_light",
            colors=ColorPalette(
                primary=0x5865F2,
                secondary=0x7289DA,
                neutral_dark=0xF2F3F5,
                neutral_light=0x1E1F22,
            ),
        )
        contrast_config = ThemeConfig(
            name="high_contrast",
            colors=ColorPalette(
                primary=0xFFFFFF,
                secondary=0x000000,
                success=0x00FF00,
                warning=0xFFFF00,
                danger=0xFF0000,
            ),
        )

        cls._nodes["yuna_dark"] = _ThemeNode(
            config=dark_config,
            brand=BrandProfile.yuna_dark(),
            palette=BrandPalette.yuna_dark(),
        )
        cls._nodes["yuna_light"] = _ThemeNode(
            config=light_config,
            brand=BrandProfile.yuna_light(),
            palette=BrandPalette.yuna_light(),
        )
        cls._nodes["high_contrast"] = _ThemeNode(
            config=contrast_config,
            brand=BrandProfile.high_contrast(),
            palette=BrandPalette.high_contrast(),
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    @classmethod
    def register(
        cls,
        config: ThemeConfig,
        brand: Optional[BrandProfile] = None,
        palette: Optional[BrandPalette] = None,
        typography: Optional[BrandTypography] = None,
        animation: Optional[AnimationToken] = None,
        parent: Optional[str] = None,
    ) -> None:
        """Register a theme with optional parent inheritance.

        If ``parent`` is specified the child theme inherits all parent tokens;
        child values take precedence (palette ``inherit_from`` semantics).

        Parameters
        ----------
        config: ThemeConfig
            Foundation ``ThemeConfig`` (consumed by ``ThemeEngine`` consumers).
        brand: BrandProfile, optional
            Visual identity descriptor for this theme.
        palette: BrandPalette, optional
            Extended color palette. If ``parent`` is set, inheritance is applied.
        typography: BrandTypography, optional
            Extended typography scale.
        animation: AnimationToken, optional
            HTML dashboard animation tokens.
        parent: str, optional
            Name of the parent theme. Must already be registered.
        """
        cls._init_defaults()

        name = config.name.lower()

        # Resolve palette inheritance.
        resolved_palette = palette or BrandPalette()
        if parent:
            parent_name = parent.lower()
            if parent_name not in cls._nodes:
                raise ThemeInheritanceError(
                    f"Parent theme '{parent_name}' is not registered."
                )
            if parent_name == name:
                raise ThemeInheritanceError(
                    f"Theme '{name}' cannot inherit from itself."
                )
            parent_node = cls._nodes[parent_name]
            resolved_palette = resolved_palette.inherit_from(parent_node.palette)

        cls._nodes[name] = _ThemeNode(
            config=config,
            brand=brand,
            palette=resolved_palette,
            typography=typography,
            animation=animation,
            parent_name=parent,
        )

        # Keep ThemeEngine in sync so all v7.x consumers work unchanged.
        ThemeEngine.register_theme(config)

    # ------------------------------------------------------------------
    # Per-guild overrides
    # ------------------------------------------------------------------
    @classmethod
    def set_guild_theme(cls, guild_id: int, theme_name: str) -> None:
        """Associate a guild with a specific registered theme."""
        cls._init_defaults()
        name = theme_name.lower()
        if name not in cls._nodes:
            from ui.foundation.exceptions import InvalidThemeError
            raise InvalidThemeError(f"Theme '{theme_name}' is not registered.")
        cls._guild_overrides[guild_id] = name

    @classmethod
    def get_guild_theme_name(cls, guild_id: int) -> Optional[str]:
        """Return the registered theme name for a guild, or ``None``."""
        return cls._guild_overrides.get(guild_id)

    @classmethod
    def clear_guild_theme(cls, guild_id: int) -> None:
        """Remove the per-guild override; the guild will fall back to global."""
        cls._guild_overrides.pop(guild_id, None)

    # ------------------------------------------------------------------
    # Active theme resolution
    # ------------------------------------------------------------------
    @classmethod
    def resolve(cls, guild_id: Optional[int] = None) -> _ThemeNode:
        """Return the resolved ``_ThemeNode`` for the given scope.

        Resolution order:
        1. Guild-specific override (if ``guild_id`` is provided and set)
        2. Global active theme (from ``ThemeEngine``)
        """
        cls._init_defaults()
        name: Optional[str] = None
        if guild_id is not None:
            name = cls._guild_overrides.get(guild_id)
        if name is None:
            name = ThemeEngine.get_active_theme().name.lower()
        return cls._nodes[name]

    @classmethod
    def resolve_config(cls, guild_id: Optional[int] = None) -> ThemeConfig:
        """Return the ``ThemeConfig`` for the resolved scope."""
        return cls.resolve(guild_id).config

    @classmethod
    def resolve_brand(cls, guild_id: Optional[int] = None) -> BrandProfile:
        """Return the ``BrandProfile`` for the resolved scope."""
        return cls.resolve(guild_id).brand

    @classmethod
    def resolve_palette(cls, guild_id: Optional[int] = None) -> BrandPalette:
        """Return the ``BrandPalette`` for the resolved scope."""
        return cls.resolve(guild_id).palette

    # ------------------------------------------------------------------
    # Manifest generation
    # ------------------------------------------------------------------
    @classmethod
    def export_css_manifest(cls, theme_name: Optional[str] = None) -> str:
        """Return a complete ``:root {}`` CSS block for the given theme.

        Includes color, typography, spacing, and animation tokens.
        Falls back to the global active theme if ``theme_name`` is ``None``.
        """
        cls._init_defaults()
        name = (theme_name or ThemeEngine.get_active_theme().name).lower()
        if name not in cls._nodes:
            from ui.foundation.exceptions import InvalidThemeError
            raise InvalidThemeError(f"Theme '{name}' is not registered.")

        node = cls._nodes[name]
        tokens: Dict[str, str] = {}
        tokens.update(node.palette.to_css_dict())
        tokens.update(node.typography.to_css_dict())
        tokens.update(node.config.spacing.to_css_dict())
        tokens.update(node.animation.to_css_dict())

        rules = "\n".join(f"  {k}: {v};" for k, v in tokens.items())
        return f":root {{\n{rules}\n}}"

    @classmethod
    def export_asset_manifest(cls, guild_id: Optional[int] = None) -> Dict[str, Optional[str]]:
        """Return a dict of ``{asset_type: url}`` for the given guild.

        Uses the shared ``BrandAssetRegistry`` with guild → global fallback.
        """
        from .assets import ASSET_TYPES
        return {
            atype: cls._asset_registry.get_or_default(guild_id, atype)
            for atype in sorted(ASSET_TYPES)
        }

    # ------------------------------------------------------------------
    # Asset registry access
    # ------------------------------------------------------------------
    @classmethod
    def assets(cls) -> BrandAssetRegistry:
        """Return the shared ``BrandAssetRegistry``."""
        return cls._asset_registry

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @classmethod
    def list_themes(cls) -> List[str]:
        """Return names of all registered themes."""
        cls._init_defaults()
        return list(cls._nodes.keys())

    @classmethod
    def get_node(cls, name: str) -> _ThemeNode:
        """Return the internal ``_ThemeNode`` for a theme name."""
        cls._init_defaults()
        name = name.lower()
        if name not in cls._nodes:
            from ui.foundation.exceptions import InvalidThemeError
            raise InvalidThemeError(f"Theme '{name}' is not registered.")
        return cls._nodes[name]

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------
    @classmethod
    def reset(cls) -> None:
        """Reset all registry state. Intended for use in tests only."""
        cls._nodes.clear()
        cls._guild_overrides.clear()
        cls._asset_registry = BrandAssetRegistry()
        cls._initialised = False
        ThemeEngine.clear()
