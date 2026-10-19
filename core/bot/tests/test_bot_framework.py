import pytest
from unittest.mock import AsyncMock, MagicMock
from core.bot.adapter import DiscordAdapter
from core.bot.events import MemberJoinedEvent
from core.event_bus import EventDispatcher


@pytest.mark.asyncio
async def test_discord_adapter_translation():
    bot_mock = MagicMock()
    bus = EventDispatcher()
    bus.publish = AsyncMock()  # type: ignore

    adapter = DiscordAdapter(bot_mock, bus)

    mock_member = MagicMock()
    mock_member.id = 123
    mock_member.name = "Alice"
    mock_member.guild.id = 456

    await adapter.on_member_join(mock_member)

    bus.publish.assert_called_once()
    args, _ = bus.publish.call_args
    event = args[0]

    assert isinstance(event, MemberJoinedEvent)
    assert event.member_id == 123
    assert event.member_name == "Alice"
    assert event.guild_id == 456
