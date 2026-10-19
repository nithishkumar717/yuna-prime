from typing import Optional, List, Dict, Any, Union
from ui.foundation.base_component import BaseUIComponent
from ui.foundation.theme import ThemeEngine
from ui.themes import ThemeRegistry, SemanticColorRole
from .fields import EmbedField
from .footer import EmbedFooter
from .author import EmbedAuthor
from .media import EmbedMedia
from .validation import EmbedValidator


class EmbedBuilder(BaseUIComponent):
    """Fluent Embed builder supporting Discord limit validation and multi-target rendering (Embed, HTML, Text)."""

    def __init__(self) -> None:
        self._title: Optional[str] = None
        self._description: Optional[str] = None
        self._color: Optional[Union[int, str, SemanticColorRole]] = None
        self._fields: List[EmbedField] = []
        self._footer: Optional[EmbedFooter] = None
        self._author: Optional[EmbedAuthor] = None
        self._media: EmbedMedia = EmbedMedia()

    def set_title(self, title: str) -> "EmbedBuilder":
        self._title = title
        return self

    def set_description(self, description: str) -> "EmbedBuilder":
        self._description = description
        return self

    def set_color(self, color: Union[int, str, SemanticColorRole]) -> "EmbedBuilder":
        """Set the embed color. Accepts hex int, semantic role string, or SemanticColorRole enum."""
        self._color = color
        return self

    def add_field(self, name: str, value: str, inline: bool = True) -> "EmbedBuilder":
        self._fields.append(EmbedField(name=name, value=value, inline=inline))
        return self

    def set_footer(self, text: str, icon_url: Optional[str] = None) -> "EmbedBuilder":
        self._footer = EmbedFooter(text=text, icon_url=icon_url)
        return self

    def set_author(self, name: str, url: Optional[str] = None, icon_url: Optional[str] = None) -> "EmbedBuilder":
        self._author = EmbedAuthor(name=name, url=url, icon_url=icon_url)
        return self

    def set_thumbnail(self, url: str) -> "EmbedBuilder":
        self._media.thumbnail_url = url
        return self

    def set_image(self, url: str) -> "EmbedBuilder":
        self._media.image_url = url
        return self

    def validate(self) -> None:
        EmbedValidator.validate(
            title=self._title,
            description=self._description,
            fields=self._fields,
            footer=self._footer,
            author=self._author
        )

    def _resolve_color(self) -> int:
        """Resolve the color value to a hex int using the active theme."""
        if isinstance(self._color, int):
            return self._color
        palette = ThemeRegistry.resolve_palette()
        if isinstance(self._color, SemanticColorRole):
            return palette.resolve(self._color)
        if isinstance(self._color, str):
            try:
                role = SemanticColorRole(self._color.lower())
                return palette.resolve(role)
            except ValueError:
                pass
        theme = ThemeEngine.get_active_theme()
        return theme.colors.primary

    def render_embed(self) -> Dict[str, Any]:
        self.validate()
        color_val = self._resolve_color()

        embed: Dict[str, Any] = {"color": color_val}

        if self._title:
            embed["title"] = self._title
        if self._description:
            embed["description"] = self._description
        if self._author:
            embed["author"] = self._author.to_dict()
        if self._footer:
            embed["footer"] = self._footer.to_dict()
        if self._fields:
            embed["fields"] = [f.to_dict() for f in self._fields]

        embed.update(self._media.to_dict())
        return embed

    def render_html(self) -> str:
        self.validate()
        color_val = self._resolve_color()
        border_hex = f"#{color_val:06X}"

        parts: List[str] = [
            f"<div class='yuna-embed' style='border-left: 4px solid {border_hex}; padding: 12px; background: var(--color-neutral-dark, #1E1F22); border-radius: 4px;'>"
        ]

        if self._author:
            parts.append(f"  <div class='embed-author' style='font-size: 0.875rem; opacity: 0.8;'>{self._author.name}</div>")
        if self._title:
            parts.append(f"  <h3 class='embed-title' style='margin: 4px 0;'>{self._title}</h3>")
        if self._description:
            parts.append(f"  <p class='embed-description' style='margin-bottom: 8px;'>{self._description}</p>")

        if self._fields:
            parts.append("  <div class='embed-fields' style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px;'>")
            for f in self._fields:
                parts.append(f"    <div class='embed-field'><strong>{f.name}</strong><br/><span>{f.value}</span></div>")
            parts.append("  </div>")

        if self._footer:
            parts.append(f"  <div class='embed-footer' style='font-size: 0.75rem; margin-top: 8px; opacity: 0.6;'>{self._footer.text}</div>")

        parts.append("</div>")
        return "\n".join(parts)

    def render_text(self) -> str:
        self.validate()
        lines: List[str] = []

        if self._author:
            lines.append(f"Author: {self._author.name}")
        if self._title:
            lines.append(f"=== {self._title} ===")
        if self._description:
            lines.append(self._description)

        for f in self._fields:
            lines.append(f"• {f.name}: {f.value}")

        if self._footer:
            lines.append(f"— {self._footer.text}")

        return "\n".join(lines)
