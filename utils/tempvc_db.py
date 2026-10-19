import os
import sqlite3
import aiosqlite
import asyncio
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join("db", "tempvc.db")

async def _init_db_async():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH, timeout=10.0) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tempvc_creators (
                guild_id TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                name TEXT NOT NULL,
                name_template TEXT,
                category_id TEXT,
                privacy_mode TEXT DEFAULT 'Public',
                user_limit INTEGER DEFAULT 0,
                bitrate TEXT DEFAULT '64kbps',
                sync_permissions TEXT DEFAULT 'Sync with Category',
                PRIMARY KEY (guild_id, creator_id)
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tempvc_config (
                guild_id TEXT PRIMARY KEY,
                interface_channel_id TEXT,
                category_id TEXT,
                name_template TEXT,
                privacy_mode TEXT,
                user_limit INTEGER,
                bitrate TEXT,
                censor_channel_names INTEGER DEFAULT 0,
                allowed_features TEXT
            )
        ''')
        await conn.commit()

def _get_connection_sync():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tempvc_creators (
            guild_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            name TEXT NOT NULL,
            name_template TEXT,
            category_id TEXT,
            privacy_mode TEXT DEFAULT 'Public',
            user_limit INTEGER DEFAULT 0,
            bitrate TEXT DEFAULT '64kbps',
            sync_permissions TEXT DEFAULT 'Sync with Category',
            PRIMARY KEY (guild_id, creator_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tempvc_config (
            guild_id TEXT PRIMARY KEY,
            interface_channel_id TEXT,
            category_id TEXT,
            name_template TEXT,
            privacy_mode TEXT,
            user_limit INTEGER,
            bitrate TEXT,
            censor_channel_names INTEGER DEFAULT 0,
            allowed_features TEXT
        )
    ''')
    return conn

async def save_creator_to_db_async(guild_id: str | int, creator: Dict[str, Any]) -> None:
    """Inserts or updates a creator channel record in SQLite (non-blocking async)."""
    try:
        await _init_db_async()
        cid = str(creator.get("id") or creator.get("creator_channel_id"))
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as conn:
            await conn.execute('''
                INSERT INTO tempvc_creators (guild_id, creator_id, name, name_template, category_id, privacy_mode, user_limit, bitrate, sync_permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, creator_id) DO UPDATE SET
                    name=excluded.name,
                    name_template=excluded.name_template,
                    category_id=excluded.category_id,
                    privacy_mode=excluded.privacy_mode,
                    user_limit=excluded.user_limit,
                    bitrate=excluded.bitrate,
                    sync_permissions=excluded.sync_permissions
            ''', (
                str(guild_id),
                cid,
                creator.get("name", "➕ Join to Create"),
                creator.get("nameTemplate", "{user}'s Lounge"),
                str(creator.get("categoryId", "")),
                creator.get("privacyMode", "Public"),
                int(creator.get("userLimit", 0)),
                creator.get("bitrate", "64kbps"),
                creator.get("syncPermissions", "Sync with Category")
            ))
            await conn.commit()
    except Exception as e:
        print(f"[TEMPVC DB ERROR] save_creator_to_db_async: {e}")

def save_creator_to_db(guild_id: str | int, creator: Dict[str, Any]) -> None:
    """Synchronous / non-blocking thread fallback for save_creator_to_db."""
    try:
        conn = _get_connection_sync()
        cid = str(creator.get("id") or creator.get("creator_channel_id"))
        conn.execute('''
            INSERT INTO tempvc_creators (guild_id, creator_id, name, name_template, category_id, privacy_mode, user_limit, bitrate, sync_permissions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, creator_id) DO UPDATE SET
                name=excluded.name,
                name_template=excluded.name_template,
                category_id=excluded.category_id,
                privacy_mode=excluded.privacy_mode,
                user_limit=excluded.user_limit,
                bitrate=excluded.bitrate,
                sync_permissions=excluded.sync_permissions
        ''', (
            str(guild_id),
            cid,
            creator.get("name", "➕ Join to Create"),
            creator.get("nameTemplate", "{user}'s Lounge"),
            str(creator.get("categoryId", "")),
            creator.get("privacyMode", "Public"),
            int(creator.get("userLimit", 0)),
            creator.get("bitrate", "64kbps"),
            creator.get("syncPermissions", "Sync with Category")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TEMPVC DB ERROR] save_creator_to_db: {e}")

async def delete_creator_from_db_async(guild_id: str | int, creator_id: str | int) -> None:
    """Deletes a creator channel record from SQLite (non-blocking async)."""
    try:
        await _init_db_async()
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as conn:
            await conn.execute("DELETE FROM tempvc_creators WHERE guild_id = ? AND creator_id = ?", (str(guild_id), str(creator_id)))
            await conn.commit()
    except Exception as e:
        print(f"[TEMPVC DB ERROR] delete_creator_from_db_async: {e}")

def delete_creator_from_db(guild_id: str | int, creator_id: str | int) -> None:
    """Deletes a creator channel record from SQLite (sync)."""
    try:
        conn = _get_connection_sync()
        conn.execute("DELETE FROM tempvc_creators WHERE guild_id = ? AND creator_id = ?", (str(guild_id), str(creator_id)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TEMPVC DB ERROR] delete_creator_from_db: {e}")

async def save_all_creators_to_db_async(guild_id: str | int, creators: List[Dict[str, Any]]) -> None:
    """Replaces all creators for a guild in SQLite (non-blocking async)."""
    try:
        await _init_db_async()
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as conn:
            await conn.execute("DELETE FROM tempvc_creators WHERE guild_id = ?", (str(guild_id),))
            for c in creators:
                cid = str(c.get("id") or c.get("creator_channel_id"))
                await conn.execute('''
                    INSERT INTO tempvc_creators (guild_id, creator_id, name, name_template, category_id, privacy_mode, user_limit, bitrate, sync_permissions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(guild_id),
                    cid,
                    c.get("name", "➕ Join to Create"),
                    c.get("nameTemplate", "{user}'s Lounge"),
                    str(c.get("categoryId", "")),
                    c.get("privacyMode", "Public"),
                    int(c.get("userLimit", 0)),
                    c.get("bitrate", "64kbps"),
                    c.get("syncPermissions", "Sync with Category")
                ))
            await conn.commit()
    except Exception as e:
        print(f"[TEMPVC DB ERROR] save_all_creators_to_db_async: {e}")

def save_all_creators_to_db(guild_id: str | int, creators: List[Dict[str, Any]]) -> None:
    """Replaces all creators for a guild in SQLite (sync)."""
    try:
        conn = _get_connection_sync()
        conn.execute("DELETE FROM tempvc_creators WHERE guild_id = ?", (str(guild_id),))
        for c in creators:
            cid = str(c.get("id") or c.get("creator_channel_id"))
            conn.execute('''
                INSERT INTO tempvc_creators (guild_id, creator_id, name, name_template, category_id, privacy_mode, user_limit, bitrate, sync_permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(guild_id),
                cid,
                c.get("name", "➕ Join to Create"),
                c.get("nameTemplate", "{user}'s Lounge"),
                str(c.get("categoryId", "")),
                c.get("privacyMode", "Public"),
                int(c.get("userLimit", 0)),
                c.get("bitrate", "64kbps"),
                c.get("syncPermissions", "Sync with Category")
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TEMPVC DB ERROR] save_all_creators_to_db: {e}")

async def load_creators_from_db_async(guild_id: str | int) -> List[Dict[str, Any]]:
    """Loads all creators for a guild from SQLite (non-blocking async)."""
    try:
        await _init_db_async()
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as conn:
            async with conn.execute('''
                SELECT creator_id, name, name_template, category_id, privacy_mode, user_limit, bitrate, sync_permissions
                FROM tempvc_creators WHERE guild_id = ?
            ''', (str(guild_id),)) as cursor:
                rows = await cursor.fetchall()
                results = []
                for cid, name, ntmpl, catid, pmode, ulimit, brit, sperms in rows:
                    results.append({
                        "id": str(cid),
                        "name": name,
                        "nameTemplate": ntmpl or "{user}'s Lounge",
                        "categoryId": str(catid or ""),
                        "privacyMode": pmode or "Public",
                        "userLimit": int(ulimit or 0),
                        "bitrate": brit or "64kbps",
                        "syncPermissions": sperms or "Sync with Category"
                    })
                return results
    except Exception as e:
        print(f"[TEMPVC DB ERROR] load_creators_from_db_async: {e}")
        return []

def load_creators_from_db(guild_id: str | int) -> List[Dict[str, Any]]:
    """Loads all creators for a guild from SQLite (sync)."""
    try:
        conn = _get_connection_sync()
        rows = conn.execute('''
            SELECT creator_id, name, name_template, category_id, privacy_mode, user_limit, bitrate, sync_permissions
            FROM tempvc_creators WHERE guild_id = ?
        ''', (str(guild_id),)).fetchall()
        conn.close()
        results = []
        for cid, name, ntmpl, catid, pmode, ulimit, brit, sperms in rows:
            results.append({
                "id": str(cid),
                "name": name,
                "nameTemplate": ntmpl or "{user}'s Lounge",
                "categoryId": str(catid or ""),
                "privacyMode": pmode or "Public",
                "userLimit": int(ulimit or 0),
                "bitrate": brit or "64kbps",
                "syncPermissions": sperms or "Sync with Category"
            })
        return results
    except Exception as e:
        print(f"[TEMPVC DB ERROR] load_creators_from_db: {e}")
        return []
