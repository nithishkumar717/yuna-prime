"""
Yuna Log Setup Cooldown Manager
Prevents Discord HTTP 429 Channel Edit Rate Limits (2 modifications per 10 minutes per channel).

Rules:
- 1st Execution: 120 seconds cooldown (2 minutes).
- 2nd Execution (within 10-minute window): 600 seconds cooldown (10 minutes).
- Resets after cooldown expires or 10 minutes of inactivity.
"""

import time
import asyncio
import discord
from typing import Tuple, Dict, Optional


class GuildLogCooldownState:
    __slots__ = ("count", "last_executed", "cooldown_until", "lock")

    def __init__(self):
        self.count: int = 0
        self.last_executed: float = 0.0
        self.cooldown_until: float = 0.0
        self.lock = asyncio.Lock()


class LogSetupCooldownManager:
    """Guild-level cooldown coordinator for log setup operations across Yuna."""

    def __init__(self):
        self._guilds: Dict[int, GuildLogCooldownState] = {}
        self._global_lock = asyncio.Lock()

    async def _get_state(self, guild_id: int) -> GuildLogCooldownState:
        async with self._global_lock:
            state = self._guilds.get(guild_id)
            if state is None:
                state = GuildLogCooldownState()
                self._guilds[guild_id] = state
            return state

    async def check(self, guild_id: int) -> Tuple[bool, float, int]:
        """
        Non-mutating check if a guild is currently on cooldown.
        Returns: (is_on_cooldown, remaining_seconds, current_execution_count)
        """
        state = await self._get_state(guild_id)
        async with state.lock:
            now = time.time()
            if now < state.cooldown_until:
                remaining = max(0.0, state.cooldown_until - now)
                return True, remaining, state.count
            return False, 0.0, state.count

    async def acquire(self, guild_id: int) -> Tuple[bool, float, int, float]:
        """
        Attempts to acquire execution permission for log setup in this guild.
        If on cooldown:
            Returns (False, remaining_seconds, current_count, 0.0)
        If allowed:
            Records execution and applies the appropriate cooldown:
            - 1st run: 120 seconds
            - 2nd+ run: 600 seconds (10 minutes)
            Returns (True, 0.0, new_count, cooldown_applied)
        """
        state = await self._get_state(guild_id)
        async with state.lock:
            now = time.time()

            # If still on cooldown, reject
            if now < state.cooldown_until:
                remaining = max(0.0, state.cooldown_until - now)
                return False, remaining, state.count, 0.0

            # If more than 10 minutes have passed since last execution, reset cycle
            if state.last_executed > 0 and (now - state.last_executed) >= 600.0:
                state.count = 0

            # Advance execution count
            state.count += 1
            state.last_executed = now

            if state.count == 1:
                cooldown_duration = 120.0  # 120 seconds for first execution
            else:
                cooldown_duration = 600.0  # 10 minutes for 2nd execution

            state.cooldown_until = now + cooldown_duration
            return True, 0.0, state.count, cooldown_duration

    @staticmethod
    def format_remaining(seconds: float) -> str:
        """Formats remaining seconds into a user-friendly string."""
        total_sec = max(1, int(round(seconds)))
        mins, secs = divmod(total_sec, 60)
        if mins > 0 and secs > 0:
            return f"{mins}m {secs}s"
        elif mins > 0:
            return f"{mins} minute{'s' if mins != 1 else ''}"
        else:
            return f"{secs} second{'s' if secs != 1 else ''}"

    def build_cooldown_embed(self, guild: discord.Guild, remaining: float, count: int) -> discord.Embed:
        """Creates a standardized embed informing the user of the rate limit protection cooldown."""
        formatted_time = self.format_remaining(remaining)
        
        if count >= 2:
            title = "⏳ Log Setup Cooldown • 10m Rate-Limit Protection"
            desc = (
                f"Log setup has been executed **2 times** in **{guild.name}**.\n\n"
                f"Discord strictly enforces a global rate limit of **2 channel modifications per 10 minutes**.\n"
                f"To protect the server from Discord API rate limits (`HTTP 429`), log setup is temporarily paused.\n\n"
                f"• **Remaining Cooldown:** `{formatted_time}`\n"
                f"• **Auto-Reset:** Full setup availability will restore automatically once the timer expires."
            )
            color = 0xED4245  # Red/Amber alert
        else:
            title = "⏳ Log Setup Cooldown Active"
            desc = (
                f"Log setup was recently initiated in **{guild.name}**.\n\n"
                f"To prevent Discord channel rate limits, please allow setup to settle before re-running.\n\n"
                f"• **Remaining Cooldown:** `{formatted_time}` (120s safety interval)\n"
                f"• Please wait until this timer reaches `0s` before executing setup again."
            )
            color = 0xFEE75C  # Yellow warning

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        bot_icon = getattr(getattr(guild.me, "display_avatar", None), "url", None)
        embed.set_footer(text=f"Guild ID: {guild.id} • Discord API Rate-Limit Shield", icon_url=bot_icon)
        return embed


# Global singleton instance
log_setup_cooldown = LogSetupCooldownManager()
