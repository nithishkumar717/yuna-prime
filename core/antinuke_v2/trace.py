"""Anti-Nuke V2 Engine — High-Precision Observability & Latency Tracing.

Tracks every stage of security event handling with sub-microsecond resolution
using time.perf_counter_ns().
Records:
- event_age: time elapsed since the Discord snowflake was generated
- handler_start: local timestamp when event entered V2 handler
- decision: local timestamp when synchronous policy decision completed
- ban_sent: local timestamp when Discord REST ban call dispatched
- ban_response: local timestamp when Discord REST response arrived
- http_status: HTTP response status code (e.g. 200, 204, 403, 429)
- result: success | failed | cache_hit | skipped | aborted | dry_run
- path: audit_stream | entity_fallback | raw_gateway
- is_warm_connection: boolean indicating whether TCP/TLS session was warm
"""
from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("antinuke.v2.trace")

DISCORD_EPOCH_MS = 1420070400000


def snowflake_to_timestamp_ns(snowflake_id: int) -> int:
    """Converts a Discord snowflake ID into epoch nanoseconds."""
    epoch_ms = (snowflake_id >> 22) + DISCORD_EPOCH_MS
    return epoch_ms * 1_000_000


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


@dataclass
class V2SecurityTrace:
    """Nanosecond-precision performance record for an Anti-Nuke incident."""
    event_id: int
    guild_id: int
    action: str
    path: str = "audit_stream"
    actor_id: Optional[int] = None
    target_id: Optional[int] = None
    dry_run: bool = False
    is_warm_connection: bool = False

    # Timing checkpoints (perf_counter_ns)
    handler_start_ns: int = field(default_factory=time.perf_counter_ns)
    decision_ns: Optional[int] = None
    ban_sent_ns: Optional[int] = None
    ban_response_ns: Optional[int] = None
    finish_ns: Optional[int] = None

    # Discord Gateway Snowflake Age
    snowflake_timestamp_ns: Optional[int] = None
    event_age_ms: float = 0.0

    # Containment details
    http_status: Optional[int] = None
    result: str = "pending"  # success, failed, cache_hit, skipped, aborted, dry_run
    reason_code: str = ""
    ratelimit_wait_ms: float = 0.0
    http_rtt_ms: float = 0.0

    def __post_init__(self) -> None:
        try:
            ev_id = int(self.event_id)
        except (ValueError, TypeError):
            ev_id = 0

        if ev_id > 0:
            try:
                self.snowflake_timestamp_ns = snowflake_to_timestamp_ns(ev_id)
                now_epoch_ns = time.time_ns()
                self.event_age_ms = max(0.0, (now_epoch_ns - self.snowflake_timestamp_ns) / 1_000_000.0)
            except Exception:
                pass

    def record_decision(self, reason_code: str, now_ns: Optional[int] = None) -> None:
        """Marks local synchronous policy decision completion."""
        if now_ns is not None:
            self.decision_ns = now_ns
        elif self.decision_ns is None:
            self.decision_ns = time.perf_counter_ns()
        self.reason_code = reason_code

    def record_ban_sent(self, now_ns: Optional[int] = None) -> None:
        """Marks dispatch of Discord REST ban call."""
        if now_ns is not None:
            self.ban_sent_ns = now_ns
        elif self.ban_sent_ns is None:
            self.ban_sent_ns = time.perf_counter_ns()

    def record_ban_response(
        self,
        http_status: Optional[int] = None,
        success: bool = True,
        ratelimit_wait_ms: float = 0.0,
        http_rtt_ms: float = 0.0,
        now_ns: Optional[int] = None,
    ) -> None:
        """Marks arrival of Discord REST ban response with rate-limit and network RTT separation."""
        if now_ns is not None:
            self.ban_response_ns = now_ns
        elif self.ban_response_ns is None:
            self.ban_response_ns = time.perf_counter_ns()
        self.http_status = http_status
        self.ratelimit_wait_ms = ratelimit_wait_ms
        if http_rtt_ms > 0:
            self.http_rtt_ms = http_rtt_ms
        elif self.ban_duration_ms > 0:
            self.http_rtt_ms = max(0.0, self.ban_duration_ms - ratelimit_wait_ms)
        if not self.result or self.result == "pending":
            self.result = "success" if success else "failed"

    def finish(self, result: str, http_status: Optional[int] = None, now_ns: Optional[int] = None) -> None:
        """Finalizes trace with outcome."""
        if now_ns is not None:
            self.finish_ns = now_ns
        elif self.finish_ns is None:
            self.finish_ns = time.perf_counter_ns()
        self.result = result
        if http_status is not None:
            self.http_status = http_status

    @property
    def decision_duration_ms(self) -> float:
        """CPU time spent making the policy decision (target < 1 ms)."""
        if self.decision_ns and self.handler_start_ns:
            return max(0.0, (self.decision_ns - self.handler_start_ns) / 1_000_000.0)
        return 0.0

    @property
    def ban_duration_ms(self) -> float:
        """Network round-trip latency to Discord REST ban endpoint."""
        if self.ban_response_ns and self.ban_sent_ns:
            return max(0.0, (self.ban_response_ns - self.ban_sent_ns) / 1_000_000.0)
        return 0.0

    @property
    def total_local_ms(self) -> float:
        """Total local processing time from handler start to completion."""
        valid = [cp for cp in (self.finish_ns, self.ban_response_ns, self.decision_ns) if cp is not None]
        end = max(valid) if valid else time.perf_counter_ns()
        return max(0.0, (end - self.handler_start_ns) / 1_000_000.0)


class V2TraceAggregator:
    """In-memory circular buffer for security traces with statistical percentile filtering."""

    def __init__(self, max_samples: int = 5000) -> None:
        self.max_samples = max_samples
        self._traces: Deque[V2SecurityTrace] = deque(maxlen=max_samples)

    def record_trace(self, trace: V2SecurityTrace) -> None:
        """Appends a completed security trace."""
        self._traces.append(trace)

    def get_filtered_traces(
        self,
        path: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[V2SecurityTrace]:
        """Returns traces strictly excluding cache hits and skipped bans.
        
        Mandatory Rule: Excludes cache hits and skipped bans to prevent skewing
        latency benchmarks.
        """
        filtered = []
        for t in self._traces:
            # Exclude cache hits and skipped bans
            if t.result in ("cache_hit", "skipped"):
                continue
            if path and t.path != path:
                continue
            if event_type and t.action != event_type:
                continue
            filtered.append(t)
        return filtered

    def calculate_metrics(
        self,
        traces: List[V2SecurityTrace],
    ) -> Dict[str, Any]:
        """Calculates p50, p95, p99 percentiles for decision, ban, HTTP RTT, rate-limit wait, and total latency."""
        count = len(traces)
        if count == 0:
            return {
                "sample_count": 0,
                "decision_p50_ms": 0.0,
                "decision_p95_ms": 0.0,
                "decision_p99_ms": 0.0,
                "ban_p50_ms": 0.0,
                "ban_p95_ms": 0.0,
                "ban_p99_ms": 0.0,
                "http_rtt_p50_ms": 0.0,
                "http_rtt_p95_ms": 0.0,
                "http_rtt_p99_ms": 0.0,
                "ratelimit_wait_p50_ms": 0.0,
                "ratelimit_wait_p95_ms": 0.0,
                "ratelimit_wait_p99_ms": 0.0,
                "ratelimit_wait_max_ms": 0.0,
                "total_p50_ms": 0.0,
                "total_p95_ms": 0.0,
                "total_p99_ms": 0.0,
                "event_age_p50_ms": 0.0,
                "event_age_p95_ms": 0.0,
                "event_age_p99_ms": 0.0,
            }

        decision_lats = [t.decision_duration_ms for t in traces if t.decision_ns is not None]
        ban_lats = [t.ban_duration_ms for t in traces if t.ban_response_ns is not None]
        http_rtt_lats = [t.http_rtt_ms for t in traces if t.ban_response_ns is not None and t.http_rtt_ms > 0]
        ratelimit_wait_lats = [t.ratelimit_wait_ms for t in traces if t.ban_response_ns is not None]
        total_lats = [t.total_local_ms for t in traces]
        age_lats = [t.event_age_ms for t in traces if t.event_age_ms > 0]

        return {
            "sample_count": count,
            "decision_p50_ms": calculate_percentile(decision_lats, 50.0),
            "decision_p95_ms": calculate_percentile(decision_lats, 95.0),
            "decision_p99_ms": calculate_percentile(decision_lats, 99.0),
            "ban_p50_ms": calculate_percentile(ban_lats, 50.0),
            "ban_p95_ms": calculate_percentile(ban_lats, 95.0),
            "ban_p99_ms": calculate_percentile(ban_lats, 99.0),
            "http_rtt_p50_ms": calculate_percentile(http_rtt_lats, 50.0),
            "http_rtt_p95_ms": calculate_percentile(http_rtt_lats, 95.0),
            "http_rtt_p99_ms": calculate_percentile(http_rtt_lats, 99.0),
            "ratelimit_wait_p50_ms": calculate_percentile(ratelimit_wait_lats, 50.0),
            "ratelimit_wait_p95_ms": calculate_percentile(ratelimit_wait_lats, 95.0),
            "ratelimit_wait_p99_ms": calculate_percentile(ratelimit_wait_lats, 99.0),
            "ratelimit_wait_max_ms": max(ratelimit_wait_lats) if ratelimit_wait_lats else 0.0,
            "total_p50_ms": calculate_percentile(total_lats, 50.0),
            "total_p95_ms": calculate_percentile(total_lats, 95.0),
            "total_p99_ms": calculate_percentile(total_lats, 99.0),
            "event_age_p50_ms": calculate_percentile(age_lats, 50.0),
            "event_age_p95_ms": calculate_percentile(age_lats, 95.0),
            "event_age_p99_ms": calculate_percentile(age_lats, 99.0),
        }

    def generate_latency_report(self) -> str:
        """Formats comprehensive latency report split by path, event type, and event-loop lag."""
        valid_traces = self.get_filtered_traces()
        overall = self.calculate_metrics(valid_traces)

        from core.antinuke_v2.lag_sampler import event_loop_lag_sampler
        if not event_loop_lag_sampler.is_running:
            try:
                event_loop_lag_sampler.start()
            except Exception:
                pass
        lag_m = event_loop_lag_sampler.get_metrics()

        lines = [
            "=======================================================================",
            "              ANTI-NUKE V2 HIGH-SPEED LATENCY REPORT                  ",
            "=======================================================================",
            f"Active Security Incident Samples: {overall['sample_count']}",
            "",
            "--- [EVENT-LOOP HEALTH & LAG SAMPLER (10ms Sampling)] ---",
            f"Total Ticks: {int(lag_m['sample_count'])} | Spikes (>50ms): {int(lag_m['spike_count'])}",
            f"  p50: {lag_m['p50_ms']:.2f}ms | p95: {lag_m['p95_ms']:.2f}ms | p99: {lag_m['p99_ms']:.2f}ms | max: {lag_m['max_ms']:.2f}ms",
            "",
            "--- [OVERALL SECURITY LATENCY] ---",
            f"Event Age (Gateway Snowflake -> Local Receipt):",
            f"  p50: {overall['event_age_p50_ms']:.2f}ms | p95: {overall['event_age_p95_ms']:.2f}ms | p99: {overall['event_age_p99_ms']:.2f}ms",
            f"Decision Latency (Local Pure Policy CPU Time):",
            f"  p50: {overall['decision_p50_ms']:.4f}ms | p95: {overall['decision_p95_ms']:.4f}ms | p99: {overall['decision_p99_ms']:.4f}ms",
            f"Ban Dispatch Latency Breakdown:",
            f"  Total Duration:     p50: {overall['ban_p50_ms']:.2f}ms | p95: {overall['ban_p95_ms']:.2f}ms | p99: {overall['ban_p99_ms']:.2f}ms",
            f"  Network HTTP RTT:   p50: {overall['http_rtt_p50_ms']:.2f}ms | p95: {overall['http_rtt_p95_ms']:.2f}ms | p99: {overall['http_rtt_p99_ms']:.2f}ms",
            f"  Rate-Limit Wait:    p50: {overall['ratelimit_wait_p50_ms']:.2f}ms | p95: {overall['ratelimit_wait_p95_ms']:.2f}ms | p99: {overall['ratelimit_wait_p99_ms']:.2f}ms | max: {overall['ratelimit_wait_max_ms']:.2f}ms",
            f"Total Local Execution (Handler Start -> Ban Complete):",
            f"  p50: {overall['total_p50_ms']:.2f}ms | p95: {overall['total_p95_ms']:.2f}ms | p99: {overall['total_p99_ms']:.2f}ms",
            "",
            "--- [BREAKDOWN BY DETECTION PATH] ---",
        ]

        # Breakdown by Path
        paths = sorted(set(t.path for t in valid_traces))
        if not paths:
            lines.append("  (No path-specific traces recorded yet)")
        for p in paths:
            p_traces = self.get_filtered_traces(path=p)
            p_m = self.calculate_metrics(p_traces)
            lines.append(
                f"• {p} (N={p_m['sample_count']}): "
                f"Decision p50={p_m['decision_p50_ms']:.4f}ms | "
                f"Ban p50={p_m['ban_p50_ms']:.2f}ms | "
                f"Total p50={p_m['total_p50_ms']:.2f}ms (p95={p_m['total_p95_ms']:.2f}ms, p99={p_m['total_p99_ms']:.2f}ms)"
            )

        lines.append("")
        lines.append("--- [BREAKDOWN BY EVENT TYPE] ---")
        actions = sorted(set(t.action for t in valid_traces))
        if not actions:
            lines.append("  (No action-specific traces recorded yet)")
        for a in actions:
            a_traces = self.get_filtered_traces(event_type=a)
            a_m = self.calculate_metrics(a_traces)
            lines.append(
                f"• {a} (N={a_m['sample_count']}): "
                f"Decision p50={a_m['decision_p50_ms']:.4f}ms | "
                f"Ban p50={a_m['ban_p50_ms']:.2f}ms | "
                f"Total p50={a_m['total_p50_ms']:.2f}ms (p95={a_m['total_p95_ms']:.2f}ms, p99={a_m['total_p99_ms']:.2f}ms)"
            )

        if any(t.path == "raw_gateway" for t in valid_traces):
            lines.extend([
                "",
                "Note: raw_gateway ban time is the client-observed Discord REST request duration.",
                "It includes any internal queue/rate-limit wait; that wait is not split out on this path.",
            ])

        lines.append("=======================================================================")
        return "\n".join(lines)


# Global singleton instance for V2
v2_trace_aggregator = V2TraceAggregator()
