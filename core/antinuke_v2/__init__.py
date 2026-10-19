"""Anti-Nuke V2 Engine — Next-Generation High-Speed Discord Security Core.

Runs in parallel with the legacy anti-nuke engine behind a feature flag.
Guarantees sub-millisecond local CPU policy evaluation with zero false bans.
"""
from __future__ import annotations

from core.antinuke_v2.engine import evaluate_policy
from core.antinuke_v2.models import (
    PROTECTED_ACTIONS,
    Decision,
    DecisionAction,
    PolicyContext,
    PunishmentType,
)
from core.antinuke_v2.rate_limiter import SlidingWindowRateLimiter
from core.antinuke_v2.resolver import ActorResolver
from core.antinuke_v2.role_index import WhitelistedRoleMemberIndex
from core.antinuke_v2.state_store import (
    ACTION_COL_TO_DASHBOARD_KEY,
    DASHBOARD_KEY_TO_ACTION_COL,
    GuildSecurityConfig,
    V2StateStore,
)

from core.antinuke_v2.containment import (
    ContainmentResult,
    V2Neutralizer,
)
from core.antinuke_v2.incident_tracker import (
    V2IncidentRecord,
    V2IncidentTracker,
)

from core.antinuke_v2.action_mapper import (
    ActionMapper,
    V2_PROTECTED_ACTIONS,
    AUDIT_ACTION_MAP,
)
from core.antinuke_v2.stream_health import StreamHealthTracker
from core.antinuke_v2.attack_mode import AttackModeManager
from core.antinuke_v2.detection_coordinator import DetectionCoordinator

from core.antinuke_v2.snapshot import (
    ChannelSnapshot,
    RoleSnapshot,
    WebhookSnapshot,
    EmojiSnapshot,
    OverwriteSnapshot,
    GuildSnapshotStore,
)
from core.antinuke_v2.recovery import (
    RecoveryResult,
    V2RecoveryEngine,
)

from core.antinuke_v2.trace import (
    V2SecurityTrace,
    V2TraceAggregator,
    v2_trace_aggregator,
    calculate_percentile,
    snowflake_to_timestamp_ns,
)
from core.antinuke_v2.warmer import (
    DiscordConnectionWarmer,
    discord_connection_warmer,
)
from core.antinuke_v2.explainer import (
    DecisionExplanation,
    explain_decision,
)
from core.antinuke_v2.notifier import (
    IncidentCluster,
    V2DashboardQueue,
    V2DMDeduplicator,
    V2LogChannelDispatcher,
    V2Notifier,
    v2_notifier,
)
from core.antinuke_v2.router import (
    EngineMode,
    ShadowDivergenceRecord,
    V2EngineRouter,
    v2_engine_router,
)
from core.antinuke_v2.lag_sampler import (
    EventLoopLagSampler,
    LagSpikeRecord,
    event_loop_lag_sampler,
)
from core.antinuke_v2.fast_path import (
    RAW_AUDIT_ACTION_MAP,
    RawAuditLogEntry,
    handle_raw_gateway_audit_entry,
    install_fast_path,
)

__all__ = (
    "evaluate_policy",
    "Decision",
    "DecisionAction",
    "PunishmentType",
    "PolicyContext",
    "PROTECTED_ACTIONS",
    "SlidingWindowRateLimiter",
    "ActorResolver",
    "WhitelistedRoleMemberIndex",
    "GuildSecurityConfig",
    "V2StateStore",
    "ACTION_COL_TO_DASHBOARD_KEY",
    "DASHBOARD_KEY_TO_ACTION_COL",
    "ContainmentResult",
    "V2Neutralizer",
    "V2IncidentRecord",
    "V2IncidentTracker",
    "ActionMapper",
    "V2_PROTECTED_ACTIONS",
    "AUDIT_ACTION_MAP",
    "StreamHealthTracker",
    "AttackModeManager",
    "DetectionCoordinator",
    "ChannelSnapshot",
    "RoleSnapshot",
    "WebhookSnapshot",
    "EmojiSnapshot",
    "OverwriteSnapshot",
    "GuildSnapshotStore",
    "RecoveryResult",
    "V2RecoveryEngine",
    "V2SecurityTrace",
    "V2TraceAggregator",
    "v2_trace_aggregator",
    "calculate_percentile",
    "snowflake_to_timestamp_ns",
    "DiscordConnectionWarmer",
    "discord_connection_warmer",
    "DecisionExplanation",
    "explain_decision",
    "IncidentCluster",
    "V2DashboardQueue",
    "V2DMDeduplicator",
    "V2LogChannelDispatcher",
    "V2Notifier",
    "v2_notifier",
    "EngineMode",
    "ShadowDivergenceRecord",
    "V2EngineRouter",
    "v2_engine_router",
    "EventLoopLagSampler",
    "LagSpikeRecord",
    "event_loop_lag_sampler",
)


