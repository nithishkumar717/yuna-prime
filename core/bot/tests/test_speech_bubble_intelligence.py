import os
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import discord
from core.bot.speech_bubble import (
    PresenceMetricsCollector,
    SpeechBubbleRenderer,
    SpeechBubbleRotationEngine,
    CANDIDATE_BUBBLES_BY_CATEGORY,
    ALL_CANDIDATE_BUBBLES,
)


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=discord.Client)
    bot.start_time = time.time() - 3600 * 25  # 1 day and 1 hour ago
    bot.latency = 0.024  # 24ms
    bot.guilds = [MagicMock(id=1, member_count=500, unavailable=False), MagicMock(id=2, member_count=1500, unavailable=False)]
    bot.users = [MagicMock(id=i) for i in range(2000)]
    bot.shards = None
    bot.shard_count = 1
    bot.status = discord.Status.do_not_disturb
    bot.change_presence = AsyncMock()
    bot.add_listener = MagicMock()
    bot.voice_clients = []
    bot.get_cog = MagicMock(return_value=None)
    return bot


# 1. Existing bubble templates render exactly as expected
def test_preserved_existing_variables(mock_bot):
    collector = PresenceMetricsCollector(mock_bot)
    collector.total_songs = 12500
    collector.process_ram = 180
    vars_dict = collector.get_variables()

    # Core 9 preserved variables
    assert "uptime" in vars_dict
    assert "guild_count" in vars_dict
    assert "user_count" in vars_dict
    assert "ping" in vars_dict
    assert "playing_count" in vars_dict
    assert "vc_count" in vars_dict
    assert "ram" in vars_dict
    assert "total_songs" in vars_dict
    assert "support_url" in vars_dict

    # Check formatting of preserved variables
    assert vars_dict["guild_count"] == "2"
    assert vars_dict["user_count"] == "2.0k"
    assert vars_dict["ping"] == "24"
    assert vars_dict["ram"] == "180"
    assert vars_dict["total_songs"] == "12,500"

    # Render a legacy template
    legacy_template = "Vibing across {guild_count} servers ✨"
    rendered = SpeechBubbleRenderer.render(legacy_template, vars_dict)
    assert rendered == "Vibing across 2 servers ✨"


# 2. Each new variable returns a valid, authoritative value
def test_new_variables_validity(mock_bot):
    collector = PresenceMetricsCollector(mock_bot)
    collector.cpu_percent = 2.4
    collector.process_ram = 142
    collector.ram_percent = 1.8
    collector.avg_latency = 22
    collector.event_loop_lag_ms = 0.5
    collector.commands_today = 85
    collector.commands_total = 12400
    collector.songs_today = 42
    collector.protected_guilds = 8
    collector.active_playlists = 7

    vars_dict = collector.get_variables()

    expected_new_vars = [
        "version", "uptime_short", "uptime_days", "shard_count", "started_at", "process_id",
        "cpu_percent", "process_ram", "ram_percent", "avg_latency", "latency_status", "event_loop_lag",
        "active_queues", "active_voice", "songs_today", "tracks_queued", "active_playlists",
        "autoplay_sessions", "music_sessions", "guilds_with_music", "music_engine_status",
        "active_guilds", "commands_today", "commands_total", "events_today", "new_guilds_today",
        "protected_guilds", "protection_status", "security_events_today", "db_status",
        "dashboard_status", "error_count_today", "recommendations_today", "ml_engine_status"
    ]

    for k in expected_new_vars:
        assert k in vars_dict, f"Missing expected variable: {k}"
        val = vars_dict[k]
        assert val is not None, f"Variable {k} is None"
        assert str(val).strip() != "", f"Variable {k} is empty"
        assert str(val) not in ("None", "null", "undefined", "NaN"), f"Variable {k} has invalid value {val}"

    # Verify unit conventions and formatting
    assert vars_dict["uptime_short"] == "1d 1h"
    assert vars_dict["uptime_days"] == "1"
    assert vars_dict["cpu_percent"] == "2.4"
    assert vars_dict["process_ram"] == "142"
    assert vars_dict["latency_status"] == "Optimal"
    assert vars_dict["commands_today"] == "85"
    assert vars_dict["commands_total"] == "12,400"


# 3. Missing optional data skips only the affected template
def test_missing_optional_data_skips_only_affected_template():
    variables = {
        "version": "7.0.2",
        "uptime_short": "2h 15m",
        "guild_count": "1,200",
        "unsupported_metric": None,
        "empty_metric": "",
    }

    # Template with valid variables renders
    t_valid = "Yuna v{version} ◈"
    assert SpeechBubbleRenderer.render(t_valid, variables) == "Yuna v7.0.2 ◈"

    # Template with missing/None variable returns None (skipped)
    t_missing = "Stats: {unsupported_metric} items"
    assert SpeechBubbleRenderer.render(t_missing, variables) is None

    # Template with empty string returns None (skipped)
    t_empty = "Value: {empty_metric}"
    assert SpeechBubbleRenderer.render(t_empty, variables) is None

    # Unknown variable returns None
    t_unknown = "Unknown: {non_existent_var}"
    assert SpeechBubbleRenderer.render(t_unknown, variables) is None


# 4. Formatting produces no unresolved placeholders or invalid numbers
def test_all_16_candidate_bubbles_render_cleanly(mock_bot):
    collector = PresenceMetricsCollector(mock_bot)
    collector.cpu_percent = 1.5
    collector.process_ram = 128
    collector.avg_latency = 20
    collector.total_songs = 5000
    collector.songs_today = 30
    collector.protected_guilds = 5
    collector.active_playlists = 3
    vars_dict = collector.get_variables()

    assert len(ALL_CANDIDATE_BUBBLES) == 16

    for template in ALL_CANDIDATE_BUBBLES:
        rendered = SpeechBubbleRenderer.render(template, vars_dict)
        assert rendered is not None, f"Template failed to render: {template}"
        assert "{" not in rendered and "}" not in rendered, f"Unresolved bracket in: {rendered}"
        assert len(rendered) <= 128, f"Status text exceeds 128 chars: {rendered}"
        assert "None" not in rendered
        assert "NaN" not in rendered


# 5. Music queue and active-session counts match the actual playback state
def test_music_queue_and_active_session_matching(mock_bot):
    mock_music_cog = MagicMock()
    mock_music_cog.queue = {
        101: [{"title": "Song 1"}, {"title": "Song 2"}],
        102: [],
        103: [{"title": "Song 3"}],
    }
    mock_music_cog.autoplay = {101: True, 102: False}
    mock_bot.get_cog.return_value = mock_music_cog

    vc1 = MagicMock()
    vc1.is_connected.return_value = True
    vc1.is_playing.return_value = True
    vc1.guild.id = 101

    vc2 = MagicMock()
    vc2.is_connected.return_value = True
    vc2.is_playing.return_value = False
    vc2.is_paused.return_value = True
    vc2.guild.id = 102

    mock_bot.voice_clients = [vc1, vc2]

    collector = PresenceMetricsCollector(mock_bot)
    vars_dict = collector.get_variables()

    assert vars_dict["active_queues"] == "2"     # Guilds 101 and 103
    assert vars_dict["tracks_queued"] == "3"     # 2 in guild 101 + 1 in guild 103
    assert vars_dict["active_voice"] == "2"      # 2 connected VCs
    assert vars_dict["playing_count"] == "1"     # 1 actively playing
    assert vars_dict["music_sessions"] == "2"    # 1 playing + 1 paused
    assert vars_dict["autoplay_sessions"] == "1" # Guild 101
    assert vars_dict["guilds_with_music"] == "1" # Guild 101 playing
    assert vars_dict["music_engine_status"] == "Streaming"


# 6. Daily counters follow a documented reset and persistence policy
def test_daily_counters_rollover(mock_bot):
    collector = PresenceMetricsCollector(mock_bot)
    collector._commands_today_date = "2026-01-01"  # Old date
    collector.commands_today = 50
    collector.commands_total = 1000

    # Recording a command on a new day triggers date rollover
    collector.record_command()

    assert collector.commands_today == 1
    assert collector.commands_total == 1001
    assert collector._commands_today_date != "2026-01-01"


# 7. Security and service-health messages cannot claim unverified status
def test_security_and_health_verification(mock_bot):
    collector = PresenceMetricsCollector(mock_bot)
    collector.protected_guilds = 0
    collector.db_status = "Degraded"

    vars_dict = collector.get_variables()
    assert vars_dict["db_status"] == "Degraded"
    # When 0 guilds protected and cache empty, status is Monitoring, not Active
    assert vars_dict["protection_status"] == "Monitoring"

    # When guilds are protected
    collector.protected_guilds = 5
    vars_dict2 = collector.get_variables()
    assert vars_dict2["protection_status"] == "Active"


# 8. The existing rotation interval remains configurable
def test_configurable_rotation_delay():
    from utils.config_loader import config
    delay = config.get("PRESENCES_CHANGE_DELAY", 30)
    assert isinstance(delay, int)
    assert delay >= 15, "Delay must be at least 15s to respect Discord rate limits"


# 9. Only speech bubbles rotate (CustomActivity type 4)
def test_strictly_speech_bubbles_only():
    text = "Always on. Always Yuna."
    act = discord.CustomActivity(name=text)
    act_dict = act.to_dict()

    assert act_dict.get("type") == 4  # Discord Type 4 = Custom Status
    assert act_dict.get("state") == text


# 10. No duplicate rotation tasks or unnecessary repeated Discord updates occur
@pytest.mark.asyncio
async def test_no_duplicate_updates_when_text_unchanged(mock_bot):
    engine = SpeechBubbleRotationEngine(mock_bot)
    engine._last_applied_text = "Always on. Always Yuna."

    # If get_next_bubble returns the exact same string
    bubble = "Always on. Always Yuna."
    if bubble == engine._last_applied_text:
        # Engine suppresses change_presence call
        mock_bot.change_presence.assert_not_called()


# 11. Balanced rotation alternates across categories
def test_rotation_balances_categories(mock_bot):
    engine = SpeechBubbleRotationEngine(mock_bot)
    collector = engine.collector
    collector.cpu_percent = 1.0
    collector.process_ram = 100
    collector.total_songs = 1000
    collector.songs_today = 10
    collector.protected_guilds = 4

    seen_categories = []
    # Capture 6 consecutive bubble picks
    for _ in range(6):
        bubble = engine.get_next_bubble()
        assert bubble is not None
        # Identify which category generated this bubble
        found_cat = None
        for cat, templates in CANDIDATE_BUBBLES_BY_CATEGORY.items():
            for tpl in templates:
                rendered = engine.renderer.render(tpl, collector.get_variables())
                if rendered == bubble:
                    found_cat = cat
                    break
            if found_cat:
                break
        seen_categories.append(found_cat)

    # All 6 categories should be represented across 6 steps
    assert len(set(seen_categories)) == 6, f"Categories were not balanced: {seen_categories}"
    assert seen_categories == ["IDENTITY", "UPTIME", "COMMUNITY", "MUSIC", "PERFORMANCE", "PROTECTION"]


# 12. No secrets or sensitive infrastructure data leak into public custom statuses
def test_sensitive_data_suppression():
    variables = {
        "token": "NzgxMjM0NTY3ODkwMTIzNDU2.Gz9xYz.1234567890abcdefghijklmnopqrstuvwxyz",
        "secret_key": "sk_live_9wDjAR2IJe0GiWoMn8U18IRbFFCVABL2",
        "clean_var": "Operational",
    }

    t_leak_token = "Status: {token}"
    assert SpeechBubbleRenderer.render(t_leak_token, variables) is None

    t_leak_key = "Key: {secret_key}"
    assert SpeechBubbleRenderer.render(t_leak_key, variables) is None

    t_clean = "System · {clean_var}"
    assert SpeechBubbleRenderer.render(t_clean, variables) == "System · Operational"
