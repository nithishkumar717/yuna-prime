"""
YUNA Welcomer Engine — Production-Grade 8-Layer GIF Welcome Card Renderer.

Architecture:
- Static clean template loaded ONCE and cached in memory
- Every animation frame starts from a fresh .copy() of the cached template
- All dynamic text is composited via transparent RGBA overlay layers
- NO draw.rectangle / draw.rounded_rectangle for dynamic content backgrounds
- Fixed coordinate system derived from pixel-level template analysis
- Anti-aliased circular avatar masking with zero green-screen artifacts
"""

from __future__ import annotations
import os
import io
import math
import asyncio
import ipaddress
import socket
from functools import lru_cache
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageSequence

import unicodedata

# ═══════════════════════════════════════════════════════════════
# Font Resolution Engine (Universal Unicode, Emoji & CJK Support)
# ═══════════════════════════════════════════════════════════════
PRIMARY_FONTS = [
    os.path.join(os.path.dirname(__file__), "arialbd.ttf"),
    os.path.join(os.path.dirname(__file__), "HelveticaNeuBold.ttf"),
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
]

CJK_FONTS = [
    ("C:/Windows/Fonts/msyh.ttc", 0),         # Microsoft YaHei (Chinese)
    ("C:/Windows/Fonts/msgothic.ttc", 0),     # MS Gothic (Japanese)
    ("C:/Windows/Fonts/malgun.ttf", 0),       # Malgun Gothic (Korean)
    ("C:/Windows/Fonts/simhei.ttf", 0),       # SimHei
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
]

EMOJI_FONTS = [
    "C:/Windows/Fonts/seguiemj.ttf",          # Segoe UI Emoji
    "C:/Windows/Fonts/seguisym.ttf",          # Segoe UI Symbol
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/unifont/unifont.ttf"
]

BUNDLED_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

CARD_FONT_FILES = {
    "DISCORD": [
        os.path.join(BUNDLED_FONTS_DIR, "PlusJakartaSans-Bold.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "segoeuib.ttf"),
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "PLUS_JAKARTA": [
        os.path.join(BUNDLED_FONTS_DIR, "PlusJakartaSans-Bold.ttf"),
        os.path.join(os.path.dirname(__file__), "HelveticaNeuBold.ttf"),
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "INTER": [
        os.path.join(BUNDLED_FONTS_DIR, "Inter.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "PlusJakartaSans-Bold.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "segoeuib.ttf"),
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "ROBOTO": [
        os.path.join(BUNDLED_FONTS_DIR, "Roboto.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "arialbd.ttf"),
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "MONO": [
        os.path.join(BUNDLED_FONTS_DIR, "JetBrainsMono-Bold.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "consolab.ttf"),
        "C:/Windows/Fonts/consolab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
    ],
    "GEORGIA": [
        os.path.join(BUNDLED_FONTS_DIR, "georgiab.ttf"),
        "C:/Windows/Fonts/georgiab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
    ],
    "CAMBRIA": [
        os.path.join(BUNDLED_FONTS_DIR, "calibrib.ttf"),
        "C:/Windows/Fonts/cambriab.ttf",
        "C:/Windows/Fonts/georgiab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
    ],
    "IMPACT": [
        os.path.join(BUNDLED_FONTS_DIR, "impact.ttf"),
        "C:/Windows/Fonts/impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "VERDANA": [
        os.path.join(BUNDLED_FONTS_DIR, "verdanab.ttf"),
        "C:/Windows/Fonts/verdanab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "TAHOMA": [
        os.path.join(BUNDLED_FONTS_DIR, "tahomabd.ttf"),
        "C:/Windows/Fonts/tahomabd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "CALIBRI": [
        os.path.join(BUNDLED_FONTS_DIR, "calibrib.ttf"),
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "COMIC": [
        os.path.join(BUNDLED_FONTS_DIR, "comicbd.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "comic.ttf"),
        "C:/Windows/Fonts/comicbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "BAHNSCHRIFT": [
        os.path.join(BUNDLED_FONTS_DIR, "bahnschrift.ttf"),
        "C:/Windows/Fonts/bahnschrift.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "CANDARA": [
        os.path.join(BUNDLED_FONTS_DIR, "Candarab.ttf"),
        "C:/Windows/Fonts/Candarab.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "MONTSERRAT": [
        os.path.join(BUNDLED_FONTS_DIR, "Montserrat-Bold.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "PlusJakartaSans-Bold.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "bahnschrift.ttf"),
        "C:/Windows/Fonts/bahnschrift.ttf",
        os.path.join(BUNDLED_FONTS_DIR, "Inter.ttf"),
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "POPPINS": [
        os.path.join(BUNDLED_FONTS_DIR, "Poppins-Bold.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "Candarab.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "PlusJakartaSans-Bold.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "Inter.ttf"),
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "OSWALD": [
        os.path.join(BUNDLED_FONTS_DIR, "bahnschrift.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "impact.ttf"),
        "C:/Windows/Fonts/impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"
    ],
    "BEBAS_NEUE": [
        os.path.join(BUNDLED_FONTS_DIR, "bahnschrift.ttf"),
        os.path.join(BUNDLED_FONTS_DIR, "impact.ttf"),
        "C:/Windows/Fonts/impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"
    ],
}

_LOADED_FONTS: Dict[Tuple[str, int, int], Optional[ImageFont.FreeTypeFont]] = {}

def _get_font_object(entry: Any, size: int) -> Optional[ImageFont.FreeTypeFont]:
    path, idx = entry if isinstance(entry, tuple) else (entry, 0)
    key = (path, idx, size)
    if key not in _LOADED_FONTS:
        if os.path.exists(path):
            try:
                f_obj = ImageFont.truetype(path, size, index=idx)
                if hasattr(f_obj, "set_variation_by_name"):
                    try:
                        f_obj.set_variation_by_name("Bold")
                    except Exception:
                        pass
                _LOADED_FONTS[key] = f_obj
            except Exception:
                _LOADED_FONTS[key] = None
        else:
            _LOADED_FONTS[key] = None
    return _LOADED_FONTS[key]

def _is_emoji_or_symbol(char: str) -> bool:
    cp = ord(char)
    if (0x1F300 <= cp <= 0x1F9FF) or (0x2600 <= cp <= 0x27BF) or (0x1F600 <= cp <= 0x1F64F) or (0x1F680 <= cp <= 0x1F6FF) or (0x2300 <= cp <= 0x23FF):
        return True
    cat = unicodedata.category(char)
    return cat in ('So', 'Sk')

def _is_cjk_char(char: str) -> bool:
    cp = ord(char)
    return (0x4E00 <= cp <= 0x9FFF) or (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF) or (0xAC00 <= cp <= 0xD7AF) or (0x3130 <= cp <= 0x318F)

def _get_best_font_for_char(char: str, size: int) -> ImageFont.FreeTypeFont:
    if _is_emoji_or_symbol(char):
        pool = EMOJI_FONTS + PRIMARY_FONTS + CJK_FONTS
    elif _is_cjk_char(char):
        pool = CJK_FONTS + PRIMARY_FONTS + EMOJI_FONTS
    else:
        pool = PRIMARY_FONTS + CJK_FONTS + EMOJI_FONTS

    for entry in pool:
        f = _get_font_object(entry, size)
        if f is not None:
            return f

    return ImageFont.load_default()

def _prepare_unicode_text(text: str) -> str:
    """Normalizes mathematical script, fraktur, gothic, and high-codepoint styled unicode letters to standard characters."""
    res = []
    for c in text:
        if ord(c) > 0xFFFF and not _is_emoji_or_symbol(c):
            norm = unicodedata.normalize('NFKC', c)
            res.append(norm if norm != c else c)
        else:
            res.append(c)
    return "".join(res)

def _resolve_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for path in PRIMARY_FONTS:
        if isinstance(path, str) and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def fit_text_to_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box_x: int,
    box_y: int,
    box_width: int,
    box_height: int,
    max_font_size: int,
    min_font_size: int = 10,
    fill: Tuple[int, ...] = (255, 255, 255),
    bold: bool = True,
    font_name: Optional[str] = None
) -> None:
    """
    Renders any Discord username or string with full support for all fonts, emojis,
    gothic/styled scripts, CJK, and Unicode characters cleanly inside a bounding box.
    """
    clean_text = _prepare_unicode_text(text)
    font_size = max_font_size

    def _resolve_char_font(ch: str, sz: int) -> ImageFont.FreeTypeFont:
        if font_name:
            return _card_font_for_char(font_name, ch, sz)
        return _get_best_font_for_char(ch, sz)

    # Auto-fit font size down if text exceeds bounds
    while font_size > min_font_size:
        total_w = 0
        max_h = 0
        for char in clean_text:
            f = _resolve_char_font(char, font_size)
            bbox = draw.textbbox((0, 0), char, font=f)
            total_w += (bbox[2] - bbox[0])
            max_h = max(max_h, bbox[3] - bbox[1])

        if total_w <= box_width and max_h <= box_height:
            break
        font_size -= 1

    # Measure character metrics for exact placement
    total_w = 0
    max_h = 0
    char_metrics = []
    for char in clean_text:
        f = _resolve_char_font(char, font_size)
        bbox = draw.textbbox((0, 0), char, font=f)
        cw = bbox[2] - bbox[0]
        ch = bbox[3] - bbox[1]
        char_metrics.append((char, f, cw, ch, bbox[0], bbox[1]))
        total_w += cw
        max_h = max(max_h, ch)

    cx = box_x + (box_width - total_w) // 2
    cy = box_y + (box_height - max_h) // 2

    first_f = char_metrics[0][1] if char_metrics else None
    if first_f is not None and all(m[1] == first_f for m in char_metrics):
        draw.text((cx, cy), clean_text, fill=fill, font=first_f)
    else:
        cur_x = cx
        for char, f, cw, ch, xoff, yoff in char_metrics:
            draw.text((cur_x, cy), char, fill=fill, font=f)
            cur_x += max(cw, 1)


# ═══════════════════════════════════════════════════════════════
# Asset Directories
# ═══════════════════════════════════════════════════════════════
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "welcome_templates")
TEMPLATE_CLEAN_PATH = os.path.join(ASSETS_DIR, "card_template_clean.png")
TEMPLATE_ORIG_PATH = os.path.join(ASSETS_DIR, "card_template.png")


# ═══════════════════════════════════════════════════════════════
# Fixed Coordinate Configuration (1024x576)
#
# Derived from pixel-level analysis of the production template:
#   - USERNAME PANEL: gold borders at Y~271 (top) and Y~326 (bottom)
#     Interior dark area: X 448-696, Y 284-312
#     Person icon ends at X=523
#     Text box: right of icon to panel right edge
#
#   - BOTTOM PANELS: gold borders at Y~343 (top) and Y~413 (bottom)
#     Left (MEMBER):  X 414-620, interior Y 352-400
#       Group icon ends at X=423
#     Right (INVITER): X 650-822, interior Y 355-400
#       Link icon ends at X=704
#
#   - AVATAR: circle centered at (248, 230), radius ~119
# ═══════════════════════════════════════════════════════════════
TEMPLATE_CONFIG: Dict[str, Any] = {
    "dimensions": (1024, 576),

    "avatar": {
        "center": (248, 230),
        "radius": 119,
        "diameter": 238
    },

    # Username text box: right of person icon inside the username panel
    # Panel interior spans X 448-696, Y 284-312 (height ~28px)
    # Person icon ends at X=523, so text starts at X=530
    "username": {
        "box_x": 550,
        "box_y": 282,
        "box_width": 140,       # 550 to 690
        "box_height": 34,       # 282 to 316
        "max_font": 22,
        "min_font": 11,
    },

    # Member count: inside left bottom panel
    # Panel interior: X 414-620, Y 352-400
    # Group icon ends at X=423, so text starts at X=435
    # Split vertically: label "MEMBER" in top half, count "#NNN" in bottom half
    "member_count": {
        "label_box_x": 435,
        "label_box_y": 352,
        "label_box_width": 175,     # 435 to 610
        "label_box_height": 22,     # 352 to 374
        "val_box_x": 435,
        "val_box_y": 374,
        "val_box_width": 175,       # 435 to 610
        "val_box_height": 32,       # 374 to 406
        "max_font": 20,
        "min_font": 11,
    },

    # Inviter name: inside right bottom panel
    # Panel interior: X 650-822, Y 355-400
    # Link icon ends at X=704, so text starts at X=715
    # Split vertically: label "INVITED BY" in top half, name in bottom half
    "inviter": {
        "label_box_x": 715,
        "label_box_y": 352,
        "label_box_width": 100,     # 715 to 815
        "label_box_height": 22,     # 352 to 374
        "val_box_x": 715,
        "val_box_y": 374,
        "val_box_width": 100,       # 715 to 815
        "val_box_height": 32,       # 374 to 406
        "max_font": 16,
        "min_font": 9,
    },

    # Header "WELCOME TO" (upper) + {SERVER_NAME} (below, above username panel)
    "header_welcome": {
        "w_box_x": 414,
        "w_box_y": 188,
        "w_box_width": 408,
        "w_box_height": 34,
        "w_max_font": 28,
        "w_min_font": 14,

        "s_box_x": 414,
        "s_box_y": 226,
        "s_box_width": 408,
        "s_box_height": 38,
        "s_max_font": 30,
        "s_min_font": 14,
    },

    "colors": {
        "accent": (240, 195, 100),
        "accent_glow": (255, 230, 160),
        "text_primary": (255, 255, 255),
        "text_secondary": (200, 205, 215),
        "text_gold": (245, 205, 115)
    }
}

TEMPLATE_CONFIGS: Dict[str, Dict[str, Any]] = {"default": TEMPLATE_CONFIG}
TEMPLATE_ALIASES: Dict[str, str] = {
    "celestial": "default",
    "grand_temple": "default",
    "temple": "default",
    "galaxy": "default",
    "sakura": "default",
    "ocean": "default",
    "dragon": "default"
}


# ═══════════════════════════════════════════════════════════════
# Static Template Caching
# ═══════════════════════════════════════════════════════════════
_CACHED_BASE_TEMPLATE: Optional[Image.Image] = None
_CACHED_BG_PALETTE: Optional[List[int]] = None


def get_clean_static_template() -> Image.Image:
    """
    Loads and caches the pristine static template.
    The cached image has:
      - Avatar area inpainted (purple/green sample removed)
      - No placeholder text
      - All static artwork preserved (gold borders, icons, lighting, marble)
    Returns a fresh .copy() every time — never the cached original.
    """
    global _CACHED_BASE_TEMPLATE, _CACHED_BG_PALETTE
    if _CACHED_BASE_TEMPLATE is None:
        raw_img = None
        for path in [TEMPLATE_CLEAN_PATH, TEMPLATE_ORIG_PATH]:
            if os.path.exists(path):
                try:
                    raw_img = Image.open(path).convert("RGBA")
                    if raw_img.size != (1024, 576):
                        raw_img = raw_img.resize((1024, 576), Image.LANCZOS)
                    break
                except Exception:
                    raw_img = None

        if raw_img is None:
            # Emergency fallback: generate a minimal dark template
            raw_img = Image.new("RGBA", (1024, 576), (15, 18, 26, 255))
            draw = ImageDraw.Draw(raw_img)
            draw.rounded_rectangle((30, 30, 994, 546), radius=20,
                                   fill=(24, 28, 40, 230),
                                   outline=(240, 195, 100, 180), width=2)

        # Inpaint the avatar circle area to remove sample avatar
        clean_img = raw_img.copy()
        draw = ImageDraw.Draw(clean_img)
        draw.ellipse((126, 108, 370, 352), fill=(12, 15, 22, 255))

        _CACHED_BASE_TEMPLATE = clean_img

        # Pre-compute background palette for GIF quantization
        bg_rgb = clean_img.convert("RGB")
        pal = bg_rgb.quantize(colors=160, method=Image.Quantize.MEDIANCUT).getpalette()
        _CACHED_BG_PALETTE = (pal or [])[:160 * 3]

    return _CACHED_BASE_TEMPLATE.copy()


def _is_public_https_url(url: str) -> bool:
    """Only fetch HTTPS images hosted on publicly routable addresses."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 443):
            return False
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(address[4][0].split("%", 1)[0]).is_global
            for address in addresses
        )
    except (OSError, ValueError):
        return False


class _PublicHTTPSRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_public_https_url(newurl):
            raise ValueError("Background image redirected to a non-public or non-HTTPS URL")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@lru_cache(maxsize=12)
def _load_custom_background(background_url: str) -> Optional[Image.Image]:
    """Fetch and cache a bounded, public HTTPS background image for greeting cards."""
    if not background_url or not _is_public_https_url(background_url):
        return None

    try:
        request = Request(
            background_url,
            headers={"User-Agent": "Yuna-Welcome-Card/1.0", "Accept": "image/*"}
        )
        opener = build_opener(_PublicHTTPSRedirectHandler())
        with opener.open(request, timeout=8) as response:
            if not response.headers.get_content_type().startswith("image/"):
                return None
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > 8 * 1024 * 1024:
                return None
            image_bytes = response.read(8 * 1024 * 1024 + 1)

        if len(image_bytes) > 8 * 1024 * 1024:
            return None

        with Image.open(io.BytesIO(image_bytes)) as source:
            if source.width * source.height > 20_000_000:
                return None
            return ImageOps.fit(
                source.convert("RGB"),
                (1024, 576),
                method=Image.LANCZOS
            )
    except Exception as exc:
        print(f"[WELCOME CARD] Custom background unavailable; using the default card: {exc}")
        return None


def _card_color(value: Any, fallback: Tuple[int, int, int]) -> Tuple[int, int, int]:
    try:
        return ImageColor.getrgb(str(value))[:3]
    except (TypeError, ValueError):
        return fallback


def _normalize_font_key(name: str) -> str:
    cleaned = str(name or "DISCORD").upper().strip().replace(" ", "_").replace("-", "_")
    alias_map = {
        "PLUS_JAKARTA_SANS": "PLUS_JAKARTA",
        "PLUSJAKARTASANS": "PLUS_JAKARTA",
        "JETBRAINS_MONO": "MONO",
        "JETBRAINS": "MONO",
        "CONSOLAS": "MONO",
        "COMIC_SANS": "COMIC",
        "COMIC_SANS_MS": "COMIC",
        "ARIAL": "ROBOTO",
        "HELVETICA": "DISCORD",
        "MONTSERRAT": "MONTSERRAT",
        "POPPINS": "POPPINS",
        "INTER": "INTER",
        "ROBOTO": "ROBOTO",
        "DISCORD": "DISCORD",
        "OSWALD": "OSWALD",
        "BEBAS": "BEBAS_NEUE",
        "BEBAS_NEUE": "BEBAS_NEUE",
    }
    return alias_map.get(cleaned, cleaned)


def _card_font_for_char(font_name: str, char: str, size: int) -> ImageFont.FreeTypeFont:
    if _is_emoji_or_symbol(char) or _is_cjk_char(char):
        return _get_best_font_for_char(char, size)
    norm_key = _normalize_font_key(font_name)
    for path in CARD_FONT_FILES.get(norm_key, []):
        font = _get_font_object(path, size)
        if font is not None:
            return font
    return _resolve_font(size, bold=True)


def _draw_centered_card_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    top: int,
    height: int,
    max_width: int,
    max_size: int,
    min_size: int,
    fill: Tuple[int, int, int],
    font_name: str,
    tracking: int = 0,
    center_x: int = 512,
    align_left: bool = False,
    align_right: bool = False
) -> None:
    clean_text = _prepare_unicode_text(str(text or "")).replace("\n", " ").strip()
    if not clean_text:
        return

    final_metrics = []
    final_total_width = 0
    final_max_height = 0

    for size in range(max_size, min_size - 1, -1):
        metrics = []
        total_width = 0
        max_height = 0
        for char in clean_text:
            font = _card_font_for_char(font_name, char, size)
            char_width = draw.textlength(char, font=font)
            bbox = draw.textbbox((0, 0), char, font=font)
            char_height = max(1, bbox[3] - bbox[1])
            metrics.append((char, font, char_width))
            total_width += char_width
            max_height = max(max_height, char_height)
        total_width += max(0, len(clean_text) - 1) * tracking
        if total_width <= max_width and max_height <= height:
            final_metrics = metrics
            final_total_width = total_width
            final_max_height = max_height
            break
        elif size == min_size:
            final_metrics = metrics
            final_total_width = total_width
            final_max_height = max_height

    if align_left:
        x = center_x - max_width // 2
    elif align_right:
        x = (center_x + max_width // 2) - final_total_width
    else:
        x = center_x - final_total_width // 2
    y = top + (height - final_max_height) // 2

    # If tracking == 0 and all characters use the primary font, render whole string for perfect kerning
    first_font = final_metrics[0][1] if final_metrics else None
    if tracking == 0 and first_font is not None and all(m[1] == first_font for m in final_metrics):
        draw.text((x, y), clean_text, fill=fill, font=first_font)
    else:
        cur_x = x
        for char, font, char_width in final_metrics:
            draw.text((cur_x, y), char, fill=fill, font=font)
            cur_x += char_width + tracking


@lru_cache(maxsize=32)
def _get_avatar_mask(size: int, shape: str) -> Image.Image:
    scale = 4
    scaled_size = size * scale
    mask = Image.new("L", (scaled_size, scaled_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    if shape == "square":
        mask_draw.rounded_rectangle(
            (0, 0, scaled_size - 1, scaled_size - 1),
            radius=size * scale // 5,
            fill=255
        )
    else:
        mask_draw.ellipse((0, 0, scaled_size - 1, scaled_size - 1), fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def _make_preview_avatar(avatar: Image.Image, size: int, shape: str) -> Image.Image:
    # Resize avatar once directly to target size with Lanczos for maximum sharpness (avoids double-resample blur)
    image = avatar.resize((size, size), Image.LANCZOS).convert("RGBA")
    # Apply subtle unsharp mask to restore crisp micro-contrast (eyes, hair, lines)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=100, threshold=2))
    mask = _get_avatar_mask(size, shape)
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(image, (0, 0), mask)
    return output


def _generate_preview_style_gif(
    avatar_input: Image.Image | bytes,
    username: str,
    member_count: int,
    background_url: Optional[str],
    card_style: Dict[str, Any],
    card_message: Optional[str],
    server_name: str = "Discord Server",
    frame_duration_ms: int = 180
) -> bytes:
    width, height = 1024, 576
    colors = card_style.get("cardColors") or {}
    if not isinstance(colors, dict):
        colors = {}

    circle_color = _card_color(
        colors.get("ring") or colors.get("circle") or card_style.get("avatarRingColor"),
        (88, 101, 242)
    )
    title_color = _card_color(colors.get("title") or card_style.get("titleColor"), (255, 255, 255))
    username_color = _card_color(colors.get("username") or card_style.get("usernameColor"), (236, 72, 153))
    message_color = _card_color(colors.get("message") or card_style.get("imageMessageColor"), (219, 222, 225))
    overlay_color = _card_color(
        card_style.get("overlayColor") or card_style.get("cardOverlayColor") or colors.get("overlay"),
        (0, 0, 0)
    )
    background_color = _card_color(
        card_style.get("backgroundColor") or colors.get("background"),
        (31, 32, 37)
    )

    raw_opacity = None
    for k in ("overlayOpacity", "cardOverlayOpacity", "overlay_opacity"):
        if k in card_style and card_style[k] is not None:
            raw_opacity = card_style[k]
            break
    if raw_opacity is not None:
        try:
            overlay_opacity = max(0, min(100, int(raw_opacity)))
        except (TypeError, ValueError):
            overlay_opacity = 0
    else:
        overlay_opacity = 0

    if not background_url:
        background_url = (
            card_style.get("cardBgUrl")
            or card_style.get("backgroundImageUrl")
            or card_style.get("backgroundUrl")
            or card_style.get("bgUrl")
        )

    background = _load_custom_background(background_url) if background_url else None
    raw_bg_opacity = card_style.get("bgOpacity")
    if background is not None and raw_bg_opacity is not None:
        try:
            bg_op = max(0, min(100, int(raw_bg_opacity)))
            if bg_op > 0:
                solid_bg = Image.new("RGB", (width, height), background_color)
                background = Image.blend(background, solid_bg, alpha=bg_op / 100.0)
        except (TypeError, ValueError):
            pass

    if background is None:
        background = Image.new("RGB", (width, height), background_color)
        gradient_draw = ImageDraw.Draw(background)
        for step in range(49):
            progress = step / 48
            color = tuple(
                int(background_color[channel] * (1 - progress) + (44, 45, 53)[channel] * progress)
                for channel in range(3)
            )
            rx = int(width * (0.96 - progress * 0.54))
            ry = int(height * (1.04 - progress * 0.65))
            gradient_draw.ellipse((width // 2 - rx, -ry // 2, width // 2 + rx, ry), fill=color)

    avatar_frames: List[Image.Image] = []
    avatar_durations: List[int] = []
    if isinstance(avatar_input, Image.Image):
        try:
            if getattr(avatar_input, "is_animated", False) and getattr(avatar_input, "n_frames", 1) > 1:
                for f in ImageSequence.Iterator(avatar_input):
                    avatar_frames.append(f.convert("RGBA"))
                    d = f.info.get("duration", 100) or 100
                    avatar_durations.append(max(20, min(1000, int(d))))
                    if len(avatar_frames) >= 120:
                        break
            else:
                avatar_frames.append(avatar_input.convert("RGBA"))
                avatar_durations.append(frame_duration_ms)
        except Exception:
            avatar_frames = [avatar_input.convert("RGBA")]
            avatar_durations = [frame_duration_ms]
    elif isinstance(avatar_input, (bytes, bytearray)) and len(avatar_input) > 0:
        try:
            with Image.open(io.BytesIO(avatar_input)) as av_src:
                if getattr(av_src, "is_animated", False) and getattr(av_src, "n_frames", 1) > 1:
                    for f in ImageSequence.Iterator(av_src):
                        avatar_frames.append(f.convert("RGBA"))
                        d = f.info.get("duration", 100) or 100
                        avatar_durations.append(max(20, min(1000, int(d))))
                        if len(avatar_frames) >= 120:
                            break
                else:
                    avatar_frames.append(av_src.convert("RGBA"))
                    avatar_durations.append(frame_duration_ms)
        except Exception:
            avatar_frames = [Image.new("RGBA", (256, 256), (90, 105, 180, 255))]
            avatar_durations = [frame_duration_ms]
    else:
        avatar_frames = [Image.new("RGBA", (256, 256), (90, 105, 180, 255))]
        avatar_durations = [frame_duration_ms]

    if not avatar_frames:
        avatar_frames = [Image.new("RGBA", (256, 256), (90, 105, 180, 255))]
        avatar_durations = [frame_duration_ms]

    avatar_image = avatar_frames[0]

    # Calculate total card frames and durations matching the avatar's full animation
    if len(avatar_frames) > 1:
        if len(avatar_frames) < 24:
            multiplier = math.ceil(24 / len(avatar_frames))
            num_card_frames = len(avatar_frames) * multiplier
        else:
            num_card_frames = len(avatar_frames)
        card_durations = [avatar_durations[i % len(avatar_durations)] for i in range(num_card_frames)]
    else:
        num_card_frames = 30
        card_durations = [max(120, frame_duration_ms)] * num_card_frames

    avatar_shape = str(card_style.get("cardAvatarShape") or card_style.get("avatarShape", "circle")).lower()
    card_font = str(card_style.get("cardFont", "DISCORD"))

    if card_message is not None and card_message != "":
        member_text = card_message
    elif "cardMessage" in card_style and card_style["cardMessage"] != "":
        member_text = card_style["cardMessage"]
    elif card_message == "" or card_style.get("cardMessage") == "":
        member_text = ""
    else:
        member_text = f"YOU ARE OUR {member_count:,}TH MEMBER"

    safe_username = str(username or "New Member").upper()

    card_layout = str(card_style.get("cardLayout") or card_style.get("cardTemplate", "classic")).lower().strip()
    custom_elements = card_style.get("customCanvasElements")
    is_custom = card_layout == "custom" and isinstance(custom_elements, list) and len(custom_elements) > 0

    layout_geometry = {
        "classic": {
            "has_avatar": True,
            "avatar_size": 170, "avatar_x": 427, "avatar_y": 80, "ring_size": 186,
            "text_center_x": 512, "text_width": 900,
            "align_left": False, "align_right": False,
            "title_top": 286, "username_top": 344, "message_top": 402,
            "title_size": 42, "username_size": 32, "message_size": 20,
            "title_height": 50, "username_height": 42, "message_height": 30,
            "title_tracking": 6, "username_tracking": 4, "message_tracking": 2,
            "panel": None,
        },
        "left": {
            # In dashboard: Avatar on LEFT, Text on RIGHT (align_left = True)
            "has_avatar": True,
            "avatar_size": 180, "avatar_x": 160, "avatar_y": 198, "ring_size": 198,
            "text_center_x": 656, "text_width": 540,
            "align_left": True, "align_right": False,
            "title_top": 195, "username_top": 252, "message_top": 306,
            "title_size": 44, "username_size": 34, "message_size": 20,
            "title_height": 52, "username_height": 44, "message_height": 30,
            "title_tracking": 4, "username_tracking": 4, "message_tracking": 1,
            "panel": None,
        },
        "right": {
            # In dashboard: Text on LEFT (align_right = True), Avatar on RIGHT
            "has_avatar": True,
            "avatar_size": 180, "avatar_x": 684, "avatar_y": 198, "ring_size": 198,
            "text_center_x": 368, "text_width": 540,
            "align_left": False, "align_right": True,
            "title_top": 195, "username_top": 252, "message_top": 306,
            "title_size": 44, "username_size": 34, "message_size": 20,
            "title_height": 52, "username_height": 44, "message_height": 30,
            "title_tracking": 4, "username_tracking": 4, "message_tracking": 1,
            "panel": None,
        },
        "text": {
            "has_avatar": False,
            "avatar_size": 0, "avatar_x": 0, "avatar_y": 0, "ring_size": 0,
            "text_center_x": 512, "text_width": 900,
            "align_left": False, "align_right": False,
            "title_top": 195, "username_top": 265, "message_top": 328,
            "title_size": 56, "username_size": 40, "message_size": 22,
            "title_height": 66, "username_height": 50, "message_height": 34,
            "title_tracking": 6, "username_tracking": 4, "message_tracking": 2,
            "panel": None,
        },
        "modern": {
            "has_avatar": True,
            "avatar_size": 170, "avatar_x": 120, "avatar_y": 203, "ring_size": 186,
            "text_center_x": 660, "text_width": 560,
            "align_left": True, "align_right": False,
            "title_top": 195, "username_top": 240, "message_top": 322,
            "title_size": 26, "username_size": 56, "message_size": 26,
            "title_height": 34, "username_height": 72, "message_height": 40,
            "title_tracking": 4, "username_tracking": 1, "message_tracking": 1,
            "panel": None,
        },
        "banner": {
            "has_avatar": True,
            "avatar_size": 170, "avatar_x": 115, "avatar_y": 203, "ring_size": 186,
            "text_center_x": 660, "text_width": 560,
            "align_left": True, "align_right": False,
            "title_top": 195, "username_top": 240, "message_top": 322,
            "title_size": 26, "username_size": 56, "message_size": 26,
            "title_height": 34, "username_height": 72, "message_height": 40,
            "title_tracking": 4, "username_tracking": 1, "message_tracking": 1,
            "panel": (60, 130, 964, 446),
        },
        "minimal": {
            "has_avatar": True,
            "avatar_size": 140, "avatar_x": 140, "avatar_y": 218, "ring_size": 154,
            "text_center_x": 650, "text_width": 520,
            "align_left": True, "align_right": False,
            "title_top": 215, "username_top": 252, "message_top": 320,
            "title_size": 22, "username_size": 48, "message_size": 22,
            "title_height": 30, "username_height": 62, "message_height": 34,
            "title_tracking": 3, "username_tracking": 1, "message_tracking": 1,
            "panel": (90, 175, 934, 401),
        },
    }

    if not is_custom and card_layout not in layout_geometry:
        card_layout = "classic"
    geom = layout_geometry.get(card_layout, layout_geometry["classic"])

    rendered_frames: List[Image.Image] = []

    if is_custom:
        sx = 1024.0 / 800.0
        sy = 576.0 / 450.0
        custom_avatar_cache: Dict[Tuple[int, str], List[Image.Image]] = {}
        for frame_index in range(num_card_frames):
            overlay_alpha = round(overlay_opacity * 2.55)
            if overlay_alpha > 0:
                frame = Image.alpha_composite(
                    background.convert("RGBA"),
                    Image.new("RGBA", (width, height), (*overlay_color, overlay_alpha))
                )
            else:
                frame = background.convert("RGBA")

            pulse = (math.sin((frame_index / num_card_frames) * 2 * math.pi) + 1) / 2
            glow_alpha = round(30 + pulse * 40)

            for el in custom_elements:
                if not isinstance(el, dict):
                    continue
                if el.get("visible") is False:
                    continue

                el_type = el.get("type")
                cx = float(el.get("x", 400)) * sx
                cy = float(el.get("y", 225)) * sy
                ew = float(el.get("width", 100)) * sx
                eh = float(el.get("height", 100)) * sy

                if el_type == "avatar":
                    size = max(32, int(round(min(ew, eh))))
                    ashape = str(el.get("avatarShape") or avatar_shape).lower()
                    cache_key = (size, ashape)
                    if cache_key not in custom_avatar_cache:
                        custom_avatar_cache[cache_key] = [
                            _make_preview_avatar(af, size, ashape)
                            for af in avatar_frames
                        ]
                    av_imgs = custom_avatar_cache[cache_key]
                    av_img = av_imgs[frame_index % len(av_imgs)]
                    r_col = _card_color(el.get("ringColor") or circle_color, circle_color)
                    r_width = max(2, int(round(float(el.get("ringWidth", 4)) * sx)))
                    r_size = size + r_width * 2
                    ax = round(cx - size / 2)
                    ay = round(cy - size / 2)
                    rx = round(cx - r_size / 2)
                    ry = round(cy - r_size / 2)

                    if el.get("ringGlow", True):
                        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                        glow_draw = ImageDraw.Draw(glow)
                        if ashape == "square":
                            glow_draw.rounded_rectangle(
                                (rx - 4, ry - 4, rx + r_size + 4, ry + r_size + 4),
                                radius=r_size // 5,
                                outline=(*r_col, glow_alpha),
                                width=18
                            )
                        else:
                            glow_draw.ellipse(
                                (rx - 4, ry - 4, rx + r_size + 4, ry + r_size + 4),
                                outline=(*r_col, glow_alpha),
                                width=18
                            )
                        frame = Image.alpha_composite(frame, glow.filter(ImageFilter.GaussianBlur(16)))

                    draw = ImageDraw.Draw(frame)
                    if ashape == "square":
                        draw.rounded_rectangle(
                            (rx, ry, rx + r_size, ry + r_size),
                            radius=r_size // 5,
                            fill=(*r_col, 255)
                        )
                    else:
                        draw.ellipse((rx, ry, rx + r_size, ry + r_size), fill=(*r_col, 255))
                    frame.alpha_composite(av_img, (ax, ay))

                elif el_type == "shape":
                    x0 = round(cx - ew / 2)
                    y0 = round(cy - eh / 2)
                    x1 = round(cx + ew / 2)
                    y1 = round(cy + eh / 2)
                    st = str(el.get("shapeType", "rectangle")).lower()
                    fill = _card_color(el.get("fillColor"), None)
                    stroke = _card_color(el.get("strokeColor"), None)
                    sw = max(1, int(round(float(el.get("strokeWidth", 1)) * sx)))
                    radius = int(round(float(el.get("borderRadiusNum", 12)) * sx))

                    s_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                    sd = ImageDraw.Draw(s_layer)
                    if st == "circle":
                        sd.ellipse((x0, y0, x1, y1), fill=(*fill, 255) if fill else None, outline=(*stroke, 255) if stroke else None, width=sw)
                    elif st == "divider":
                        sd.line((x0, round(cy), x1, round(cy)), fill=(*stroke, 255) if stroke else (*fill, 255) if fill else (255, 255, 255, 100), width=max(1, sw))
                    else:
                        sd.rounded_rectangle((x0, y0, x1, y1), radius=min(ew, eh) // 2 if st == "pill" else radius, fill=(*fill, 255) if fill else None, outline=(*stroke, 255) if stroke else None, width=sw)
                    frame = Image.alpha_composite(frame, s_layer)

                elif el_type == "text":
                    raw_t = str(el.get("text", ""))
                    t_resolved = (
                        raw_t
                        .replace("{user.mention}", f"@{safe_username}")
                        .replace("{user.name}", safe_username)
                        .replace("{user}", f"@{safe_username}")
                        .replace("{mention}", f"@{safe_username}")
                        .replace("{user_name}", safe_username)
                        .replace("{server.name}", server_name)
                        .replace("{server}", server_name)
                        .replace("{server_name}", server_name)
                        .replace("{member_count}", f"{member_count:,}")
                        .replace("{count}", str(member_count))
                    )
                    f_size = int(round(float(el.get("fontSize", 24)) * sx))
                    f_name = str(el.get("fontFamily") or card_font)
                    col = _card_color(el.get("color"), (255, 255, 255))
                    t_align = str(el.get("textAlign", "center")).lower()
                    l_spacing = int(round(float(el.get("letterSpacing", 0))))
                    top_y = round(cy - eh / 2)

                    draw = ImageDraw.Draw(frame)
                    # Shadow + text
                    _draw_centered_card_text(
                        draw, t_resolved,
                        top_y + 2, int(round(eh)),
                        int(round(ew)), f_size, max(10, f_size - 8),
                        (0, 0, 0), f_name,
                        tracking=l_spacing,
                        center_x=round(cx),
                        align_left=(t_align == "left"),
                        align_right=(t_align == "right")
                    )
                    _draw_centered_card_text(
                        draw, t_resolved,
                        top_y, int(round(eh)),
                        int(round(ew)), f_size, max(10, f_size - 8),
                        col, f_name,
                        tracking=l_spacing,
                        center_x=round(cx),
                        align_left=(t_align == "left"),
                        align_right=(t_align == "right")
                    )

            rendered_frames.append(frame.convert("RGB"))

    else:
        # Standard layouts (classic, left, right, text, modern, banner, minimal)
        has_avatar = geom.get("has_avatar", True)
        avatar_x, avatar_y, ring_x, ring_y, ring_size = 0, 0, 0, 0, 0
        processed_avatars: List[Image.Image] = []
        if has_avatar:
            avatar_size = geom["avatar_size"]
            processed_avatars = [
                _make_preview_avatar(af, avatar_size, avatar_shape)
                for af in avatar_frames
            ]
            avatar_x = geom["avatar_x"]
            avatar_y = geom["avatar_y"]
            ring_size = geom["ring_size"]
            ring_x = avatar_x - (ring_size - avatar_size) // 2
            ring_y = avatar_y - (ring_size - avatar_size) // 2

        for frame_index in range(num_card_frames):
            overlay_alpha = round(overlay_opacity * 2.55)
            if overlay_alpha > 0:
                frame = Image.alpha_composite(
                    background.convert("RGBA"),
                    Image.new("RGBA", (width, height), (*overlay_color, overlay_alpha))
                )
            else:
                frame = background.convert("RGBA")

            if geom.get("panel"):
                panel = geom["panel"]
                panel_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                panel_draw = ImageDraw.Draw(panel_layer)
                panel_draw.rounded_rectangle(
                    panel,
                    radius=28 if card_layout == "banner" else 84,
                    fill=(8, 10, 16, 132 if card_layout == "banner" else 156),
                    outline=(255, 255, 255, 42),
                    width=2
                )
                frame = Image.alpha_composite(frame, panel_layer)

            if has_avatar and processed_avatars:
                avatar = processed_avatars[frame_index % len(processed_avatars)]
                pulse = (math.sin((frame_index / num_card_frames) * 2 * math.pi) + 1) / 2
                glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                glow_draw = ImageDraw.Draw(glow)
                glow_alpha = round(30 + pulse * 40)
                if avatar_shape == "square":
                    glow_draw.rounded_rectangle(
                        (ring_x - 4, ring_y - 4, ring_x + ring_size + 4, ring_y + ring_size + 4),
                        radius=ring_size // 5,
                        outline=(*circle_color, glow_alpha),
                        width=18
                    )
                else:
                    glow_draw.ellipse(
                        (ring_x - 4, ring_y - 4, ring_x + ring_size + 4, ring_y + ring_size + 4),
                        outline=(*circle_color, glow_alpha),
                        width=18
                    )
                frame = Image.alpha_composite(frame, glow.filter(ImageFilter.GaussianBlur(16)))

                draw = ImageDraw.Draw(frame)
                if avatar_shape == "square":
                    draw.rounded_rectangle(
                        (ring_x, ring_y, ring_x + ring_size, ring_y + ring_size),
                        radius=ring_size // 5,
                        fill=(*circle_color, 255)
                    )
                else:
                    draw.ellipse((ring_x, ring_y, ring_x + ring_size, ring_y + ring_size), fill=(*circle_color, 255))
                frame.alpha_composite(avatar, (avatar_x, avatar_y))

            draw = ImageDraw.Draw(frame)
            align_left = geom.get("align_left", False)
            align_right = geom.get("align_right", False)

            for ox, oy, col in [(0, 3, (0, 0, 0)), (0, 1, (0, 0, 0)), (0, 0, None)]:
                t_col = col if col else title_color
                u_col = col if col else username_color
                m_col = col if col else message_color

                _draw_centered_card_text(
                    draw, "WELCOME",
                    geom["title_top"] + oy, geom["title_height"],
                    geom["text_width"], geom["title_size"], 16,
                    t_col, card_font,
                    tracking=geom["title_tracking"],
                    center_x=geom["text_center_x"] + ox,
                    align_left=align_left,
                    align_right=align_right
                )
                _draw_centered_card_text(
                    draw, safe_username,
                    geom["username_top"] + oy, geom["username_height"],
                    geom["text_width"], geom["username_size"], 20,
                    u_col, card_font,
                    tracking=geom["username_tracking"],
                    center_x=geom["text_center_x"] + ox,
                    align_left=align_left,
                    align_right=align_right
                )
                if member_text:
                    _draw_centered_card_text(
                        draw, member_text,
                        geom["message_top"] + oy, geom["message_height"],
                        geom["text_width"], geom["message_size"], 14,
                        m_col, card_font,
                        tracking=geom["message_tracking"],
                        center_x=geom["text_center_x"] + ox,
                        align_left=align_left,
                        align_right=align_right
                    )

            rendered_frames.append(frame.convert("RGB"))

    # Dedicated composite master palette:
    # 1. Avatar color budget: 76 colors (skin tone fidelity, hair, clothing)
    # 2. Background color budget: 164 colors (smooth gradients, rich wallpapers, zero banding)
    # 3. Fixed UI colors: 16 slots (gold ring, white text, accent highlights)
    # Total = 76 + 164 + 16 = 256 colors.
    if has_avatar and avatar_frames:
        av_colors = 76
        bg_colors = 164
        if len(avatar_frames) > 1:
            step = max(1, len(avatar_frames) // 5)
            sampled = [avatar_frames[i].convert("RGB") for i in range(0, len(avatar_frames), step)][:5]
            sw, sh = sampled[0].width, sampled[0].height
            strip = Image.new("RGB", (sw * len(sampled), sh))
            for idx, s_img in enumerate(sampled):
                strip.paste(s_img, (idx * sw, 0))
            avatar_pal_img = strip.quantize(colors=av_colors, method=Image.Quantize.MEDIANCUT)
        else:
            avatar_pal_img = avatar_image.convert("RGB").quantize(colors=av_colors, method=Image.Quantize.MEDIANCUT)
        avatar_pal = (avatar_pal_img.getpalette() or [])[:av_colors * 3]
    else:
        av_colors = 0
        bg_colors = 240
        avatar_pal = []

    # Sample background WITH overlay and panel applied so the palette matches actual on-screen composited pixels
    overlay_alpha = round(overlay_opacity * 2.55)
    if overlay_alpha > 0:
        bg_sample = Image.alpha_composite(
            background.convert("RGBA"),
            Image.new("RGBA", (width, height), (*overlay_color, overlay_alpha))
        )
    else:
        bg_sample = background.convert("RGBA")

    if geom.get("panel"):
        panel = geom["panel"]
        panel_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel_layer)
        panel_draw.rounded_rectangle(
            panel,
            radius=28 if card_layout == "banner" else 84,
            fill=(8, 10, 16, 132 if card_layout == "banner" else 156),
            outline=(255, 255, 255, 42),
            width=2
        )
        bg_sample = Image.alpha_composite(bg_sample, panel_layer)

    bg_rgb = bg_sample.convert("RGB")
    bg_pal_img = bg_rgb.quantize(colors=bg_colors, method=Image.Quantize.MEDIANCUT)
    bg_pal = (bg_pal_img.getpalette() or [])[:bg_colors * 3]

    # 3. Reserve 16 fixed slots for key UI accent & text colors
    fixed_colors = [
        circle_color,
        title_color,
        username_color,
        message_color,
        overlay_color,
        (255, 255, 255),
        (0, 0, 0),
        (128, 128, 128),
        (88, 101, 242),
        (236, 72, 153),
        (59, 165, 93),
        (237, 66, 69),
        (250, 166, 26),
        (255, 255, 255),
        (0, 0, 0),
        (31, 32, 37)
    ]
    ui_pal = []
    for c in fixed_colors[:16]:
        ui_pal.extend(c[:3])

    full_pal = avatar_pal + bg_pal + ui_pal
    if len(full_pal) < 768:
        full_pal.extend([0] * (768 - len(full_pal)))
    else:
        full_pal = full_pal[:768]

    palette = Image.new("P", (1, 1))
    palette.putpalette(full_pal)
    paletted_frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in rendered_frames]
    output = io.BytesIO()
    paletted_frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=paletted_frames[1:],
        duration=card_durations,
        loop=0,
        optimize=True
    )
    gif_bytes = output.getvalue()
    validate_welcome_gif(gif_bytes, min_expected_frames=1)
    return gif_bytes


# ═══════════════════════════════════════════════════════════════
# Circular Avatar (zero green-screen artifacts)
# ═══════════════════════════════════════════════════════════════
def create_circular_avatar(avatar_img: Image.Image, diameter: int) -> Image.Image:
    """
    Produces a perfectly circular avatar with anti-aliased edges.
    Uses a high-res mask downscaled for smooth edges (supersampled 4x).
    No green pixels, no square corners, no halo.
    """
    # Resize avatar once directly to target diameter for maximum sharpness
    avatar = avatar_img.resize((diameter, diameter), Image.LANCZOS).convert("RGBA")
    avatar = avatar.filter(ImageFilter.UnsharpMask(radius=1.0, percent=100, threshold=2))
    mask = _get_avatar_mask(diameter, "circle")

    # Apply mask
    output = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    output.paste(avatar, (0, 0), mask)
    return output


def ease_out_cubic(x: float) -> float:
    return 1.0 - math.pow(1.0 - max(0.0, min(1.0, x)), 3)


# ═══════════════════════════════════════════════════════════════
# GIF Validation
# ═══════════════════════════════════════════════════════════════
def validate_welcome_gif(gif_bytes: bytes, min_expected_frames: int = 20) -> None:
    """Programmatically verifies dimensions, frame count, and non-empty byte size."""
    if not gif_bytes or len(gif_bytes) < 1000:
        raise RuntimeError("Generated GIF bytes payload is empty or invalid.")

    with Image.open(io.BytesIO(gif_bytes)) as img:
        if img.size != (1024, 576):
            raise RuntimeError(f"Invalid GIF dimensions: {img.size}, expected (1024, 576).")

        frame_count = 0
        try:
            while True:
                frame_count += 1
                img.seek(img.tell() + 1)
        except EOFError:
            pass

        if frame_count < min_expected_frames:
            raise RuntimeError(f"Invalid GIF frame count: {frame_count}, expected >= {min_expected_frames}.")


# ═══════════════════════════════════════════════════════════════
# Main GIF Generator
# ═══════════════════════════════════════════════════════════════
def generate_welcome_gif(
    avatar_input: Image.Image | bytes,
    username: str = "New Member",
    member_count: int = 100,
    previous_count: Optional[int] = None,
    inviter_name: str = "Direct Join",
    server_name: str = "Discord Server",
    template_name: str = "default",
    total_frames: int = 36,
    frame_duration_ms: int = 180,
    background_url: Optional[str] = None,
    card_style: Optional[Dict[str, Any]] = None,
    card_message: Optional[str] = None
) -> bytes:
    """
    Renders a production-grade animated GIF welcome card.

    Frame isolation architecture:
      - Every frame starts from a fresh copy of the cached clean static template
      - All dynamic text is drawn on a transparent RGBA overlay
      - The overlay is alpha-composited onto the frame
      - NO rectangles/boxes are drawn behind dynamic text
      - Each dynamic field is rendered exactly ONCE per frame
    """
    if card_style is not None:
        return _generate_preview_style_gif(
            avatar_input=avatar_input,
            username=username,
            member_count=member_count,
            background_url=background_url,
            card_style=card_style,
            card_message=card_message,
            server_name=server_name,
            frame_duration_ms=frame_duration_ms
        )

    cfg = TEMPLATE_CONFIG
    base_static = get_clean_static_template()
    custom_background = _load_custom_background(background_url) if background_url else None
    if custom_background is not None:
        # Keep the card's gold artwork visible while making the saved background dominant.
        base_static = Image.blend(base_static.convert("RGB"), custom_background, alpha=0.72).convert("RGBA")
        bg_rgb = base_static.convert("RGB")
        bg_palette = bg_rgb.quantize(colors=160, method=Image.Quantize.MEDIANCUT).getpalette()
        bg_pal = (bg_palette or [])[:160 * 3]
    else:
        bg_pal = (_CACHED_BG_PALETTE or [])[:160 * 3]

    # Safe fallback values
    safe_user = username.strip() or "New Member"
    safe_inviter = inviter_name.strip() or "Direct Join"

    # ── Avatar Resolution ──
    avatar_frames: List[Image.Image] = []
    avatar_durations: List[int] = []
    if isinstance(avatar_input, (bytes, bytearray)) and len(avatar_input) > 0:
        try:
            with Image.open(io.BytesIO(avatar_input)) as av_src:
                if getattr(av_src, "is_animated", False) and getattr(av_src, "n_frames", 1) > 1:
                    for f in ImageSequence.Iterator(av_src):
                        avatar_frames.append(f.convert("RGBA"))
                        d = f.info.get("duration", 100) or 100
                        avatar_durations.append(max(20, min(1000, int(d))))
                        if len(avatar_frames) >= 120:
                            break
                else:
                    avatar_frames.append(av_src.convert("RGBA"))
                    avatar_durations.append(frame_duration_ms)
        except Exception:
            avatar_frames = []
    elif isinstance(avatar_input, Image.Image):
        try:
            if getattr(avatar_input, "is_animated", False) and getattr(avatar_input, "n_frames", 1) > 1:
                for f in ImageSequence.Iterator(avatar_input):
                    avatar_frames.append(f.convert("RGBA"))
                    d = f.info.get("duration", 100) or 100
                    avatar_durations.append(max(20, min(1000, int(d))))
                    if len(avatar_frames) >= 120:
                        break
            else:
                avatar_frames.append(avatar_input.convert("RGBA"))
                avatar_durations.append(frame_duration_ms)
        except Exception:
            avatar_frames = [avatar_input.convert("RGBA")]
            avatar_durations = [frame_duration_ms]

    if not avatar_frames:
        fallback = Image.new("RGBA", (256, 256), (20, 24, 32, 255))
        p_draw = ImageDraw.Draw(fallback)
        p_draw.ellipse((20, 20, 236, 236), fill=(240, 195, 100, 255))
        avatar_frames = [fallback]
        avatar_durations = [frame_duration_ms]

    radius = cfg["avatar"]["radius"]
    diameter = cfg["avatar"]["diameter"]
    circ_avatars = [create_circular_avatar(af, diameter) for af in avatar_frames]
    ax, ay = cfg["avatar"]["center"]

    # ── Palette for GIF quantization ──
    if len(avatar_frames) > 1:
        step = max(1, len(avatar_frames) // 5)
        sampled = [avatar_frames[i].convert("RGB") for i in range(0, len(avatar_frames), step)][:5]
        sw, sh = sampled[0].width, sampled[0].height
        strip = Image.new("RGB", (sw * len(sampled), sh))
        for idx, s_img in enumerate(sampled):
            strip.paste(s_img, (idx * sw, 0))
        av_quant = strip.quantize(colors=80, method=Image.Quantize.MEDIANCUT)
    else:
        av_rgb = avatar_frames[0].resize((diameter, diameter), Image.LANCZOS).convert("RGB")
        av_quant = av_rgb.quantize(colors=80, method=Image.Quantize.MEDIANCUT)
    av_pal = (av_quant.getpalette() or [])[:80 * 3]

    full_pal = av_pal + bg_pal
    if len(full_pal) < 768:
        full_pal += [0] * (768 - len(full_pal))
    else:
        full_pal = full_pal[:768]

    palette_ref = Image.new("P", (1, 1))
    palette_ref.putpalette(full_pal)

    # ── Member count animation setup ──
    if previous_count is not None and 0 < (member_count - previous_count) <= 40:
        start_count = previous_count
    else:
        start_count = max(1, member_count - 6)
    diff = member_count - start_count

    if len(avatar_frames) > 1:
        if len(avatar_frames) < 24:
            multiplier = math.ceil(24 / len(avatar_frames))
            n_frames = len(avatar_frames) * multiplier
        else:
            n_frames = len(avatar_frames)
        card_durations = [avatar_durations[i % len(avatar_durations)] for i in range(n_frames)]
    else:
        n_frames = total_frames
        card_durations = [frame_duration_ms] * n_frames

    anim_duration = max(5, n_frames - 8)
    rendered_frames = []

    # Pre-resolve label font
    font_label = _resolve_font(10, bold=True)

    for f in range(n_frames):
        # ══════════════════════════════════════════════════
        # FRAME ISOLATION: fresh copy of static template
        # ══════════════════════════════════════════════════
        frame = base_static.copy()

        # ── Layer 1: Avatar ──
        circ_avatar = circ_avatars[f % len(circ_avatars)]
        frame.paste(circ_avatar, (ax - radius, ay - radius), circ_avatar)

        # ── Layer 2: Animated Gold Ring ──
        ring_draw = ImageDraw.Draw(frame)
        pulse = math.sin((f / n_frames) * 2 * math.pi) * 2.0
        r_outer = radius + 1 + pulse
        glow_col = cfg["colors"]["accent_glow"] if (f >= anim_duration) else cfg["colors"]["accent"]
        ring_draw.ellipse(
            (ax - r_outer, ay - r_outer, ax + r_outer, ay + r_outer),
            outline=glow_col, width=3
        )

        # ══════════════════════════════════════════════════
        # DYNAMIC TEXT OVERLAY — transparent RGBA layer
        # No rectangles, no opaque backgrounds
        # ══════════════════════════════════════════════════
        text_layer = Image.new("RGBA", (1024, 576), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)

        # Dynamic render registry — each field exactly once
        rendered_dynamic = {"username": 0, "member_count": 0, "inviter": 0}

        # ── Layer 3: Username (inside username panel) ──
        u_cfg = cfg["username"]
        u_col = cfg["colors"]["accent_glow"] if (f % 6 < 3) else cfg["colors"]["text_primary"]
        fit_text_to_box(
            draw=text_draw,
            text=safe_user,
            box_x=u_cfg["box_x"],
            box_y=u_cfg["box_y"],
            box_width=u_cfg["box_width"],
            box_height=u_cfg["box_height"],
            max_font_size=u_cfg["max_font"],
            min_font_size=u_cfg["min_font"],
            fill=u_col,
            bold=True
        )
        rendered_dynamic["username"] += 1

        # ── Layer 4: Member Count ──
        mc_cfg = cfg["member_count"]

        # Static "MEMBER" label in top half of panel
        fit_text_to_box(
            draw=text_draw,
            text="MEMBER",
            box_x=mc_cfg["label_box_x"],
            box_y=mc_cfg["label_box_y"],
            box_width=mc_cfg["label_box_width"],
            box_height=mc_cfg["label_box_height"],
            max_font_size=10,
            min_font_size=8,
            fill=cfg["colors"]["text_secondary"],
            bold=True
        )

        # Animated count value
        if f < anim_duration:
            t = f / anim_duration
            cur_count = int(start_count + diff * ease_out_cubic(t))
            cnt_col = cfg["colors"]["text_primary"]
        else:
            cur_count = member_count
            cnt_col = cfg["colors"]["accent_glow"]

        fit_text_to_box(
            draw=text_draw,
            text=f"#{cur_count:,}",
            box_x=mc_cfg["val_box_x"],
            box_y=mc_cfg["val_box_y"],
            box_width=mc_cfg["val_box_width"],
            box_height=mc_cfg["val_box_height"],
            max_font_size=mc_cfg["max_font"],
            min_font_size=mc_cfg["min_font"],
            fill=cnt_col,
            bold=True
        )
        rendered_dynamic["member_count"] += 1

        # ── Layer 5: Inviter ──
        inv_cfg = cfg["inviter"]

        # Static "INVITED BY" label in top half of panel
        fit_text_to_box(
            draw=text_draw,
            text="INVITED BY",
            box_x=inv_cfg["label_box_x"],
            box_y=inv_cfg["label_box_y"],
            box_width=inv_cfg["label_box_width"],
            box_height=inv_cfg["label_box_height"],
            max_font_size=10,
            min_font_size=7,
            fill=cfg["colors"]["text_secondary"],
            bold=True
        )

        # Inviter name with fade-in
        fade_ratio = min(1.0, (f + 1) / 10.0)
        inv_col = tuple(
            int(c * fade_ratio + 50 * (1 - fade_ratio))
            for c in cfg["colors"]["text_primary"]
        )
        fit_text_to_box(
            draw=text_draw,
            text=safe_inviter,
            box_x=inv_cfg["val_box_x"],
            box_y=inv_cfg["val_box_y"],
            box_width=inv_cfg["val_box_width"],
            box_height=inv_cfg["val_box_height"],
            max_font_size=inv_cfg["max_font"],
            min_font_size=inv_cfg["min_font"],
            fill=inv_col,
            bold=True
        )
        rendered_dynamic["inviter"] += 1

        # ── Layer 6: Header Welcome (upper) + Server Name (below, above username panel) ──
        hw_cfg = cfg.get("header_welcome", {})

        # Upper Line: "WELCOME TO" (increased font size)
        fit_text_to_box(
            draw=text_draw,
            text="WELCOME TO",
            box_x=hw_cfg.get("w_box_x", 414),
            box_y=hw_cfg.get("w_box_y", 188),
            box_width=hw_cfg.get("w_box_width", 408),
            box_height=hw_cfg.get("w_box_height", 34),
            max_font_size=hw_cfg.get("w_max_font", 28),
            min_font_size=hw_cfg.get("w_min_font", 14),
            fill=cfg["colors"]["accent_glow"],
            bold=True
        )

        # Lower Line: Server Name (increased font size, gold)
        safe_server = server_name.strip() or "Discord Server"
        fit_text_to_box(
            draw=text_draw,
            text=safe_server.upper(),
            box_x=hw_cfg.get("s_box_x", 414),
            box_y=hw_cfg.get("s_box_y", 226),
            box_width=hw_cfg.get("s_box_width", 408),
            box_height=hw_cfg.get("s_box_height", 38),
            max_font_size=hw_cfg.get("s_max_font", 30),
            min_font_size=hw_cfg.get("s_min_font", 14),
            fill=cfg["colors"]["text_gold"],
            bold=True
        )

        # ══════════════════════════════════════════════════
        # Composite text overlay onto frame
        # ══════════════════════════════════════════════════
        frame = Image.alpha_composite(frame.convert("RGBA"), text_layer)

        rendered_frames.append(frame.convert("RGB"))

    # ═══════════════════════════════════════════════════════════
    # GIF Encoding with optimized palette
    # ═══════════════════════════════════════════════════════════
    out_buf = io.BytesIO()
    paletted_frames = [
        f.quantize(palette=palette_ref, dither=Image.Dither.NONE)
        for f in rendered_frames
    ]

    paletted_frames[0].save(
        out_buf,
        format="GIF",
        save_all=True,
        append_images=paletted_frames[1:],
        duration=card_durations,
        loop=0,
        optimize=True
    )
    result_bytes = out_buf.getvalue()

    validate_welcome_gif(result_bytes, min_expected_frames=20)
    return result_bytes


# ═══════════════════════════════════════════════════════════════
# Async Wrapper
# ═══════════════════════════════════════════════════════════════
async def generate_welcome_card_async(
    avatar_bytes: bytes,
    username: str,
    member_count: int,
    previous_count: Optional[int] = None,
    inviter_name: str = "Direct Join",
    server_name: str = "Discord Server",
    template_name: str = "default",
    background_url: Optional[str] = None,
    card_style: Optional[Dict[str, Any]] = None,
    card_message: Optional[str] = None
) -> io.BytesIO:
    """Asynchronous wrapper returning validated GIF BytesIO payload via thread pool execution."""
    gif_bytes = await asyncio.to_thread(
        generate_welcome_gif,
        avatar_input=avatar_bytes,
        username=username,
        member_count=member_count,
        previous_count=previous_count,
        inviter_name=inviter_name,
        server_name=server_name,
        template_name=template_name,
        background_url=background_url,
        card_style=card_style,
        card_message=card_message
    )
    buf = io.BytesIO(gif_bytes)
    buf.seek(0)
    return buf
