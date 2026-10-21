"""Anti-Nuke V2 Engine — High-Fidelity In-Memory Snapshot Engine.

Maintains bounded in-memory structural snapshots of guild channels, roles,
webhooks, and emojis. Enables instant, rate-limit-aware, and idempotent
recovery following a confirmed security incident neutralization.
"""
from __future__ import annotations

import asyncio
import os
import json
import sqlite3
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import discord

logger = logging.getLogger("antinuke.v2.snapshot")

TEMPLATE_DIR = os.path.join("data", "templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)
DB_PATH = os.path.join("db", "anti.db")


def _init_template_db() -> None:
    """Ensures server_templates table exists in SQLite database for automatic MongoDB sync."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS server_templates (
                    guild_id INTEGER PRIMARY KEY,
                    template_data TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()
    except Exception as exc:
        logger.error("[Snapshot] Failed to initialize server_templates table: %s", exc)


_init_template_db()


@dataclass
class OverwriteSnapshot:
    """Serialized representation of a Discord permission overwrite."""
    target_id: int
    target_type: str  # "role" or "member"
    allow_bits: int
    deny_bits: int

    def to_discord(self, guild: discord.Guild) -> Tuple[Optional[Union[discord.Role, discord.Member]], Optional[discord.PermissionOverwrite]]:
        """Reconstructs the discord target and PermissionOverwrite object."""
        target: Optional[Union[discord.Role, discord.Member]] = None
        if self.target_type == "role":
            target = guild.get_role(self.target_id)
        else:
            target = guild.get_member(self.target_id)

        if not target:
            return None, None

        overwrite = discord.PermissionOverwrite.from_pair(
            discord.Permissions(self.allow_bits),
            discord.Permissions(self.deny_bits)
        )
        return target, overwrite

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "allow_bits": self.allow_bits,
            "deny_bits": self.deny_bits,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> OverwriteSnapshot:
        return cls(
            target_id=int(d["target_id"]),
            target_type=str(d.get("target_type", "role")),
            allow_bits=int(d.get("allow_bits", 0)),
            deny_bits=int(d.get("deny_bits", 0)),
        )


@dataclass
class ChannelSnapshot:
    """Structural snapshot of a Discord channel."""
    id: int
    guild_id: int
    name: str
    type: discord.ChannelType
    position: int
    topic: Optional[str] = None
    nsfw: bool = False
    bitrate: Optional[int] = None
    user_limit: Optional[int] = None
    rate_limit_per_user: Optional[int] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    overwrites: List[OverwriteSnapshot] = field(default_factory=list)
    child_channel_ids: List[int] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "name": self.name,
            "type": self.type.value if hasattr(self.type, "value") else int(self.type),
            "position": self.position,
            "topic": self.topic,
            "nsfw": self.nsfw,
            "bitrate": self.bitrate,
            "user_limit": self.user_limit,
            "rate_limit_per_user": self.rate_limit_per_user,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "overwrites": [ow.to_dict() for ow in self.overwrites],
            "child_channel_ids": self.child_channel_ids,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ChannelSnapshot:
        raw_type = d.get("type", 0)
        try:
            ch_type = discord.ChannelType(raw_type)
        except Exception:
            ch_type = discord.ChannelType.text
        return cls(
            id=int(d["id"]),
            guild_id=int(d.get("guild_id", 0)),
            name=str(d.get("name", "unknown")),
            type=ch_type,
            position=int(d.get("position", 0)),
            topic=d.get("topic"),
            nsfw=bool(d.get("nsfw", False)),
            bitrate=d.get("bitrate"),
            user_limit=d.get("user_limit"),
            rate_limit_per_user=d.get("rate_limit_per_user"),
            category_id=int(d["category_id"]) if d.get("category_id") else None,
            category_name=d.get("category_name"),
            overwrites=[OverwriteSnapshot.from_dict(ow) for ow in d.get("overwrites", [])],
            child_channel_ids=[int(c) for c in d.get("child_channel_ids", [])],
            timestamp=float(d.get("timestamp", time.time())),
        )

    @classmethod
    def from_channel(cls, channel: discord.abc.GuildChannel) -> ChannelSnapshot:
        ch_type = getattr(channel, "type", discord.ChannelType.text)
        cat_id: Optional[int] = None
        cat_name: Optional[str] = None
        if ch_type != discord.ChannelType.category:
            cat = getattr(channel, "category", None)
            raw_cat_id = getattr(channel, "category_id", None) or (getattr(cat, "id", None) if cat else None)
            try:
                cat_id = int(raw_cat_id) if raw_cat_id is not None else None
            except (ValueError, TypeError):
                cat_id = None
            cat_name = getattr(cat, "name", None) if cat else None

        overwrites_list: List[OverwriteSnapshot] = []
        raw_overwrites = getattr(channel, "overwrites", {})
        for target, overwrite in raw_overwrites.items():
            if not hasattr(target, "id"):
                continue
            t_type = "role" if isinstance(target, discord.Role) else "member"
            allow, deny = overwrite.pair()
            overwrites_list.append(OverwriteSnapshot(
                target_id=target.id,
                target_type=t_type,
                allow_bits=allow.value,
                deny_bits=deny.value,
            ))

        ch_type = getattr(channel, "type", discord.ChannelType.text)
        child_ids: List[int] = []
        if ch_type == discord.ChannelType.category and hasattr(channel, "channels"):
            child_ids = [c.id for c in channel.channels]

        return cls(
            id=channel.id,
            guild_id=channel.guild.id if channel.guild else 0,
            name=getattr(channel, "name", "unknown"),
            type=ch_type,
            position=getattr(channel, "position", 0),
            topic=getattr(channel, "topic", None),
            nsfw=getattr(channel, "nsfw", False),
            bitrate=getattr(channel, "bitrate", None),
            user_limit=getattr(channel, "user_limit", None),
            rate_limit_per_user=getattr(channel, "rate_limit_per_user", None),
            category_id=cat_id,
            category_name=cat_name,
            overwrites=overwrites_list,
            child_channel_ids=child_ids,
        )


@dataclass
class RoleSnapshot:
    """Structural snapshot of a Discord role."""
    id: int
    guild_id: int
    name: str
    color: int
    hoist: bool
    position: int
    permissions: int
    mentionable: bool
    unicode_emoji: Optional[str] = None
    icon: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "name": self.name,
            "color": self.color,
            "hoist": self.hoist,
            "position": self.position,
            "permissions": self.permissions,
            "mentionable": self.mentionable,
            "unicode_emoji": self.unicode_emoji,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> RoleSnapshot:
        return cls(
            id=int(d["id"]),
            guild_id=int(d.get("guild_id", 0)),
            name=str(d.get("name", "unknown_role")),
            color=int(d.get("color", 0)),
            hoist=bool(d.get("hoist", False)),
            position=int(d.get("position", 0)),
            permissions=int(d.get("permissions", 0)),
            mentionable=bool(d.get("mentionable", False)),
            unicode_emoji=d.get("unicode_emoji"),
            timestamp=float(d.get("timestamp", time.time())),
        )

    @classmethod
    def from_role(cls, role: discord.Role) -> RoleSnapshot:
        return cls(
            id=role.id,
            guild_id=role.guild.id if role.guild else 0,
            name=role.name,
            color=role.color.value,
            hoist=role.hoist,
            position=role.position,
            permissions=role.permissions.value,
            mentionable=role.mentionable,
            unicode_emoji=getattr(role, "unicode_emoji", None),
        )


@dataclass
class WebhookSnapshot:
    """Structural snapshot of a Discord webhook."""
    id: int
    guild_id: int
    channel_id: int
    name: str
    avatar: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "name": self.name,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> WebhookSnapshot:
        return cls(
            id=int(d["id"]),
            guild_id=int(d.get("guild_id", 0)),
            channel_id=int(d.get("channel_id", 0)),
            name=str(d.get("name", "Restored Webhook")),
            timestamp=float(d.get("timestamp", time.time())),
        )

    @classmethod
    def from_webhook(cls, webhook: discord.Webhook) -> WebhookSnapshot:
        return cls(
            id=webhook.id,
            guild_id=webhook.guild_id or (webhook.guild.id if getattr(webhook, "guild", None) else 0),
            channel_id=webhook.channel_id or (webhook.channel.id if getattr(webhook, "channel", None) else 0),
            name=webhook.name or "Restored Webhook",
        )


@dataclass
class EmojiSnapshot:
    """Structural snapshot of a Discord emoji."""
    id: int
    guild_id: int
    name: str
    roles: List[int] = field(default_factory=list)
    image: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "name": self.name,
            "roles": self.roles,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> EmojiSnapshot:
        return cls(
            id=int(d["id"]),
            guild_id=int(d.get("guild_id", 0)),
            name=str(d.get("name", "emoji")),
            roles=[int(r) for r in d.get("roles", [])],
            timestamp=float(d.get("timestamp", time.time())),
        )

    @classmethod
    def from_emoji(cls, emoji: discord.Emoji) -> EmojiSnapshot:
        role_ids = [r.id for r in getattr(emoji, "roles", [])]
        return cls(
            id=emoji.id,
            guild_id=emoji.guild.id if emoji.guild else 0,
            name=emoji.name,
            roles=role_ids,
        )


class GuildSnapshotStore:
    """Thread-safe bounded in-memory snapshot cache per guild."""

    def __init__(self, max_channels_per_guild: int = 500, max_roles_per_guild: int = 500) -> None:
        self.max_channels = max_channels_per_guild
        self.max_roles = max_roles_per_guild

        # guild_id -> dict of id -> Snapshot
        self._channels: Dict[int, Dict[int, ChannelSnapshot]] = {}
        self._roles: Dict[int, Dict[int, RoleSnapshot]] = {}
        self._webhooks: Dict[int, Dict[int, WebhookSnapshot]] = {}
        self._emojis: Dict[int, Dict[int, EmojiSnapshot]] = {}

        # Restored mapping: (guild_id, resource_type, old_id) -> new_id
        self._restored_mapping: Dict[Tuple[int, str, int], int] = {}

        # 1-Hour Snapshot Cooldown per Guild: guild_id -> monotonic timestamp of last full snapshot
        self._last_snapshot_time: Dict[int, float] = {}
        self.SNAPSHOT_COOLDOWN_SECONDS: float = 3600.0  # 1 Hour (3600s)

    def snapshot_channel(self, channel: discord.abc.GuildChannel) -> Optional[ChannelSnapshot]:
        """Snapshots a channel into RAM."""
        if not channel or not getattr(channel, "guild", None):
            return None
        gid = channel.guild.id
        if gid not in self._channels:
            self._channels[gid] = {}

        snap = ChannelSnapshot.from_channel(channel)
        # Bounded check
        if len(self._channels[gid]) >= self.max_channels and channel.id not in self._channels[gid]:
            # Evict oldest entry
            oldest_id = next(iter(self._channels[gid]))
            self._channels[gid].pop(oldest_id, None)

        self._channels[gid][channel.id] = snap
        return snap

    def snapshot_role(self, role: discord.Role) -> Optional[RoleSnapshot]:
        """Snapshots a role into RAM."""
        if not role or not getattr(role, "guild", None):
            return None
        gid = role.guild.id
        if gid not in self._roles:
            self._roles[gid] = {}

        snap = RoleSnapshot.from_role(role)
        if len(self._roles[gid]) >= self.max_roles and role.id not in self._roles[gid]:
            oldest_id = next(iter(self._roles[gid]))
            self._roles[gid].pop(oldest_id, None)

        self._roles[gid][role.id] = snap
        return snap

    def snapshot_webhook(self, webhook: discord.Webhook) -> Optional[WebhookSnapshot]:
        """Snapshots a webhook into RAM."""
        if not webhook:
            return None
        gid = webhook.guild_id or (webhook.guild.id if getattr(webhook, "guild", None) else 0)
        if not gid:
            return None
        if gid not in self._webhooks:
            self._webhooks[gid] = {}

        snap = WebhookSnapshot.from_webhook(webhook)
        self._webhooks[gid][webhook.id] = snap
        return snap

    def snapshot_emoji(self, emoji: discord.Emoji) -> Optional[EmojiSnapshot]:
        """Snapshots an emoji into RAM."""
        if not emoji or not getattr(emoji, "guild", None):
            return None
        gid = emoji.guild.id
        if gid not in self._emojis:
            self._emojis[gid] = {}

        snap = EmojiSnapshot.from_emoji(emoji)
        self._emojis[gid][emoji.id] = snap
        return snap

    def save_template_to_disk(self, guild_id: int) -> bool:
        """Serializes current in-memory guild snapshot to local NVMe disk."""
        try:
            data = {
                "guild_id": guild_id,
                "timestamp": time.time(),
                "channels": [ch.to_dict() for ch in self._channels.get(guild_id, {}).values()],
                "roles": [r.to_dict() for r in self._roles.get(guild_id, {}).values()],
                "emojis": [e.to_dict() for e in self._emojis.get(guild_id, {}).values()],
                "webhooks": [w.to_dict() for w in self._webhooks.get(guild_id, {}).values()],
            }
            filepath = os.path.join(TEMPLATE_DIR, f"template_{guild_id}.json")
            tmp_path = filepath + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, filepath)
            logger.info("[Snapshot] Saved template to disk for guild %s", guild_id)
            return True
        except Exception as exc:
            logger.error("[Snapshot] Failed to save template to disk for guild %s: %s", guild_id, exc)
            return False

    def save_template_to_db(self, guild_id: int) -> bool:
        """Saves current in-memory guild snapshot to SQLite anti.db (which syncs to MongoDB Cloud Atlas)."""
        try:
            data = {
                "guild_id": guild_id,
                "timestamp": time.time(),
                "channels": [ch.to_dict() for ch in self._channels.get(guild_id, {}).values()],
                "roles": [r.to_dict() for r in self._roles.get(guild_id, {}).values()],
                "emojis": [e.to_dict() for e in self._emojis.get(guild_id, {}).values()],
                "webhooks": [w.to_dict() for w in self._webhooks.get(guild_id, {}).values()],
            }
            template_json = json.dumps(data)
            now = time.time()
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    """
                    INSERT INTO server_templates (guild_id, template_data, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        template_data = excluded.template_data,
                        updated_at = excluded.updated_at
                    """,
                    (guild_id, template_json, now)
                )
                conn.commit()
            logger.info("[Snapshot] Synced template to DB for guild %s (ready for Cloud sync)", guild_id)
            return True
        except Exception as exc:
            logger.error("[Snapshot] Failed to save template to DB for guild %s: %s", guild_id, exc)
            return False

    def load_template_from_disk(self, guild_id: int) -> bool:
        """Loads guild template from NVMe disk, falling back to SQLite DB if not found on disk."""
        filepath = os.path.join(TEMPLATE_DIR, f"template_{guild_id}.json")
        data: Optional[Dict[str, Any]] = None

        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                logger.error("[Snapshot] Failed to read disk template for guild %s: %s", guild_id, exc)

        if not data:
            # Fallback to SQLite DB
            data = self.load_template_from_db(guild_id)

        if not data:
            return False

        try:
            if guild_id not in self._channels:
                self._channels[guild_id] = {}
            for ch_raw in data.get("channels", []):
                ch_snap = ChannelSnapshot.from_dict(ch_raw)
                if ch_snap.id not in self._channels[guild_id]:
                    self._channels[guild_id][ch_snap.id] = ch_snap

            if guild_id not in self._roles:
                self._roles[guild_id] = {}
            for r_raw in data.get("roles", []):
                r_snap = RoleSnapshot.from_dict(r_raw)
                if r_snap.id not in self._roles[guild_id]:
                    self._roles[guild_id][r_snap.id] = r_snap

            if guild_id not in self._emojis:
                self._emojis[guild_id] = {}
            for e_raw in data.get("emojis", []):
                e_snap = EmojiSnapshot.from_dict(e_raw)
                if e_snap.id not in self._emojis[guild_id]:
                    self._emojis[guild_id][e_snap.id] = e_snap

            if guild_id not in self._webhooks:
                self._webhooks[guild_id] = {}
            for w_raw in data.get("webhooks", []):
                w_snap = WebhookSnapshot.from_dict(w_raw)
                if w_snap.id not in self._webhooks[guild_id]:
                    self._webhooks[guild_id][w_snap.id] = w_snap

            logger.info(
                "[Snapshot] Loaded template for guild %s into RAM (%d channels, %d roles)",
                guild_id, len(self._channels[guild_id]), len(self._roles[guild_id])
            )
            return True
        except Exception as exc:
            logger.error("[Snapshot] Failed parsing template for guild %s: %s", guild_id, exc)
            return False

    def load_template_from_db(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves template JSON from SQLite server_templates table."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT template_data FROM server_templates WHERE guild_id = ?",
                    (guild_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
        except Exception as exc:
            logger.error("[Snapshot] DB query error for guild %s: %s", guild_id, exc)
        return None

    def get_guild_template(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Returns the full template dictionary for the guild, loading from storage if not in RAM."""
        if guild_id not in self._channels or guild_id not in self._roles:
            self.load_template_from_disk(guild_id)

        channels = list(self._channels.get(guild_id, {}).values())
        roles = list(self._roles.get(guild_id, {}).values())
        if not channels and not roles:
            return None

        return {
            "guild_id": guild_id,
            "timestamp": time.time(),
            "channels": [ch.to_dict() for ch in channels],
            "roles": [r.to_dict() for r in roles],
            "emojis": [e.to_dict() for e in self._emojis.get(guild_id, {}).values()],
            "webhooks": [w.to_dict() for w in self._webhooks.get(guild_id, {}).values()],
        }

    def get_all_channels(self, guild_id: int) -> List[ChannelSnapshot]:
        if guild_id not in self._channels:
            self.load_template_from_disk(guild_id)
        return list(self._channels.get(guild_id, {}).values())

    def get_all_roles(self, guild_id: int) -> List[RoleSnapshot]:
        if guild_id not in self._roles:
            self.load_template_from_disk(guild_id)
        return list(self._roles.get(guild_id, {}).values())

    def snapshot_guild(self, guild: discord.Guild, force: bool = False) -> bool:
        """Full baseline capture of guild channels, roles, and emojis with disk & cloud DB sync.
        
        Enforces a 1-hour cooldown per guild to prevent event loop lag spikes and CPU bottlenecks,
        unless `force=True` (e.g. initial setup or manual trigger).
        """
        if not guild:
            return False
        gid = guild.id
        now = time.monotonic()

        if not force:
            last_time = self._last_snapshot_time.get(gid, 0.0)
            elapsed = now - last_time
            if elapsed < self.SNAPSHOT_COOLDOWN_SECONDS:
                logger.debug(
                    "[Snapshot] Cooldown active for guild %s (%.0fs / %.0fs remaining); skipping full snapshot",
                    gid, self.SNAPSHOT_COOLDOWN_SECONDS - elapsed, self.SNAPSHOT_COOLDOWN_SECONDS
                )
                return False

        self._last_snapshot_time[gid] = now
        self._channels[gid] = {}
        self._roles[gid] = {}
        self._emojis[gid] = {}

        for ch in getattr(guild, "channels", []):
            try:
                self._channels[gid][ch.id] = ChannelSnapshot.from_channel(ch)
            except Exception:
                pass

        for r in getattr(guild, "roles", []):
            try:
                self._roles[gid][r.id] = RoleSnapshot.from_role(r)
            except Exception:
                pass

        for e in getattr(guild, "emojis", []):
            try:
                self._emojis[gid][e.id] = EmojiSnapshot.from_emoji(e)
            except Exception:
                pass

        # Persist to local disk NVMe and SQLite DB off-thread to prevent blocking event loop
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self.save_template_to_disk, gid)
            loop.run_in_executor(None, self.save_template_to_db, gid)
        except RuntimeError:
            self.save_template_to_disk(gid)
            self.save_template_to_db(gid)

        return True

    def record_channel(self, guild_id: int, channel: discord.abc.GuildChannel) -> ChannelSnapshot:
        """Records a live channel directly into snapshot RAM cache on the fly."""
        if guild_id not in self._channels:
            self._channels[guild_id] = {}
        snap = ChannelSnapshot.from_channel(channel)
        self._channels[guild_id][channel.id] = snap
        return snap

    def record_role(self, guild_id: int, role: discord.Role) -> RoleSnapshot:
        """Records a live role directly into snapshot RAM cache on the fly."""
        if guild_id not in self._roles:
            self._roles[guild_id] = {}
        snap = RoleSnapshot.from_role(role)
        self._roles[guild_id][role.id] = snap
        return snap

    def get_channel(self, guild_id: int, channel_id: int) -> Optional[ChannelSnapshot]:
        ch = self._channels.get(guild_id, {}).get(channel_id)
        if not ch:
            self.load_template_from_disk(guild_id)
            ch = self._channels.get(guild_id, {}).get(channel_id)
        if not ch:
            try:
                from core.services.channel_snapshot import channel_snapshot_manager
                legacy_snap = channel_snapshot_manager.get_snapshot(guild_id, channel_id)
                if legacy_snap:
                    ch = ChannelSnapshot(
                        id=legacy_snap.id,
                        guild_id=legacy_snap.guild_id,
                        name=legacy_snap.name,
                        type=legacy_snap.type,
                        position=legacy_snap.position,
                        topic=legacy_snap.topic,
                        nsfw=legacy_snap.nsfw,
                        bitrate=legacy_snap.bitrate,
                        user_limit=legacy_snap.user_limit,
                        category_id=legacy_snap.category_id,
                        category_name=legacy_snap.category_name,
                        overwrites=[
                            OverwriteSnapshot(
                                target_id=t.id,
                                target_type="role" if isinstance(t, discord.Role) else "member",
                                allow_bits=ow.pair()[0].value,
                                deny_bits=ow.pair()[1].value,
                            )
                            for t, ow in legacy_snap.overwrites.items() if hasattr(t, "id")
                        ],
                        child_channel_ids=getattr(legacy_snap, "child_channel_ids", []),
                    )
                    if guild_id not in self._channels:
                        self._channels[guild_id] = {}
                    self._channels[guild_id][channel_id] = ch
            except Exception:
                pass
        return ch

    def get_role(self, guild_id: int, role_id: int) -> Optional[RoleSnapshot]:
        r = self._roles.get(guild_id, {}).get(role_id)
        if not r:
            self.load_template_from_disk(guild_id)
            r = self._roles.get(guild_id, {}).get(role_id)
        return r

    def get_webhook(self, guild_id: int, webhook_id: int) -> Optional[WebhookSnapshot]:
        return self._webhooks.get(guild_id, {}).get(webhook_id)

    def get_emoji(self, guild_id: int, emoji_id: int) -> Optional[EmojiSnapshot]:
        return self._emojis.get(guild_id, {}).get(emoji_id)

    def register_restored_mapping(self, guild_id: int, resource_type: str, old_id: int, new_id: int) -> None:
        """Records mapping from destroyed entity ID to newly recreated entity ID."""
        self._restored_mapping[(guild_id, resource_type, old_id)] = new_id

    def get_restored_id(self, guild_id: int, resource_type: str, old_id: int) -> Optional[int]:
        """Resolves whether a resource has already been recreated."""
        return self._restored_mapping.get((guild_id, resource_type, old_id))

    def prune_guild(self, guild_id: int) -> None:
        """Evicts guild snapshot state upon bot departure."""
        self._channels.pop(guild_id, None)
        self._roles.pop(guild_id, None)
        self._webhooks.pop(guild_id, None)
        self._emojis.pop(guild_id, None)
        # Clear mappings for this guild
        keys_to_remove = [k for k in self._restored_mapping if k[0] == guild_id]
        for k in keys_to_remove:
            self._restored_mapping.pop(k, None)
