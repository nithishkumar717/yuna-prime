"""
Database & In-Memory Cache module for Pre-Release Notice DM Tracking.
Tracks users who have received the daily YUNΛ Pre-Release Notice DM (1 DM per day) in db/prerelease_users.db.
"""
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "prerelease_users.db")
_PRERELEASE_SENT_DATES: Dict[int, str] = {}
_INITIALIZED: bool = False

def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_prerelease_db():
    global _INITIALIZED, _PRERELEASE_SENT_DATES
    if _INITIALIZED:
        return
    try:
        with _get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prerelease_notices (
                    user_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL
                );
            """)
            conn.commit()
            cursor = conn.execute("SELECT user_id, timestamp FROM prerelease_notices")
            for row in cursor.fetchall():
                if row[0] and str(row[0]).isdigit():
                    uid = int(row[0])
                    raw_ts = str(row[1]) if row[1] else ""
                    date_part = raw_ts[:10] if len(raw_ts) >= 10 else ""
                    if date_part:
                        _PRERELEASE_SENT_DATES[uid] = date_part
        _INITIALIZED = True
    except Exception as e:
        print(f"[PreReleaseDB] Initialization error: {e}", flush=True)

init_prerelease_db()

def _get_today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def has_received_prerelease_notice(user_id: int | str) -> bool:
    """
    Fast <1ms check if a user has ALREADY received today's Pre-Release Notice DM.
    Returns True if notice was already sent today (DO NOT SEND ANOTHER).
    Returns False if notice has NOT been sent today (OK TO SEND).
    """
    if not _INITIALIZED:
        init_prerelease_db()
    try:
        uid_int = int(user_id)
        today_date = _get_today_utc_date()
        last_sent_date = _PRERELEASE_SENT_DATES.get(uid_int)
        return last_sent_date == today_date
    except (ValueError, TypeError):
        return True  # Invalid ID safety fallback

def mark_prerelease_notice_sent(user_id: int | str) -> bool:
    """Records today's date for user DM delivery in memory and SQLite."""
    if not _INITIALIZED:
        init_prerelease_db()
    try:
        uid_int = int(user_id)
        uid_str = str(uid_int)
        today_date = _get_today_utc_date()
        
        # Update in-memory dict immediately
        _PRERELEASE_SENT_DATES[uid_int] = today_date
        
        # Persist to database (INSERT OR REPLACE)
        timestamp_str = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO prerelease_notices (user_id, timestamp) VALUES (?, ?)",
                (uid_str, timestamp_str)
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"[PreReleaseDB] Failed to record user {user_id}: {e}", flush=True)
        return False

