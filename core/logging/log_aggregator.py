import time
import asyncio
import discord
from typing import Dict, List, Any
from core.discord.request_manager import request_manager, Priority


class LogAggregator:
    """Buffers rapid security log events per guild and dispatches aggregated incident report embeds every 3-5s."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LogAggregator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, flush_interval: float = 3.0, max_buffer_size: int = 20):
        if self._initialized:
            return
        # Structure: {guild_id: [event_summary_dict, ...]}
        self.buffers: Dict[int, List[Dict[str, Any]]] = {}
        self.flush_interval = flush_interval
        self.max_buffer_size = max_buffer_size
        self.running = False
        self._flush_task = None
        self._initialized = True

    def start(self):
        if self.running:
            return
        self.running = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        self._flush_task = loop.create_task(self._flush_loop())

    def stop(self):
        self.running = False
        if self._flush_task:
            self._flush_task.cancel()

    def log_event(self, guild_id: int, action_type: str, executor: discord.User | discord.Member, details: str):
        """Buffers an incident log event for aggregated dispatch."""
        if guild_id not in self.buffers:
            self.buffers[guild_id] = []
        self.buffers[guild_id].append({
            "action": action_type,
            "executor_id": executor.id,
            "executor_name": str(executor),
            "details": details,
            "time": time.time()
        })

        # Instant flush if max buffer size is reached
        if len(self.buffers[guild_id]) >= self.max_buffer_size:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._flush_guild_buffer(guild_id))
            except Exception:
                pass

    async def _flush_loop(self):
        while self.running:
            await asyncio.sleep(self.flush_interval)
            try:
                await self._flush_all_buffers()
            except Exception as e:
                print(f"[LOG AGGREGATOR ERROR] {e}")

    async def _flush_all_buffers(self):
        if not self.buffers:
            return

        for guild_id in list(self.buffers.keys()):
            await self._flush_guild_buffer(guild_id)

    async def _flush_guild_buffer(self, guild_id: int):
        events = self.buffers.pop(guild_id, None)
        if not events:
            return

        # Format aggregated incident report embed
        count = len(events)
        action_counts = {}
        executors = set()

        for ev in events:
            act = ev["action"]
            action_counts[act] = action_counts.get(act, 0) + 1
            executors.add(f"<@{ev['executor_id']}> ({ev['executor_name']})")

        summary_lines = [f"• **{act}**: {cnt} event(s)" for act, cnt in action_counts.items()]
        executors_str = ", ".join(executors)

        embed = discord.Embed(
            title="🛡️ Yuna Security Incident Summary Report",
            description=(
                f"**Total Events Detected:** {count}\n"
                f"**Executors:** {executors_str}\n\n"
                f"**Event Summary:**\n" + "\n".join(summary_lines)
            ),
            color=0xFF0000,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Yuna Security Rate-Limit Log Aggregator")

        # Dispatch via P3 Low Priority Queue so security actions take precedence
        async def dispatch_log():
            from utils.settings_manager import settings
            log_chan_id = settings.get_guild_setting(guild_id, "log_channel")
            if log_chan_id:
                from core.Bot import bot_instance
                if bot_instance:
                    guild = bot_instance.get_guild(guild_id)
                    if guild:
                        chan = guild.get_channel(int(log_chan_id))
                        if chan:
                            await chan.send(embed=embed)

        try:
            await request_manager.enqueue(
                priority=Priority.P3_LOW,
                task_id=f"log_flush_{guild_id}_{time.time()}",
                coro_func=dispatch_log
            )
        except Exception:
            pass


# Global singleton instance
log_aggregator = LogAggregator()
