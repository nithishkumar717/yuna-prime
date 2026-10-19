import discord
from typing import Any, Type
from discord.ext import commands
from core.container import Container
from core.event_bus import EventDispatcher
from core.services.manager import ServiceManager
from .context import YunaContext


class YunaBot(commands.Bot):
    """Primary discord adapter strictly delegating logic back to Domain Services."""

    def __init__(
        self,
        container: Container,
        event_bus: EventDispatcher,
        service_manager: ServiceManager,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.container = container
        self.event_bus = event_bus
        self.service_manager = service_manager
        try:
            from utils.emojis import install_emoji_sanitizer_hooks
            install_emoji_sanitizer_hooks(self)
        except Exception:
            pass

    async def on_ready(self) -> None:
        try:
            from utils.emojis import install_emoji_sanitizer_hooks
            install_emoji_sanitizer_hooks(self)
        except Exception:
            pass

    async def get_context(  # type: ignore[override]
        self,
        message: discord.Message | discord.Interaction[Any],
        *,
        cls: Type[commands.Context[Any]] = YunaContext,
    ) -> commands.Context[Any]:
        return await super().get_context(message, cls=cls)  # type: ignore
