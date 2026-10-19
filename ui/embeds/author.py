from typing import Optional, Dict, Any
from pydantic import BaseModel


class EmbedAuthor(BaseModel):
    """Encapsulates author header information in a Discord Embed payload."""
    name: str
    url: Optional[str] = None
    icon_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"name": self.name}
        if self.url:
            res["url"] = self.url
        if self.icon_url:
            res["icon_url"] = self.icon_url
        return res
