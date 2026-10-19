"""
Axiom Cloud Audit Logging Service for Yuna
Streams audit log events to Axiom cloud for unlimited free storage (up to 500GB/mo)
with zero VPS disk space usage, and enables instant dashboard querying.
"""

from __future__ import annotations
import os
import time
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import aiohttp

AXIOM_API_URL = "https://api.axiom.co/v1"
MAX_AUDIT_LOG_QUERY_RESULTS = 2500


def get_axiom_config() -> tuple[Optional[str], Optional[str], Optional[str]]:
    token = os.getenv("AXIOM_TOKEN")
    dataset = os.getenv("AXIOM_DATASET", "yuna-audit-logs")
    org_id = os.getenv("AXIOM_ORG_ID")
    return token, dataset, org_id


def is_axiom_configured() -> bool:
    token, dataset, _ = get_axiom_config()
    return bool(token and dataset)


async def send_to_axiom(records: List[Dict[str, Any]]) -> bool:
    """
    Ingests a list of audit log records directly into the Axiom dataset asynchronously.
    """
    token, dataset, org_id = get_axiom_config()
    if not token or not dataset or not records:
        return False

    payload = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for rec in records:
        item = dict(rec)
        # Ensure standard ISO timestamp for Axiom time-series indexing
        if "_time" not in item:
            created_at = item.get("createdAt")
            if created_at and isinstance(created_at, (int, float)) and created_at > 0:
                item["_time"] = datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat()
            else:
                item["_time"] = now_iso

        if "guild_id" in item:
            item["guild_id"] = str(item["guild_id"])
        elif "guildId" in item:
            item["guild_id"] = str(item["guildId"])

        payload.append(item)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    if org_id:
        headers["x-axiom-org-id"] = org_id

    url = f"{AXIOM_API_URL}/datasets/{dataset}/ingest"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20.0, connect=10.0)) as resp:
                if resp.status in (200, 201):
                    return True
                else:
                    err_text = await resp.text()
                    print(f"[AXIOM INGEST WARN] HTTP {resp.status}: {err_text}")
                    return False
    except asyncio.TimeoutError:
        return False
    except Exception as e:
        print(f"[AXIOM INGEST ERROR] {e}")
        return False


def _normalize_audit_module(record: Dict[str, Any]) -> str:
    """Map logger routing keys and legacy module names to the dashboard categories."""
    raw_module = str(record.get("module") or "").strip().upper().replace("-", "_").replace(" ", "_")
    channel_key = str(record.get("channel_key") or record.get("channelKey") or "").strip().lower()
    event_key = str(record.get("event_key") or record.get("eventKey") or "").strip().lower()
    action_code = str(record.get("actionCode") or "")
    event_text = " ".join(
        str(record.get(key) or "") for key in ("action", "title", "headline", "details")
    ).lower()

    if raw_module in {"ANTI_NUKE", "SECURITY"} or channel_key in {"security", "antinuke"}:
        return "ANTINUKE"
    if raw_module in {"AUTO_MOD", "AUTOMODERATION"} or channel_key == "automod":
        return "AUTOMOD"
    if raw_module in {"MOD", "BAN", "KICK", "WARN", "TIMEOUT", "MUTE", "UNBAN"} or channel_key in {"mod", "ban"}:
        return "MODERATION"

    if action_code in {"140", "141", "142", "143", "144", "145", "146"}:
        return "AUTOMOD"
    if action_code in {"20", "21", "22", "23", "24", "25"}:
        return "MODERATION"
    if action_code in {"10", "11", "12", "13", "14", "15", "28", "30", "31", "32", "50", "51", "52"}:
        return "ANTINUKE"
    if event_key in {"automod_block", "automod_flag", "automod_timeout", "automod_rule_create", "automod_rule_update", "automod_rule_delete"}:
        return "AUTOMOD"
    if event_key in {"ban", "unban", "kick", "timeout", "warn", "softban", "unmute", "untimeout", "role_given", "role_removed"}:
        return "MODERATION"
    if event_key in {"channel_create", "channel_update", "channel_delete", "permission_overwrite_create", "permission_overwrite_update", "permission_overwrite_delete", "role_create", "role_update", "role_delete", "webhook_create", "webhook_update", "webhook_delete", "bot_add"}:
        return "ANTINUKE"
    if any(term in event_text for term in ("automod", "auto-mod", "message blocked", "message flagged")):
        return "AUTOMOD"
    if channel_key == "message":
        return "MANAGEMENT"
    if event_key in {"message_delete", "message_edit", "bulk_delete", "pins_update", "invite_posted", "event_create", "event_update", "event_delete", "cmd_perms"}:
        return "MANAGEMENT"
    if any(term in event_text for term in ("member banned", "member kicked", "member warned", "member timed out", "user banned", "user unbanned", "roles added", "roles removed")):
        return "MODERATION"
    if channel_key == "role":
        return "ANTINUKE" if event_key.startswith("role_") else "MANAGEMENT"
    if channel_key == "channel":
        return "ANTINUKE"
    if channel_key in {"voice", "member", "server", "invite", "boost", "emoji", "thread", "integration", "stage", "sticker", "scheduled_event", "joins", "leaves"}:
        return "MANAGEMENT"

    # Keep valid canonical categories when older records lack action/event metadata.
    if raw_module in {"ANTINUKE", "AUTOMOD", "MODERATION", "MANAGEMENT"}:
        return raw_module

    # Unknown categories stay uncategorized; they remain visible under ALL only.
    return ""


async def query_axiom(guild_id: int | str, limit: int = MAX_AUDIT_LOG_QUERY_RESULTS) -> List[Dict[str, Any]]:
    """
    Queries Axiom for audit logs belonging to a specific guild_id.
    Returns normalized records compatible with the Yuna Dashboard.
    """
    token, dataset, org_id = get_axiom_config()
    if not token or not dataset:
        return []

    limit = min(max(int(limit), 1), MAX_AUDIT_LOG_QUERY_RESULTS)
    fetch_limit = min(limit * 2, 5000)
    # The dashboard's background sync can submit the same Discord audit entry
    # more than once. Query newest events first and deduplicate by stable record id.
    apl_query = (
        f"['{dataset}'] | where guild_id == '{guild_id}' "
        f"| sort by _time desc | take {fetch_limit}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    if org_id:
        headers["x-axiom-org-id"] = org_id

    url = f"{AXIOM_API_URL}/datasets/_apl?format=legacy"
    payload = {"apl": apl_query}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8.0)) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    print(f"[AXIOM QUERY WARN] HTTP {resp.status}: {err_text}")
                    return []

                result = await resp.json()
                matches = result.get("matches", [])
                logs: List[Dict[str, Any]] = []
                seen_ids = set()

                for m in matches:
                    data = m.get("data", {})
                    if not data:
                        continue

                    rec_id = str(data.get("id") or data.get("entryId") or f"axiom-{m.get('_rowId', 'unknown')}")
                    if rec_id in seen_ids:
                        continue
                    seen_ids.add(rec_id)

                    # Standardize back to Yuna web dashboard schema
                    logs.append({
                        "id": rec_id,
                        "entryId": data.get("entryId") or rec_id,
                        "actionCode": data.get("actionCode", 0),
                        "module": _normalize_audit_module(data),
                        "channelKey": data.get("channel_key") or data.get("channelKey", ""),
                        "eventKey": data.get("event_key") or data.get("eventKey", ""),
                        "action": data.get("action", "Audit Event"),
                        "headline": data.get("headline", data.get("action", "Audit Event")),
                        "actor": data.get("actor", "System"),
                        "actorId": data.get("actorId", "0"),
                        "actorAvatar": data.get("actorAvatar", ""),
                        "target": data.get("target", "Server"),
                        "targetId": data.get("targetId", ""),
                        "status": data.get("status", "SUCCESS"),
                        "reason": data.get("reason"),
                        "details": data.get("details", ""),
                        "items": data.get("items") if isinstance(data.get("items"), list) else [],
                        "changes": data.get("changes") if isinstance(data.get("changes"), list) else [],
                        "timestamp": data.get("timestamp", m.get("_time", "Recently")),
                        "timestampIso": data.get("_time") or m.get("_time") or data.get("timestamp"),
                        "createdAt": data.get("createdAt", 0)
                    })

                    if len(logs) >= limit:
                        break

                return logs
    except Exception as e:
        print(f"[AXIOM QUERY ERROR] {e}")
        return []


async def query_axiom_page(
    guild_id: int | str,
    limit: int = 100,
    cursor: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch one newest-first Axiom page and its documented continuation cursor."""
    token, dataset, org_id = get_axiom_config()
    if not token or not dataset:
        return {"ok": False, "logs": [], "nextCursor": None, "hasMore": False, "error": "Axiom is not configured."}

    limit = min(max(int(limit), 1), 500)
    apl_query = (
        f"['{dataset}'] | where guild_id == '{guild_id}' "
        f"| sort by _time desc | limit {limit}"
    )
    payload: Dict[str, Any] = {"apl": apl_query, "includeCursor": False}
    if cursor:
        payload["cursor"] = cursor
    if start_time:
        payload["startTime"] = start_time
    if end_time:
        payload["endTime"] = end_time

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if org_id:
        headers["x-axiom-org-id"] = org_id

    url = f"{AXIOM_API_URL}/datasets/_apl?format=legacy"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=12.0)) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    print(f"[AXIOM PAGE QUERY WARN] HTTP {resp.status}: {err_text}")
                    return {"ok": False, "logs": [], "nextCursor": None, "hasMore": False, "error": f"Axiom returned HTTP {resp.status}."}

                result = await resp.json()
                matches = result.get("matches", [])
                logs: List[Dict[str, Any]] = []
                seen_ids = set()
                for match in matches:
                    data = match.get("data", {})
                    if not isinstance(data, dict) or not data:
                        continue
                    rec_id = str(data.get("id") or data.get("entryId") or f"axiom-{match.get('_rowId', 'unknown')}")
                    if rec_id in seen_ids:
                        continue
                    seen_ids.add(rec_id)
                    event_items = data.get("items") if isinstance(data.get("items"), list) else []
                    event_changes = data.get("changes") if isinstance(data.get("changes"), list) else []
                    invited_by = data.get("invitedBy")
                    invite_code = data.get("inviteCode")
                    if isinstance(event_items, list):
                        for item in event_items:
                            text = str(item)
                            if not invited_by and text.lower().startswith(("invited by:", "added by:")):
                                invited_by = text.split(":", 1)[1].strip()
                            if not invite_code and text.lower().startswith("invite code:"):
                                invite_code = text.split(":", 1)[1].strip()
                    logs.append({
                        "id": rec_id,
                        "entryId": data.get("entryId") or rec_id,
                        "actionCode": data.get("actionCode", 0),
                        "module": _normalize_audit_module(data),
                        "channelKey": data.get("channel_key") or data.get("channelKey", ""),
                        "eventKey": data.get("event_key") or data.get("eventKey", ""),
                        "action": data.get("action", "Audit Event"),
                        "headline": data.get("headline", data.get("action", "Audit Event")),
                        "actor": data.get("actor", "System"),
                        "actorId": data.get("actorId", "0"),
                        "actorAvatar": data.get("actorAvatar", ""),
                        "target": data.get("target", "Server"),
                        "targetId": data.get("targetId", ""),
                        "status": data.get("status", "SUCCESS"),
                        "reason": data.get("reason"),
                        "details": data.get("details", ""),
                        "items": event_items,
                        "changes": event_changes,
                        "timestamp": data.get("timestamp", match.get("_time", "Recently")),
                        "timestampIso": data.get("_time") or match.get("_time") or data.get("timestamp"),
                        "createdAt": data.get("createdAt", 0),
                        "invitedBy": invited_by,
                        "inviteCode": invite_code,
                    })

                status = result.get("status") or {}
                next_cursor = status.get("minCursor")
                has_more = len(matches) >= limit and bool(next_cursor) and next_cursor != cursor
                return {
                    "ok": True,
                    "logs": logs,
                    "nextCursor": next_cursor if has_more else None,
                    "hasMore": has_more,
                    "error": None,
                }
    except Exception as exc:
        print(f"[AXIOM PAGE QUERY ERROR] {exc}")
        return {"ok": False, "logs": [], "nextCursor": None, "hasMore": False, "error": "Axiom query failed. Check the bot's Axiom connection."}


async def probe_axiom_latency() -> Any:
    """
    Probes Axiom API latency (ping). Returns latency in ms (float) or 'N/A'.
    """
    token, dataset, org_id = get_axiom_config()
    if not token or not dataset:
        return "N/A"

    headers = {
        "Authorization": f"Bearer {token}"
    }
    if org_id:
        headers["x-axiom-org-id"] = org_id

    url = f"{AXIOM_API_URL}/datasets/{dataset}"
    t0 = time.perf_counter()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                if resp.status == 200:
                    return max(0.01, round((time.perf_counter() - t0) * 1000, 2))
                return "N/A"
    except Exception:
        return "N/A"

