"""Right-to-left (RTL) layout and text direction support."""

from __future__ import annotations

from typing import Set


class RTLHelper:
    """Utility class for right-to-left layout and text direction management."""

    # Set of standard ISO language codes that use RTL scripts
    RTL_LANGUAGES: Set[str] = {
        "ar",  # Arabic
        "he",  # Hebrew
        "fa",  # Persian
        "ur",  # Urdu
        "ps",  # Pashto
        "sd",  # Sindhi
        "ug",  # Uyghur
        "yi",  # Yiddish
        "syr",  # Syriac
    }

    @classmethod
    def is_rtl_language(cls, lang_code: str) -> bool:
        """Check if a language code (e.g., 'ar', 'he', 'en-US') is right-to-left."""
        if not lang_code:
            return False
        # Normalize: convert to lowercase and take the language prefix (e.g. 'en-US' -> 'en')
        clean_code = lang_code.strip().lower().split("-")[0]
        return clean_code in cls.RTL_LANGUAGES

    @classmethod
    def get_dir_attribute(cls, lang_code: str) -> str:
        """Get the HTML 'dir' attribute value ('rtl' or 'ltr') for a language."""
        return "rtl" if cls.is_rtl_language(lang_code) else "ltr"

    @classmethod
    def mirror_alignment(cls, alignment: str) -> str:
        """Mirror alignment strings ('left' <-> 'right', 'start' <-> 'end')."""
        val = alignment.strip().lower()
        if val == "left":
            return "right"
        if val == "right":
            return "left"
        if val == "start":
            return "end"
        if val == "end":
            return "start"
        if val == "ltr":
            return "rtl"
        if val == "rtl":
            return "ltr"
        return alignment

    @classmethod
    def mirror_icon(cls, icon: str) -> str:
        """Mirror arrow icons or chevron characters for RTL support."""
        mapping = {
            "←": "→",
            "→": "←",
            "◀": "▶",
            "▶": "◀",
            "◀─": "─▶",
            "─▶": "◀─",
            "left": "right",
            "right": "left",
            "chevron-left": "chevron-right",
            "chevron-right": "chevron-left",
        }
        return mapping.get(icon, icon)
