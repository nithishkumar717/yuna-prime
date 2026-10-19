"""Brand asset registry for per-guild and global brand assets.

``BrandAssetRegistry`` is an in-memory store mapping (guild_id, asset_type)
pairs to URLs. When a guild-specific asset is absent, it falls back to the
global default registered under ``guild_id=None``.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .exceptions import AssetNotFoundError

# Supported asset type identifiers
ASSET_TYPES = frozenset({"logo", "banner", "icon", "thumbnail", "favicon"})

# Key is (guild_id_or_None, asset_type)
_AssetKey = Tuple[Optional[int], str]


class BrandAssetRegistry:
    """Centralized store for per-guild brand asset URLs.

    Guild-specific assets take precedence over global defaults.
    Global defaults are registered with ``guild_id=None``.

    Usage
    -----
    registry = BrandAssetRegistry()
    registry.register(None, "logo", "https://example.com/yuna_logo.png")   # global
    registry.register(123456789, "banner", "https://example.com/banner.png")  # guild

    url = registry.get_or_default(123456789, "logo")  # falls back to global logo
    """

    def __init__(self) -> None:
        self._assets: Dict[_AssetKey, str] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(
        self,
        guild_id: Optional[int],
        asset_type: str,
        url: str,
    ) -> None:
        """Register a brand asset URL.

        Parameters
        ----------
        guild_id:
            Guild snowflake ID, or ``None`` for the global default.
        asset_type:
            One of: ``logo``, ``banner``, ``icon``, ``thumbnail``, ``favicon``.
        url:
            Publicly accessible asset URL.
        """
        self._validate_type(asset_type)
        self._assets[(guild_id, asset_type)] = url

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def get(self, guild_id: Optional[int], asset_type: str) -> Optional[str]:
        """Return the asset URL for the given guild and type, or ``None``."""
        self._validate_type(asset_type)
        return self._assets.get((guild_id, asset_type))

    def get_or_default(
        self,
        guild_id: Optional[int],
        asset_type: str,
        fallback: Optional[str] = None,
    ) -> Optional[str]:
        """Return the guild-specific asset, falling back to the global default.

        Returns ``fallback`` (default ``None``) if neither is set.
        """
        self._validate_type(asset_type)
        # Guild-specific lookup first.
        url = self._assets.get((guild_id, asset_type))
        if url is not None:
            return url
        # Fall back to global default.
        url = self._assets.get((None, asset_type))
        return url if url is not None else fallback

    def require(self, guild_id: Optional[int], asset_type: str) -> str:
        """Return the resolved asset URL or raise ``AssetNotFoundError``."""
        url = self.get_or_default(guild_id, asset_type)
        if url is None:
            scope = f"guild {guild_id}" if guild_id else "global"
            raise AssetNotFoundError(
                f"Asset '{asset_type}' not found for {scope}."
            )
        return url

    # ------------------------------------------------------------------
    # Removal
    # ------------------------------------------------------------------
    def remove(self, guild_id: Optional[int], asset_type: str) -> None:
        """Remove a specific asset entry. No-op if the entry doesn't exist."""
        self._assets.pop((guild_id, asset_type), None)

    def clear(self, guild_id: Optional[int]) -> None:
        """Remove all assets for the given ``guild_id`` (or global if ``None``)."""
        keys = [k for k in self._assets if k[0] == guild_id]
        for k in keys:
            del self._assets[k]

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------
    def list_assets(self, guild_id: Optional[int]) -> Dict[str, str]:
        """Return a dict of ``{asset_type: url}`` for the given guild.

        Guild-specific assets are listed first; global defaults fill any gaps.
        """
        result: Dict[str, str] = {}
        # Start from globals.
        for (gid, atype), url in self._assets.items():
            if gid is None:
                result[atype] = url
        # Override with guild-specific values.
        for (gid, atype), url in self._assets.items():
            if gid == guild_id:
                result[atype] = url
        return result

    def __len__(self) -> int:
        return len(self._assets)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_type(asset_type: str) -> None:
        if asset_type not in ASSET_TYPES:
            raise ValueError(
                f"Unknown asset type '{asset_type}'. "
                f"Valid types: {sorted(ASSET_TYPES)}"
            )
