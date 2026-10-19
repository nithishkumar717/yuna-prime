from __future__ import annotations

from discord.ext import commands
import discord
import functools
from typing import Optional, Any
import asyncio

__all__ = ("Context", )


class Context(commands.Context):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return "<core.Context>"

    @property
    async def session(self):
        return self.bot.session

    @discord.utils.cached_property
    def replied_reference(self) -> Optional[discord.Message]:
        if not self.message:
            return None
        ref = getattr(self.message, "reference", None)
        if ref and isinstance(getattr(ref, "resolved", None), discord.Message):
            return ref.resolved.to_reference()
        return None

    def with_type(func):

        @functools.wraps(func)
        async def wrapped(self, *args, **kwargs):
            context = args[0] if isinstance(args[0],
                                            commands.Context) else args[1]
            try:
                async with context.typing():
                    await func(*args, **kwargs)
            except discord.Forbidden:  
                await func(*args, **kwargs)

        return wrapped

    async def show_help(self, command: str = None) -> Any:
        cmd = self.bot.get_command('help')
        command = command or self.command.qualified_name
        await self.invoke(cmd, command=command)

    async def send(self,
                   content: Optional[str] = None,
                   **kwargs) -> Optional[discord.Message]:
        try:
            from utils.emojis import sanitize_emoji_string, sanitize_embed
            if content and isinstance(content, str):
                content = sanitize_emoji_string(content, self.bot)
            if 'embed' in kwargs and kwargs['embed']:
                kwargs['embed'] = sanitize_embed(kwargs['embed'], self.bot)
            if 'embeds' in kwargs and kwargs['embeds']:
                kwargs['embeds'] = [sanitize_embed(e, self.bot) for e in kwargs['embeds'] if e]
        except Exception:
            pass

        # For interaction contexts (slash commands), interaction responses bypass standard send_messages channel permissions
        if self.interaction is None and self.guild and self.me and hasattr(self.channel, 'permissions_for'):
            try:
                if not (self.channel.permissions_for(self.me)).send_messages:
                    try:
                        await self.author.send(
                            "bot dont have perms to send msg in that channel")
                    except discord.Forbidden:  
                        pass
                    return None
            except Exception:
                pass
        return await super().send(content, **kwargs)

    async def reply(self,
                    content: Optional[str] = None,
                    **kwargs) -> Optional[discord.Message]:
        if self.interaction is not None:
            return await self.send(content, **kwargs)

        try:
            from utils.emojis import sanitize_emoji_string, sanitize_embed
            if content and isinstance(content, str):
                content = sanitize_emoji_string(content, self.bot)
            if 'embed' in kwargs and kwargs['embed']:
                kwargs['embed'] = sanitize_embed(kwargs['embed'], self.bot)
            if 'embeds' in kwargs and kwargs['embeds']:
                kwargs['embeds'] = [sanitize_embed(e, self.bot) for e in kwargs['embeds'] if e]
        except Exception:
            pass

        if self.guild and self.me and hasattr(self.channel, 'permissions_for'):
            try:
                if not (self.channel.permissions_for(self.me)).send_messages:
                    try:
                        await self.author.send(
                            "bot dont have perms to send msg in that channel")
                    except discord.Forbidden:  
                        pass
                    return None
            except Exception:
                pass
        return await super().reply(content, **kwargs)

    async def release(self, delay: Optional[int] = None) -> None:
        delay = delay or 0
        await asyncio.sleep(delay)

    async def error(self,
                    message: Optional[str] = None,
                    **kwargs) -> Optional[discord.Message]:
        try:
            from utils.emojis import get_emoji
            cross = get_emoji("cross") or "<:yuna_cross:1227866668152393789>"
        except Exception:
            cross = "<:yuna_cross:1227866668152393789>"
        content = f"{cross} | {message}" if message else None
        if self.interaction is not None:
            kwargs.setdefault("ephemeral", True)
        return await self.send(content, **kwargs)

    async def success(self,
                      message: Optional[str] = None,
                      **kwargs) -> Optional[discord.Message]:
        try:
            from utils.emojis import get_emoji
            tick = get_emoji("tick") or "<a:tick:1558726958802800660>"
        except Exception:
            tick = "<a:tick:1558726958802800660>"
        content = f"{tick} | {message}" if message else None
        if self.interaction is not None:
            kwargs.setdefault("ephemeral", True)
        return await self.send(content, **kwargs)
