"""
utils/embed_theme.py
Enforces strict 4-color palette across all Discord embeds:
- Red: 0xFF0000 / 0xED4245 (Danger, Bans, Kicks, Timeouts, Errors, Alerts)
- Golden Yellow: 0xD4AF37 / 0xF1C40F / 0xFEE75C (Success, Warnings, Stars, Gold, Leveling)
- Black: 0x000000 (Moderation logs, Stealth, Minimalist Dark)
- Grey: 0x2B2D31 (General info, Help, SaaS panels, Stats, Containers)
"""

import discord
from typing import Any, Optional, Union

COLOR_RED = 0xFF0000
COLOR_GOLDEN_YELLOW = 0xD4AF37
COLOR_BLACK = 0x000000
COLOR_GREY = 0x2B2D31

RED_VARIANTS = {0xFF0000, 0xED4245, 0xDC143C, 0xE74C3C, 0xFF0055, 0xFF0044, 0x8B0000}
GOLDEN_YELLOW_VARIANTS = {0xD4AF37, 0xF1C40F, 0xFEE75C, 0xD6B15E, 0xF5CD73, 0xF39C12, 0xFFAA00, 0xFFA500, 0xE67E22, 0xF59E0B}
BLACK_VARIANTS = {0x000000, 0x000001, 0x010101, 0x0C0606}
GREY_VARIANTS = {0x2B2D31, 0x2F3136, 0x808080, 0x888888, 0x95A5A6, 0x949BA4, 0x5C5C5C, 0x232428, 0x2E3035}


def normalize_embed_color(val: Any) -> Any:
    """
    Normalizes any embed color to one of the 4 allowed palette colors:
    - Red
    - Golden Yellow
    - Black
    - Grey
    """
    if val is None:
        return None

    is_color_obj = isinstance(val, discord.Color)
    if is_color_obj:
        raw = val.value
    elif isinstance(val, int):
        raw = val
    else:
        try:
            raw = int(val)
        except Exception:
            return discord.Color(COLOR_GREY) if is_color_obj else COLOR_GREY

    # If already one of the allowed categories, preserve it
    if (raw in RED_VARIANTS or
        raw in GOLDEN_YELLOW_VARIANTS or
        raw in BLACK_VARIANTS or
        raw in GREY_VARIANTS):
        norm = raw
    else:
        r = (raw >> 16) & 0xFF
        g = (raw >> 8) & 0xFF
        b = raw & 0xFF

        # Greens / Success -> Golden Yellow
        if g > r and g > b:
            norm = COLOR_GOLDEN_YELLOW
        # Reds / Crimson -> Red
        elif r > 180 and g < 100 and b < 100:
            norm = COLOR_RED
        # Dark shades -> Black or Grey
        elif r < 15 and g < 15 and b < 15:
            norm = COLOR_BLACK
        # All other (Pinks, Blues, Purples, Cyan, Pastels) -> Grey
        else:
            norm = COLOR_GREY

    return discord.Color(norm) if is_color_obj else norm


_HOOK_INSTALLED = False


def install_embed_theme_hook():
    """Globally hooks discord.Embed so all embeds conform to the 4-color palette."""
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED:
        return
    _HOOK_INSTALLED = True

    # 1. Hook discord.Embed.__init__
    _orig_init = discord.Embed.__init__

    def _themed_init(self, *args, **kwargs):
        if 'color' in kwargs and kwargs['color'] is not None:
            kwargs['color'] = normalize_embed_color(kwargs['color'])
        elif 'colour' in kwargs and kwargs['colour'] is not None:
            kwargs['colour'] = normalize_embed_color(kwargs['colour'])
        _orig_init(self, *args, **kwargs)
        if hasattr(self, '_colour') and self._colour is not None:
            norm = normalize_embed_color(self._colour)
            self._colour = norm if isinstance(norm, discord.Colour) else discord.Colour(norm)

    discord.Embed.__init__ = _themed_init

    # 2. Hook discord.Embed.color / colour property setter
    _orig_color_prop = discord.Embed.color

    def _get_color(self):
        return _orig_color_prop.fget(self)

    def _set_color(self, value):
        if value is not None:
            value = normalize_embed_color(value)
        _orig_color_prop.fset(self, value)

    discord.Embed.color = property(_get_color, _set_color)
    discord.Embed.colour = discord.Embed.color

    # 3. Hook discord.Embed.to_dict
    _orig_to_dict = discord.Embed.to_dict

    def _themed_to_dict(self):
        d = _orig_to_dict(self)
        if 'color' in d and d['color'] is not None:
            d['color'] = normalize_embed_color(d['color'])
        return d

    discord.Embed.to_dict = _themed_to_dict


# Auto-install upon module import
install_embed_theme_hook()
