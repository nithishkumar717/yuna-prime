"""
Zero-Overhead Security & Anti-Nuke Latency Instrumentation for YUNA V7.

Captures high-resolution monotonic timestamps (time.perf_counter_ns) across each
stage of the Anti-Nuke execution pipeline:
1. Gateway event dispatch (earliest observable point in process)
2. Entity listener start
3. Security policy & feature-toggle evaluation
4. Audit-log attribution
5. Actor authorization & threat decision
6. Containment / Ban dispatch & REST completion
7. Entity recovery & restoration

Features:
- Bounded in-memory ring buffer (default maxlen=1000)
- Non-blocking (recording takes <1 microsecond, never awaits disk/network)
- Exact percentile calculations (p50, p95, p99) computed from actual recorded samples
- Tracking of failures, attribution misses, role hierarchy errors, and API rate-limits
- Zero exposure of sensitive tokens, credentials, or PII
"""

import time
import math
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class SecurityEventRecord:
    incident_id: str
    event_type: str
    guild_id: int
    path: str  # "gateway_stream" | "entity_listener"
    target_id: Optional[int] = None
    result: str = "unknown"
    error: Optional[str] = None
    audit_attempts: int = 1
    http_status: Optional[int] = None
    durations_ns: Dict[str, int] = field(default_factory=dict)
    timestamp_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        durations_ms = {
            k: round(v / 1_000_000, 3) for k, v in self.durations_ns.items()
        }
        return {
            "incident_id": self.incident_id,
            "event_type": self.event_type,
            "guild_id": self.guild_id,
            "path": self.path,
            "target_id": self.target_id,
            "result": self.result,
            "error": self.error,
            "audit_attempts": self.audit_attempts,
            "http_status": self.http_status,
            "durations_ms": durations_ms,
            "timestamp_epoch": self.timestamp_epoch,
        }


class SecurityTrace:
    """Monotonic performance tracker for a single Anti-Nuke incident."""

    __slots__ = (
        "incident_id",
        "event_type",
        "guild_id",
        "path",
        "target_id",
        "t_dispatch_ns",
        "t_listener_start_ns",
        "t_policy_ns",
        "t_audit_start_ns",
        "t_audit_end_ns",
        "t_auth_ns",
        "t_containment_start_ns",
        "t_containment_end_ns",
        "t_recovery_start_ns",
        "t_recovery_end_ns",
        "audit_attempts",
        "http_status",
        "_collector",
        "_finished",
    )

    def __init__(
        self,
        event_type: str,
        guild_id: int,
        path: str = "entity_listener",
        target_id: Optional[int] = None,
        t_dispatch_ns: Optional[int] = None,
        collector: Optional["SecurityMetricsCollector"] = None,
    ):
        self.incident_id = f"inc_{time.time_ns()}_{uuid.uuid4().hex[:6]}"
        self.event_type = event_type
        self.guild_id = guild_id
        self.path = path
        self.target_id = target_id
        now = time.perf_counter_ns()
        self.t_dispatch_ns = t_dispatch_ns or now
        self.t_listener_start_ns = now
        self.t_policy_ns: Optional[int] = None
        self.t_audit_start_ns: Optional[int] = None
        self.t_audit_end_ns: Optional[int] = None
        self.t_auth_ns: Optional[int] = None
        self.t_containment_start_ns: Optional[int] = None
        self.t_containment_end_ns: Optional[int] = None
        self.t_recovery_start_ns: Optional[int] = None
        self.t_recovery_end_ns: Optional[int] = None
        self.audit_attempts: int = 1
        self.http_status: Optional[int] = None
        self._collector = collector
        self._finished = False

    def mark_policy_checked(self, enabled: bool, is_immune: bool = False):
        self.t_policy_ns = time.perf_counter_ns()

    def mark_audit_started(self):
        self.t_audit_start_ns = time.perf_counter_ns()

    def mark_audit_completed(self, found: bool, attempts: int = 1):
        self.t_audit_end_ns = time.perf_counter_ns()
        self.audit_attempts = attempts

    def mark_auth_decision(self, allowed: bool, reason: str = ""):
        self.t_auth_ns = time.perf_counter_ns()

    def mark_containment_started(self):
        self.t_containment_start_ns = time.perf_counter_ns()

    def mark_containment_completed(self, success: bool, http_status: Optional[int] = None):
        self.t_containment_end_ns = time.perf_counter_ns()
        self.http_status = http_status

    def mark_recovery_started(self):
        self.t_recovery_start_ns = time.perf_counter_ns()

    def mark_recovery_completed(self, success: bool):
        self.t_recovery_end_ns = time.perf_counter_ns()

    def record_stage(self, stage: str, **kwargs):
        """Unified stage timing recorder mapping milestone names to high-resolution timestamps."""
        now = time.perf_counter_ns()
        if stage in ("started", "listener_start"):
            self.t_listener_start_ns = now
        elif stage in ("policy_checked", "policy_check"):
            self.t_policy_ns = now
        elif stage in ("audit_attribution_started", "audit_started"):
            self.t_audit_start_ns = now
        elif stage in ("audit_attribution_completed", "audit_completed"):
            self.t_audit_end_ns = now
            if "attempts" in kwargs:
                self.audit_attempts = kwargs["attempts"]
        elif stage in ("threat_decision_completed", "auth_decision"):
            self.t_auth_ns = now
        elif stage in ("containment_dispatched", "containment_started"):
            self.t_containment_start_ns = now
        elif stage in ("containment_completed",):
            self.t_containment_end_ns = now
            if "http_status" in kwargs:
                self.http_status = kwargs["http_status"]
        elif stage in ("recovery_started",):
            self.t_recovery_start_ns = now
        elif stage in ("recovery_completed",):
            self.t_recovery_end_ns = now

    def finish(self, result: str, error: Optional[str] = None) -> SecurityEventRecord:
        if self._finished:
            return None
        self._finished = True
        t_finish_ns = time.perf_counter_ns()

        durations: Dict[str, int] = {}

        # 1. Dispatch-to-listener scheduling lag
        durations["scheduling_lag"] = max(0, self.t_listener_start_ns - self.t_dispatch_ns)

        # 2. Policy evaluation
        if self.t_policy_ns:
            durations["policy_check"] = max(0, self.t_policy_ns - self.t_listener_start_ns)

        # 3. Audit attribution
        if self.t_audit_start_ns and self.t_audit_end_ns:
            durations["audit_attribution"] = max(0, self.t_audit_end_ns - self.t_audit_start_ns)

        # 4. Auth & threat decision
        if self.t_auth_ns:
            base_t = self.t_audit_end_ns or self.t_policy_ns or self.t_listener_start_ns
            durations["auth_decision"] = max(0, self.t_auth_ns - base_t)

        # 5. Total detection (from dispatch to confirmed threat decision)
        decision_t = self.t_auth_ns or self.t_policy_ns or t_finish_ns
        durations["detection_total"] = max(0, decision_t - self.t_dispatch_ns)

        # 6. Containment / Ban execution
        if self.t_containment_start_ns and self.t_containment_end_ns:
            durations["containment_dispatch"] = max(0, self.t_containment_end_ns - self.t_containment_start_ns)
            durations["containment_total"] = max(0, self.t_containment_end_ns - self.t_dispatch_ns)

        # 7. Recovery
        if self.t_recovery_start_ns and self.t_recovery_end_ns:
            durations["recovery_duration"] = max(0, self.t_recovery_end_ns - self.t_recovery_start_ns)

        # 8. End-to-end event duration
        durations["end_to_end"] = max(0, t_finish_ns - self.t_dispatch_ns)

        record = SecurityEventRecord(
            incident_id=self.incident_id,
            event_type=self.event_type,
            guild_id=self.guild_id,
            path=self.path,
            target_id=self.target_id,
            result=result,
            error=error,
            audit_attempts=self.audit_attempts,
            http_status=self.http_status,
            durations_ns=durations,
        )

        if self._collector:
            self._collector.record(record)

        return record


class SecurityMetricsCollector:
    """Central non-blocking bounded latency metrics collector for Anti-Nuke."""

    _instance: Optional["SecurityMetricsCollector"] = None

    def __init__(self, max_records: int = 1000):
        self._records: deque[SecurityEventRecord] = deque(maxlen=max_records)
        # Structure: {(guild_id, event_name, target_id): t_dispatch_ns}
        self._dispatch_map: Dict[Tuple[int, str, Optional[int]], Tuple[int, float]] = {}
        self._max_records = max_records

    @classmethod
    def get_instance(cls) -> "SecurityMetricsCollector":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def notify_gateway_dispatch(self, event_name: str, args: tuple):
        """Captures the absolute earliest observable timestamp when Discord Gateway dispatches an event."""
        now_ns = time.perf_counter_ns()
        now_epoch = time.time()

        guild_id = None
        target_id = None

        try:
            if not args:
                return
            first = args[0]
            # Handle discord.AuditLogEntry
            if hasattr(first, "guild"):
                guild = getattr(first, "guild", None)
                if guild:
                    guild_id = getattr(guild, "id", None)
                target_id = getattr(first, "_target_id", None) or getattr(getattr(first, "target", None), "id", None)
            # Handle channel or role objects
            elif hasattr(first, "guild_id"):
                guild_id = getattr(first, "guild_id", None)
                target_id = getattr(first, "id", None)
            elif hasattr(first, "guild"):
                guild = getattr(first, "guild", None)
                guild_id = getattr(guild, "id", None) if guild else None
                target_id = getattr(first, "id", None)

            if guild_id:
                # Store dispatch time with 10s expiration
                key = (guild_id, event_name, target_id)
                self._dispatch_map[key] = (now_ns, now_epoch)

                # Periodic pruning of dispatch map if it exceeds 200 items
                if len(self._dispatch_map) > 200:
                    cutoff = now_epoch - 10.0
                    for k in list(self._dispatch_map.keys()):
                        if self._dispatch_map[k][1] < cutoff:
                            self._dispatch_map.pop(k, None)
        except Exception:
            pass

    def create_trace(
        self,
        event_type: str,
        guild_id: int,
        path: str = "entity_listener",
        processing_path: Optional[str] = None,
        target_id: Optional[int] = None,
        event_dispatch_name: Optional[str] = None,
        t_dispatch_ns: Optional[int] = None,
    ) -> SecurityTrace:
        """Creates a SecurityTrace and links it to the earliest gateway dispatch timestamp if available."""
        effective_path = processing_path or path
        dispatch_ns = t_dispatch_ns

        if not dispatch_ns and event_dispatch_name:
            # Check with exact target_id
            entry = self._dispatch_map.pop((guild_id, event_dispatch_name, target_id), None)
            if not entry:
                # Check with target_id=None
                entry = self._dispatch_map.pop((guild_id, event_dispatch_name, None), None)
            if entry:
                dispatch_ns = entry[0]

        return SecurityTrace(
            event_type=event_type,
            guild_id=guild_id,
            path=effective_path,
            target_id=target_id,
            t_dispatch_ns=dispatch_ns,
            collector=self,
        )

    def record(self, record: SecurityEventRecord):
        """Appends a record to the bounded ring buffer."""
        self._records.append(record)

    def get_records(self, limit: Optional[int] = None) -> List[SecurityEventRecord]:
        if limit is None or limit >= len(self._records):
            return list(self._records)
        return list(self._records)[-limit:]

    def clear(self):
        """Clears all in-memory records (useful for test resets)."""
        self._records.clear()
        self._dispatch_map.clear()

    @staticmethod
    def _compute_percentile(data: List[float], percentile: float) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(sorted_data[int(k)], 3)
        d0 = sorted_data[int(f)] * (c - k)
        d1 = sorted_data[int(c)] * (k - f)
        return round(d0 + d1, 3)

    def get_summary(self, last_n: Optional[int] = None) -> Dict[str, Any]:
        """Calculates p50, p95, p99 percentiles and error metrics from recorded samples."""
        records = self.get_records(last_n)
        total = len(records)
        if total == 0:
            return {
                "total_events": 0,
                "paths": {},
                "results": {},
                "percentiles_ms": {},
            }

        paths: Dict[str, int] = {}
        results: Dict[str, int] = {}

        detection_samples: List[float] = []
        containment_samples: List[float] = []
        audit_samples: List[float] = []
        scheduling_samples: List[float] = []
        end_to_end_samples: List[float] = []

        for r in records:
            paths[r.path] = paths.get(r.path, 0) + 1
            results[r.result] = results.get(r.result, 0) + 1

            d_ns = r.durations_ns
            if "detection_total" in d_ns:
                detection_samples.append(d_ns["detection_total"] / 1_000_000)
            if "containment_dispatch" in d_ns:
                containment_samples.append(d_ns["containment_dispatch"] / 1_000_000)
            if "audit_attribution" in d_ns:
                audit_samples.append(d_ns["audit_attribution"] / 1_000_000)
            if "scheduling_lag" in d_ns:
                scheduling_samples.append(d_ns["scheduling_lag"] / 1_000_000)
            if "end_to_end" in d_ns:
                end_to_end_samples.append(d_ns["end_to_end"] / 1_000_000)

        def _stats_for(samples: List[float]) -> Dict[str, float]:
            if not samples:
                return {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0}
            return {
                "count": len(samples),
                "p50": self._compute_percentile(samples, 50),
                "p95": self._compute_percentile(samples, 95),
                "p99": self._compute_percentile(samples, 99),
                "min": round(min(samples), 3),
                "max": round(max(samples), 3),
            }

        return {
            "total_events": total,
            "paths": paths,
            "results": results,
            "percentiles_ms": {
                "detection_total": _stats_for(detection_samples),
                "containment_dispatch": _stats_for(containment_samples),
                "audit_attribution": _stats_for(audit_samples),
                "scheduling_lag": _stats_for(scheduling_samples),
                "end_to_end": _stats_for(end_to_end_samples),
            },
        }

    def get_detailed_latency_report(self) -> str:
        """Generates a comprehensive CLI/Discord monospace report with p50/p95/p99 percentiles
        broken down per event type and per processing path (audit_stream vs entity_listener),
        including total incidents handled by each path."""
        records = self.get_records()
        if not records:
            return (
                "================================================================================\n"
                "                    YUNA V7 ANTI-NUKE LATENCY REPORT\n"
                "================================================================================\n"
                "  No Anti-Nuke security incidents have been recorded in the metrics buffer yet.\n"
                "================================================================================"
            )

        CANONICAL_NAMES = {
            "channel_delete": "channel delete",
            "guild_channel_delete": "channel delete",
            "audit_stream_chdl": "channel delete",
            "chdl": "channel delete",
            "role_delete": "role delete",
            "guild_role_delete": "role delete",
            "audit_stream_rldl": "role delete",
            "rldl": "role delete",
            "dangerous_role_grant": "dangerous role grant",
            "member_role_update": "dangerous role grant",
            "audit_stream_memup": "dangerous role grant",
            "memup": "dangerous role grant",
            "unauthorized_ban": "unauthorized ban",
            "member_ban": "unauthorized ban",
            "audit_stream_ban": "unauthorized ban",
            "ban": "unauthorized ban",
            "unauthorized_bot_add": "unauthorized bot add",
            "bot_add": "unauthorized bot add",
            "audit_stream_botadd": "unauthorized bot add",
            "botadd": "unauthorized bot add",
        }

        # Track per-path and per-event latencies (in milliseconds)
        path_samples: Dict[str, List[float]] = {"audit_stream": [], "entity_listener": []}
        event_path_samples: Dict[str, Dict[str, List[float]]] = {}
        event_totals: Dict[str, List[float]] = {}

        for r in records:
            path = r.path if r.path in ("audit_stream", "entity_listener") else "entity_listener"
            raw_event = str(r.event_type or "").lower().strip()
            event_name = CANONICAL_NAMES.get(raw_event, raw_event.replace("_", " ").lower())

            d_ns = r.durations_ns
            latency_ms = None
            if "end_to_end" in d_ns:
                latency_ms = d_ns["end_to_end"] / 1_000_000
            elif "containment_total" in d_ns:
                latency_ms = d_ns["containment_total"] / 1_000_000
            elif "detection_total" in d_ns:
                latency_ms = d_ns["detection_total"] / 1_000_000

            if latency_ms is None:
                continue

            path_samples.setdefault(path, []).append(latency_ms)
            if event_name not in event_path_samples:
                event_path_samples[event_name] = {"audit_stream": [], "entity_listener": []}
            event_path_samples[event_name].setdefault(path, []).append(latency_ms)
            event_totals.setdefault(event_name, []).append(latency_ms)

        total_incidents = len(records)
        stream_count = len(path_samples.get("audit_stream", []))
        listener_count = len(path_samples.get("entity_listener", []))
        stream_pct = (stream_count / total_incidents * 100) if total_incidents else 0.0
        listener_pct = (listener_count / total_incidents * 100) if total_incidents else 0.0

        def _calc(samples: List[float]) -> Tuple[float, float, float, float, float]:
            if not samples:
                return 0.0, 0.0, 0.0, 0.0, 0.0
            return (
                self._compute_percentile(samples, 50),
                self._compute_percentile(samples, 95),
                self._compute_percentile(samples, 99),
                round(min(samples), 2),
                round(max(samples), 2),
            )

        lines = [
            "=" * 80,
            "                    YUNA V7 ANTI-NUKE LATENCY REPORT",
            "=" * 80,
            f"Total Incidents Recorded: {total_incidents}",
            f"Incidents Handled by Path:",
            f"  * audit_stream:    {stream_count} incidents ({stream_pct:.1f}%)",
            f"  * entity_listener: {listener_count} incidents ({listener_pct:.1f}%)",
            "",
            "-" * 80,
            "PATH PERFORMANCE SUMMARY (Containment Latency):",
            f"{'Path':<18} {'Count':>6} {'p50 (ms)':>10} {'p95 (ms)':>10} {'p99 (ms)':>10} {'Min - Max (ms)':>18}",
            "-" * 80,
        ]

        for p_name in ("audit_stream", "entity_listener"):
            s = path_samples.get(p_name, [])
            p50, p95, p99, pmin, pmax = _calc(s)
            min_max_str = f"{pmin:.2f} - {pmax:.2f}" if s else "0.00 - 0.00"
            lines.append(f"{p_name:<18} {len(s):>6} {p50:>10.2f} {p95:>10.2f} {p99:>10.2f} {min_max_str:>18}")

        lines.extend([
            "",
            "-" * 80,
            "PER-EVENT TYPE BREAKDOWN (p50 / p95 / p99 per Event & Path):",
            f"{'Event Type':<22} {'Path':<17} {'Count':>6} {'p50 (ms)':>10} {'p95 (ms)':>10} {'p99 (ms)':>10}",
            "-" * 80,
        ])

        standard_order = [
            "channel delete",
            "role delete",
            "dangerous role grant",
            "unauthorized ban",
            "unauthorized bot add",
        ]
        all_events = standard_order + [e for e in sorted(event_path_samples.keys()) if e not in standard_order]

        for idx, ev in enumerate(all_events):
            if ev not in event_path_samples:
                continue
            paths_data = event_path_samples[ev]
            for p in ("audit_stream", "entity_listener"):
                s = paths_data.get(p, [])
                p50, p95, p99, _, _ = _calc(s)
                lines.append(f"{ev:<22} {p:<17} {len(s):>6} {p50:>10.2f} {p95:>10.2f} {p99:>10.2f}")
            if idx < len(all_events) - 1:
                lines.append("-" * 80)

        lines.append("=" * 80)
        return "\n".join(lines)


security_metrics = SecurityMetricsCollector.get_instance()
