"""Anti-Nuke V2 Engine — Synchronous Decision Explainer & Dry-Run Inspector.

Provides full diagnostic visibility into the pure synchronous policy engine:
1. Explains why a user would be allowed, banned, or alerted for any action.
2. Inspects immunity hierarchy, whitelist status, rate limit thresholds, and toggles.
3. Completely side-effect free: never consumes rate limit tokens and never bans.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Union

import discord

from core.antinuke_v2.engine import evaluate_policy
from core.antinuke_v2.models import (
    PROTECTED_ACTIONS,
    Decision,
    DecisionAction,
    PolicyContext,
)
from core.antinuke_v2.rate_limiter import SlidingWindowRateLimiter
from core.antinuke_v2.role_index import WhitelistedRoleMemberIndex
from core.antinuke_v2.state_store import (
    ACTION_COL_TO_DASHBOARD_KEY,
    GuildSecurityConfig,
)

logger = logging.getLogger("antinuke.v2.explainer")

FRIENDLY_REASONS: Dict[str, str] = {
    "antinuke_disabled": "Anti-Nuke is completely disabled for this server.",
    "action_disabled": "The toggle for this specific action is disabled.",
    "immune_server_owner": "User is the Discord Server Owner (Absolute Immunity).",
    "immune_bot_owner": "User is a Global Bot Developer / Bot Owner (Absolute Immunity).",
    "immune_extra_owner": "User is configured as an Extra Owner in Yuna security settings.",
    "immune_client_bot": "User is the Bot itself (Immune from self-containment).",
    "whitelisted_user": "User is explicitly whitelisted for this action.",
    "whitelisted_role": "User holds a role that is whitelisted for this action.",
    "whitelisted_bot": "Bot is explicitly added to the trusted Bot Whitelist.",
    "under_threshold": "Action velocity is currently within permissible threshold limits.",
    "exceeded_threshold": "Action velocity has exceeded rate limit threshold (Triggers Neutralization).",
    "target_mismatch_alert": "Ambiguous executor match — alerted security team instead of false ban.",
    "stale_audit_log_entry": "Audit log entry is older than age threshold (Skipped).",
}

ENGINE_CODE_TO_FRIENDLY_CODE: Dict[str, str] = {
    "IMMUNITY_GUILD_OWNER": "immune_server_owner",
    "IMMUNITY_EXTRA_OWNER": "immune_extra_owner",
    "IMMUNITY_BOT_OWNER": "immune_bot_owner",
    "IMMUNITY_BOT_CLIENT": "immune_client_bot",
    "GLOBAL_ANTINUKE_DISABLED": "antinuke_disabled",
    "ACTION_TOGGLE_DISABLED": "action_disabled",
    "WHITELISTED_USER": "whitelisted_user",
    "WHITELISTED_ROLE": "whitelisted_role",
    "WHITELISTED_BOT": "whitelisted_bot",
    "ACTION_WITHIN_THRESHOLD_LIMIT": "under_threshold",
    "UNAUTHORIZED_ACTION_THRESHOLD_EXCEEDED": "exceeded_threshold",
    "ATTRIBUTION_TARGET_MISMATCH_AMBIGUITY": "target_mismatch_alert",
    "STALE_AUDIT_ENTRY": "stale_audit_log_entry",
    "UNRESOLVED_ACTOR_CACHE_MISS_ALERT": "target_mismatch_alert",
}


@dataclass
class DecisionExplanation:
    """Detailed synchronous analysis of how V2 evaluates an action for a user."""
    guild_id: int
    actor_id: int
    actor_name: str
    action: str
    decision: DecisionAction
    reason_code: str
    reason_description: str
    is_immune: bool
    is_whitelisted: bool
    current_count: int
    max_limit: int
    window_seconds: int
    punishment_type: str

    def to_embed(self) -> discord.Embed:
        """Generates a rich Discord embed detailing the security decision."""
        if self.decision == DecisionAction.ALLOW:
            color = 0x2ECC71  # Green
            status_text = "✅ **ALLOWED**"
        elif self.decision == DecisionAction.PUNISH:
            color = 0xE74C3C  # Red
            status_text = f"🚨 **PUNISHED ({self.punishment_type.upper()})**"
        else:
            color = 0xF1C40F  # Yellow
            status_text = "⚠️ **ALERT ONLY**"

        embed = discord.Embed(
            title=f"🛡️ Anti-Nuke V2 Decision Path: {self.actor_name}",
            description=f"Action: `{self.action}` | Outcome: {status_text}",
            color=color,
        )
        embed.add_field(name="Reason Code", value=f"`{self.reason_code}`", inline=True)
        embed.add_field(name="Explanation", value=self.reason_description, inline=False)
        embed.add_field(
            name="Security Status",
            value=(
                f"• **Immune:** {'Yes' if self.is_immune else 'No'}\n"
                f"• **Whitelisted:** {'Yes' if self.is_whitelisted else 'No'}\n"
                f"• **Velocity:** {self.current_count} / {self.max_limit} in {self.window_seconds}s\n"
                f"• **Configured Punishment:** `{self.punishment_type}`"
            ),
            inline=False,
        )
        embed.set_footer(text="Pure Synchronous Policy Engine (0ms REST latency) • Anti-Nuke V2")
        return embed

    def to_text(self) -> str:
        """Plain-text diagnostic breakdown."""
        return (
            f"[V2 Decision Path]\n"
            f"Actor: {self.actor_name} ({self.actor_id})\n"
            f"Action: {self.action}\n"
            f"Outcome: {self.decision.value.upper()}\n"
            f"Reason: {self.reason_code} - {self.reason_description}\n"
            f"Immune: {self.is_immune} | Whitelisted: {self.is_whitelisted}\n"
            f"Rate Limit: {self.current_count}/{self.max_limit} ({self.window_seconds}s)\n"
            f"Punishment: {self.punishment_type}"
        )


def explain_decision(
    guild: discord.Guild,
    actor: Union[discord.Member, discord.User],
    action: str,
    state: GuildSecurityConfig,
    context: Optional[PolicyContext] = None,
    role_index: Optional[WhitelistedRoleMemberIndex] = None,
    rate_limiter: Optional[SlidingWindowRateLimiter] = None,
    bot_owner_ids: Optional[Set[int]] = None,
) -> DecisionExplanation:
    """Performs a pure, side-effect-free diagnostic evaluation of what V2 would do."""
    now = time.time()
    ctx = context or PolicyContext(event_time=now, dry_run=True)
    ctx.dry_run = True

    limiter = rate_limiter or getattr(state, "rate_limiter", None) or SlidingWindowRateLimiter()
    r_index = role_index or WhitelistedRoleMemberIndex()
    owners = bot_owner_ids or set()

    decision = evaluate_policy(
        guild=guild,
        actor=actor,
        action=action,
        target=None,
        context=ctx,
        state=state,
        role_index=r_index,
        rate_limiter=limiter,
        bot_owner_ids=owners,
    )

    friendly_code = ENGINE_CODE_TO_FRIENDLY_CODE.get(decision.reason_code, decision.reason_code.lower())
    reason_desc = FRIENDLY_REASONS.get(friendly_code, FRIENDLY_REASONS.get(decision.reason_code, f"Rule '{decision.reason_code}' applied."))

    actor_id = getattr(actor, "id", 0)
    is_owner = (actor_id == getattr(guild, "owner_id", 0))
    is_extra = (actor_id in state.extra_owners)
    is_bot_owner = (actor_id in owners)
    is_immune = is_owner or is_extra or is_bot_owner

    is_user_wl = False
    if actor_id in state.whitelisted_users:
        user_perms = state.whitelisted_users[actor_id]
        dash_key = ACTION_COL_TO_DASHBOARD_KEY.get(action.lower(), action.lower())
        is_user_wl = bool(user_perms.get("all") or user_perms.get(action.lower()) or user_perms.get(dash_key))
    
    is_role_wl = False
    if hasattr(actor, "roles") and actor.roles:
        is_role_wl = any(r.id in state.whitelisted_roles for r in actor.roles)
    if not is_role_wl and r_index.has_whitelisted_role(guild.id, actor_id):
        is_role_wl = True

    is_whitelisted = is_user_wl or is_role_wl

    limit, window = state.get_threshold(action)
    current_count = limiter.get_count(guild.id, actor_id, action.lower(), float(window), now=ctx.event_time)

    punishment_enum = state.get_punishment(action)
    punishment_str = punishment_enum.value if hasattr(punishment_enum, "value") else str(punishment_enum)

    actor_display = getattr(actor, "display_name", getattr(actor, "name", str(actor_id)))

    return DecisionExplanation(
        guild_id=guild.id,
        actor_id=actor_id,
        actor_name=actor_display,
        action=action,
        decision=decision.action,
        reason_code=friendly_code,
        reason_description=reason_desc,
        is_immune=is_immune,
        is_whitelisted=is_whitelisted,
        current_count=current_count,
        max_limit=limit,
        window_seconds=window,
        punishment_type=punishment_str,
    )
