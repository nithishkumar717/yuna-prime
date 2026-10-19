"""
Database module for Guild Join & Leave Activity Logs.
Persists guild lifecycle events to db/guild_logs.db for Web Admin Dashboard visibility.
"""
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "guild_logs.db")

def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_guild_logs_db():
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                guild_name TEXT NOT NULL,
                guild_icon TEXT,
                member_count INTEGER DEFAULT 0,
                owner_id TEXT,
                owner_name TEXT,
                invite_url TEXT,
                bot_guilds_count INTEGER DEFAULT 0,
                bot_users_count INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_guild_events_time ON guild_events(timestamp DESC);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_guild_events_type ON guild_events(event_type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_guild_events_guild_id ON guild_events(guild_id);")
        conn.commit()

init_guild_logs_db()

def record_guild_event(
    event_type: str,
    guild: Any,
    invite_url: Optional[str] = None,
    bot: Optional[Any] = None
) -> Optional[int]:
    """Records a guild event (JOIN or LEAVE) safely."""
    try:
        guild_id = str(getattr(guild, "id", ""))
        raw_name = getattr(guild, "name", "") or ""
        guild_name = raw_name.strip() if raw_name.strip() else f"Server {guild_id}"
        
        guild_icon = None
        icon_attr = getattr(guild, "icon", None)
        if icon_attr:
            guild_icon = str(getattr(icon_attr, "url", icon_attr))

        member_count = getattr(guild, "member_count", None)
        if member_count is None and hasattr(guild, "members"):
            member_count = len(guild.members)
        member_count = int(member_count or 0)

        raw_owner_id = str(getattr(guild, "owner_id", "") or "")
        owner_id = "" if raw_owner_id == "None" else raw_owner_id
        owner_name = ""
        owner_obj = getattr(guild, "owner", None)
        if owner_obj and str(owner_obj) != "None":
            owner_name = str(owner_obj)

        bot_guilds_count = 0
        bot_users_count = 0
        if bot:
            if hasattr(bot, "guilds"):
                bot_guilds_count = len(bot.guilds)
            if hasattr(bot, "users"):
                bot_users_count = len(bot.users)

        timestamp_str = datetime.now(timezone.utc).isoformat()

        with _get_connection() as conn:
            cur = conn.execute("""
                INSERT INTO guild_events (
                    event_type, guild_id, guild_name, guild_icon,
                    member_count, owner_id, owner_name, invite_url,
                    bot_guilds_count, bot_users_count, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_type.upper(), guild_id, guild_name, guild_icon,
                member_count, owner_id, owner_name, invite_url,
                bot_guilds_count, bot_users_count, timestamp_str
            ))
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        print(f"[GuildLogsDB] Failed to record guild event: {e}", flush=True)
        return None

def get_guild_logs(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    event_type: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves filtered and paginated guild logs along with summary statistics."""
    with _get_connection() as conn:
        total_joins = conn.execute("SELECT COUNT(*) FROM guild_events WHERE event_type = 'JOIN'").fetchone()[0]
        total_leaves = conn.execute("SELECT COUNT(*) FROM guild_events WHERE event_type = 'LEAVE'").fetchone()[0]
        avg_member_res = conn.execute("SELECT AVG(member_count) FROM guild_events WHERE event_type = 'JOIN'").fetchone()[0]
        avg_members = round(avg_member_res) if avg_member_res else 0

        where_clauses = []
        params = []

        if event_type and event_type.upper() in ["JOIN", "LEAVE"]:
            where_clauses.append("event_type = ?")
            params.append(event_type.upper())

        if search and search.strip():
            term = f"%{search.strip()}%".lower()
            where_clauses.append("(LOWER(guild_name) LIKE ? OR guild_id LIKE ? OR LOWER(owner_name) LIKE ? OR owner_id LIKE ?)")
            params.extend([term, term, term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_sql = f"SELECT COUNT(*) FROM guild_events {where_sql}"
        total_filtered = conn.execute(count_sql, params).fetchone()[0]

        query_sql = f"""
            SELECT id, event_type, guild_id, guild_name, guild_icon,
                   member_count, owner_id, owner_name, invite_url,
                   bot_guilds_count, bot_users_count, timestamp
            FROM guild_events
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, params + [limit, offset]).fetchall()

        events = []
        for r in rows:
            events.append({
                "id": r["id"],
                "eventType": r["event_type"],
                "guildId": r["guild_id"],
                "guildName": r["guild_name"],
                "guildIcon": r["guild_icon"],
                "memberCount": r["member_count"],
                "ownerId": r["owner_id"],
                "ownerName": r["owner_name"],
                "inviteUrl": r["invite_url"],
                "botGuildsCount": r["bot_guilds_count"],
                "botUsersCount": r["bot_users_count"],
                "timestamp": r["timestamp"]
            })

        return {
            "total": total_filtered,
            "totalJoins": total_joins,
            "totalLeaves": total_leaves,
            "netGrowth": total_joins - total_leaves,
            "avgMembers": avg_members,
            "events": events,
            "limit": limit,
            "offset": offset
        }

def clear_guild_logs() -> bool:
    """Purges all records from guild_events table."""
    try:
        with _get_connection() as conn:
            conn.execute("DELETE FROM guild_events")
            conn.commit()
        return True
    except Exception as e:
        print(f"[GuildLogsDB] Clear logs failed: {e}", flush=True)
        return False

def sync_all_active_guilds(bot: Any) -> Dict[str, int]:
    """
    Syncs all currently connected bot guilds across all shards into the guild_events table.
    - If a guild does not exist in guild_events, inserts a new 'JOIN' event.
    - If a guild already exists in guild_events as a 'JOIN' event, updates its details
      (name, icon, member count, owner) if they were incomplete or changed.
    """
    if not bot or not hasattr(bot, "guilds") or not bot.guilds:
        return {"total": 0, "added": 0, "updated": 0}

    added = 0
    updated = 0
    total = len(bot.guilds)

    with _get_connection() as conn:
        for g in bot.guilds:
            guild_id = str(getattr(g, "id", ""))
            raw_name = getattr(g, "name", "") or ""
            guild_name = raw_name.strip() if raw_name.strip() else f"Server {guild_id}"
            guild_icon = str(g.icon.url) if getattr(g, "icon", None) else None
            member_count = getattr(g, "member_count", 0) or 0
            raw_owner_id = str(getattr(g, "owner_id", "") or "")
            owner_id = "" if raw_owner_id == "None" else raw_owner_id
            raw_owner = str(getattr(g, "owner", "") or "")
            owner_name = "" if raw_owner == "None" else raw_owner

            custom_time = None
            if hasattr(g, "joined_at") and g.joined_at:
                custom_time = g.joined_at.isoformat()
            timestamp_str = custom_time or datetime.now(timezone.utc).isoformat()

            # Check if this guild is already recorded
            existing = conn.execute(
                "SELECT id, guild_name, member_count FROM guild_events WHERE guild_id = ? AND event_type = 'JOIN' ORDER BY id DESC LIMIT 1",
                (guild_id,)
            ).fetchone()

            if existing:
                row_id, old_name, old_members = existing
                # Update if old record had incomplete name or member count was 0 or changed
                if not old_name or old_name.startswith("Server ") or old_members == 0 or old_members != member_count:
                    conn.execute("""
                        UPDATE guild_events
                        SET guild_name = ?, guild_icon = ?, member_count = ?,
                            owner_id = ?, owner_name = ?,
                            bot_guilds_count = ?, bot_users_count = ?
                        WHERE id = ?
                    """, (
                        guild_name, guild_icon, member_count,
                        owner_id, owner_name,
                        total, len(getattr(bot, "users", [])),
                        row_id
                    ))
                    updated += 1
            else:
                conn.execute("""
                    INSERT INTO guild_events (
                        event_type, guild_id, guild_name, guild_icon,
                        member_count, owner_id, owner_name, invite_url,
                        bot_guilds_count, bot_users_count, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "JOIN", guild_id, guild_name, guild_icon,
                    member_count, owner_id, owner_name, None,
                    total, len(getattr(bot, "users", [])), timestamp_str
                ))
                added += 1

        conn.commit()

    return {"total": total, "added": added, "updated": updated}

def seed_active_guilds_if_empty(bot: Any) -> int:
    """Convenience wrapper that calls sync_all_active_guilds."""
    res = sync_all_active_guilds(bot)
    return res.get("added", 0)

def update_guild_invite_url(guild_id: str, invite_url: str) -> bool:
    """Updates the invite URL for a recorded guild event."""
    try:
        with _get_connection() as conn:
            conn.execute(
                "UPDATE guild_events SET invite_url = ? WHERE guild_id = ?",
                (invite_url, str(guild_id))
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"[GuildLogsDB] Failed to update invite url: {e}", flush=True)
        return False


