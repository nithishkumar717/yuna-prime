from typing import Dict, Any
from pydantic import BaseModel


class EmbedField(BaseModel):
    """Encapsulates a single field entry in a Discord Embed payload."""
    name: str
    value: str
    inline: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "inline": self.inline
        }
