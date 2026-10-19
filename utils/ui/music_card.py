import io
import time
import asyncio
import urllib.request
import re
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import aiohttp
import discord

import os

# Cache for downloaded thumbnails to avoid re-fetching on every 15s progress update
_THUMBNAIL_CACHE: Dict[str, Image.Image] = {}
_MAX_CACHE_SIZE = 60
_UTILS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _get_font(font_name: str, size: int):
    candidates = [
        font_name,
        os.path.join(_UTILS_DIR, os.path.basename(font_name)),
        os.path.join(_UTILS_DIR, "arial.ttf"),
        "arial.ttf"
    ]
    for p in candidates:
        try:
            if os.path.isfile(p):
                return ImageFont.truetype(p, size)
        except Exception:
            pass
    try:
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()

def format_time_str(seconds: int) -> str:
    if seconds <= 0:
        return "00:00"
    m = seconds // 60
    s = seconds % 60
    if m >= 60:
        h = m // 60
        m = m % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

class MusicCardGenerator:
    """High-performance, non-blocking PIL renderer for dynamic Discord music player cards."""

    @staticmethod
    async def fetch_thumbnail(url: str, session: Optional[aiohttp.ClientSession] = None) -> Optional[Image.Image]:
        if not url or not str(url).startswith(("http://", "https://")):
            return None

        clean_url = str(url).strip()
        if clean_url in _THUMBNAIL_CACHE:
            return _THUMBNAIL_CACHE[clean_url]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
        }

        # 1. Primary: Async HTTP with 3.5s timeout (connect=2.0s to failover fast if DNS hangs)
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True

        try:
            async with session.get(clean_url, headers=headers, timeout=aiohttp.ClientTimeout(total=3.5, connect=2.0)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if len(data) > 300:
                        img = await asyncio.to_thread(Image.open, io.BytesIO(data))
                        img = img.convert("RGBA")
                        if len(_THUMBNAIL_CACHE) >= _MAX_CACHE_SIZE:
                            _THUMBNAIL_CACHE.pop(next(iter(_THUMBNAIL_CACHE)))
                        _THUMBNAIL_CACHE[clean_url] = img
                        return img
        except Exception:
            pass
        finally:
            if close_session and not session.closed:
                try:
                    await session.close()
                except Exception:
                    pass

        # 2. Secondary fallback: Native OS socket fetch via urllib (bypasses aiohttp Windows DNS issues)
        def _sync_fetch():
            try:
                req = urllib.request.Request(clean_url, headers=headers)
                with urllib.request.urlopen(req, timeout=4.0) as r:
                    if r.status == 200:
                        raw = r.read()
                        if len(raw) > 300:
                            im = Image.open(io.BytesIO(raw)).convert("RGBA")
                            return im
            except Exception:
                return None

        img_fallback = await asyncio.to_thread(_sync_fetch)
        if img_fallback:
            if len(_THUMBNAIL_CACHE) >= _MAX_CACHE_SIZE:
                _THUMBNAIL_CACHE.pop(next(iter(_THUMBNAIL_CACHE)))
            _THUMBNAIL_CACHE[clean_url] = img_fallback
            return img_fallback

        return None

    @staticmethod
    def render_platform_icon(platform: str, size: int = 20) -> Image.Image:
        scale = 4
        s = size * scale
        icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(icon)
        p = (platform or "youtube").lower()

        if "spotify" in p:
            # Official Spotify green circle (#1DB954) with 3 curved soundwave lines
            d.ellipse((0, 0, s, s), fill=(29, 185, 84, 255))
            cx, cy = s * 0.5, s * 0.5
            d.arc((cx - s * 0.38, cy - s * 0.38, cx + s * 0.38, cy + s * 0.22), start=205, end=335, fill=(18, 18, 18, 255), width=max(2, int(s * 0.08)))
            d.arc((cx - s * 0.32, cy - s * 0.18, cx + s * 0.32, cy + s * 0.36), start=205, end=335, fill=(18, 18, 18, 255), width=max(2, int(s * 0.075)))
            d.arc((cx - s * 0.26, cy + s * 0.02, cx + s * 0.26, cy + s * 0.50), start=205, end=335, fill=(18, 18, 18, 255), width=max(2, int(s * 0.07)))
        elif "youtubemusic" in p or "ytm" in p or "music.youtube" in p:
            # YouTube Music: red circle with concentric white ring & play triangle
            d.ellipse((0, 0, s, s), fill=(255, 0, 0, 255))
            d.ellipse((s * 0.2, s * 0.2, s * 0.8, s * 0.8), outline=(255, 255, 255, 255), width=max(2, int(s * 0.06)))
            tri = [(s * 0.42, s * 0.35), (s * 0.42, s * 0.65), (s * 0.68, s * 0.50)]
            d.polygon(tri, fill=(255, 255, 255, 255))
        elif "jiosaavn" in p or "saavn" in p:
            # JioSaavn: emerald green/teal circle
            d.ellipse((0, 0, s, s), fill=(43, 194, 150, 255))
            d.ellipse((s * 0.25, s * 0.25, s * 0.75, s * 0.75), fill=(255, 255, 255, 255))
            d.ellipse((s * 0.40, s * 0.40, s * 0.60, s * 0.60), fill=(43, 194, 150, 255))
        elif "apple" in p:
            # Apple Music: vibrant pink/red rounded badge with music note
            d.rounded_rectangle((0, 0, s, s), radius=int(s * 0.22), fill=(252, 60, 68, 255))
            d.ellipse((s * 0.28, s * 0.55, s * 0.48, s * 0.75), fill=(255, 255, 255, 255))
            d.rectangle((s * 0.42, s * 0.25, s * 0.48, s * 0.65), fill=(255, 255, 255, 255))
            d.polygon([(s * 0.42, s * 0.25), (s * 0.75, s * 0.18), (s * 0.75, s * 0.32), (s * 0.42, s * 0.38)], fill=(255, 255, 255, 255))
            d.rectangle((s * 0.69, s * 0.25, s * 0.75, s * 0.65), fill=(255, 255, 255, 255))
            d.ellipse((s * 0.55, s * 0.52, s * 0.75, s * 0.72), fill=(255, 255, 255, 255))
        elif "soundcloud" in p:
            # SoundCloud: orange rounded badge
            d.rounded_rectangle((0, 0, s, s), radius=int(s * 0.22), fill=(255, 85, 0, 255))
            d.ellipse((s * 0.35, s * 0.35, s * 0.75, s * 0.65), fill=(255, 255, 255, 255))
            d.rectangle((s * 0.25, s * 0.45, s * 0.75, s * 0.70), fill=(255, 255, 255, 255))
        else:
            # Standard YouTube: red rounded rectangle with white play triangle
            d.rounded_rectangle((0, int(s * 0.08), s, int(s * 0.92)), radius=int(s * 0.24), fill=(255, 0, 0, 255))
            tri = [(s * 0.38, s * 0.32), (s * 0.38, s * 0.68), (s * 0.72, s * 0.50)]
            d.polygon(tri, fill=(255, 255, 255, 255))

        return icon.resize((size, size), Image.Resampling.LANCZOS)

    @classmethod
    def render_card(
        cls,
        title: str,
        artist: str,
        elapsed_sec: int,
        duration_sec: int,
        thumb_img: Optional[Image.Image] = None,
        platform: str = "youtube"
    ) -> io.BytesIO:
        # Canvas dimensions matching reference (520x190 = ~2.74:1)
        W, H = 520, 190
        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        # 1. Blurred Artwork Background with Dark Vignette Overlay
        if thumb_img:
            bg = ImageOps.fit(thumb_img, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            bg = bg.filter(ImageFilter.GaussianBlur(radius=28))

            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            o_draw = ImageDraw.Draw(overlay)
            for x in range(W):
                # Smooth darkening gradient from left to right
                alpha = int(215 - (x / W) * 20)
                o_draw.line([(x, 0), (x, H)], fill=(16, 17, 22, alpha))

            bg = Image.alpha_composite(bg.convert("RGBA"), overlay)
        else:
            bg = Image.new("RGBA", (W, H), (20, 21, 26, 255))
            bg_draw = ImageDraw.Draw(bg)
            for y in range(H):
                shade = int(24 - (y / H) * 8)
                bg_draw.line([(0, y), (W, y)], fill=(shade, shade + 2, shade + 6, 255))

        # Smooth rounded card outer corners (radius=14)
        card_mask = Image.new("L", (W, H), 0)
        cm_draw = ImageDraw.Draw(card_mask)
        cm_draw.rounded_rectangle((0, 0, W, H), radius=14, fill=255)
        card.paste(bg, (0, 0), card_mask)

        draw = ImageDraw.Draw(card)

        # 2. Thumbnail on Left Side (1:1 Square, 170x170, pad=10, radius=10)
        thumb_pad = 10
        thumb_size = H - (thumb_pad * 2)  # 170x170
        if thumb_img:
            t_square = ImageOps.fit(thumb_img, (thumb_size, thumb_size), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            t_mask = Image.new("L", (thumb_size, thumb_size), 0)
            tm_draw = ImageDraw.Draw(t_mask)
            tm_draw.rounded_rectangle((0, 0, thumb_size, thumb_size), radius=10, fill=255)
            card.paste(t_square, (thumb_pad, thumb_pad), t_mask)
        else:
            draw.rounded_rectangle(
                (thumb_pad, thumb_pad, thumb_pad + thumb_size, thumb_pad + thumb_size),
                radius=10,
                fill=(32, 33, 40, 255),
                outline=(48, 50, 60, 255),
                width=1
            )
            # Elegant minimalist music note icon in center of placeholder
            cx = thumb_pad + (thumb_size // 2)
            cy = thumb_pad + (thumb_size // 2)
            nc = (95, 98, 115, 255)
            draw.ellipse((cx - 20, cy + 6, cx - 6, cy + 18), fill=nc)
            draw.ellipse((cx + 8, cy + 1, cx + 22, cy + 13), fill=nc)
            draw.rectangle((cx - 9, cy - 18, cx - 6, cy + 12), fill=nc)
            draw.rectangle((cx + 19, cy - 23, cx + 22, cy + 7), fill=nc)
            draw.polygon([(cx - 9, cy - 18), (cx + 22, cy - 23), (cx + 22, cy - 17), (cx - 9, cy - 12)], fill=nc)

        # 3. Typography Fonts
        font_title = _get_font("utils/HelveticaNeuBold.ttf", 25)
        font_artist = _get_font("utils/arial.ttf", 17)
        font_time = _get_font("utils/arial.ttf", 13)

        # 4. Dynamic Platform Badge (Top Right)
        badge_size = 20
        badge_x = W - 14 - badge_size
        badge_y = 12
        platform_icon = cls.render_platform_icon(platform, badge_size)
        card.paste(platform_icon, (badge_x, badge_y), platform_icon)

        # 5. Title & Artist Text
        text_x = 195
        title_max_w = badge_x - text_x - 10

        # Truncate title cleanly
        clean_t = title.strip()
        if font_title.getlength(clean_t) > title_max_w:
            while len(clean_t) > 3 and font_title.getlength(clean_t + "...") > title_max_w:
                clean_t = clean_t[:-1]
            clean_t = clean_t.rstrip() + "..."
        draw.text((text_x, 34), clean_t, font=font_title, fill=(255, 255, 255, 255))

        # Truncate artist cleanly
        clean_a = artist.strip()
        artist_max_w = W - text_x - 8
        if font_artist.getlength(clean_a) > artist_max_w:
            while len(clean_a) > 3 and font_artist.getlength(clean_a + "...") > artist_max_w:
                clean_a = clean_a[:-1]
            clean_a = clean_a.rstrip() + "..."
        draw.text((text_x, 69), clean_a, font=font_artist, fill=(146, 147, 166, 255))

        # 6. Progress Bar & Duration
        bar_x = 194
        bar_w = W - bar_x - 6  # 320px
        bar_y = 136

        pct = min(1.0, max(0.0, elapsed_sec / duration_sec)) if duration_sec > 0 else 0.0
        active_w = int(bar_w * pct)

        # Base unplayed track (3px height)
        draw.rounded_rectangle((bar_x, bar_y - 1, bar_x + bar_w, bar_y + 2), radius=1, fill=(75, 75, 80, 255))
        # Active progress track (3px height)
        if active_w > 0:
            draw.rounded_rectangle((bar_x, bar_y - 1, bar_x + active_w, bar_y + 2), radius=1, fill=(255, 255, 255, 255))

        # Circular Scrubber Knob (radius 4.5)
        knob_x = bar_x + active_w
        knob_r = 4.5
        draw.ellipse((knob_x - knob_r, bar_y - knob_r + 0.5, knob_x + knob_r, bar_y + knob_r + 0.5), fill=(255, 255, 255, 255))

        # 7. Timestamps
        el_str = format_time_str(elapsed_sec)
        dur_str = format_time_str(duration_sec) if duration_sec > 0 else "LIVE"

        time_y = 148
        draw.text((bar_x, time_y), el_str, font=font_time, fill=(140, 141, 155, 255))
        dur_w = font_time.getlength(dur_str)
        draw.text((bar_x + bar_w - dur_w, time_y), dur_str, font=font_time, fill=(140, 141, 155, 255))

        buf = io.BytesIO()
        card.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    @classmethod
    async def create_card_file(
        cls,
        title: str,
        artist: str,
        elapsed_sec: int,
        duration_sec: int,
        thumbnail_url: Optional[str] = None,
        platform: str = "youtube",
        session: Optional[aiohttp.ClientSession] = None,
        fallback_urls: Optional[List[str]] = None
    ) -> discord.File:
        candidates: List[str] = []
        if thumbnail_url:
            candidates.append(thumbnail_url)
        if fallback_urls:
            for fu in fallback_urls:
                if fu and fu not in candidates:
                    candidates.append(fu)

        thumb_img = None
        for cand in candidates:
            try:
                thumb_img = await cls.fetch_thumbnail(cand, session=session)
                if thumb_img:
                    break
            except Exception:
                continue

        buf = await asyncio.to_thread(
            cls.render_card,
            title,
            artist,
            elapsed_sec,
            duration_sec,
            thumb_img,
            platform
        )
        return discord.File(fp=buf, filename="music_card.png")
