"""Shared helpers for mapping `/logs setup` channels to dashboard event routes."""

from typing import Any


DASHBOARD_EVENT_SETUP_CHANNELS = {
    "message_delete": "message",
    "message_edit": "message",
    "bulk_delete": "message",
    "invite_posted": "invite",
    "message_pin": "message",
    "message_unpin": "message",
    "pins_update": "message",
    "joins": "joins",
    "leaves": "leaves",
    "role_given": "role",
    "role_removed": "role",
    "nick_change": "member",
    "ban": "ban",
    "unban": "ban",
    "kick": "mod",
    "timeout": "mod",
    "warn": "mod",
    "server_update": "server",
    "bot_add": "security",
    "event_create": "server",
    "event_update": "server",
    "event_delete": "server",
    "cmd_perms": "server",
    "channel_create": "channel",
    "channel_delete": "channel",
    "channel_update": "channel",
    "channel_perm_create": "channel",
    "channel_perm_update": "channel",
    "channel_perm_delete": "channel",
    "role_create": "role",
    "role_delete": "role",
    "role_update": "role",
    "voice_join": "voice",
    "voice_leave": "voice",
    "voice_move": "voice",
    "voice_mute": "voice",
    "voice_deafen": "voice",
    "invite_create": "invite",
    "invite_delete": "invite",
    "automod_rule_create": "automod",
    "automod_rule_update": "automod",
    "automod_rule_delete": "automod",
    "automod_block": "automod",
    "automod_flag": "automod",
    "automod_timeout": "automod",
    "invite_tracker": "invite_tracker",
    "invite_topz": "invite_topz",
    "verify": "verify",
    "whitelist": "whitelist",
    "security": "security",
    "ticket": "ticket",
    "admin": "admin",
    "raid": "raid",
    "misuse": "misuse",
    "antinuke": "antinuke",
    "nightmode": "nightmode",
    "presence": "presence",
    "relationship": "relationship",
    "boost": "boost",
    "file": "file",
}


def extract_setup_channel_ids(payload: dict[str, Any]) -> dict[str, str]:
    """Extract per-category channel IDs stored by `/logs setup`."""
    return {
        str(key).lower(): str(value["channel_id"])
        for key, value in payload.items()
        if isinstance(value, dict)
        and value.get("channel_id")
        and str(value["channel_id"]).isdigit()
    }


def dashboard_events_from_setup(setup_channels: dict[str, str]) -> dict[str, str]:
    """Build dashboard routes for both setup categories and their event keys."""
    events_config = dict(setup_channels)
    for event_key, setup_key in DASHBOARD_EVENT_SETUP_CHANNELS.items():
        if setup_key in setup_channels:
            events_config[event_key] = setup_channels[setup_key]
    return events_config


def merge_dashboard_events(
    saved_events_config: Any,
    setup_channels: dict[str, str],
) -> dict[str, str]:
    """Backfill setup defaults without replacing saved dashboard destinations."""
    events_config = dashboard_events_from_setup(setup_channels)
    if isinstance(saved_events_config, dict):
        for key, value in saved_events_config.items():
            if isinstance(key, str) and value is not None and str(value).strip():
                events_config[key] = str(value).strip()
    return events_config
