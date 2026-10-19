import os
import aiosqlite
import sqlite3
import datetime
from typing import Optional, Dict, Any

DB_PATH = os.path.join("db", "marry.db")

async def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH, timeout=10.0) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS marriages (
                guild_id TEXT NOT NULL,
                user1_id TEXT NOT NULL,
                user2_id TEXT NOT NULL,
                married_at TEXT NOT NULL,
                vows TEXT,
                PRIMARY KEY (guild_id, user1_id)
            )
        ''')
        try:
            await db.execute("ALTER TABLE marriages ADD COLUMN vows TEXT")
        except Exception:
            pass
        await db.commit()

async def get_marriage(guild_id: int | str, user_id: int | str) -> Optional[Dict[str, Any]]:
    """Returns marriage record for a user in a guild if married (non-blocking async)."""
    try:
        await _init_db()
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as db:
            async with db.execute(
                "SELECT user2_id, married_at, vows FROM marriages WHERE guild_id = ? AND user1_id = ?",
                (str(guild_id), str(user_id))
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "spouse_id": int(row[0]),
                        "married_at": row[1],
                        "vows": row[2] if len(row) > 2 and row[2] else None
                    }
        return None
    except Exception as e:
        print(f"[MARRY DB ERROR] get_marriage: {e}")
        return None

async def set_marriage(guild_id: int | str, user1_id: int | str, user2_id: int | str, vows: Optional[str] = None) -> None:
    """Records bidirectional marriage between user1 and user2 in a guild with vows (non-blocking async)."""
    try:
        await _init_db()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        gid = str(guild_id)
        u1 = str(user1_id)
        u2 = str(user2_id)
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as db:
            await db.execute(
                "INSERT OR REPLACE INTO marriages (guild_id, user1_id, user2_id, married_at, vows) VALUES (?, ?, ?, ?, ?)",
                (gid, u1, u2, now_iso, vows)
            )
            await db.execute(
                "INSERT OR REPLACE INTO marriages (guild_id, user1_id, user2_id, married_at, vows) VALUES (?, ?, ?, ?, ?)",
                (gid, u2, u1, now_iso, vows)
            )
            await db.commit()
    except Exception as e:
        print(f"[MARRY DB ERROR] set_marriage: {e}")

async def update_vows(guild_id: int | str, user1_id: int | str, user2_id: int | str, vows: str) -> bool:
    """Updates wedding vows bidirectionally for a married couple (non-blocking async)."""
    try:
        await _init_db()
        gid = str(guild_id)
        u1 = str(user1_id)
        u2 = str(user2_id)
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as db:
            await db.execute(
                "UPDATE marriages SET vows = ? WHERE guild_id = ? AND (user1_id = ? OR user1_id = ?)",
                (vows, gid, u1, u2)
            )
            await db.commit()
        return True
    except Exception as e:
        print(f"[MARRY DB ERROR] update_vows: {e}")
        return False

async def remove_marriage(guild_id: int | str, user_id: int | str) -> Optional[int]:
    """Removes bidirectional marriage for a user in a guild. Returns spouse_id if was married (non-blocking async)."""
    try:
        await _init_db()
        gid = str(guild_id)
        uid = str(user_id)
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as db:
            async with db.execute(
                "SELECT user2_id FROM marriages WHERE guild_id = ? AND user1_id = ?",
                (gid, uid)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                spouse_id = int(row[0])
            await db.execute("DELETE FROM marriages WHERE guild_id = ? AND (user1_id = ? OR user1_id = ?)", (gid, uid, str(spouse_id)))
            await db.commit()
            return spouse_id
    except Exception as e:
        print(f"[MARRY DB ERROR] remove_marriage: {e}")
        return None
