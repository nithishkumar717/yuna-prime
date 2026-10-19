import uuid
from typing import Any
from discord.ext import commands
from core.container import Container


class YunaContext(commands.Context[Any]):
    """Custom context injecting IoC dependencies natively into commands."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.correlation_id: str = str(uuid.uuid4())

    @property
    def container(self) -> Container:
        """Exposes the global DI container dynamically."""
        return getattr(self.bot, "container")
