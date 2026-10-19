"""Shared Components V2 formatting for Yuna's Discord audit logs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence, Tuple

import discord


YUNA_LOG_ACCENT = 0xD6B15E
MAX_LAYOUT_TEXT = 3900
MAX_EVENTS_PER_LAYOUT = 5
MAX_LAYOUT_COMPONENTS = 40


def _http_url(value: Optional[str]) -> Optional[str]:
    value = str(value or "").strip()
    return value if value.startswith(("https://", "http://")) else None


def _field_body(embed: discord.Embed) -> str:
    parts: List[str] = []
    if embed.description:
        parts.append(str(embed.description))

    for field in embed.fields:
        name = str(field.name or "Details").strip()
        value = str(field.value or "—").strip()
        parts.append(f"**{name}**\n{value}")

    footer = getattr(embed, "footer", None)
    footer_text = getattr(footer, "text", None) if footer else None
    if footer_text:
        parts.append(f"-# {footer_text}")

    timestamp = getattr(embed, "timestamp", None)
    if isinstance(timestamp, datetime):
        try:
            parts.append(f"-# <t:{int(timestamp.timestamp())}:F>")
        except (OverflowError, OSError, ValueError):
            pass

    return "\n\n".join(parts).strip() or "-# No additional details."


def _event_parts(embed: discord.Embed, module_label: str) -> Tuple[str, str, Optional[str], Optional[str]]:
    title = str(embed.title or "Yuna Server Log").strip()
    module = str(module_label or "server").replace("_", " ").strip().upper()
    author = getattr(embed, "author", None)
    author_name = str(getattr(author, "name", "") or "").strip()
    if author_name and title and author_name.startswith(f"{title} • "):
        author_name = author_name[len(title) + 3 :].strip()
    elif author_name.casefold() == title.casefold():
        author_name = ""

    header = f"## {title}\n-# YUNA · {module} LOG"
    if author_name:
        header += f"\n-# {author_name}"

    thumbnail_url = _http_url(getattr(author, "icon_url", None))
    if not thumbnail_url:
        thumbnail = getattr(embed, "thumbnail", None)
        thumbnail_url = _http_url(getattr(thumbnail, "url", None) if thumbnail else None)

    image = getattr(embed, "image", None)
    image_url = _http_url(getattr(image, "url", None) if image else None)
    return header, _field_body(embed), thumbnail_url, image_url


def _truncate_body(body: str, budget: int) -> str:
    if len(body) <= budget:
        return body
    marker = "\n\n-# Additional details omitted to fit Discord's Components V2 limit."
    if budget <= len(marker):
        return body[:budget]
    return body[: budget - len(marker)].rstrip() + marker


def _component_cost(has_thumbnail: bool, has_image: bool) -> int:
    # Container + header TextDisplay/Section + separator + body TextDisplay + optional media gallery.
    return 5 + int(has_thumbnail) + int(has_image)


def build_log_v2_views(
    embeds: Sequence[discord.Embed],
    module_label: str = "server",
) -> List[discord.ui.LayoutView]:
    """Convert one or more legacy log embeds into compact, gold-accented V2 cards.

    The result is split into multiple layouts when Discord's 4,000-character text
    or 40-component limits would otherwise be exceeded.
    """
    records = [embed for embed in embeds if isinstance(embed, discord.Embed)]
    if not records:
        return []

    layouts: List[discord.ui.LayoutView] = []
    current_view: Optional[discord.ui.LayoutView] = None
    current_text = 0
    current_components = 0
    current_events = 0

    def flush() -> None:
        nonlocal current_view, current_text, current_components, current_events
        if current_view is not None and current_events:
            layouts.append(current_view)
        current_view = None
        current_text = 0
        current_components = 0
        current_events = 0

    for embed in records:
        header, body, thumbnail_url, image_url = _event_parts(embed, module_label)
        # Keep room under Discord's aggregate Components V2 text ceiling.
        text_budget = max(100, MAX_LAYOUT_TEXT - len(header) - 1)
        body = _truncate_body(body, text_budget)
        text_weight = len(header) + 1 + len(body)
        cost = _component_cost(bool(thumbnail_url), bool(image_url))

        if current_events and (
            current_events >= MAX_EVENTS_PER_LAYOUT
            or current_text + text_weight > MAX_LAYOUT_TEXT
            or current_components + cost > MAX_LAYOUT_COMPONENTS
        ):
            flush()

        if current_view is None:
            current_view = discord.ui.LayoutView(timeout=None)

        accent = int(embed.color) if embed.color else YUNA_LOG_ACCENT
        container = discord.ui.Container(accent_color=accent)
        header_display = discord.ui.TextDisplay(header)
        if thumbnail_url:
            container.add_item(discord.ui.Section(
                header_display,
                accessory=discord.ui.Thumbnail(
                    thumbnail_url,
                    description=(str(embed.title or "Yuna log")[:1024]),
                ),
            ))
        else:
            container.add_item(header_display)

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(body))

        if image_url:
            gallery = discord.ui.MediaGallery()
            gallery.add_item(media=image_url, description=str(embed.title or "Yuna log")[:1024])
            container.add_item(gallery)

        current_view.add_item(container)
        current_text += text_weight
        current_components += cost
        current_events += 1

    flush()
    return layouts
