from typing import Optional, List
from .fields import EmbedField
from .footer import EmbedFooter
from .author import EmbedAuthor
from .exceptions import EmbedLimitExceededError


class EmbedValidator:
    """Enforces official Discord API character limits and structural boundaries for Embed payloads."""

    MAX_TITLE_LENGTH = 256
    MAX_DESCRIPTION_LENGTH = 4096
    MAX_FIELDS_COUNT = 25
    MAX_FIELD_NAME_LENGTH = 256
    MAX_FIELD_VALUE_LENGTH = 1024
    MAX_FOOTER_TEXT_LENGTH = 2048
    MAX_AUTHOR_NAME_LENGTH = 256
    MAX_TOTAL_CHARACTERS = 6000

    @classmethod
    def validate(
        cls,
        title: Optional[str] = None,
        description: Optional[str] = None,
        fields: Optional[List[EmbedField]] = None,
        footer: Optional[EmbedFooter] = None,
        author: Optional[EmbedAuthor] = None
    ) -> None:
        total_chars = 0

        if title:
            if len(title) > cls.MAX_TITLE_LENGTH:
                raise EmbedLimitExceededError(
                    f"Embed title exceeds maximum length of {cls.MAX_TITLE_LENGTH} characters (got {len(title)})."
                )
            total_chars += len(title)

        if description:
            if len(description) > cls.MAX_DESCRIPTION_LENGTH:
                raise EmbedLimitExceededError(
                    f"Embed description exceeds maximum length of {cls.MAX_DESCRIPTION_LENGTH} characters (got {len(description)})."
                )
            total_chars += len(description)

        if footer and footer.text:
            if len(footer.text) > cls.MAX_FOOTER_TEXT_LENGTH:
                raise EmbedLimitExceededError(
                    f"Embed footer text exceeds maximum length of {cls.MAX_FOOTER_TEXT_LENGTH} characters (got {len(footer.text)})."
                )
            total_chars += len(footer.text)

        if author and author.name:
            if len(author.name) > cls.MAX_AUTHOR_NAME_LENGTH:
                raise EmbedLimitExceededError(
                    f"Embed author name exceeds maximum length of {cls.MAX_AUTHOR_NAME_LENGTH} characters (got {len(author.name)})."
                )
            total_chars += len(author.name)

        if fields:
            if len(fields) > cls.MAX_FIELDS_COUNT:
                raise EmbedLimitExceededError(
                    f"Embed fields count exceeds maximum of {cls.MAX_FIELDS_COUNT} fields (got {len(fields)})."
                )

            for i, field in enumerate(fields):
                if len(field.name) > cls.MAX_FIELD_NAME_LENGTH:
                    raise EmbedLimitExceededError(
                        f"Field #{i+1} name exceeds maximum length of {cls.MAX_FIELD_NAME_LENGTH} characters."
                    )
                if len(field.value) > cls.MAX_FIELD_VALUE_LENGTH:
                    raise EmbedLimitExceededError(
                        f"Field #{i+1} value exceeds maximum length of {cls.MAX_FIELD_VALUE_LENGTH} characters."
                    )
                total_chars += len(field.name) + len(field.value)

        if total_chars > cls.MAX_TOTAL_CHARACTERS:
            raise EmbedLimitExceededError(
                f"Combined embed content total of {total_chars} characters exceeds maximum limit of {cls.MAX_TOTAL_CHARACTERS} characters."
            )
