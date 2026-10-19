"""
Yuna V7 — Permission Notification Database Layer
Persistently tracks and audits all missing permission DM notifications sent to server authorities.
Strictly guarantees that DM notifications are sent only once per server & action to prevent spamming,
persisting the send count and audit logs across bot reboots.
"""

import os
import time
import sqlite3
import datetime
from typing import Optional, Dict, Any, List, Union

try:
    import pytz
    IST_TZ = pytz.timezone("Asia/Kolkata")
except Exception:
    IST_TZ = None

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db"))
DB_PATH = os.path.join(DB_DIR, "permission_notifications.db")


def _get_connection() -> sqlite3.Connection:
    """Creates a thread-safe connection to the permission notifications database."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def _format_ist_time(epoch_time: float) -> str:
    """Formats epoch timestamp into human-readable IST string."""
    try:
        if IST_TZ:
            dt = datetime.datetime.fromtimestamp(epoch_time, tz=datetime.timezone.utc).astimezone(IST_TZ)
            return dt.strftime("%d-%m-%Y %I:%M:%S %p IST")
        else:
            dt = datetime.datetime.fromtimestamp(epoch_time, tz=datetime.timezone.utc)
            return dt.strftime("%d-%m-%Y %H:%M:%S UTC")
    except Exception:
        return str(epoch_time)


def init_permission_db():
    """Initializes tables and indexes for permission notification tracking and auditing."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS permission_notification_tracking (
                guild_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                permission TEXT NOT NULL,
                target_user_id INTEGER DEFAULT 0,
                send_count INTEGER NOT NULL DEFAULT 0,
                first_sent_at REAL NOT NULL,
                last_sent_at REAL NOT NULL,
                last_channel_ids TEXT,
                last_channel_names TEXT,
                status TEXT DEFAULT 'SENT',
                PRIMARY KEY (guild_id, action)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS permission_dm_send_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                guild_name TEXT,
                action TEXT NOT NULL,
                permission TEXT NOT NULL,
                recipient_id INTEGER NOT NULL,
                recipient_type TEXT NOT NULL,
                channel_count INTEGER NOT NULL DEFAULT 0,
                channel_ids TEXT,
                channel_names TEXT,
                sent_at REAL NOT NULL,
                sent_at_ist TEXT NOT NULL,
                details TEXT
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_tracking_guild ON permission_notification_tracking(guild_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_tracking_status ON permission_notification_tracking(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_logs_guild ON permission_dm_send_logs(guild_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_logs_time ON permission_dm_send_logs(sent_at DESC);")
        conn.commit()


# Ensure database and tables exist upon module import
init_permission_db()


def normalize_action_key(action: str) -> str:
    """Normalizes action string for consistent database lookup."""
    return str(action or "").lower().strip()


def get_permission_send_count(guild_id: int, action: str) -> int:
    """
    Returns how many times a missing permission DM has been sent for this guild and action.
    Returns 0 if no notification has been sent yet.
    """
    if not guild_id or not action:
        return 0

    action_key = normalize_action_key(action)
    try:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT send_count FROM permission_notification_tracking WHERE guild_id = ? AND action = ?",
                (int(guild_id), action_key)
            ).fetchone()
            if row:
                return int(row["send_count"])
    except Exception as e:
        print(f"[PERMISSION DB ERROR] Error fetching send count for guild {guild_id}: {e}", flush=True)
    return 0


def can_send_permission_dm(guild_id: int, action: str, max_sends: int = 1) -> bool:
    """
    Strictly checks whether a missing permission DM is permitted to be sent.
    Returns True if send_count < max_sends (default 1), False otherwise.
    """
    current_count = get_permission_send_count(guild_id, action)
    return current_count < max_sends


def record_permission_dm_sent(
    guild_id: int,
    guild_name: str,
    action: str,
    permission: str,
    recipient_id: int,
    recipient_type: str = "owner",
    channels: Optional[List[Any]] = None,
    details: str = ""
) -> int:
    """
    Atomically updates the send_count in the database and creates an audit log entry.
    Returns the new send_count.
    """
    if not guild_id or not action:
        return 0

    action_key = normalize_action_key(action)
    now = time.time()
    now_ist = _format_ist_time(now)

    ch_list = channels or []
    ch_ids = [str(getattr(c, "id", c)) for c in ch_list if getattr(c, "id", c)]
    ch_names = [str(getattr(c, "name", c)) for c in ch_list if getattr(c, "name", c)]

    ch_ids_str = ",".join(ch_ids)
    ch_names_str = ", ".join(ch_names)
    ch_count = len(ch_list)

    new_count = 1
    try:
        with _get_connection() as conn:
            # Upsert into tracking table
            conn.execute("""
                INSERT INTO permission_notification_tracking (
                    guild_id, action, permission, target_user_id, send_count,
                    first_sent_at, last_sent_at, last_channel_ids, last_channel_names, status
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, 'SENT')
                ON CONFLICT(guild_id, action) DO UPDATE SET
                    send_count = permission_notification_tracking.send_count + 1,
                    last_sent_at = excluded.last_sent_at,
                    last_channel_ids = excluded.last_channel_ids,
                    last_channel_names = excluded.last_channel_names,
                    permission = excluded.permission,
                    target_user_id = excluded.target_user_id,
                    status = 'SENT';
            """, (
                int(guild_id), action_key, str(permission), int(recipient_id or 0),
                now, now, ch_ids_str, ch_names_str
            ))

            # Fetch updated send_count
            row = conn.execute(
                "SELECT send_count FROM permission_notification_tracking WHERE guild_id = ? AND action = ?",
                (int(guild_id), action_key)
            ).fetchone()
            if row:
                new_count = int(row["send_count"])

            # Insert audit log row
            conn.execute("""
                INSERT INTO permission_dm_send_logs (
                    guild_id, guild_name, action, permission, recipient_id, recipient_type,
                    channel_count, channel_ids, channel_names, sent_at, sent_at_ist, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                int(guild_id), str(guild_name or ""), action_key, str(permission),
                int(recipient_id or 0), str(recipient_type or "owner"),
                ch_count, ch_ids_str, ch_names_str, now, now_ist, str(details or "")
            ))
            conn.commit()
    except Exception as e:
        print(f"[PERMISSION DB ERROR] Error recording DM sent for guild {guild_id}: {e}", flush=True)

    return new_count


def get_permission_dm_info(guild_id: int, action: str) -> Optional[Dict[str, Any]]:
    """Retrieves full tracking information for a specific guild and action."""
    action_key = normalize_action_key(action)
    try:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM permission_notification_tracking WHERE guild_id = ? AND action = ?",
                (int(guild_id), action_key)
            ).fetchone()
            if row:
                return dict(row)
    except Exception as e:
        print(f"[PERMISSION DB ERROR] Error fetching tracking info for guild {guild_id}: {e}", flush=True)
    return None


def reset_permission_dm_tracking(guild_id: int, action: Optional[str] = None):
    """
    Resets the send_count and marks status as 'RESOLVED' once permissions have been restored,
    allowing a single future notification if permissions are ever revoked again.
    """
    try:
        with _get_connection() as conn:
            if action:
                action_key = normalize_action_key(action)
                conn.execute(
                    "UPDATE permission_notification_tracking SET send_count = 0, status = 'RESOLVED' WHERE guild_id = ? AND action = ?",
                    (int(guild_id), action_key)
                )
            else:
                conn.execute(
                    "UPDATE permission_notification_tracking SET send_count = 0, status = 'RESOLVED' WHERE guild_id = ?",
                    (int(guild_id),)
                )
            conn.commit()
    except Exception as e:
        print(f"[PERMISSION DB ERROR] Error resetting permission tracking for guild {guild_id}: {e}", flush=True)


def get_all_permission_dm_logs(guild_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches chronological audit logs of all missing permission DMs dispatched."""
    try:
        with _get_connection() as conn:
            if guild_id:
                rows = conn.execute(
                    "SELECT * FROM permission_dm_send_logs WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
                    (int(guild_id), limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM permission_dm_send_logs ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[PERMISSION DB ERROR] Error fetching permission logs: {e}", flush=True)
    return []
