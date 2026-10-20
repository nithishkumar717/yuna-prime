"""Anti-Nuke V2 Engine — High-Precision Event-Loop Lag Sampler.

Monitors event-loop responsiveness by scheduling a callback every 10 ms.
Measures scheduling lag (how late the callback executed relative to expected dispatch).
Maintains a bounded sliding window of latency samples to calculate p50, p95, p99, and max lag.
Immediately logs any single lag spike exceeding 50 ms along with the names of all asyncio tasks
currently executing in the event loop at that moment.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("antinuke.v2.lag_sampler")


def _debug_enabled() -> bool:
    """Return whether verbose diagnostics are enabled in the environment."""
    return os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}


def calculate_percentile(data: List[float], p: float) -> float:
    """Calculates the p-th percentile from an array of numbers."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    idx = (n - 1) * (p / 100.0)
    low = int(math.floor(idx))
    high = int(math.ceil(idx))
    if low == high:
        return sorted_data[low]
    weight = idx - low
    return sorted_data[low] * (1.0 - weight) + sorted_data[high] * weight


@dataclass(slots=True)
class LagSpikeRecord:
    """Detailed record of an event loop blocking spike exceeding 50ms."""
    timestamp: float
    lag_ms: float
    running_tasks: List[str]

    def to_log_string(self) -> str:
        tasks_preview = ", ".join(self.running_tasks[:10])
        if len(self.running_tasks) > 10:
            tasks_preview += f" ... (+{len(self.running_tasks) - 10} more)"
        return (
            f"[EventLoopLag] ⚠️ SPIKE DETECTED: {self.lag_ms:.2f} ms (>50ms) | "
            f"{len(self.running_tasks)} running tasks: [{tasks_preview}]"
        )


class EventLoopLagSampler:
    """High-frequency event-loop lag sampler with spike task introspection."""

    __slots__ = (
        "interval_seconds",
        "spike_threshold_ms",
        "max_samples",
        "_samples",
        "_spikes",
        "_running",
        "_handle",
        "_target_time",
        "_loop",
    )

    def __init__(
        self,
        interval_seconds: float = 0.010,
        spike_threshold_ms: float = 50.0,
        max_samples: int = 10000,
    ) -> None:
        self.interval_seconds = interval_seconds
        self.spike_threshold_ms = spike_threshold_ms
        self.max_samples = max_samples
        self._samples: Deque[float] = deque(maxlen=max_samples)
        self._spikes: Deque[LagSpikeRecord] = deque(maxlen=200)
        self._running: bool = False
        self._handle: Optional[asyncio.TimerHandle] = None
        self._target_time: float = 0.0
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Starts the 10ms sampling timer on the active asyncio event loop."""
        if self._running:
            return

        try:
            self._loop = loop or asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()

        self._running = True
        self._target_time = self._loop.time() + self.interval_seconds
        self._handle = self._loop.call_at(self._target_time, self._on_tick)
        logger.debug("[EventLoopLagSampler] Started 10ms event loop lag monitoring (spike threshold: %.1fms)", self.spike_threshold_ms)

    def stop(self) -> None:
        """Stops the sampling timer."""
        self._running = False
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        logger.debug("[EventLoopLagSampler] Stopped event loop lag monitoring")

    def _on_tick(self) -> None:
        if not self._running or self._loop is None:
            return

        now = self._loop.time()
        # Calculate how late the callback ran compared to target time
        lag_seconds = max(0.0, now - self._target_time)
        lag_ms = lag_seconds * 1000.0
        self._samples.append(lag_ms)

        # Log any single lag spike over 50 ms with task introspection
        if lag_ms > self.spike_threshold_ms:
            debug_enabled = _debug_enabled()
            running_tasks = self._inspect_running_tasks() if debug_enabled else []
            spike = LagSpikeRecord(
                timestamp=time.time(),
                lag_ms=lag_ms,
                running_tasks=running_tasks,
            )
            self._spikes.append(spike)
            if debug_enabled:
                logger.warning(spike.to_log_string())

        # Schedule next tick precisely 10 ms from now
        self._target_time = now + self.interval_seconds
        self._handle = self._loop.call_at(self._target_time, self._on_tick)

    def _inspect_running_tasks(self) -> List[str]:
        """Introspects and names all currently active asyncio tasks on the event loop."""
        if self._loop is None:
            return []

        task_descriptions: List[str] = []
        try:
            tasks = asyncio.all_tasks(self._loop)
            for t in tasks:
                if t.done():
                    continue
                name = t.get_name()
                coro = getattr(t, "get_coro", lambda: None)()
                qualname = getattr(coro, "__qualname__", None)
                if not qualname:
                    qualname = repr(coro) if coro else "unknown"
                task_descriptions.append(f"{name}[{qualname}]")
        except Exception as exc:
            task_descriptions.append(f"<introspection_error: {exc}>")

        return task_descriptions

    def get_metrics(self) -> Dict[str, float]:
        """Calculates p50, p95, p99, and max lag statistics across the active sample window."""
        sample_list = list(self._samples)
        if not sample_list:
            return {
                "sample_count": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "max_ms": 0.0,
                "spike_count": float(len(self._spikes)),
            }

        return {
            "sample_count": float(len(sample_list)),
            "p50_ms": calculate_percentile(sample_list, 50.0),
            "p95_ms": calculate_percentile(sample_list, 95.0),
            "p99_ms": calculate_percentile(sample_list, 99.0),
            "max_ms": max(sample_list),
            "spike_count": float(len(self._spikes)),
        }

    def get_recent_spikes(self, limit: int = 10) -> List[LagSpikeRecord]:
        """Returns the most recent lag spike records."""
        return list(self._spikes)[-limit:]


# Global singleton instance
event_loop_lag_sampler = EventLoopLagSampler()
