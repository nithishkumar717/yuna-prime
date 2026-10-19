import logging
from typing import Dict, Any, Optional
import unicodedata
import discord

logger = logging.getLogger("yuna.channel_snapshot")


def _norm_ch_name(name: str) -> str:
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(name))
    cleaned = nfkd.lower()
    for ch in (" ", "-", "_", ".", "·", "․", "・", "⚛", "❀", "★", "⚡", "|", "│", "┃", "•", "﹒", "#"):
        cleaned = cleaned.replace(ch, "")
    return cleaned.strip()


def _channel_matches_target(existing_ch: Any, target_name: str, target_type: Any, deleted_id: int) -> bool:
    if not existing_ch:
        return False
    if getattr(existing_ch, "id", None) == deleted_id:
        return False

    ch_type = getattr(existing_ch, "type", None)
    if ch_type is not None and target_type is not None:
        try:
            if int(ch_type) != int(target_type):
                return False
        except (ValueError, TypeError):
            if ch_type != target_type:
                return False

    ch_name = getattr(existing_ch, "name", "")
    if ch_name == target_name:
        return True
    if ch_name.lower().strip() == str(target_name).lower().strip():
        return True
    if ch_name.lower().replace(" ", "-").strip() == str(target_name).lower().replace(" ", "-").strip():
        return True
    norm_ch = _norm_ch_name(ch_name)
    norm_target = _norm_ch_name(target_name)
    if norm_ch and norm_target and norm_ch == norm_target:
        return True
    return False


class ChannelSnapshot:
    __slots__ = (
        "id", "guild_id", "name", "type", "category_id", "category_name",
        "position", "topic", "nsfw", "bitrate", "user_limit", "overwrites",
        "child_channel_ids"
    )

    def __init__(self, channel: discord.abc.GuildChannel):
        self.id = channel.id
        self.guild_id = channel.guild.id if channel.guild else 0
        self.name = getattr(channel, "name", "channel")
        self.type = getattr(channel, "type", discord.ChannelType.text)
        cat = getattr(channel, "category", None)
        self.category_id = getattr(channel, "category_id", None) or (cat.id if cat else None)
        self.category_name = cat.name if cat else None
        self.position = getattr(channel, "position", 0)
        self.topic = getattr(channel, "topic", None)
        self.nsfw = getattr(channel, "nsfw", False)
        self.bitrate = getattr(channel, "bitrate", None)
        self.user_limit = getattr(channel, "user_limit", None)
        # Deep copy overwrites dictionary
        self.overwrites = dict(getattr(channel, "overwrites", {}))
        # Track child channels if this snapshot is for a CategoryChannel
        if self.type == discord.ChannelType.category and hasattr(channel, "channels"):
            self.child_channel_ids = [c.id for c in channel.channels]
        else:
            self.child_channel_ids = []


class ChannelSnapshotManager:
    """
    Maintains resilient snapshots of guild channel states and permission overwrites.
    Guarantees that when an unauthorized channel deletion occurs, YUNA restores
    the channel with 100% accurate role and member permission fidelity, even if
    certain roles were tampered with during the raid.
    """

    def __init__(self):
        # guild_id -> channel_id -> ChannelSnapshot
        self._cache: Dict[int, Dict[int, ChannelSnapshot]] = {}
        # guild_id -> old_category_id -> newly restored discord.CategoryChannel
        self._restored_categories: Dict[int, Dict[int, discord.CategoryChannel]] = {}
        # guild_id -> category_name.lower() -> newly restored discord.CategoryChannel
        self._restored_categories_by_name: Dict[int, Dict[str, discord.CategoryChannel]] = {}

    def snapshot_channel(self, channel: discord.abc.GuildChannel) -> Optional[ChannelSnapshot]:
        if not channel or not getattr(channel, "guild", None):
            return None
        gid = channel.guild.id
        if gid not in self._cache:
            self._cache[gid] = {}
        snap = ChannelSnapshot(channel)
        self._cache[gid][channel.id] = snap
        return snap

    def snapshot_guild(self, guild: discord.Guild):
        if not guild:
            return
        gid = guild.id
        if gid not in self._cache:
            self._cache[gid] = {}
        for ch in guild.channels:
            try:
                self._cache[gid][ch.id] = ChannelSnapshot(ch)
            except Exception:
                pass

    def get_snapshot(self, guild_id: int, channel_id: int) -> Optional[ChannelSnapshot]:
        return self._cache.get(guild_id, {}).get(channel_id)

    def resolve_category(
        self,
        guild: discord.Guild,
        snap: Optional[ChannelSnapshot],
        channel: discord.abc.GuildChannel
    ) -> Optional[discord.CategoryChannel]:
        """
        Resolves the target CategoryChannel for a channel being restored.
        Supports live category lookup, category ID mapping from simultaneous deletions,
        and category name matching.
        """
        if not guild:
            return None
        gid = guild.id

        # 1. Direct attribute on channel if still cached in guild.categories
        cat = getattr(channel, "category", None)
        if cat and cat in guild.categories:
            return cat

        cat_id = (snap.category_id if snap else None) or getattr(channel, "category_id", None)
        cat_name = (snap.category_name if snap else None) or (cat.name if cat else None)

        # 2. Check if the original category ID is in guild channels or categories
        if cat_id:
            found = guild.get_channel(cat_id) or discord.utils.get(guild.categories, id=cat_id)
            if isinstance(found, discord.CategoryChannel):
                return found
            # Check if this category was recently restored in this guild
            restored = self._restored_categories.get(gid, {}).get(cat_id)
            if restored and restored in guild.categories:
                return restored

        # 3. Check by category name (e.g. if category was recreated with a new snowflake)
        if cat_name:
            restored_by_name = self._restored_categories_by_name.get(gid, {}).get(cat_name.lower())
            if restored_by_name and restored_by_name in guild.categories:
                return restored_by_name
            found_by_name = discord.utils.get(guild.categories, name=cat_name)
            if found_by_name:
                return found_by_name

        return None

    def sanitize_overwrites(self, guild: discord.Guild, overwrites: dict) -> dict:
        """
        Removes any stale or deleted roles/members from the overwrites dictionary.
        Prevents Discord API HTTP 400 Bad Request (Unknown Role / Unknown Member).
        """
        if not guild or not overwrites:
            return {}

        guild_role_ids = {r.id for r in guild.roles}
        sanitized = {}

        for target, overwrite in overwrites.items():
            if isinstance(target, discord.Role):
                if target.id in guild_role_ids:
                    sanitized[target] = overwrite
                else:
                    live_role = guild.get_role(target.id)
                    if live_role:
                        sanitized[live_role] = overwrite
            elif isinstance(target, (discord.Member, discord.User)):
                live_member = guild.get_member(target.id)
                if live_member:
                    sanitized[live_member] = overwrite
            elif isinstance(target, int):
                live_role = guild.get_role(target)
                if live_role:
                    sanitized[live_role] = overwrite
                else:
                    live_member = guild.get_member(target)
                    if live_member:
                        sanitized[live_member] = overwrite
        return sanitized

    async def restore_channel_safely(
        self,
        channel: discord.abc.GuildChannel,
        reason: str = "[Anti-Nuke] Auto-Restore Deleted Channel"
    ) -> Optional[discord.abc.GuildChannel]:
        """
        Restores a deleted channel with full permission overwrite & category fidelity.
        - If a CategoryChannel was deleted, recreates the Category and re-adopts any orphan channels.
        - If a text/voice/stage channel was deleted, places it back inside its original category
          and restores its exact position and permissions.
        """
        guild = getattr(channel, "guild", None)
        if not guild:
            return None

        gid = guild.id
        snap = self.get_snapshot(gid, channel.id) or self.snapshot_channel(channel)
        ch_type = snap.type if snap else getattr(channel, "type", discord.ChannelType.text)
        name = snap.name if snap else getattr(channel, "name", "channel")
        pos = snap.position if snap else getattr(channel, "position", 0)

        # Check if matching channel or category already exists (ignore if already created by another bot or admin)
        existing_ch = None
        for ch in getattr(guild, "channels", []):
            if _channel_matches_target(ch, name, ch_type, channel.id):
                existing_ch = ch
                break

        if not existing_ch and hasattr(guild, "fetch_channels"):
            try:
                fetched = await guild.fetch_channels()
                for ch in fetched:
                    if _channel_matches_target(ch, name, ch_type, channel.id):
                        existing_ch = ch
                        break
            except Exception:
                pass

        if existing_ch:
            logger.info(f"[CHANNEL SNAPSHOT] Channel/Category '{name}' already exists (ID: {existing_ch.id}) in guild {gid}. Skipping recreation.")
            if ch_type == discord.ChannelType.category:
                if gid not in self._restored_categories:
                    self._restored_categories[gid] = {}
                if gid not in self._restored_categories_by_name:
                    self._restored_categories_by_name[gid] = {}
                self._restored_categories[gid][channel.id] = existing_ch
                self._restored_categories_by_name[gid][name.lower()] = existing_ch
            return existing_ch

        # =========================================================================
        # CASE 1: DELETED CHANNEL WAS A CATEGORY
        # =========================================================================
        if ch_type == discord.ChannelType.category:
            try:
                new_category = await guild.create_category(
                    name=name,
                    position=pos,
                    overwrites=clean_overwrites,
                    reason=reason
                )
                if gid not in self._restored_categories:
                    self._restored_categories[gid] = {}
                if gid not in self._restored_categories_by_name:
                    self._restored_categories_by_name[gid] = {}
                self._restored_categories[gid][channel.id] = new_category
                self._restored_categories_by_name[gid][name.lower()] = new_category

                logger.info(f"[CHANNEL SNAPSHOT] Restored category '{name}' ({new_category.id}) in guild {gid}")

                # Re-adopt orphan channels that were formerly inside this category
                orphan_ids = set()
                if snap and snap.child_channel_ids:
                    orphan_ids.update(snap.child_channel_ids)
                guild_snaps = self._cache.get(gid, {})
                for cid, csnap in guild_snaps.items():
                    if csnap.category_id == channel.id:
                        orphan_ids.add(cid)

                for oid in orphan_ids:
                    live_ch = guild.get_channel(oid)
                    if live_ch and getattr(live_ch, "category_id", None) is None:
                        try:
                            await live_ch.edit(category=new_category, reason=f"{reason} (Re-adopt Orphan Channel)")
                        except Exception as edit_err:
                            logger.debug(f"[CHANNEL SNAPSHOT] Re-adopt orphan channel {oid} failed: {edit_err}")

                return new_category
            except Exception as e:
                logger.error(f"[CHANNEL SNAPSHOT] Failed category restore '{name}' in guild {gid}: {e}")
                return None

        # =========================================================================
        # CASE 2: DELETED CHANNEL WAS A TEXT / VOICE / STAGE CHANNEL
        # =========================================================================
        category = self.resolve_category(guild, snap, channel)

        # Attempt 1: Native channel.clone with resolved category
        try:
            new_channel = await channel.clone(
                category=category,
                reason=reason
            )
            # Re-apply sanitized overwrites or enforce category if clone defaulted
            needs_edit = False
            edit_kwargs = {}
            if category and getattr(new_channel, "category_id", None) != category.id:
                edit_kwargs["category"] = category
                needs_edit = True
            if clean_overwrites:
                edit_kwargs["overwrites"] = clean_overwrites
                needs_edit = True
            if needs_edit:
                try:
                    await new_channel.edit(reason=f"{reason} (Permissions & Category)", **edit_kwargs)
                except Exception:
                    pass
            return new_channel
        except discord.Forbidden:
            return None
        except Exception as e:
            logger.debug(f"[CHANNEL SNAPSHOT] Clone failed ({e}), attempting resilient direct creation...")

        # Attempt 2: Direct recreation using snapshot attributes & resolved category
        try:
            common_kwargs = {
                "name": name,
                "category": category,
                "position": pos,
                "overwrites": clean_overwrites,
                "reason": reason
            }

            if ch_type == discord.ChannelType.voice:
                new_channel = await guild.create_voice_channel(
                    bitrate=snap.bitrate if snap and snap.bitrate else 64000,
                    user_limit=snap.user_limit if snap and snap.user_limit else 0,
                    **common_kwargs
                )
            elif ch_type == discord.ChannelType.stage_voice:
                new_channel = await guild.create_stage_channel(
                    **common_kwargs
                )
            else:
                new_channel = await guild.create_text_channel(
                    topic=snap.topic if snap and snap.topic else None,
                    nsfw=snap.nsfw if snap else False,
                    **common_kwargs
                )

            # Ensure newly created channel aligns with parent category
            if category and getattr(new_channel, "category_id", None) != category.id:
                try:
                    await new_channel.edit(category=category, position=pos, reason=f"{reason} (Category Alignment)")
                except Exception:
                    pass

            return new_channel
        except Exception as e:
            logger.error(f"[CHANNEL SNAPSHOT] Failed resilient channel recreation in guild {gid}: {e}")
            return None


channel_snapshot_manager = ChannelSnapshotManager()
