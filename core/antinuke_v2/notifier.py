"""Anti-Nuke V2 Engine — High-Performance Notification, Logging & Dashboard Subsystem.

Provides resilient, non-blocking notification and persistence:
1. Batched Log-Channel Embeds: Buffers burst events (e.g. 10 rapid channel deletes)
   into batched embeds (up to 10 per message) to prevent Discord 429 rate limits.
2. Deduplicated Incident DM Reports: Ensures exactly ONE unified security alert
   is delivered to the Guild Owner and Extra Owners per incident/raid across dual paths
   (audit_stream and entity_fallback).
3. Background Dashboard Storage Queue: Asynchronously queues incident records and
   flushes to SQLite (db/audit_logs.db) without blocking the critical containment path.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import itertools
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiosqlite
import discord

from core.antinuke_v2.containment import ContainmentResult
from core.antinuke_v2.models import Decision, DecisionAction, PunishmentType
from core.antinuke_v2.state_store import GuildSecurityConfig

logger = logging.getLogger("antinuke.v2.notifier")

_ENTRY_ID_SEQ = itertools.count(1)

ANIMATED_TICK = "<:17742:1560628833105743972>"

_ACTION_LABELS: Dict[str, str] = {
    "chcr": "Channel Created",
    "chdl": "Channel Deleted",
    "chup": "Channel Updated",
    "rlcr": "Role Created",
    "rldl": "Role Deleted",
    "rlup": "Role Updated",
    "kick": "Member Kicked",
    "ban": "Member Banned",
    "unban": "Member Unbanned",
    "botadd": "Bot Added",
    "prune": "Member Pruned",
    "memup": "Member Roles Escalated",
    "serverup": "Server Settings Changed",
    "mngweb": "Webhook Modified",
    "webhook_create": "Webhook Created",
    "webhook_delete": "Webhook Deleted",
    "webhook_update": "Webhook Updated",
    "everyone": "Mass Mention (@everyone/@here)",
    "meneve": "Mass Mention (@everyone/@here)",
    "vanity": "Vanity URL Changed",
    "integration": "Integration Modified",
    "emocr": "Emoji Created",
    "emodl": "Emoji Deleted",
    "stkcr": "Sticker Created",
    "stkdl": "Sticker Deleted",
    "invdl": "Invite Deleted",
    "overwrite_create": "Permission Overwrite Created",
    "overwrite_update": "Permission Overwrite Updated",
    "overwrite_delete": "Permission Overwrite Deleted",
}


def humanize_action_name(action: str) -> str:
    """Converts internal action code into clean, readable display title."""
    act_lower = str(action or "").lower().strip()
    return _ACTION_LABELS.get(act_lower, act_lower.replace("_", " ").title())


def clean_target_name(target: Any, action_label: str = "") -> Tuple[str, str, str]:
    """Extracts (target_name, target_id, target_type) cleanly without Python reprs."""
    if target is None:
        return "Server", "", "Server"

    target_id = str(getattr(target, "id", ""))
    target_name = getattr(target, "name", getattr(target, "display_name", None))

    class_name = type(target).__name__.lower()
    if "channel" in class_name or "thread" in class_name:
        t_type = "Channel"
    elif "role" in class_name:
        t_type = "Role"
    elif "webhook" in class_name:
        t_type = "Webhook"
    elif "member" in class_name or "user" in class_name:
        t_type = "Member"
    elif "emoji" in class_name or "sticker" in class_name:
        t_type = "Emoji/Sticker"
    elif "guild" in class_name:
        t_type = "Server"
    else:
        t_type = "Discord Object"

    if isinstance(target, str):
        # Handle string object reprs
        match = re.search(r"<Object\s+id=(\d+)\s+type=<class\s+'([^']+)'", target)
        if match:
            target_id = target_id or match.group(1)
            t_type = "Webhook" if "webhook" in match.group(2).lower() else "Object"
        else:
            target_name = target

    target_name = target_name or (f"#{target_id}" if target_id else "Unknown Target")
    return str(target_name), target_id, t_type


# ==============================================================================
# 1. BACKGROUND DASHBOARD STORAGE QUEUE
# ==============================================================================

class V2DashboardQueue:
    """Asynchronous bounded background queue for dashboard audit log storage."""

    def __init__(self, db_path: str = "db/audit_logs.db", maxsize: int = 10000) -> None:
        self.db_path = db_path
        self.maxsize = maxsize
        self._queue: asyncio.Queue[Tuple[int, Dict[str, Any]]] = asyncio.Queue(maxsize=maxsize)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._db_lock = asyncio.Lock()

    def enqueue_incident(
        self,
        guild_id: int,
        action: str,
        actor: Any,
        target: Any,
        action_taken: str,
        details: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> bool:
        """Enqueues an audit log record without awaiting or blocking CPU."""
        now_ts = timestamp or time.time()
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        time_str = datetime.fromtimestamp(now_ts, tz=ist_tz).strftime("%b %d, %Y - %I:%M:%S %p IST")

        actor_id = str(getattr(actor, "id", "0"))
        actor_name = getattr(actor, "name", getattr(actor, "display_name", f"User {actor_id}"))
        actor_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"
        if hasattr(actor, "display_avatar") and actor.display_avatar:
            actor_avatar = str(actor.display_avatar.url)
        elif hasattr(actor, "avatar") and actor.avatar:
            actor_avatar = str(actor.avatar.url)

        target_name, target_id, target_type = clean_target_name(target, action)
        display_event = humanize_action_name(action)

        is_punished = any(k in action_taken.lower() for k in ["ban", "kick", "quarantine", "strip", "delete", "neutralize", "revert"])
        status = "BLOCKED" if is_punished else "LOGGED"

        headline = f"Anti-Nuke [{display_event}]: {action_taken} against @{actor_name}"
        items = [f"Event: {display_event}", f"Action Taken: {action_taken}"]
        if details:
            items.append(f"Details: {details}")
        if target_name and target_name != "Server":
            items.append(f"Target: {target_name} ({target_type})")

        entry_id = f"antinuke-v2-{guild_id}-{int(now_ts * 1000)}-{next(_ENTRY_ID_SEQ)}"
        record: Dict[str, Any] = {
            "id": entry_id,
            "entryId": entry_id,
            "module": "ANTINUKE",
            "action": f"Anti-Nuke {display_event}",
            "headline": headline,
            "actionCode": 0,
            "actor": f"@{actor_name}",
            "actorId": actor_id,
            "actorAvatar": actor_avatar,
            "target": f"{target_name} (ID: {target_id})" if target_id else target_name,
            "targetId": target_id,
            "status": status,
            "timestamp": time_str,
            "createdAt": now_ts,
            "reason": action_taken,
            "details": details or action_taken,
            "items": items,
            "changes": [],
        }

        try:
            self._queue.put_nowait((guild_id, record))
            return True
        except asyncio.QueueFull:
            logger.warning("[V2DashboardQueue] Queue full (size=%d), dropping log for guild %s", self.maxsize, guild_id)
            return False

    def start(self) -> None:
        """Starts the background worker task."""
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._worker_task = loop.create_task(self._worker_loop())
        except RuntimeError:
            pass

    async def stop(self) -> None:
        """Drains and stops the background worker task."""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        await self.drain()

    async def drain(self) -> None:
        """Flushes all queued items to SQLite synchronously."""
        batch: List[Tuple[int, Dict[str, Any]]] = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if batch:
            await self._write_batch_to_sqlite(batch)

    async def _worker_loop(self) -> None:
        """Pulls logs from the queue and writes in batches to SQLite."""
        while self._running:
            try:
                # Wait for at least one item or timeout
                item = await self._queue.get()
                batch = [item]

                # Collect burst items up to 50
                for _ in range(49):
                    if self._queue.empty():
                        break
                    try:
                        batch.append(self._queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                await self._write_batch_to_sqlite(batch)
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[V2DashboardQueue] Worker error: %s", exc)
                await asyncio.sleep(1.0)

    async def _write_batch_to_sqlite(self, batch: List[Tuple[int, Dict[str, Any]]]) -> None:
        """Inserts records into db/audit_logs.db with schema auto-init."""
        if not batch:
            return

        async with self._db_lock:
            try:
                async with aiosqlite.connect(self.db_path, timeout=10.0) as db:
                    await db.execute("PRAGMA busy_timeout = 30000;")
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS audit_logs (
                            id TEXT PRIMARY KEY,
                            guild_id INTEGER,
                            entry_id TEXT,
                            action_code INTEGER,
                            module TEXT,
                            action TEXT,
                            headline TEXT,
                            actor_name TEXT,
                            actor_id TEXT,
                            actor_avatar TEXT,
                            target_name TEXT,
                            target_id TEXT,
                            reason TEXT,
                            details TEXT,
                            items_json TEXT,
                            changes_json TEXT,
                            timestamp_str TEXT,
                            created_at REAL
                        )
                    """)

                    for guild_id, rec in batch:
                        items_str = json.dumps(rec.get("items") or [])
                        changes_str = json.dumps(rec.get("changes") or [])
                        await db.execute("""
                            INSERT OR REPLACE INTO audit_logs (
                                id, guild_id, entry_id, action_code, module, action, headline,
                                actor_name, actor_id, actor_avatar, target_name, target_id,
                                reason, details, items_json, changes_json, timestamp_str, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            rec["id"],
                            guild_id,
                            rec.get("entryId", rec["id"]),
                            rec.get("actionCode", 0),
                            rec.get("module", "ANTINUKE"),
                            rec.get("action", "Anti-Nuke Incident"),
                            rec.get("headline", rec.get("action", "Anti-Nuke Incident")),
                            rec.get("actor", "System"),
                            rec.get("actorId", "0"),
                            rec.get("actorAvatar", ""),
                            rec.get("target", "Server"),
                            rec.get("targetId", ""),
                            rec.get("reason", None),
                            rec.get("details", ""),
                            items_str,
                            changes_str,
                            rec.get("timestamp", "Just now"),
                            rec.get("createdAt", time.time())
                        ))
                    await db.commit()
            except Exception as exc:
                logger.error("[V2DashboardQueue] Failed to write batch of %d records to SQLite: %s", len(batch), exc)


# ==============================================================================
# 2. BATCHED LOG-CHANNEL DISPATCHER
# ==============================================================================

class V2LogChannelDispatcher:
    """Buffers security embeds per channel and dispatches in multi-embed batches."""

    def __init__(self, batch_window: float = 0.5, max_batch_size: int = 10, message_spacing: float = 0.2) -> None:
        self.batch_window = batch_window
        self.max_batch_size = max_batch_size
        self.message_spacing = message_spacing
        self._buffers: Dict[int, List[discord.Embed]] = {}
        self._channels: Dict[int, discord.abc.Messageable] = {}
        self._flush_tasks: Dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def build_security_embed(
        self,
        guild: discord.Guild,
        action: str,
        actor: Any,
        target: Any,
        action_taken: str,
        details: Optional[str] = None,
        detection_time: Optional[datetime] = None,
    ) -> discord.Embed:
        """Constructs an embed identical to existing Yuna Anti-Nuke security logs."""
        display_event = humanize_action_name(action)
        is_punished = any(k in action_taken.lower() for k in ["ban", "kick", "quarantine", "strip", "delete", "neutralize", "revert"])
        outcome = "BLOCKED" if is_punished else ("AUTHORIZED" if "author" in action_taken.lower() else "ACTION TAKEN")
        color = 0xED4245 if outcome == "BLOCKED" else (0x5865F2 if outcome == "AUTHORIZED" else 0xF0A33A)
        outcome_icon = "🛡️" if outcome == "BLOCKED" else ("✅" if outcome == "AUTHORIZED" else "⚠️")

        detected_at = detection_time or datetime.now(timezone.utc)
        ts_int = int(detected_at.timestamp())

        actor_id = getattr(actor, "id", None)
        actor_name = getattr(actor, "display_name", getattr(actor, "name", f"User {actor_id}"))
        target_name, target_id, target_type = clean_target_name(target, action)

        embed = discord.Embed(
            title=f"{outcome_icon} Anti-Nuke Security Log · {outcome}",
            description=f"**{display_event}** in **{guild.name}**",
            color=color,
        )
        embed.add_field(name="Initiator", value=f"**{actor_name}**\nID: `{actor_id}`" if actor_id else f"**{actor_name}**", inline=True)
        embed.add_field(name="Affected target", value=f"**{target_name}**\nType: {target_type} · ID: `{target_id or 'Unavailable'}`", inline=True)
        embed.add_field(name="Yuna's action", value=action_taken, inline=False)
        if details:
            embed.add_field(name="Detection details", value=details, inline=False)
        embed.add_field(name="Detection time", value=f"<t:{ts_int}:F> · <t:{ts_int}:R>", inline=False)

        avatar_asset = getattr(actor, "display_avatar", None) or getattr(actor, "avatar", None)
        if avatar_asset and hasattr(avatar_asset, "url"):
            embed.set_thumbnail(url=str(avatar_asset.url))

        footer_icon = guild.me.display_avatar.url if hasattr(guild, "me") and guild.me and hasattr(guild.me, "display_avatar") else None
        embed.set_footer(text=f"YUNA Security · {guild.name}", icon_url=footer_icon)
        return embed

    def enqueue_log(
        self,
        channel: discord.abc.Messageable,
        embed: discord.Embed,
    ) -> None:
        """Buffers embed for channel and schedules batch dispatch."""
        if not channel or not hasattr(channel, "id") or not embed:
            return

        channel_id = channel.id
        if channel_id not in self._buffers:
            self._buffers[channel_id] = []
        self._buffers[channel_id].append(embed)
        self._channels[channel_id] = channel

        if channel_id not in self._flush_tasks or self._flush_tasks[channel_id].done():
            try:
                loop = asyncio.get_running_loop()
                self._flush_tasks[channel_id] = loop.create_task(self._flush_channel_loop(channel_id))
            except RuntimeError:
                pass

    async def _flush_channel_loop(self, channel_id: int) -> None:
        """Batches and dispatches up to 10 embeds per message."""
        await asyncio.sleep(self.batch_window)

        while channel_id in self._buffers and self._buffers[channel_id]:
            buffer = self._buffers[channel_id]
            batch = buffer[:self.max_batch_size]
            del buffer[:len(batch)]

            channel = self._channels.get(channel_id)
            if channel and batch:
                try:
                    await channel.send(embeds=batch)
                    if self.message_spacing > 0:
                        await asyncio.sleep(self.message_spacing)
                except discord.RateLimited as rl:
                    retry_after = getattr(rl, "retry_after", 2.0)
                    await asyncio.sleep(retry_after)
                    # Reinsert batch at the head of buffer
                    buffer[0:0] = batch
                except Exception as exc:
                    logger.error("[V2LogChannel] Failed to send log batch to channel %s: %s", channel_id, exc)

        self._buffers.pop(channel_id, None)
        self._channels.pop(channel_id, None)


# ==============================================================================
# 3. DEDUPLICATED DM DISPATCHER
# ==============================================================================

@dataclass
class IncidentCluster:
    """Aggregates rapid multi-action destructive events from the same attacker."""
    guild_id: int
    actor_id: int
    actor_name: str
    actions: List[Tuple[str, str]] = field(default_factory=list)  # (action_name, target_name)
    punishment: str = "Banned the offending account"
    reason: str = ""
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    dispatched: bool = False
    debounce_task: Optional[asyncio.Task] = None


class V2DMDeduplicator:
    """Guarantees exactly ONE deduplicated DM report per incident across all detection paths."""

    def __init__(
        self,
        dedup_window_seconds: float = 20.0,
        debounce_seconds: float = 0.5,
        pacing_delay: float = 0.05,
    ) -> None:
        self.dedup_window = dedup_window_seconds
        self.debounce_seconds = debounce_seconds
        self.pacing_delay = pacing_delay

        # (guild_id, action, target_id) -> last_notified_ts
        self._notified_actions: Dict[Tuple[int, str, Optional[int]], float] = {}
        # (guild_id, actor_id) -> IncidentCluster
        self._active_clusters: Dict[Tuple[int, int], IncidentCluster] = {}
        self._lock = asyncio.Lock()

    def is_action_duplicate(self, guild_id: int, action: str, target_id: Optional[int], now: Optional[float] = None) -> bool:
        """Checks if the exact action+target was already notified across stream/fallback."""
        current = now or time.time()
        key = (guild_id, action.lower(), target_id)

        # Evict expired keys
        for k, ts in list(self._notified_actions.items()):
            if current - ts > self.dedup_window:
                self._notified_actions.pop(k, None)

        if key in self._notified_actions:
            return True

        self._notified_actions[key] = current
        return False

    async def record_and_dispatch_dm(
        self,
        guild: discord.Guild,
        action: str,
        actor: Any,
        target: Any,
        punishment: str,
        reason: str,
        state: GuildSecurityConfig,
        detection_time: Optional[datetime] = None,
    ) -> bool:
        """Coalesces burst actions from the same attacker and dispatches ONE deduplicated DM."""
        actor_id = getattr(actor, "id", 0)
        target_name, target_id_str, target_type = clean_target_name(target, action)
        target_int = int(target_id_str) if target_id_str.isdigit() else None
        now_ts = time.time()

        # 1. Dual-path deduplication: check if exact action & target was already alerted
        if self.is_action_duplicate(guild.id, action, target_int, now=now_ts):
            logger.debug("[V2DMDedup] Suppressed duplicate action alert for %s on %s across paths", action, target_int)
            return False

        cluster_key = (guild.id, actor_id)
        cluster = self._active_clusters.get(cluster_key)

        actor_name = getattr(actor, "display_name", getattr(actor, "name", f"User {actor_id}"))

        if not cluster or (now_ts - cluster.first_seen > self.dedup_window):
            # Create new incident cluster
            cluster = IncidentCluster(
                guild_id=guild.id,
                actor_id=actor_id,
                actor_name=actor_name,
                punishment=punishment,
                reason=reason,
                first_seen=now_ts,
                last_seen=now_ts,
            )
            self._active_clusters[cluster_key] = cluster

        cluster.actions.append((humanize_action_name(action), target_name))
        cluster.last_seen = now_ts

        # If already dispatched for this cluster, avoid spamming repeated DMs for subsequent actions of the same ban
        if cluster.dispatched:
            logger.debug("[V2DMDedup] Swallowed subsequent event for active cluster %s", cluster_key)
            return False

        # Cancel previous debounce task if waiting
        if cluster.debounce_task and not cluster.debounce_task.done():
            cluster.debounce_task.cancel()

        # Schedule debounce dispatch
        try:
            loop = asyncio.get_running_loop()
            cluster.debounce_task = loop.create_task(
                self._dispatch_cluster_dm(guild, cluster, state, detection_time)
            )
            return True
        except RuntimeError:
            return False

    async def _dispatch_cluster_dm(
        self,
        guild: discord.Guild,
        cluster: IncidentCluster,
        state: GuildSecurityConfig,
        detection_time: Optional[datetime] = None,
    ) -> None:
        """Executes actual DM transmission after debounce delay."""
        await asyncio.sleep(self.debounce_seconds)
        cluster.dispatched = True

        # Resolve recipients
        recipients: List[discord.abc.Messageable] = []
        seen_ids: Set[int] = set()

        def add_user(user: Any) -> None:
            if user and not getattr(user, "bot", False) and user.id not in seen_ids:
                if user.id == cluster.actor_id and user.id != getattr(guild, "owner_id", None):
                    return
                seen_ids.add(user.id)
                recipients.append(user)

        # 1. Guild Owner
        owner = getattr(guild, "owner", None)
        if not owner and hasattr(guild, "owner_id") and guild.owner_id:
            owner = guild.get_member(guild.owner_id)
        if owner:
            add_user(owner)

        # 2. Extra Owners
        for extra_id in state.extra_owners:
            extra_user = guild.get_member(extra_id)
            if extra_user:
                add_user(extra_user)

        if not recipients:
            return

        # Build consolidated alert embed
        action_count = len(cluster.actions)
        detected_at = detection_time or datetime.now(timezone.utc)
        ts_int = int(detected_at.timestamp())

        if action_count > 1:
            title = "🚨 ANTI-NUKE SECURITY ALERT · BLOCKED"
            desc = f"**Mass Raid Prevented** in **{guild.name}**\nNeutralized attacker after **{action_count}** destructive actions."
            actions_summary = "\n".join([f"• `{act}`: {t}" for act, t in cluster.actions[:5]])
            if action_count > 5:
                actions_summary += f"\n*...and {action_count - 5} more actions.*"
        else:
            first_act, first_target = cluster.actions[0] if cluster.actions else ("Security Violation", "Server")
            title = "🚨 ANTI-NUKE SECURITY ALERT · BLOCKED"
            desc = f"**{first_act}** in **{guild.name}**"
            actions_summary = f"Affected Target: **{first_target}**"

        # Modern Components V2 (CV2) Card
        cv2_view = None
        try:
            from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow, Button
            cv2_view = LayoutView(timeout=None)
            container = Container(accent_color=0xED4245)
            container.add_item(TextDisplay(f"### {ANIMATED_TICK} {title}"))
            container.add_item(Separator(visible=True))
            container.add_item(TextDisplay(
                f"**Guild:** {guild.name} (`{guild.id}`)\n"
                f"**Initiator:** **@{cluster.actor_name}** (`{cluster.actor_id}`)\n"
                f"**Containment:** `{cluster.punishment}`\n"
                f"**Reason:** `{cluster.reason or 'Unspecified Security Violation'}`"
            ))
            container.add_item(Separator(visible=True))
            container.add_item(TextDisplay(f"**Violations Blocked:**\n{actions_summary}"))
            container.add_item(TextDisplay(f"-# Incident detected at <t:{ts_int}:F> (<t:{ts_int}:R>)"))
            container.add_item(ActionRow(
                Button(
                    label="Server Security Dashboard",
                    url="https://discord.gg/YzHCx5yQXv",
                    style=discord.ButtonStyle.link,
                )
            ))
            cv2_view.add_item(container)
        except Exception as cv2_err:
            logger.debug("[V2DMDedup] Could not construct CV2 layout view: %s", cv2_err)
            cv2_view = None

        embed = discord.Embed(
            title=f"{ANIMATED_TICK} {title}",
            description=desc,
            color=0xED4245,
        )
        embed.add_field(
            name="Initiator",
            value=f"**{cluster.actor_name}**\nID: `{cluster.actor_id}`",
            inline=True
        )
        embed.add_field(
            name="Containment Outcome",
            value=f"**{cluster.punishment}**",
            inline=True
        )
        embed.add_field(
            name="Violations Detected",
            value=actions_summary,
            inline=False
        )
        if cluster.reason:
            embed.add_field(name="Reason Code", value=f"`{cluster.reason}`", inline=False)
        embed.add_field(
            name="Detection Time",
            value=f"<t:{ts_int}:F> · <t:{ts_int}:R>",
            inline=False
        )

        footer_icon = guild.icon.url if getattr(guild, "icon", None) else None
        embed.set_footer(text=f"YUNA Security V2 • {guild.name}", icon_url=footer_icon)

        # Dispatch with gentle pacing (capped at 10 recipients to respect rate limits)
        for admin in recipients[:10]:
            try:
                if cv2_view:
                    try:
                        await admin.send(view=cv2_view)
                    except Exception:
                        await admin.send(embed=embed)
                else:
                    await admin.send(embed=embed)
                if self.pacing_delay > 0:
                    await asyncio.sleep(self.pacing_delay)
            except (discord.Forbidden, discord.HTTPException):
                pass
            except Exception as e:
                logger.debug("[V2DMDedup] Could not DM user %s: %s", getattr(admin, "id", 0), e)


# ==============================================================================
# 4. MASTER NOTIFICATION COORDINATOR
# ==============================================================================

class V2Notifier:
    """Master coordinator dispatching log-channel embeds, DMs, and dashboard storage."""

    def __init__(
        self,
        db_path: str = "db/audit_logs.db",
        dashboard_queue: Optional[V2DashboardQueue] = None,
        channel_dispatcher: Optional[V2LogChannelDispatcher] = None,
        dm_deduplicator: Optional[V2DMDeduplicator] = None,
    ) -> None:
        self.dashboard_queue = dashboard_queue or V2DashboardQueue(db_path=db_path)
        self.channel_dispatcher = channel_dispatcher or V2LogChannelDispatcher()
        self.dm_deduplicator = dm_deduplicator or V2DMDeduplicator()
        self._started = False

    def start(self) -> None:
        """Starts worker tasks for dashboard queue."""
        if not self._started:
            self.dashboard_queue.start()
            self._started = True

    async def stop(self) -> None:
        """Drains and stops all background workers."""
        if self._started:
            await self.dashboard_queue.stop()
            self._started = False

    async def dispatch_incident(
        self,
        guild: discord.Guild,
        action: str,
        actor: Any,
        target: Any,
        result: ContainmentResult,
        decision: Decision,
        state: GuildSecurityConfig,
        details: Optional[str] = None,
        detection_time: Optional[datetime] = None,
    ) -> None:
        """Unified dispatch method called after emergency containment."""
        self.start()

        actor_name = getattr(actor, "display_name", getattr(actor, "name", str(getattr(actor, "id", 0))))
        punishment_str = (
            f"Banned offending account (@{actor_name})"
            if result.punishment == PunishmentType.BAN
            else f"Neutralized ({result.punishment.value if hasattr(result.punishment, 'value') else result.punishment})"
        )
        if not result.success:
            punishment_str = f"Attempted containment ({result.error_code or 'Failed'})"

        # 1. Background Dashboard Storage Queue (Non-blocking)
        self.dashboard_queue.enqueue_incident(
            guild_id=guild.id,
            action=action,
            actor=actor,
            target=target,
            action_taken=punishment_str,
            details=details or decision.reason_code,
            timestamp=detection_time.timestamp() if detection_time else time.time(),
        )

        # 2. Batched Log-Channel Embed
        log_channel = None
        if state.log_channel_id:
            log_channel = guild.get_channel(state.log_channel_id)

        if not log_channel:
            # Fallback search matching channels
            for ch in getattr(guild, "text_channels", []):
                if ch.name.lower() in ("yuna-antinuke", "antinuke-logs", "antinuke-log", "security-logs", "security-log"):
                    log_channel = ch
                    break

        if log_channel:
            embed = self.channel_dispatcher.build_security_embed(
                guild=guild,
                action=action,
                actor=actor,
                target=target,
                action_taken=punishment_str,
                details=details or decision.reason_code,
                detection_time=detection_time,
            )
            self.channel_dispatcher.enqueue_log(log_channel, embed)

        # 3. Deduplicated Incident DM Report
        if result.success and decision.is_punish:
            await self.dm_deduplicator.record_and_dispatch_dm(
                guild=guild,
                action=action,
                actor=actor,
                target=target,
                punishment=punishment_str,
                reason=decision.reason_code,
                state=state,
                detection_time=detection_time,
            )


v2_notifier = V2Notifier()
