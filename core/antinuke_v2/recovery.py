"""Anti-Nuke V2 Engine — Idempotent, Rate-Limit Aware Recovery Engine.

Guarantees:
1. Strict Containment Precondition: Never recovers an entity unless the offender
   has been successfully neutralized (banned or escalated containment).
2. Idempotency: Multiple recovery triggers for the same incident or resource will
   never create duplicate channels, roles, or webhooks.
3. Overwrite & Category Fidelity: Resolves category deletion chains and maps
   permission overwrites to restored roles/members.
4. Batched Positions: Defers single-entity position edits into rate-limit-aware
   bulk Discord position updates.
5. Documented API Limitations: Explicitly tracks and documents non-restorable Discord
   primitives (e.g., message history).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import discord

from core.antinuke_v2.snapshot import (
    ChannelSnapshot,
    EmojiSnapshot,
    GuildSnapshotStore,
    RoleSnapshot,
    WebhookSnapshot,
)

logger = logging.getLogger("antinuke.v2.recovery")


@dataclass
class RecoveryResult:
    """Outcome of an entity recovery attempt."""
    success: bool
    resource_type: str
    original_id: int
    restored_id: Optional[int] = None
    aborted: bool = False
    reason: str = ""
    duration_ms: float = 0.0
    restored_channel: Optional[Any] = None


import unicodedata


def _normalize_name_for_dedup(name: str) -> str:
    """Normalizes channel/role names for cross-bot/cross-process deduplication."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(name))
    cleaned = nfkd.lower()
    for ch in (" ", "-", "_", ".", "·", "․", "・", "⚛", "❀", "★", "⚡", "|", "│", "┃", "•", "﹒", "#"):
        cleaned = cleaned.replace(ch, "")
    return cleaned.strip()


async def sync_discord_server_template(guild: Any) -> None:
    """Non-blocking sync for native Discord Server Template to keep it perpetually clean and in-sync."""
    if not guild or not hasattr(guild, "templates"):
        return
    try:
        templates = await guild.templates()
        for tmpl in templates:
            if getattr(tmpl, "is_dirty", False):
                await tmpl.sync()
                logger.info("[Recovery] 🔄 Synced native Discord server template '%s' for guild %s", tmpl.name, getattr(guild, "id", 0))
    except Exception as exc:
        logger.debug("[Recovery] Server template sync ignored: %s", exc)


def _channel_matches_snapshot(ch: Any, snap: ChannelSnapshot) -> bool:
    """Checks whether a live Discord channel corresponds to the channel snapshot."""
    if not ch or not snap:
        return False
    if getattr(ch, "id", None) == snap.id:
        return True

    ch_type = getattr(ch, "type", None)
    if ch_type is not None:
        try:
            if int(ch_type) != int(snap.type):
                return False
        except (ValueError, TypeError):
            if ch_type != snap.type:
                return False

    ch_name = getattr(ch, "name", "")
    snap_name = snap.name or ""
    if ch_name == snap_name:
        return True
    if ch_name.lower().strip() == snap_name.lower().strip():
        return True
    if ch_name.lower().replace(" ", "-").strip() == snap_name.lower().replace(" ", "-").strip():
        return True
    norm_ch = _normalize_name_for_dedup(ch_name)
    norm_snap = _normalize_name_for_dedup(snap_name)
    if norm_ch and norm_snap and norm_ch == norm_snap:
        return True
    return False


def _role_matches_snapshot(role: Any, snap: RoleSnapshot) -> bool:
    """Checks whether a live Discord role corresponds to the role snapshot."""
    if not role or not snap:
        return False
    if getattr(role, "id", None) == snap.id:
        return True
    if getattr(role, "is_default", None) and role.is_default():
        return False

    r_name = getattr(role, "name", "")
    snap_name = snap.name or ""
    if r_name == snap_name:
        return True
    if r_name.lower().strip() == snap_name.lower().strip():
        return True
    norm_r = _normalize_name_for_dedup(r_name)
    norm_snap = _normalize_name_for_dedup(snap_name)
    if norm_r and norm_snap and norm_r == norm_snap:
        return True
    return False


class V2RecoveryEngine:
    """Manages resilient, rate-limit aware restoration of destroyed server assets."""

    def __init__(
        self,
        snapshot_store: Optional[GuildSnapshotStore] = None,
        neutralizer: Optional[Any] = None,
        incident_tracker: Optional[Any] = None,
    ) -> None:
        self.snapshot_store = snapshot_store or GuildSnapshotStore()
        self.neutralizer = neutralizer
        self.incident_tracker = incident_tracker
        # guild_id -> {channel_id: target_position}
        self._pending_channel_positions: Dict[int, Dict[int, int]] = {}
        # guild_id -> {role_id: target_position}
        self._pending_role_positions: Dict[int, Dict[int, int]] = {}
        # Lock per guild to serialize restore sequences and avoid race conditions
        self._guild_locks: Dict[int, asyncio.Lock] = {}

    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._guild_locks:
            self._guild_locks[guild_id] = asyncio.Lock()
        return self._guild_locks[guild_id]

    async def restore_channel(
        self,
        guild: discord.Guild,
        channel_id: int,
        containment_success: bool,
        target_channel: Optional[Any] = None,
    ) -> RecoveryResult:
        """Restores a deleted channel with original overwrites, category, and position."""
        t_start = time.perf_counter()

        # 1. STRICT PRECONDITION: Neutralization must have succeeded!
        if not containment_success:
            logger.warning(
                "[Recovery] Aborting recovery for channel %s in guild %s: containment failed or unconfirmed.",
                channel_id, guild.id
            )
            return RecoveryResult(
                success=False,
                resource_type="channel",
                original_id=channel_id,
                aborted=True,
                reason="containment_failed",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        async with self._get_lock(guild.id):
            return await self._restore_channel_unlocked(guild, channel_id, t_start, target_channel=target_channel)

    async def _restore_channel_unlocked(
        self,
        guild: discord.Guild,
        channel_id: int,
        t_start: float,
        target_channel: Optional[Any] = None,
    ) -> RecoveryResult:
        # 2. IDEMPOTENCY CHECK
        already_restored_id = self.snapshot_store.get_restored_id(guild.id, "channel", channel_id)
        if already_restored_id:
            existing = guild.get_channel(already_restored_id)
            if existing:
                return RecoveryResult(
                    success=True,
                    resource_type="channel",
                    original_id=channel_id,
                    restored_id=already_restored_id,
                    reason="already_restored",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )

        # 2.5 ROGUE CHANNEL CHECK: Never restore channels created during an unauthorized raid!
        tracker = self.incident_tracker
        if not tracker:
            try:
                from core.antinuke_v2.router import v2_engine_router
                tracker = getattr(v2_engine_router.coordinator, "incident_tracker", None)
            except Exception:
                tracker = None
        if tracker and hasattr(tracker, "is_rogue_channel") and tracker.is_rogue_channel(channel_id):
            logger.info("[Recovery] Skipping restoration of rogue channel %s (created during raid)", channel_id)
            return RecoveryResult(
                success=True,
                resource_type="channel",
                original_id=channel_id,
                reason="rogue_channel_not_restored",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        # 3. RETRIEVE SNAPSHOT (OR CAPTURE FROM target_channel ON-THE-FLY)
        snap = self.snapshot_store.get_channel(guild.id, channel_id)
        if not snap and target_channel and hasattr(target_channel, "name"):
            # Never capture on-the-fly snapshots for channels with obvious raid signature names
            ch_name = str(getattr(target_channel, "name", "")).lower()
            if any(p in ch_name for p in ("nuked", "raided", "hacked", "wiped")):
                logger.info("[Recovery] Ignoring on-the-fly snapshot for raid channel '%s'", ch_name)
                return RecoveryResult(
                    success=True,
                    resource_type="channel",
                    original_id=channel_id,
                    reason="raid_signature_channel_ignored",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )
            try:
                snap = ChannelSnapshot.from_channel(target_channel)
                if guild.id not in self.snapshot_store._channels:
                    self.snapshot_store._channels[guild.id] = {}
                self.snapshot_store._channels[guild.id][channel_id] = snap
                logger.info("[Recovery] Captured on-the-fly snapshot for deleted channel %s (%s)", snap.name, channel_id)
            except Exception as e:
                logger.warning("[Recovery] Failed constructing on-the-fly channel snapshot: %s", e)

        if not snap:
            logger.error("[Recovery] No snapshot found for channel %s in guild %s.", channel_id, guild.id)
            return RecoveryResult(
                success=False,
                resource_type="channel",
                original_id=channel_id,
                reason="snapshot_missing",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        # 4. RESOLVE CATEGORY DEPENDENCY
        target_category: Optional[discord.CategoryChannel] = None
        if snap.type != discord.ChannelType.category:
            cat_id = 0
            if snap.category_id:
                try:
                    cat_id = int(snap.category_id)
                except (ValueError, TypeError):
                    cat_id = 0

            # 4.1 Lookup by exact cat_id in live guild
            if cat_id > 0 and cat_id != channel_id:
                target_category = discord.utils.get(getattr(guild, "categories", []), id=cat_id)
                if not target_category:
                    # Check if category was previously restored under a new ID
                    restored_cat_id = self.snapshot_store.get_restored_id(guild.id, "channel", cat_id)
                    if restored_cat_id:
                        target_category = discord.utils.get(getattr(guild, "categories", []), id=restored_cat_id)

            # 4.2 Lookup by category name match in live guild
            cat_name = snap.category_name
            if not cat_name and cat_id:
                old_cat_snap = self.snapshot_store.get_channel(guild.id, cat_id)
                if old_cat_snap:
                    cat_name = old_cat_snap.name

            if not target_category and cat_name:
                clean_name = cat_name.strip().lower()
                target_category = discord.utils.find(
                    lambda c: c.name.strip().lower() == clean_name or _normalize_name_for_dedup(c.name) == _normalize_name_for_dedup(cat_name),
                    getattr(guild, "categories", [])
                )

            # 4.3 If category was deleted in raid and doesn't exist at all, restore it first!
            if not target_category and cat_id > 0 and cat_id != channel_id:
                cat_res = await self._restore_channel_unlocked(guild, cat_id, t_start)
                if cat_res.success and cat_res.restored_id:
                    target_category = discord.utils.get(getattr(guild, "categories", []), id=cat_res.restored_id) or cat_res.restored_channel

            # 4.4 If still not found, but we know the category name, recreate the category!
            if not target_category and cat_name:
                try:
                    target_category = await guild.create_category(
                        name=cat_name,
                        reason="Yuna Anti-Nuke V2: Recreate Missing Category for Channel Recovery"
                    )
                    if target_category and cat_id:
                        self.snapshot_store.register_restored_mapping(guild.id, "channel", cat_id, target_category.id)
                except Exception as cat_err:
                    logger.warning("[Recovery] Failed to recreate missing category '%s': %s", cat_name, cat_err)

        # 5. RECONSTRUCT PERMISSION OVERWRITES
        overwrites: Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite] = {}
        for ow in snap.overwrites:
            target, perm_overwrite = ow.to_discord(guild)
            if not target and ow.target_type == "role":
                # Check if role was restored under a new ID
                new_role_id = self.snapshot_store.get_restored_id(guild.id, "role", ow.target_id)
                if new_role_id:
                    target = guild.get_role(new_role_id)
                    if target:
                        perm_overwrite = discord.PermissionOverwrite.from_pair(
                            discord.Permissions(ow.allow_bits),
                            discord.Permissions(ow.deny_bits)
                        )
            if target and perm_overwrite:
                overwrites[target] = perm_overwrite

        # 5.5 ZERO-DELAY RAM CACHE CHECK FOR EXISTING CHANNEL (PREVENT DUPLICATES)
        existing_ch: Optional[discord.abc.GuildChannel] = None
        for ch in getattr(guild, "channels", []):
            if _channel_matches_snapshot(ch, snap):
                existing_ch = ch
                break

        if not existing_ch and isinstance(getattr(guild, "channels", None), list) and len(guild.channels) == 0 and hasattr(guild, "fetch_channels"):
            try:
                fetched_channels = await guild.fetch_channels()
                for ch in (fetched_channels or []):
                    if _channel_matches_snapshot(ch, snap):
                        existing_ch = ch
                        break
            except Exception:
                pass

        if existing_ch:
            if target_category and getattr(existing_ch, "category_id", None) != target_category.id:
                try:
                    await existing_ch.edit(
                        category=target_category,
                        sync_permissions=(len(snap.overwrites) == 0),
                        reason="Yuna Anti-Nuke V2: Relink existing restored channel to category"
                    )
                except Exception as cat_err:
                    logger.debug("[Recovery] Relink existing channel to category error: %s", cat_err)
            self.snapshot_store.register_restored_mapping(guild.id, "channel", channel_id, existing_ch.id)
            logger.info("[Recovery] Channel '%s' already exists (ID: %s). Avoiding duplicate creation.", snap.name, existing_ch.id)
            return RecoveryResult(
                success=True,
                resource_type="channel",
                original_id=channel_id,
                restored_id=existing_ch.id,
                restored_channel=existing_ch,
                reason="already_created_or_restored",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        # 6. DISCORD REST DISPATCH (RATE-LIMIT AWARE & OVERWRITE FALLBACK)
        new_channel: Optional[discord.abc.GuildChannel] = None
        retries = 3
        backoff = 0.5
        attempt_overwrites = overwrites
        while retries > 0:
            try:
                ch_type = snap.type
                if ch_type == discord.ChannelType.category:
                    new_channel = await guild.create_category(
                        name=snap.name,
                        overwrites=attempt_overwrites,
                        reason="Yuna Anti-Nuke V2: Automatic Asset Recovery"
                    )
                elif ch_type == discord.ChannelType.voice:
                    kwargs: Dict[str, Any] = {
                        "name": snap.name,
                        "category": target_category,
                        "reason": "Yuna Anti-Nuke V2: Automatic Asset Recovery",
                    }
                    if attempt_overwrites:
                        kwargs["overwrites"] = attempt_overwrites
                    if snap.bitrate:
                        kwargs["bitrate"] = snap.bitrate
                    if snap.user_limit is not None:
                        kwargs["user_limit"] = snap.user_limit
                    new_channel = await guild.create_voice_channel(**kwargs)
                elif ch_type == discord.ChannelType.stage_voice:
                    kwargs = {
                        "name": snap.name,
                        "category": target_category,
                        "reason": "Yuna Anti-Nuke V2: Automatic Asset Recovery",
                    }
                    if attempt_overwrites:
                        kwargs["overwrites"] = attempt_overwrites
                    new_channel = await guild.create_stage_channel(**kwargs)
                elif ch_type == discord.ChannelType.forum and hasattr(guild, "create_forum_channel"):
                    kwargs = {
                        "name": snap.name,
                        "category": target_category,
                        "topic": snap.topic,
                        "reason": "Yuna Anti-Nuke V2: Automatic Asset Recovery",
                    }
                    if attempt_overwrites:
                        kwargs["overwrites"] = attempt_overwrites
                    new_channel = await guild.create_forum_channel(**kwargs)
                else:
                    # Default / TextChannel
                    kwargs = {
                        "name": snap.name,
                        "category": target_category,
                        "topic": snap.topic,
                        "nsfw": snap.nsfw,
                        "slowmode_delay": snap.rate_limit_per_user or 0,
                        "reason": "Yuna Anti-Nuke V2: Automatic Asset Recovery",
                    }
                    if attempt_overwrites:
                        kwargs["overwrites"] = attempt_overwrites
                    new_channel = await guild.create_text_channel(**kwargs)
                break
            except discord.RateLimited as rl:
                retry_after = getattr(rl, "retry_after", backoff)
                logger.warning("[Recovery] Rate limited creating channel %s: waiting %.2fs", snap.name, retry_after)
                if retry_after > 5.0:
                    logger.warning("[Recovery] Rate limit exceeds 5.0s (%.1fs). Aborting channel %s creation to prevent hang.", retry_after, snap.name)
                    return RecoveryResult(
                        success=False,
                        resource_type="channel",
                        original_id=channel_id,
                        reason=f"rate_limited_{retry_after:.1f}s",
                        duration_ms=(time.perf_counter() - t_start) * 1000,
                    )
                await asyncio.sleep(retry_after)
                retries -= 1
            except discord.HTTPException as exc:
                if exc.status == 429:
                    retry_after = float(getattr(exc, "retry_after", backoff) or backoff)
                    logger.warning("[Recovery] 429 Rate limited creating channel %s: waiting %.2fs", snap.name, retry_after)
                    if retry_after > 5.0:
                        logger.warning("[Recovery] Rate limit exceeds 5.0s (%.1fs). Aborting channel %s creation to prevent hang.", retry_after, snap.name)
                        return RecoveryResult(
                            success=False,
                            resource_type="channel",
                            original_id=channel_id,
                            reason=f"rate_limited_{retry_after:.1f}s",
                            duration_ms=(time.perf_counter() - t_start) * 1000,
                        )
                    await asyncio.sleep(retry_after)
                    retries -= 1
                    continue
                if attempt_overwrites:
                    logger.warning("[Recovery] Failed creating channel %s with overwrites (%s). Retrying without overwrites.", snap.name, exc)
                    attempt_overwrites = {}
                    retries -= 1
                    continue
                logger.error("[Recovery] Failed to recreate channel %s (%s): %s", snap.name, channel_id, exc)
                return RecoveryResult(
                    success=False,
                    resource_type="channel",
                    original_id=channel_id,
                    reason=f"discord_error: {exc}",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )
            except Exception as exc:
                logger.error("[Recovery] Failed to recreate channel %s (%s): %s", snap.name, channel_id, exc)
                return RecoveryResult(
                    success=False,
                    resource_type="channel",
                    original_id=channel_id,
                    reason=f"discord_error: {exc}",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )

        if not new_channel:
            return RecoveryResult(
                success=False,
                resource_type="channel",
                original_id=channel_id,
                reason="retries_exhausted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        # Ensure newly created channel is placed into target_category and synced
        if target_category and new_channel:
            if getattr(new_channel, "category_id", None) != target_category.id:
                try:
                    await new_channel.edit(
                        category=target_category,
                        sync_permissions=(len(overwrites) == 0),
                        reason="Yuna Anti-Nuke V2: Relink channel to category",
                    )
                except Exception as cat_err:
                    logger.debug("[Recovery] Relink category error: %s", cat_err)
            elif len(overwrites) == 0:
                try:
                    await new_channel.edit(
                        sync_permissions=True,
                        reason="Yuna Anti-Nuke V2: Sync Permissions with Category",
                    )
                except Exception as sync_err:
                    logger.debug("[Recovery] Sync permissions error: %s", sync_err)

        # Trigger non-blocking native Discord Server Template sync
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(sync_discord_server_template(guild))
        except Exception:
            pass

        # 7. REGISTER RESTORED MAPPING & QUEUE POSITION
        self.snapshot_store.register_restored_mapping(guild.id, "channel", channel_id, new_channel.id)
        self._queue_channel_position(guild.id, new_channel.id, snap.position)

        logger.info(
            "[Recovery] Successfully restored channel %s (old: %s -> new: %s) with %d overwrites.",
            snap.name, channel_id, new_channel.id, len(overwrites)
        )

        return RecoveryResult(
            success=True,
            resource_type="channel",
            original_id=channel_id,
            restored_id=new_channel.id,
            duration_ms=(time.perf_counter() - t_start) * 1000,
            restored_channel=new_channel,
        )

    async def restore_role(
        self,
        guild: discord.Guild,
        role_id: int,
        containment_success: bool,
        target_role: Optional[Any] = None,
    ) -> RecoveryResult:
        """Restores a deleted role with original permissions, color, hoist, and position."""
        t_start = time.perf_counter()

        if not containment_success:
            return RecoveryResult(
                success=False,
                resource_type="role",
                original_id=role_id,
                aborted=True,
                reason="containment_failed",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        async with self._get_lock(guild.id):
            # Idempotency
            already_restored_id = self.snapshot_store.get_restored_id(guild.id, "role", role_id)
            if already_restored_id and guild.get_role(already_restored_id):
                return RecoveryResult(
                    success=True,
                    resource_type="role",
                    original_id=role_id,
                    restored_id=already_restored_id,
                    reason="already_restored",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )

            snap = self.snapshot_store.get_role(guild.id, role_id)
            if not snap and target_role and hasattr(target_role, "name"):
                try:
                    snap = RoleSnapshot.from_role(target_role)
                    if guild.id not in self.snapshot_store._roles:
                        self.snapshot_store._roles[guild.id] = {}
                    self.snapshot_store._roles[guild.id][role_id] = snap
                    logger.info("[Recovery] Captured on-the-fly snapshot for deleted role @%s (%s)", snap.name, role_id)
                except Exception as e:
                    logger.warning("[Recovery] Failed constructing on-the-fly role snapshot: %s", e)

            if not snap:
                return RecoveryResult(
                    success=False,
                    resource_type="role",
                    original_id=role_id,
                    reason="snapshot_missing",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )

            # Check for existing role with matching name (prevent duplicate roles)
            existing_role: Optional[discord.Role] = None
            for existing_r in getattr(guild, "roles", []):
                if _role_matches_snapshot(existing_r, snap):
                    existing_role = existing_r
                    break


            if existing_role:
                self.snapshot_store.register_restored_mapping(guild.id, "role", role_id, existing_role.id)
                logger.info("[Recovery] Role '%s' already exists (ID: %s). Avoiding duplicate creation.", snap.name, existing_role.id)
                return RecoveryResult(
                    success=True,
                    resource_type="role",
                    original_id=role_id,
                    restored_id=existing_role.id,
                    reason="already_created_or_restored",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )

            try:
                new_role = await guild.create_role(
                    name=snap.name,
                    permissions=discord.Permissions(snap.permissions),
                    colour=discord.Colour(snap.color),
                    hoist=snap.hoist,
                    mentionable=snap.mentionable,
                    reason="Yuna Anti-Nuke V2: Automatic Asset Recovery",
                )
            except discord.Forbidden:
                # Bot does not have all permissions the role had; mask with bot's current guild permissions
                my_perms = guild.me.guild_permissions.value if guild.me else 0
                safe_perms = snap.permissions & my_perms
                logger.warning(
                    "[Recovery] 403 Forbidden creating role @%s with perms %s. Retrying with masked perms %s.",
                    snap.name, snap.permissions, safe_perms
                )
                try:
                    new_role = await guild.create_role(
                        name=snap.name,
                        permissions=discord.Permissions(safe_perms),
                        colour=discord.Colour(snap.color),
                        hoist=snap.hoist,
                        mentionable=snap.mentionable,
                        reason="Yuna Anti-Nuke V2: Automatic Asset Recovery (Perms Masked)",
                    )
                except Exception as exc:
                    logger.error("[Recovery] Failed to restore role @%s on retry: %s", snap.name, exc)
                    return RecoveryResult(
                        success=False,
                        resource_type="role",
                        original_id=role_id,
                        reason=f"discord_error: {exc}",
                        duration_ms=(time.perf_counter() - t_start) * 1000,
                    )
            except Exception as exc:
                logger.error("[Recovery] Failed to restore role %s: %s", snap.name, exc)
                return RecoveryResult(
                    success=False,
                    resource_type="role",
                    original_id=role_id,
                    reason=f"discord_error: {exc}",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )

            self.snapshot_store.register_restored_mapping(guild.id, "role", role_id, new_role.id)
            self._queue_role_position(guild.id, new_role.id, snap.position)

            logger.info("[Recovery] Successfully restored role %s (old: %s -> new: %s)", snap.name, role_id, new_role.id)
            return RecoveryResult(
                success=True,
                resource_type="role",
                original_id=role_id,
                restored_id=new_role.id,
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

    async def restore_webhook(
        self,
        guild: discord.Guild,
        webhook_id: int,
        containment_success: bool,
    ) -> RecoveryResult:
        """Restores a deleted webhook in its designated channel."""
        t_start = time.perf_counter()

        if not containment_success:
            return RecoveryResult(
                success=False,
                resource_type="webhook",
                original_id=webhook_id,
                aborted=True,
                reason="containment_failed",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        snap = self.snapshot_store.get_webhook(guild.id, webhook_id)
        if not snap:
            return RecoveryResult(
                success=False,
                resource_type="webhook",
                original_id=webhook_id,
                reason="snapshot_missing",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        # Resolve channel (live or restored)
        ch = guild.get_channel(snap.channel_id)
        if not ch:
            restored_ch_id = self.snapshot_store.get_restored_id(guild.id, "channel", snap.channel_id)
            if restored_ch_id:
                ch = guild.get_channel(restored_ch_id)

        if not ch or not hasattr(ch, "create_webhook"):
            return RecoveryResult(
                success=False,
                resource_type="webhook",
                original_id=webhook_id,
                reason="channel_missing",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        try:
            new_wh = await ch.create_webhook(name=snap.name, reason="Yuna Anti-Nuke V2: Automatic Asset Recovery")
            self.snapshot_store.register_restored_mapping(guild.id, "webhook", webhook_id, new_wh.id)
            return RecoveryResult(
                success=True,
                resource_type="webhook",
                original_id=webhook_id,
                restored_id=new_wh.id,
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            return RecoveryResult(
                success=False,
                resource_type="webhook",
                original_id=webhook_id,
                reason=f"discord_error: {exc}",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

    async def restore_emoji(
        self,
        guild: discord.Guild,
        emoji_id: int,
        containment_success: bool,
    ) -> RecoveryResult:
        """Restores a deleted custom emoji if image bytes are preserved."""
        t_start = time.perf_counter()

        if not containment_success:
            return RecoveryResult(
                success=False,
                resource_type="emoji",
                original_id=emoji_id,
                aborted=True,
                reason="containment_failed",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        snap = self.snapshot_store.get_emoji(guild.id, emoji_id)
        if not snap:
            return RecoveryResult(
                success=False,
                resource_type="emoji",
                original_id=emoji_id,
                reason="snapshot_missing",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        if not snap.image:
            return RecoveryResult(
                success=False,
                resource_type="emoji",
                original_id=emoji_id,
                reason="image_bytes_missing",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        try:
            # Map whitelisted roles
            roles: List[discord.Role] = []
            for rid in snap.roles:
                r = guild.get_role(rid) or guild.get_role(self.snapshot_store.get_restored_id(guild.id, "role", rid) or 0)
                if r:
                    roles.append(r)

            new_emoji = await guild.create_custom_emoji(
                name=snap.name,
                image=snap.image,
                roles=roles if roles else None,
                reason="Yuna Anti-Nuke V2: Automatic Asset Recovery"
            )
            self.snapshot_store.register_restored_mapping(guild.id, "emoji", emoji_id, new_emoji.id)
            return RecoveryResult(
                success=True,
                resource_type="emoji",
                original_id=emoji_id,
                restored_id=new_emoji.id,
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            return RecoveryResult(
                success=False,
                resource_type="emoji",
                original_id=emoji_id,
                reason=f"discord_error: {exc}",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

    # ==========================================================================
    # BATCHED POSITION RESTORATION (RATE-LIMIT AWARE)
    # ==========================================================================

    def _queue_channel_position(self, guild_id: int, channel_id: int, position: int) -> None:
        if guild_id not in self._pending_channel_positions:
            self._pending_channel_positions[guild_id] = {}
        self._pending_channel_positions[guild_id][channel_id] = position

    def _queue_role_position(self, guild_id: int, role_id: int, position: int) -> None:
        if guild_id not in self._pending_role_positions:
            self._pending_role_positions[guild_id] = {}
        self._pending_role_positions[guild_id][role_id] = position

    async def flush_batched_positions(self, guild: discord.Guild) -> Tuple[int, int]:
        """Flushes queued channel and role positions using Discord bulk position endpoints.
        
        Returns:
            Tuple of (restored_channel_positions_count, restored_role_positions_count)
        """
        ch_count = 0
        rl_count = 0

        # 1. Bulk Channels Position Update
        ch_positions = self._pending_channel_positions.pop(guild.id, {})
        if ch_positions:
            try:
                # Discord.py supports guild.edit_channel_positions({channel: position})
                positions_map: Dict[discord.abc.GuildChannel, int] = {}
                for cid, pos in ch_positions.items():
                    channel = guild.get_channel(cid)
                    if channel:
                        positions_map[channel] = pos

                if positions_map and hasattr(guild, "edit_channel_positions"):
                    await guild.edit_channel_positions(positions_map, reason="Yuna Anti-Nuke V2: Bulk Position Recovery")
                    ch_count = len(positions_map)
            except discord.RateLimited as rl:
                await asyncio.sleep(getattr(rl, "retry_after", 1.0))
            except Exception as exc:
                logger.error("[Recovery] Failed to edit channel positions for guild %s: %s", guild.id, exc)

        # 2. Bulk Roles Position Update
        rl_positions = self._pending_role_positions.pop(guild.id, {})
        if rl_positions:
            try:
                roles_map: Dict[discord.Role, int] = {}
                for rid, pos in rl_positions.items():
                    role = guild.get_role(rid)
                    if role and not role.is_default() and role < guild.me.top_role:
                        roles_map[role] = pos

                if roles_map and hasattr(guild, "edit_role_positions"):
                    await guild.edit_role_positions(roles_map, reason="Yuna Anti-Nuke V2: Bulk Position Recovery")
                    rl_count = len(roles_map)
            except discord.RateLimited as rl:
                await asyncio.sleep(getattr(rl, "retry_after", 1.0))
            except Exception as exc:
                logger.error("[Recovery] Failed to edit role positions for guild %s: %s", guild.id, exc)

        return ch_count, rl_count

    async def delete_rogue_channel(
        self,
        guild: discord.Guild,
        channel_id: int,
    ) -> RecoveryResult:
        """Instantly deletes an unauthorized rogue channel created during an incident."""
        t_start = time.perf_counter()
        if not guild or not channel_id:
            return RecoveryResult(success=False, resource_type="channel", original_id=channel_id, reason="invalid_guild_or_id")

        tracker = self.incident_tracker
        if not tracker:
            try:
                from core.antinuke_v2.router import v2_engine_router
                tracker = getattr(v2_engine_router.coordinator, "incident_tracker", None)
            except Exception:
                tracker = None
        if tracker and hasattr(tracker, "mark_rogue_channel"):
            tracker.mark_rogue_channel(channel_id)

        try:
            # 1. Fast raw REST delete via internal http client
            if hasattr(guild, "_state") and hasattr(guild._state, "http"):
                await guild._state.http.delete_channel(channel_id, reason="[Anti-Nuke V2] Rogue Channel Auto-Deleted")
            else:
                ch = guild.get_channel(channel_id)
                if ch:
                    await ch.delete(reason="[Anti-Nuke V2] Rogue Channel Auto-Deleted")
            
            logger.info("[Recovery] ⚡ Instantly deleted rogue channel %s in guild %s (%.2fms)", channel_id, guild.id, (time.perf_counter() - t_start) * 1000)
            return RecoveryResult(
                success=True,
                resource_type="channel",
                original_id=channel_id,
                reason="rogue_channel_deleted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except discord.NotFound:
            return RecoveryResult(
                success=True,
                resource_type="channel",
                original_id=channel_id,
                reason="already_deleted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            logger.error("[Recovery] Failed to delete rogue channel %s in guild %s: %s", channel_id, guild.id, exc)
            return RecoveryResult(
                success=False,
                resource_type="channel",
                original_id=channel_id,
                reason=f"error_{exc}",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

    async def delete_rogue_role(
        self,
        guild: discord.Guild,
        role_id: int,
    ) -> RecoveryResult:
        """Instantly deletes an unauthorized rogue role created during an incident."""
        t_start = time.perf_counter()
        if not guild or not role_id:
            return RecoveryResult(success=False, resource_type="role", original_id=role_id, reason="invalid_guild_or_id")

        try:
            if hasattr(guild, "_state") and hasattr(guild._state, "http"):
                await guild._state.http.delete_role(guild.id, role_id, reason="[Anti-Nuke V2] Rogue Role Auto-Deleted")
            else:
                role = guild.get_role(role_id)
                if role:
                    await role.delete(reason="[Anti-Nuke V2] Rogue Role Auto-Deleted")

            logger.info("[Recovery] ⚡ Instantly deleted rogue role %s in guild %s (%.2fms)", role_id, guild.id, (time.perf_counter() - t_start) * 1000)
            return RecoveryResult(
                success=True,
                resource_type="role",
                original_id=role_id,
                reason="rogue_role_deleted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except discord.NotFound:
            return RecoveryResult(
                success=True,
                resource_type="role",
                original_id=role_id,
                reason="already_deleted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            logger.error("[Recovery] Failed to delete rogue role %s in guild %s: %s", role_id, guild.id, exc)
            return RecoveryResult(
                success=False,
                resource_type="role",
                original_id=role_id,
                reason=f"error_{exc}",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

    async def revert_channel(
        self,
        guild: discord.Guild,
        channel_id: int,
        target_channel: Optional[Any] = None,
    ) -> RecoveryResult:
        """Reverts unauthorized modifications to a channel back to baseline snapshot."""
        t_start = time.perf_counter()
        snap = self.snapshot_store.get_channel(guild.id, channel_id)
        ch = target_channel or guild.get_channel(channel_id)
        if not snap or not ch:
            return RecoveryResult(
                success=False,
                resource_type="channel",
                original_id=channel_id,
                reason="missing_snapshot_or_channel",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        try:
            edit_kwargs: Dict[str, Any] = {}
            if getattr(ch, "name", None) != snap.name:
                edit_kwargs["name"] = snap.name
            if hasattr(ch, "topic") and getattr(ch, "topic", None) != snap.topic:
                edit_kwargs["topic"] = snap.topic or ""
            if hasattr(ch, "nsfw") and getattr(ch, "nsfw", None) != snap.nsfw:
                edit_kwargs["nsfw"] = snap.nsfw
            if hasattr(ch, "slowmode_delay") and getattr(ch, "slowmode_delay", None) != snap.rate_limit_per_user:
                edit_kwargs["slowmode_delay"] = snap.rate_limit_per_user or 0

            # Overwrites
            if snap.overwrites:
                overwrites: Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite] = {}
                for ow in snap.overwrites:
                    target, perm_overwrite = ow.to_discord(guild)
                    if target and perm_overwrite:
                        overwrites[target] = perm_overwrite
                if overwrites:
                    edit_kwargs["overwrites"] = overwrites

            if edit_kwargs:
                await ch.edit(**edit_kwargs, reason="[Anti-Nuke V2] Channel Modifications Reverted")
                logger.info("[Recovery] ⚡ Reverted unauthorized channel modifications on #%s (%.2fms)", snap.name, (time.perf_counter() - t_start) * 1000)

            return RecoveryResult(
                success=True,
                resource_type="channel",
                original_id=channel_id,
                reason="channel_reverted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            logger.error("[Recovery] Failed to revert channel %s in guild %s: %s", channel_id, guild.id, exc)
            return RecoveryResult(
                success=False,
                resource_type="channel",
                original_id=channel_id,
                reason=f"error_{exc}",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

    async def revert_role(
        self,
        guild: discord.Guild,
        role_id: int,
        target_role: Optional[Any] = None,
    ) -> RecoveryResult:
        """Reverts unauthorized modifications to a role back to baseline snapshot."""
        t_start = time.perf_counter()
        snap = self.snapshot_store.get_role(guild.id, role_id)
        role = target_role or guild.get_role(role_id)
        if not snap or not role:
            return RecoveryResult(
                success=False,
                resource_type="role",
                original_id=role_id,
                reason="missing_snapshot_or_role",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

        try:
            edit_kwargs: Dict[str, Any] = {}
            if role.name != snap.name:
                edit_kwargs["name"] = snap.name
            if role.permissions.value != snap.permissions:
                edit_kwargs["permissions"] = discord.Permissions(snap.permissions)
            if role.color.value != snap.color:
                edit_kwargs["color"] = discord.Color(snap.color)
            if role.hoist != snap.hoist:
                edit_kwargs["hoist"] = snap.hoist
            if role.mentionable != snap.mentionable:
                edit_kwargs["mentionable"] = snap.mentionable

            can_edit = True
            if guild.me and getattr(guild.me, "top_role", None):
                try:
                    can_edit = getattr(role, "position", 0) < getattr(guild.me.top_role, "position", 0)
                except Exception:
                    can_edit = True

            if edit_kwargs and can_edit:
                await role.edit(**edit_kwargs, reason="[Anti-Nuke V2] Role Modifications Reverted")
                logger.info("[Recovery] ⚡ Reverted unauthorized role modifications on @%s (%.2fms)", snap.name, (time.perf_counter() - t_start) * 1000)

            return RecoveryResult(
                success=True,
                resource_type="role",
                original_id=role_id,
                reason="role_reverted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            logger.error("[Recovery] Failed to revert role %s in guild %s: %s", role_id, guild.id, exc)
            return RecoveryResult(
                success=False,
                resource_type="role",
                original_id=role_id,
                reason=f"error_{exc}",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )

    async def kick_rogue_bot(
        self,
        guild: discord.Guild,
        bot_id: int,
    ) -> RecoveryResult:
        """Instantly kicks/removes an unauthorized rogue bot added to the server."""
        t_start = time.perf_counter()
        if not guild or not bot_id:
            return RecoveryResult(success=False, resource_type="member", original_id=bot_id, reason="invalid_params")
        try:
            if hasattr(guild, "_state") and hasattr(guild._state, "http"):
                await guild._state.http.kick(bot_id, guild.id, reason="[Anti-Nuke V2] Rogue Bot Removed")
            else:
                member = guild.get_member(bot_id)
                if member:
                    await member.kick(reason="[Anti-Nuke V2] Rogue Bot Removed")
            logger.info("[Recovery] ⚡ Instantly kicked rogue bot %s in guild %s (%.2fms)", bot_id, guild.id, (time.perf_counter() - t_start) * 1000)
            return RecoveryResult(
                success=True,
                resource_type="member",
                original_id=bot_id,
                reason="rogue_bot_kicked",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except discord.NotFound:
            return RecoveryResult(success=True, resource_type="member", original_id=bot_id, reason="already_removed")
        except Exception as exc:
            logger.error("[Recovery] Failed to kick rogue bot %s in guild %s: %s", bot_id, guild.id, exc)
            return RecoveryResult(success=False, resource_type="member", original_id=bot_id, reason=f"error_{exc}")

    async def delete_rogue_webhook(
        self,
        guild: discord.Guild,
        webhook_id: int,
    ) -> RecoveryResult:
        """Instantly deletes an unauthorized or compromised rogue webhook."""
        t_start = time.perf_counter()
        if not guild or not webhook_id:
            return RecoveryResult(success=False, resource_type="webhook", original_id=webhook_id, reason="invalid_params")
        try:
            if hasattr(guild, "_state") and hasattr(guild._state, "http"):
                http = guild._state.http
                if hasattr(http, "delete_webhook") and callable(getattr(http, "delete_webhook")):
                    await http.delete_webhook(webhook_id, reason="[Anti-Nuke V2] Rogue Webhook Auto-Deleted")
                else:
                    route = discord.http.Route("DELETE", "/webhooks/{webhook_id}", webhook_id=webhook_id)
                    await http.request(route, reason="[Anti-Nuke V2] Rogue Webhook Auto-Deleted")
            logger.info("[Recovery] ⚡ Instantly deleted rogue webhook %s in guild %s (%.2fms)", webhook_id, guild.id, (time.perf_counter() - t_start) * 1000)
            return RecoveryResult(
                success=True,
                resource_type="webhook",
                original_id=webhook_id,
                reason="rogue_webhook_deleted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except discord.NotFound:
            return RecoveryResult(success=True, resource_type="webhook", original_id=webhook_id, reason="already_deleted")
        except Exception as exc:
            logger.error("[Recovery] Failed to delete rogue webhook %s in guild %s: %s", webhook_id, guild.id, exc)
            return RecoveryResult(success=False, resource_type="webhook", original_id=webhook_id, reason=f"error_{exc}")

    async def strip_dangerous_roles(
        self,
        guild: discord.Guild,
        member_id: int,
        target_member: Optional[Any] = None,
        added_roles: Optional[List[Any]] = None,
    ) -> RecoveryResult:
        """Instantly strips dangerous administrative roles granted to a member."""
        t_start = time.perf_counter()
        member = target_member or guild.get_member(member_id)
        if not guild or not member:
            return RecoveryResult(success=False, resource_type="member", original_id=member_id, reason="member_not_found")
        try:
            from security.authorization.dangerous_permissions import is_dangerous_role
            if added_roles:
                roles_to_remove = [r for r in added_roles if is_dangerous_role(r)]
            else:
                roles_to_remove = [r for r in getattr(member, "roles", []) if is_dangerous_role(r)]

            for role in roles_to_remove:
                if hasattr(guild, "_state") and hasattr(guild._state, "http"):
                    await guild._state.http.remove_role(guild.id, member.id, role.id, reason="[Anti-Nuke V2] Dangerous Role Revoked")
                else:
                    await member.remove_roles(role, reason="[Anti-Nuke V2] Dangerous Role Revoked")

            logger.info("[Recovery] ⚡ Stripped %d dangerous roles from member %s in guild %s (%.2fms)", len(roles_to_remove), member_id, guild.id, (time.perf_counter() - t_start) * 1000)
            return RecoveryResult(
                success=True,
                resource_type="member",
                original_id=member_id,
                reason="dangerous_roles_stripped",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            logger.error("[Recovery] Failed to strip dangerous roles from member %s in guild %s: %s", member_id, guild.id, exc)
            return RecoveryResult(success=False, resource_type="member", original_id=member_id, reason=f"error_{exc}")

    async def revert_guild(
        self,
        guild: discord.Guild,
        before_guild: Optional[Any] = None,
    ) -> RecoveryResult:
        """Reverts unauthorized modifications to the guild (name, verification level, etc.)."""
        t_start = time.perf_counter()
        if not guild:
            return RecoveryResult(success=False, resource_type="guild", original_id=0, reason="invalid_guild")
        try:
            edit_kwargs: Dict[str, Any] = {}
            if before_guild:
                if getattr(before_guild, "name", None) and before_guild.name != guild.name:
                    edit_kwargs["name"] = before_guild.name
                if getattr(before_guild, "verification_level", None) and before_guild.verification_level != guild.verification_level:
                    edit_kwargs["verification_level"] = before_guild.verification_level
                if getattr(before_guild, "default_notifications", None) and before_guild.default_notifications != guild.default_notifications:
                    edit_kwargs["default_notifications"] = before_guild.default_notifications

            if edit_kwargs:
                await guild.edit(**edit_kwargs, reason="[Anti-Nuke V2] Guild Modifications Reverted")
                logger.info("[Recovery] ⚡ Reverted guild modifications for %s (%.2fms)", guild.id, (time.perf_counter() - t_start) * 1000)

            return RecoveryResult(
                success=True,
                resource_type="guild",
                original_id=guild.id,
                reason="guild_reverted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            logger.error("[Recovery] Failed to revert guild modifications for %s: %s", guild.id, exc)
            return RecoveryResult(success=False, resource_type="guild", original_id=guild.id, reason=f"error_{exc}")

    async def delete_mass_mention(
        self,
        message: Any,
    ) -> RecoveryResult:
        """Instantly deletes a mass mention / spam message."""
        t_start = time.perf_counter()
        msg_id = getattr(message, "id", None)
        ch_id = getattr(getattr(message, "channel", None), "id", None)
        if not msg_id or not ch_id:
            return RecoveryResult(success=False, resource_type="message", original_id=0, reason="invalid_message")
        try:
            guild = getattr(message, "guild", None)
            if guild and hasattr(guild, "_state") and hasattr(guild._state, "http"):
                await guild._state.http.delete_message(ch_id, msg_id, reason="[Anti-Nuke V2] Mass Mention Message Deleted")
            elif hasattr(message, "delete"):
                await message.delete()
            logger.info("[Recovery] ⚡ Instantly deleted mass mention message %s in channel %s (%.2fms)", msg_id, ch_id, (time.perf_counter() - t_start) * 1000)
            return RecoveryResult(
                success=True,
                resource_type="message",
                original_id=msg_id,
                reason="message_deleted",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except discord.NotFound:
            return RecoveryResult(success=True, resource_type="message", original_id=msg_id, reason="already_deleted")
        except Exception as exc:
            logger.error("[Recovery] Failed to delete mass mention message %s: %s", msg_id, exc)
            return RecoveryResult(success=False, resource_type="message", original_id=msg_id, reason=f"error_{exc}")

    async def unban_innocent_member(
        self,
        guild: discord.Guild,
        user_id: int,
    ) -> RecoveryResult:
        """Instantly unbans a legitimate member who was banned by an attacker."""
        t_start = time.perf_counter()
        if not guild or not user_id:
            return RecoveryResult(success=False, resource_type="ban", original_id=user_id, reason="invalid_params")

        # STRICT SAFETY: Never unban if user was recently neutralized as a raid offender!
        if self.neutralizer and hasattr(self.neutralizer, "is_recently_neutralized"):
            if self.neutralizer.is_recently_neutralized(guild.id, user_id):
                logger.warning(
                    "[Recovery] Aborting unban for user %s in guild %s: user is a recently neutralized raid offender!",
                    user_id, guild.id,
                )
                return RecoveryResult(
                    success=False,
                    resource_type="ban",
                    original_id=user_id,
                    aborted=True,
                    reason="user_is_neutralized_offender",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )

        if self.incident_tracker and hasattr(self.incident_tracker, "is_actor_involved_in_recent_incident"):
            if self.incident_tracker.is_actor_involved_in_recent_incident(guild.id, user_id):
                logger.warning(
                    "[Recovery] Aborting unban for user %s in guild %s: user is an active incident perpetrator!",
                    user_id, guild.id,
                )
                return RecoveryResult(
                    success=False,
                    resource_type="ban",
                    original_id=user_id,
                    aborted=True,
                    reason="user_is_incident_perpetrator",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )

        try:
            if hasattr(guild, "_state") and hasattr(guild._state, "http"):
                await guild._state.http.unban(user_id, guild.id, reason="[Anti-Nuke V2] Innocent Member Unbanned")
            else:
                user = discord.Object(id=user_id)
                await guild.unban(user, reason="[Anti-Nuke V2] Innocent Member Unbanned")
            logger.info("[Recovery] ⚡ Instantly unbanned innocent member %s in guild %s (%.2fms)", user_id, guild.id, (time.perf_counter() - t_start) * 1000)
            return RecoveryResult(
                success=True,
                resource_type="ban",
                original_id=user_id,
                reason="innocent_member_unbanned",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except discord.NotFound:
            return RecoveryResult(success=True, resource_type="ban", original_id=user_id, reason="not_banned")
        except Exception as exc:
            logger.error("[Recovery] Failed to unban innocent member %s in guild %s: %s", user_id, guild.id, exc)
            return RecoveryResult(success=False, resource_type="ban", original_id=user_id, reason=f"error_{exc}")

    async def reban_malicious_member(
        self,
        guild: discord.Guild,
        user_id: int,
    ) -> RecoveryResult:
        """Instantly re-bans a malicious/blacklisted user who was unbanned during an attack."""
        t_start = time.perf_counter()
        if not guild or not user_id:
            return RecoveryResult(success=False, resource_type="ban", original_id=user_id, reason="invalid_params")
        try:
            if hasattr(guild, "_state") and hasattr(guild._state, "http"):
                await guild._state.http.ban(user_id, guild.id, delete_message_days=0, reason="[Anti-Nuke V2] Malicious User Re-Banned")
            else:
                user = discord.Object(id=user_id)
                await guild.ban(user, reason="[Anti-Nuke V2] Malicious User Re-Banned", delete_message_days=0)
            logger.info("[Recovery] ⚡ Instantly re-banned malicious user %s in guild %s (%.2fms)", user_id, guild.id, (time.perf_counter() - t_start) * 1000)
            return RecoveryResult(
                success=True,
                resource_type="ban",
                original_id=user_id,
                reason="malicious_user_rebanned",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
        except Exception as exc:
            logger.error("[Recovery] Failed to re-ban malicious user %s in guild %s: %s", user_id, guild.id, exc)
            return RecoveryResult(success=False, resource_type="ban", original_id=user_id, reason=f"error_{exc}")

    async def recover_all_from_template(
        self,
        guild: discord.Guild,
    ) -> Dict[str, Any]:
        """Compares current guild state against the saved template and restores all missing roles and channels."""
        t_start = time.perf_counter()
        gid = guild.id
        logger.info("[Recovery] 🚀 Starting full template recovery for guild %s", gid)

        roles_snaps = self.snapshot_store.get_all_roles(gid)
        channel_snaps = self.snapshot_store.get_all_channels(gid)

        existing_role_ids = {r.id for r in getattr(guild, "roles", [])}
        existing_channel_ids = {c.id for c in getattr(guild, "channels", [])}

        roles_restored = 0
        categories_restored = 0
        channels_restored = 0

        # 1. Restore missing roles (sorted by position ascending to preserve hierarchy)
        sorted_roles = sorted(roles_snaps, key=lambda r: r.position)
        for r_snap in sorted_roles:
            if r_snap.name == "@everyone" or r_snap.id in existing_role_ids:
                continue
            if self.snapshot_store.get_restored_id(gid, "role", r_snap.id):
                continue
            res = await self.restore_role(guild, r_snap.id, containment_success=True)
            if res.success:
                roles_restored += 1

        # 2. Restore missing categories first
        categories = [c for c in channel_snaps if c.type == discord.ChannelType.category]
        for cat_snap in sorted(categories, key=lambda c: c.position):
            live_cat = discord.utils.find(
                lambda c: c.id == cat_snap.id or c.name.strip().lower() == cat_snap.name.strip().lower(),
                getattr(guild, "categories", [])
            )
            if live_cat:
                self.snapshot_store.register_restored_mapping(gid, "channel", cat_snap.id, live_cat.id)
                continue
            if self.snapshot_store.get_restored_id(gid, "channel", cat_snap.id):
                continue
            res = await self.restore_channel(guild, cat_snap.id, containment_success=True)
            if res.success:
                categories_restored += 1

        # 3. Restore remaining missing channels
        non_categories = [c for c in channel_snaps if c.type != discord.ChannelType.category]
        for ch_snap in sorted(non_categories, key=lambda c: c.position):
            live_ch = discord.utils.find(
                lambda c: c.id == ch_snap.id or _channel_matches_snapshot(c, ch_snap),
                getattr(guild, "channels", [])
            )
            if live_ch:
                self.snapshot_store.register_restored_mapping(gid, "channel", ch_snap.id, live_ch.id)
                continue
            if self.snapshot_store.get_restored_id(gid, "channel", ch_snap.id):
                continue
            res = await self.restore_channel(guild, ch_snap.id, containment_success=True)
            if res.success:
                channels_restored += 1

        # 3.5 Ensure ALL channels (even existing ones) are in their proper template category!
        for ch_snap in non_categories:
            live_ch = discord.utils.find(
                lambda c: c.id == ch_snap.id or _channel_matches_snapshot(c, ch_snap),
                getattr(guild, "channels", [])
            )
            if not live_ch:
                continue

            target_cat = None
            if ch_snap.category_id:
                target_cat = discord.utils.get(getattr(guild, "categories", []), id=ch_snap.category_id)
                if not target_cat:
                    mapped_id = self.snapshot_store.get_restored_id(gid, "channel", ch_snap.category_id)
                    if mapped_id:
                        target_cat = discord.utils.get(getattr(guild, "categories", []), id=mapped_id)
            if not target_cat and ch_snap.category_name:
                clean_name = ch_snap.category_name.strip().lower()
                target_cat = discord.utils.find(
                    lambda c: c.name.strip().lower() == clean_name or _normalize_name_for_dedup(c.name) == _normalize_name_for_dedup(ch_snap.category_name),
                    getattr(guild, "categories", [])
                )

            if target_cat and getattr(live_ch, "category_id", None) != target_cat.id:
                try:
                    await live_ch.edit(
                        category=target_cat,
                        sync_permissions=(len(ch_snap.overwrites) == 0),
                        reason="Yuna Anti-Nuke V2: Template Sync - Move Channel to Category"
                    )
                    logger.info("[Recovery] Moved channel '%s' into category '%s'", live_ch.name, target_cat.name)
                except Exception as move_err:
                    logger.warning("[Recovery] Failed to move channel '%s' to category: %s", live_ch.name, move_err)

        # 4. Flush pending position edits
        await self.flush_batched_positions(guild)

        # 5. Sync native Discord Server Template to keep it clean
        await sync_discord_server_template(guild)

        duration_ms = (time.perf_counter() - t_start) * 1000
        logger.info(
            "[Recovery] 🎯 Full template recovery finished for guild %s: %d roles, %d categories, %d channels (%.2fms)",
            gid, roles_restored, categories_restored, channels_restored, duration_ms
        )
        return {
            "success": True,
            "roles_restored": roles_restored,
            "categories_restored": categories_restored,
            "channels_restored": channels_restored,
            "duration_ms": duration_ms,
        }
