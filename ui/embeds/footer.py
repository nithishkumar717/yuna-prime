from typing import Optional, Dict, Any
from pydantic import BaseModel


class EmbedFooter(BaseModel):
    """Encapsulates footer content in a Discord Embed payload."""
    text: str
    icon_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"text": self.text}
        if self.icon_url:
            res["icon_url"] = self.icon_url
        return res
