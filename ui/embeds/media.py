from typing import Optional, Dict, Any
from pydantic import BaseModel


class EmbedMedia(BaseModel):
    """Encapsulates image and thumbnail media attachments in a Discord Embed payload."""
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}
        if self.image_url:
            res["image"] = {"url": self.image_url}
        if self.thumbnail_url:
            res["thumbnail"] = {"url": self.thumbnail_url}
        return res
