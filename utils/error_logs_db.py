"""
YUNA Bot Error Logs Database Layer
Stores, indexes, and queries runtime exceptions, command errors, and event failures.
"""
import sqlite3
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db"))
DB_PATH = os.path.join(DB_DIR, "error_logs.db")

def _get_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def init_error_logs_db():
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                error_name TEXT NOT NULL,
                error_message TEXT NOT NULL,
                traceback TEXT,
                source TEXT,
                guild_id TEXT,
                guild_name TEXT,
                user_id TEXT,
                user_name TEXT,
                channel_id TEXT,
                timestamp TEXT NOT NULL,
                resolved INTEGER DEFAULT 0
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_errors_time ON bot_error_logs(timestamp DESC);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_errors_resolved ON bot_error_logs(resolved);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_errors_type ON bot_error_logs(error_type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_errors_guild ON bot_error_logs(guild_id);")
        conn.commit()

init_error_logs_db()

def record_bot_error(
    error: Any = None,
    error_type: str = "UnhandledException",
    source: str = "",
    guild: Any = None,
    user: Any = None,
    channel: Any = None,
    details: Optional[str] = None,
    *,
    error_name: Optional[str] = None,
    error_message: Optional[str] = None,
    traceback_str: Optional[str] = None,
    guild_id: Optional[str] = None,
    guild_name: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    channel_id: Optional[str] = None
) -> Optional[int]:
    """
    Safely captures and records a runtime exception into the SQLite database.
    Accepts an Exception object, or explicit error details via keyword arguments.
    """
    try:
        # Extract exception name and message
        orig = getattr(error, "original", error)
        if isinstance(orig, Exception):
            err_name = error_name or type(orig).__name__
            err_msg = error_message or (str(orig) or type(orig).__name__)
            tb_lines = traceback.format_exception(type(orig), orig, orig.__traceback__)
            tb_val = traceback_str or details or "".join(tb_lines).strip()
        else:
            err_name = error_name or (type(error).__name__ if error is not None else "UnknownError")
            err_msg = error_message or (str(error) if error is not None else "Unknown exception")
            tb_val = traceback_str or details or (traceback.format_exc() if error is not None else "")

        # Context attribution
        gid = guild_id or ""
        gname = guild_name or ""
        if guild:
            gid = str(getattr(guild, "id", "") or gid)
            gname = str(getattr(guild, "name", "") or gname)

        uid = user_id or ""
        uname = user_name or ""
        if user:
            uid = str(getattr(user, "id", "") or uid)
            uname = str(getattr(user, "name", "") or str(user) or uname)

        cid = channel_id or ""
        if channel:
            cid = str(getattr(channel, "id", "") or cid)

        timestamp_str = datetime.now(timezone.utc).isoformat()

        with _get_connection() as conn:
            cur = conn.execute("""
                INSERT INTO bot_error_logs (
                    error_type, error_name, error_message, traceback,
                    source, guild_id, guild_name, user_id, user_name,
                    channel_id, timestamp, resolved
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                error_type, err_name, err_msg, tb_val,
                source, gid, gname, uid, uname,
                cid, timestamp_str
            ))
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        print(f"[ErrorLogsDB] Failed to record error log: {e}", flush=True)
        return None

def get_error_logs(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    error_type: Optional[str] = None,
    resolved: Optional[str] = "ALL"  # 'ALL' | 'UNRESOLVED' | 'RESOLVED'
) -> Dict[str, Any]:
    """Retrieves paginated and filtered bot error logs with summary metrics."""
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM bot_error_logs").fetchone()[0]
        unresolved_count = conn.execute("SELECT COUNT(*) FROM bot_error_logs WHERE resolved = 0").fetchone()[0]
        resolved_count = conn.execute("SELECT COUNT(*) FROM bot_error_logs WHERE resolved = 1").fetchone()[0]

        # Calculate errors today (UTC)
        today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_count = conn.execute("SELECT COUNT(*) FROM bot_error_logs WHERE timestamp LIKE ?", (f"{today_prefix}%",)).fetchone()[0]

        where_clauses = []
        params = []

        if resolved == "UNRESOLVED":
            where_clauses.append("resolved = 0")
        elif resolved == "RESOLVED":
            where_clauses.append("resolved = 1")

        if error_type and error_type.upper() != "ALL":
            where_clauses.append("error_type = ?")
            params.append(error_type)

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            where_clauses.append("""(
                LOWER(error_name) LIKE ? OR
                LOWER(error_message) LIKE ? OR
                LOWER(source) LIKE ? OR
                LOWER(guild_name) LIKE ? OR
                guild_id LIKE ? OR
                LOWER(user_name) LIKE ? OR
                LOWER(traceback) LIKE ?
            )""")
            params.extend([term, term, term, term, term, term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_sql = f"SELECT COUNT(*) FROM bot_error_logs {where_sql}"
        filtered_total = conn.execute(count_sql, params).fetchone()[0]

        query_sql = f"""
            SELECT id, error_type, error_name, error_message, traceback,
                   source, guild_id, guild_name, user_id, user_name,
                   channel_id, timestamp, resolved
            FROM bot_error_logs
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, params + [limit, offset]).fetchall()

        logs = []
        for r in rows:
            logs.append({
                "id": r["id"],
                "errorType": r["error_type"],
                "errorName": r["error_name"],
                "errorMessage": r["error_message"],
                "traceback": r["traceback"],
                "source": r["source"],
                "guildId": r["guild_id"],
                "guildName": r["guild_name"],
                "userId": r["user_id"],
                "userName": r["user_name"],
                "channelId": r["channel_id"],
                "timestamp": r["timestamp"],
                "resolved": bool(r["resolved"])
            })

        return {
            "total": total,
            "filteredTotal": filtered_total,
            "unresolved": unresolved_count,
            "resolved": resolved_count,
            "today": today_count,
            "logs": logs,
            "limit": limit,
            "offset": offset
        }

def mark_error_resolved(error_id: int, resolved: bool = True) -> bool:
    """Marks an error as resolved or re-opened."""
    try:
        with _get_connection() as conn:
            cur = conn.execute("UPDATE bot_error_logs SET resolved = ? WHERE id = ?", (1 if resolved else 0, error_id))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ErrorLogsDB] Failed to toggle error status: {e}", flush=True)
        return False

def clear_error_logs(resolved_only: bool = False) -> bool:
    """Purges all or only resolved error logs."""
    try:
        with _get_connection() as conn:
            if resolved_only:
                conn.execute("DELETE FROM bot_error_logs WHERE resolved = 1")
            else:
                conn.execute("DELETE FROM bot_error_logs")
            conn.commit()
        return True
    except Exception as e:
        print(f"[ErrorLogsDB] Clear error logs failed: {e}", flush=True)
        return False

def run_maintenance_check() -> Dict[str, Any]:
    """Performs database PRAGMA quick_check, calculates stats, and verifies error logs table integrity."""
    try:
        db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        db_size_mb = round(db_size_bytes / (1024 * 1024), 2)
        with _get_connection() as conn:
            integrity_row = conn.execute("PRAGMA quick_check;").fetchone()
            db_integrity = integrity_row[0] if integrity_row else "ok"
            total = conn.execute("SELECT COUNT(*) FROM bot_error_logs").fetchone()[0]
            unresolved = conn.execute("SELECT COUNT(*) FROM bot_error_logs WHERE resolved = 0").fetchone()[0]
            resolved = conn.execute("SELECT COUNT(*) FROM bot_error_logs WHERE resolved = 1").fetchone()[0]
            today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today = conn.execute("SELECT COUNT(*) FROM bot_error_logs WHERE timestamp LIKE ?", (f"{today_prefix}%",)).fetchone()[0]

        status = "HEALTHY" if str(db_integrity).lower() == "ok" and unresolved == 0 else ("ATTENTION" if unresolved > 0 else "HEALTHY")

        return {
            "success": True,
            "status": status,
            "dbIntegrity": str(db_integrity),
            "dbSizeMb": db_size_mb,
            "total": total,
            "unresolved": unresolved,
            "resolved": resolved,
            "today": today,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Maintenance check completed successfully. DB Integrity: '{db_integrity}', DB Size: {db_size_mb} MB, Unresolved Issues: {unresolved}."
        }
    except Exception as e:
        return {
            "success": False,
            "status": "ERROR",
            "error": str(e)
        }

