import discord
from discord.ext import commands
import asyncio
import collections
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import aiosqlite
from utils.Tools import send_antinuke_log
from core.cache.security_cache import security_cache

logger = logging.getLogger("yuna.antiraid")

DB_PATH = "db/anti.db"


class RaidState:
    """In-memory sliding window and lockdown state per guild."""
    __slots__ = ("join_times", "is_locked_down", "lockdown_until", "elevated_verification")

    def __init__(self):
        self.join_times: collections.deque = collections.deque()
        self.is_locked_down: bool = False
        self.lockdown_until: float = 0.0
        self.elevated_verification: Optional[discord.VerificationLevel] = None


class AntiRaid(commands.Cog):
    """
    Enterprise Anti-Raid & Join-Gate Shield for Yuna Supreme.
    Sub-15ms join interception, token raid detection, account age verification,
    and automatic guild quarantine.
    """

    def __init__(self, bot):
        self.bot = bot
        # In-memory config cache: guild_id -> dict
        self._config_cache: Dict[int, dict] = {}
        # In-memory runtime state: guild_id -> RaidState
        self._states: Dict[int, RaidState] = {}

    async def cog_load(self):
        """Asynchronously initializes SQLite schema and warms cache when cog is loaded."""
        await self._init_database()

    async def _init_database(self):
        """Initializes SQLite schema and warms cache."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS antiraid (
                        guild_id INTEGER PRIMARY KEY,
                        enabled BOOLEAN DEFAULT 0,
                        massjoin_enabled BOOLEAN DEFAULT 1,
                        threshold_count INTEGER DEFAULT 5,
                        threshold_seconds INTEGER DEFAULT 10,
                        action TEXT DEFAULT 'kick',
                        min_age_hours INTEGER DEFAULT 24,
                        avatar_filter BOOLEAN DEFAULT 0,
                        quarantine_role_id INTEGER DEFAULT NULL,
                        lockdown_duration INTEGER DEFAULT 120
                    )
                """)
                await db.commit()

                async with db.execute("SELECT * FROM antiraid") as cursor:
                    rows = await cursor.fetchall()
                    col_names = [d[0] for d in cursor.description]
                    for row in rows:
                        data = dict(zip(col_names, row))
                        self._config_cache[data["guild_id"]] = data

            logger.info("[AntiRaid] Initialized database and cached %d configs", len(self._config_cache))
        except Exception as e:
            logger.error("[AntiRaid] DB Init error: %s", e)

    def get_config(self, guild_id: int) -> dict:
        """Zero-latency configuration fetch from in-memory cache."""
        return self._config_cache.get(guild_id, {
            "guild_id": guild_id,
            "enabled": False,
            "massjoin_enabled": True,
            "threshold_count": 5,
            "threshold_seconds": 10,
            "action": "kick",
            "min_age_hours": 24,
            "avatar_filter": False,
            "quarantine_role_id": None,
            "lockdown_duration": 120
        })

    def update_cache(self, guild_id: int, new_data: dict):
        current = self.get_config(guild_id)
        current.update(new_data)
        self._config_cache[guild_id] = current

    def get_state(self, guild_id: int) -> RaidState:
        if guild_id not in self._states:
            self._states[guild_id] = RaidState()
        return self._states[guild_id]

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if not guild or not guild.me or member.bot:
            return

        cfg = self.get_config(guild.id)
        if not cfg.get("enabled"):
            return

        now = time.time()
        state = self.get_state(guild.id)

        # 1. Check if guild is currently under Active Raid Lockdown
        if state.is_locked_down:
            if now < state.lockdown_until:
                # Still locked down: immediately neutralize incoming joiner
                await self._punish_member(
                    member,
                    cfg.get("action", "kick"),
                    cfg.get("quarantine_role_id"),
                    reason="[Anti-Raid] Active Mass Join Lockdown in Progress"
                )
                return
            else:
                # Lockdown expired: restore settings
                state.is_locked_down = False
                await self._lift_lockdown(guild, state)

        # 2. Velocity Tracking (Sliding Window Join Rate)
        if cfg.get("massjoin_enabled", True):
            thresh_count = cfg.get("threshold_count", 5)
            thresh_secs = cfg.get("threshold_seconds", 10)

            # Push current timestamp
            state.join_times.append(now)
            cutoff = now - thresh_secs
            while state.join_times and state.join_times[0] < cutoff:
                state.join_times.popleft()

            # Trigger Raid Lockdown if burst detected!
            if len(state.join_times) >= thresh_count:
                state.is_locked_down = True
                duration = cfg.get("lockdown_duration", 120)
                state.lockdown_until = now + duration

                asyncio.create_task(self._trigger_lockdown(guild, state, member, len(state.join_times), thresh_secs))
                await self._punish_member(
                    member,
                    cfg.get("action", "kick"),
                    cfg.get("quarantine_role_id"),
                    reason=f"[Anti-Raid] Burst Join Spike ({len(state.join_times)} in {thresh_secs}s)"
                )
                return

        # 3. Account Age Filter
        min_age_hours = cfg.get("min_age_hours", 0)
        if min_age_hours > 0 and member.created_at:
            created_utc = member.created_at.replace(tzinfo=timezone.utc) if member.created_at.tzinfo is None else member.created_at
            now_utc = datetime.now(timezone.utc)
            age_hours = (now_utc - created_utc).total_seconds() / 3600.0

            if age_hours < min_age_hours:
                reason = f"[Anti-Raid] Account Too Young ({age_hours:.1f}h < {min_age_hours}h required)"
                await self._punish_member(
                    member,
                    cfg.get("action", "kick"),
                    cfg.get("quarantine_role_id"),
                    reason=reason
                )
                asyncio.create_task(send_antinuke_log(
                    guild,
                    "Anti-Raid: Young Account",
                    member,
                    f"Action: {cfg.get('action', 'kick').upper()}",
                    details=f"Account Age: {age_hours:.1f}h | Min Req: {min_age_hours}h"
                ))
                return

        # 4. Default Avatar Filter
        if cfg.get("avatar_filter") and member.avatar is None:
            reason = "[Anti-Raid] Default Avatar Prohibited"
            await self._punish_member(
                member,
                cfg.get("action", "kick"),
                cfg.get("quarantine_role_id"),
                reason=reason
            )
            asyncio.create_task(send_antinuke_log(
                guild,
                "Anti-Raid: Default Avatar",
                member,
                f"Action: {cfg.get('action', 'kick').upper()}",
                details="Account has no custom profile avatar"
            ))
            return

    async def _punish_member(self, member: discord.Member, action: str, quarantine_role_id: Optional[int], reason: str):
        """Applies configured penalty to raid/suspicious account."""
        guild = member.guild
        try:
            if action == "ban" and guild.me.guild_permissions.ban_members:
                await member.ban(reason=reason, delete_message_days=1)
            elif action == "quarantine" and quarantine_role_id:
                q_role = guild.get_role(quarantine_role_id)
                if q_role and guild.me.top_role > q_role:
                    await member.add_roles(q_role, reason=reason)
                elif guild.me.guild_permissions.kick_members:
                    await member.kick(reason=reason)
            elif guild.me.guild_permissions.kick_members:
                await member.kick(reason=reason)
        except Exception as e:
            logger.warning("[AntiRaid] Could not punish %s (%s): %s", member.id, action, e)

    async def _trigger_lockdown(self, guild: discord.Guild, state: RaidState, trigger_member: discord.Member, count: int, window: int):
        """Elevates verification level and broadcasts critical raid alert."""
        try:
            if guild.me.guild_permissions.manage_guild and guild.verification_level != discord.VerificationLevel.highest:
                state.elevated_verification = guild.verification_level
                await guild.edit(verification_level=discord.VerificationLevel.highest, reason="[Anti-Raid] Auto-Lockdown Triggered")
        except Exception as e:
            logger.warning("[AntiRaid] Could not elevate verification level: %s", e)

        # Log to anti-nuke channel
        await send_antinuke_log(
            guild,
            "🚨 CRITICAL: RAID LOCKDOWN ACTIVATED",
            trigger_member,
            f"Mass join detected: {count} accounts joined in {window}s!",
            details=f"Guild verification elevated to HIGHEST. Auto-quarantine engaged for 120s."
        )

        # Notify Server Owner via DM
        try:
            if guild.owner and not guild.owner.bot:
                embed = discord.Embed(
                    title="🚨 RAID ALERT — SERVER LOCKDOWN",
                    description=(
                        f"An active raid was intercepted in **{guild.name}**!\n\n"
                        f"• **Trigger:** {count} members joined in under {window} seconds.\n"
                        f"• **Action:** Guild verification raised to HIGHEST, raid accounts quarantined/kicked.\n"
                        f"• **Duration:** Active for 120 seconds or until rate normalizes."
                    ),
                    color=0xFF0033
                )
                await guild.owner.send(embed=embed)
        except Exception:
            pass

    async def _lift_lockdown(self, guild: discord.Guild, state: RaidState):
        """Restores verification level after raid subsides."""
        try:
            if state.elevated_verification is not None and guild.me.guild_permissions.manage_guild:
                await guild.edit(verification_level=state.elevated_verification, reason="[Anti-Raid] Raid Subsided — Restoring Verification")
                state.elevated_verification = None
        except Exception:
            pass

        await send_antinuke_log(
            guild,
            "🛡️ Anti-Raid: Lockdown Lifted",
            guild.me,
            "Join velocity has normalized.",
            details="Standard security monitoring resumed."
        )
