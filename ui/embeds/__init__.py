"""
Embed Builder System providing fluent embed creation, limit validation, enterprise templates, and multi-target rendering.
"""

from .exceptions import EmbedValidationError, EmbedLimitExceededError
from .fields import EmbedField
from .footer import EmbedFooter
from .author import EmbedAuthor
from .media import EmbedMedia
from .validation import EmbedValidator
from .builder import EmbedBuilder
from .templates import EmbedTemplates

__all__ = [
    "EmbedValidationError",
    "EmbedLimitExceededError",
    "EmbedField",
    "EmbedFooter",
    "EmbedAuthor",
    "EmbedMedia",
    "EmbedValidator",
    "EmbedBuilder",
    "EmbedTemplates",
]
