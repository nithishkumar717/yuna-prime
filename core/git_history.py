"""Persistent Git deployment audit history for Yuna Supreme."""
from __future__ import annotations

import logging
import sqlite3
import os
import time
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger("core.git_history")
DB_PATH = os.path.join("db", "git_deploy.db")


def _init_db() -> None:
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deploy_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    success INTEGER NOT NULL,
                    output TEXT,
                    triggered_by TEXT,
                    restarted INTEGER NOT NULL,
                    git_status TEXT
                )
                """
            )
            conn.commit()
    except Exception as exc:
        logger.error("[GitHistory] Could not initialize deploy_history table: %s", exc)


_init_db()


def record_git_deploy(
    success: bool,
    output: str,
    triggered_by: str = "Unknown",
    restarted: bool = False,
    git_status: Optional[Dict[str, Any]] = None,
) -> bool:
    """Records a deployment attempt into the persistent SQLite deployment log."""
    try:
        status_json = json.dumps(git_status) if git_status else "{}"
        now = time.time()
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO deploy_history (timestamp, success, output, triggered_by, restarted, git_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, 1 if success else 0, str(output)[:4096], str(triggered_by), 1 if restarted else 0, status_json),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("[GitHistory] Failed to record deploy history: %s", exc)
        return False


def get_recent_deploys(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves recent deployment attempts."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM deploy_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("[GitHistory] Failed to query deploy history: %s", exc)
        return []
