"""Anti-Nuke V2 Engine — Pure Synchronous Policy Decision Pipeline.

Evaluates security policy deterministically in < 1 ms of CPU time.
Pure and synchronous: zero awaits, zero network I/O, zero disk I/O.
Every early exit logs a single structured line with a distinct reason_code.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Set

from core.antinuke_v2.models import (
    Decision,
    DecisionAction,
    PolicyContext,
    PunishmentType,
)
from core.antinuke_v2.rate_limiter import SlidingWindowRateLimiter
from core.antinuke_v2.role_index import WhitelistedRoleMemberIndex
from core.antinuke_v2.state_store import (
    ACTION_COL_TO_DASHBOARD_KEY,
    ACTION_TO_WHITELIST_COLUMNS,
    GuildSecurityConfig,
)
from utils.config import SIBLING_BOT_IDS


logger = logging.getLogger("antinuke.v2.policy")


def _log_and_return(
    decision: Decision,
    guild_id: Optional[int],
    actor_id: Optional[int],
    action: str,
) -> Decision:
    """Helper to log exactly one line per decision before returning."""
    if decision.action == DecisionAction.PUNISH:
        logger.info(
            "[V2Policy] Guild=%s Actor=%s Action=%s -> Decision=%s Reason=%s Punishment=%s",
            guild_id,
            actor_id,
            action,
            decision.action.value,
            decision.reason_code,
            decision.punishment.value if decision.punishment else "none",
        )
    else:
        logger.debug(
            "[V2Policy] Guild=%s Actor=%s Action=%s -> Decision=%s Reason=%s Punishment=%s",
            guild_id,
            actor_id,
            action,
            decision.action.value,
            decision.reason_code,
            decision.punishment.value if decision.punishment else "none",
        )
    return decision


def evaluate_policy(
    guild: Any,
    actor: Any,
    action: str,
    target: Any,
    context: PolicyContext,
    state: GuildSecurityConfig,
    role_index: WhitelistedRoleMemberIndex,
    rate_limiter: SlidingWindowRateLimiter,
    bot_owner_ids: Optional[Set[int]] = None,
) -> Decision:
    """Pure, synchronous decision function for Discord security policy evaluation.
    
    Guarantees < 1 ms CPU execution time. Zero I/O, zero awaits.
    
    Args:
        guild: Discord Guild object
        actor: Discord Member or User initiating the action
        action: Anti-nuke action identifier (e.g. 'chdl', 'ban', 'rlcr')
        target: Target Discord entity or Object
        context: PolicyContext containing timestamps, target matching, and resolution state
        state: In-memory GuildSecurityConfig for this guild
        role_index: In-memory WhitelistedRoleMemberIndex
        rate_limiter: SlidingWindowRateLimiter instance
        bot_owner_ids: Global bot owner user IDs
        
    Returns:
        Decision(action, reason_code, punishment, details)
    """
    guild_id: Optional[int] = getattr(guild, "id", None)
    actor_id: Optional[int] = getattr(actor, "id", None)
    action_key = action.lower()

    if guild_id is None or actor_id is None:
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="INVALID_GUILD_OR_ACTOR",
            ),
            guild_id, actor_id, action_key
        )

    # 1. IMMUNITY: Bot Client (Self) & Sibling Bots (Yuna, Zyuna)
    bot_id = state.bot_id
    if bot_id is None and hasattr(guild, "me") and guild.me and hasattr(guild.me, "id"):
        bot_id = guild.me.id
        state.bot_id = bot_id
    if actor_id == bot_id or actor_id in SIBLING_BOT_IDS:
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="IMMUNITY_SIBLING_BOT" if actor_id in SIBLING_BOT_IDS else "IMMUNITY_BOT_CLIENT",
            ),
            guild_id, actor_id, action_key
        )

    # 1b. Fast Global Immunity Check
    from core.cache.security_cache import security_cache
    if security_cache.is_immune(guild, actor):
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="IMMUNITY_GLOBAL",
            ),
            guild_id, actor_id, action_key
        )

    # 2. IMMUNITY: Server Owner
    owner_id = state.owner_id
    if owner_id is None:
        owner_id = getattr(guild, "owner_id", None)
        if owner_id:
            state.owner_id = owner_id
    guild_owner = getattr(guild, "owner_id", None)
    if actor_id == owner_id or (guild_owner is not None and actor_id == int(guild_owner)):
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="IMMUNITY_GUILD_OWNER",
            ),
            guild_id, actor_id, action_key
        )

    # 3. IMMUNITY: Global Bot Owner / Developer
    if bot_owner_ids and actor_id in bot_owner_ids:
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="IMMUNITY_BOT_OWNER",
            ),
            guild_id, actor_id, action_key
        )

    # 4. IMMUNITY: Extra Owner (Co-Owner)
    if actor_id in state.extra_owners or security_cache.is_extra_owner(guild_id, actor_id):
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="IMMUNITY_EXTRA_OWNER",
            ),
            guild_id, actor_id, action_key
        )

    # 5. GLOBAL TOGGLE: Anti-Nuke Enabled for Guild
    if not state.antinuke_enabled:
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="GLOBAL_ANTINUKE_DISABLED",
            ),
            guild_id, actor_id, action_key
        )

    # 6. GRANULAR TOGGLE: Per-Action Toggle
    if not state.is_action_enabled(action_key):
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="ACTION_TOGGLE_DISABLED",
            ),
            guild_id, actor_id, action_key
        )

    # 7. ATTRIBUTION: Stale Audit Log Entry Check
    if context.audit_entry_created_at is not None:
        try:
            ts = context.audit_entry_created_at.timestamp()
            entry_age = context.event_time - ts
            if isinstance(entry_age, (int, float)) and entry_age > context.age_limit_seconds:
                return _log_and_return(
                    Decision(
                        action=DecisionAction.ALLOW,
                        reason_code="STALE_AUDIT_ENTRY",
                        details={"entry_age": entry_age, "age_limit": context.age_limit_seconds},
                    ),
                    guild_id, actor_id, action_key
                )
        except (TypeError, AttributeError):
            pass

    # 8. ATTRIBUTION: Strict Target Match Check (No Heuristic Guessing)
    if context.raw_entry_target_id is not None and context.target_id is not None:
        if context.raw_entry_target_id != context.target_id:
            # Ambiguity detected: strictly alert instead of taking a destructive false action
            return _log_and_return(
                Decision(
                    action=DecisionAction.ALERT_ONLY,
                    reason_code="ATTRIBUTION_TARGET_MISMATCH_AMBIGUITY",
                    details={
                        "raw_target": context.raw_entry_target_id,
                        "expected_target": context.target_id,
                    },
                ),
                guild_id, actor_id, action_key
            )

    # 9. WHITELIST: Whitelisted Bot
    if actor_id in state.whitelisted_bots or security_cache.is_bot_whitelisted(guild_id, actor_id):
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="WHITELISTED_BOT",
            ),
            guild_id, actor_id, action_key
        )

    # 10. WHITELIST: Whitelisted User (Per-action or Full)
    if security_cache.is_executor_allowed_sync(guild, actor, action_key) or security_cache.is_whitelisted(guild_id, actor_id):
        return _log_and_return(
            Decision(
                action=DecisionAction.ALLOW,
                reason_code="WHITELISTED_USER",
            ),
            guild_id, actor_id, action_key
        )

    if actor_id in state.whitelisted_users:
        user_perms = state.whitelisted_users[actor_id]
        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(action_key, action_key)
        whitelist_keys = (action_key, dash_key) + ACTION_TO_WHITELIST_COLUMNS.get(action_key, ())
        if (
            user_perms.get("all", False)
            or any(user_perms.get(key, False) for key in whitelist_keys)
        ):
            return _log_and_return(
                Decision(
                    action=DecisionAction.ALLOW,
                    reason_code="WHITELISTED_USER",
                ),
                guild_id, actor_id, action_key
            )

    # 11. WHITELIST: Whitelisted Role (Human members only; bots must be explicitly in whitelisted_bots)
    is_actor_bot = bool(getattr(actor, "bot", False) or context.actor_is_bot)
    if not is_actor_bot and state.whitelisted_roles:
        # Check direct roles on actor if Member object (zero-allocation short-circuit)
        actor_roles = getattr(actor, "roles", None)
        if actor_roles and any(getattr(r, "id", None) in state.whitelisted_roles for r in actor_roles):
            return _log_and_return(
                Decision(
                    action=DecisionAction.ALLOW,
                    reason_code="WHITELISTED_ROLE",
                ),
                guild_id, actor_id, action_key
            )

        # Check WhitelistedRoleMemberIndex
        if role_index.has_whitelisted_role(guild_id, actor_id):
            return _log_and_return(
                Decision(
                    action=DecisionAction.ALLOW,
                    reason_code="WHITELISTED_ROLE",
                ),
                guild_id, actor_id, action_key
            )

    # 12. UNCACHED ACTOR SAFETY: Never ban on a cache miss alone (only applies to human staff)!
    if not is_actor_bot and state.whitelisted_roles and context.actor_unresolved:
        # The actor could not be resolved from local cache or bounded REST lookup.
        # Punishing here could falsely ban a whitelisted staff member!
        return _log_and_return(
            Decision(
                action=DecisionAction.ALERT_ONLY,
                reason_code="UNRESOLVED_ACTOR_CACHE_MISS_ALERT",
                details={"unresolved": True},
            ),
            guild_id, actor_id, action_key
        )

    # 13. TURBO BAN PREDICTION: High-Speed Bot Action Detection
    # If the actor is a bot and we're seeing a protected action, 
    # check if it's whitelisted. If not, this is a high-probability attack.
    is_actor_bot = bool(getattr(actor, "bot", False) or context.actor_is_bot)
    if is_actor_bot and actor_id not in state.whitelisted_bots:
        # Check security cache for latest whitelist status (fast path)
        from core.cache.security_cache import security_cache
        if not security_cache.is_bot_whitelisted(guild_id, actor_id):
            return _log_and_return(
                Decision(
                    action=DecisionAction.PUNISH,
                    reason_code="TURBO_BAN_PREDICTION",
                    punishment=PunishmentType.BAN,
                    details={"prediction": "unauthorized_bot_action"},
                ),
                guild_id, actor_id, action_key
            )

    # 14. NEW BOT VIGILANCE & THRESHOLD EVALUATION
    is_new_bot = False

    if hasattr(state, "is_new_bot") and state.is_new_bot(actor_id):
        is_new_bot = True
    elif is_actor_bot:
        actor_joined_at = getattr(actor, "joined_at", None)
        if actor_joined_at:
            try:
                j_ts = actor_joined_at.timestamp()
                if (context.event_time - j_ts) < 86400.0:
                    is_new_bot = True
                    if hasattr(state, "record_new_bot"):
                        state.record_new_bot(actor_id, j_ts)
            except Exception:
                pass

    # STRICT NEW BOT & UNWHITELISTED BOT ZERO TOLERANCE:
    # If the actor is a newly joined bot or unwhitelisted bot performing ANY protected action,
    # override limit to 1 (Zero-Tolerance: instant containment on first action!)
    if is_new_bot or (is_actor_bot and actor_id not in state.whitelisted_bots):
        limit = 1
        window = 300
    else:
        limit, window = state.get_threshold(action_key)

    if context.dry_run:
        count = rate_limiter.get_count(
            guild_id=guild_id,
            actor_id=actor_id,
            action=action_key,
            window=float(window),
            now=context.event_time,
        )
        is_exceeded = (count + 1 >= limit) if limit > 1 else True
        count = count + 1
    else:
        is_exceeded, count = rate_limiter.check_and_record(
            guild_id=guild_id,
            actor_id=actor_id,
            action=action_key,
            limit=limit,
            window=float(window),
            now=context.event_time,
        )

    if is_exceeded:
        punishment = state.get_punishment(action_key)
        if is_new_bot:
            punishment = PunishmentType.BAN
            reason_code = "NEW_BOT_UNAUTHORIZED_ACTION"
        elif is_actor_bot and actor_id not in state.whitelisted_bots:
            punishment = PunishmentType.BAN
            reason_code = "UNAUTHORIZED_BOT_ACTION"
        else:
            reason_code = "UNAUTHORIZED_ACTION_THRESHOLD_EXCEEDED"

        return _log_and_return(
            Decision(
                action=DecisionAction.PUNISH,
                reason_code=reason_code,
                punishment=punishment,
                details={
                    "count": count,
                    "limit": limit,
                    "window": window,
                    "is_new_bot": is_new_bot,
                    "is_actor_bot": is_actor_bot,
                },
            ),
            guild_id, actor_id, action_key
        )

    return _log_and_return(
        Decision(
            action=DecisionAction.ALLOW,
            reason_code="ACTION_WITHIN_THRESHOLD_LIMIT",
            details={"count": count, "limit": limit, "window": window},
        ),
        guild_id, actor_id, action_key
    )
