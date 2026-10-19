"""
YUNA Ticket System Database Layer.
Provides high-performance, asynchronous SQLite persistence with WAL mode,
transactional write safety, indexes, and full multi-tenant isolation.
"""

from __future__ import annotations
import os
import time
import json
import uuid
import aiosqlite
from typing import Dict, Any, Optional, List, Tuple

TICKETS_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "db", "tickets.db")
)


async def init_tickets_db():
    """Initializes the tickets database schema and indexes."""
    os.makedirs(os.path.dirname(TICKETS_DB_PATH), exist_ok=True)
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        # 1. Ticket System Settings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_settings (
                guild_id INTEGER PRIMARY KEY,
                global_ticket_limit INTEGER DEFAULT 50,
                max_tickets_per_user INTEGER DEFAULT 1,
                auto_close_hours INTEGER DEFAULT 0,
                auto_close_warning_hours INTEGER DEFAULT 0,
                auto_close_message TEXT DEFAULT 'This ticket has been marked inactive and will close automatically.',
                transcript_channel_id TEXT DEFAULT '',
                working_hours_enabled INTEGER DEFAULT 0,
                working_hours_start TEXT DEFAULT '09:00',
                working_hours_end TEXT DEFAULT '18:00',
                working_hours_timezone TEXT DEFAULT 'UTC',
                working_hours_message TEXT DEFAULT 'Our support team is currently out of office. Your ticket has been logged and we will respond during business hours.',
                feedback_enabled INTEGER DEFAULT 0,
                feedback_channel_id TEXT DEFAULT '',
                default_naming_template TEXT DEFAULT 'ticket-{id}',
                created_at REAL,
                updated_at REAL
            );
        """)

        # 2. Ticket Panels
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_panels (
                id TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                channel_id TEXT DEFAULT '',
                message_id TEXT DEFAULT '',
                title TEXT DEFAULT 'Support Desk',
                message_content TEXT DEFAULT '',
                embed_color TEXT DEFAULT '#5865F2',
                embed_description TEXT DEFAULT 'Need assistance? Click a button below or select a category to open a private support ticket.',
                embed_fields TEXT DEFAULT '[]',
                button_label TEXT DEFAULT 'Open Ticket',
                button_style TEXT DEFAULT 'PRIMARY',
                button_emoji TEXT DEFAULT '📩',
                category_ids TEXT DEFAULT '[]',
                support_role_ids TEXT DEFAULT '[]',
                config_data TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                created_at REAL,
                updated_at REAL
            );
        """)

        # 3. Ticket Categories / Types
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_categories (
                id TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                emoji TEXT DEFAULT '🎫',
                discord_category_id TEXT DEFAULT '',
                support_role_ids TEXT DEFAULT '[]',
                individual_staff_ids TEXT DEFAULT '[]',
                opening_message TEXT DEFAULT 'Hello {user}, thank you for reaching out! A staff member will be with you shortly.',
                form_id TEXT DEFAULT '',
                naming_template TEXT DEFAULT 'ticket-{id}',
                ticket_limit INTEGER DEFAULT 1,
                priority TEXT DEFAULT 'NORMAL',
                auto_close_hours INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                created_at REAL,
                updated_at REAL
            );
        """)

        # 4. Ticket Intake Forms
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_forms (
                id TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                questions TEXT DEFAULT '[]',
                created_at REAL,
                updated_at REAL
            );
        """)

        # 5. Tickets
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                ticket_number INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                panel_id TEXT DEFAULT '',
                category_id TEXT DEFAULT '',
                channel_id TEXT DEFAULT '',
                requester_id TEXT NOT NULL,
                requester_name TEXT NOT NULL,
                requester_avatar TEXT DEFAULT '',
                status TEXT DEFAULT 'OPEN',
                priority TEXT DEFAULT 'NORMAL',
                assigned_staff_id TEXT DEFAULT '',
                assigned_staff_name TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                form_responses TEXT DEFAULT '[]',
                closed_by_id TEXT DEFAULT '',
                closed_by_name TEXT DEFAULT '',
                closed_reason TEXT DEFAULT '',
                closed_at REAL DEFAULT 0,
                rating INTEGER DEFAULT 0,
                rating_feedback TEXT DEFAULT '',
                first_response_at REAL DEFAULT 0,
                last_activity_at REAL DEFAULT 0,
                created_at REAL,
                updated_at REAL
            );
        """)

        # 6. Ticket Conversation Messages
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id TEXT PRIMARY KEY,
                ticket_id TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                message_id TEXT DEFAULT '',
                author_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_avatar TEXT DEFAULT '',
                is_staff INTEGER DEFAULT 0,
                is_dashboard INTEGER DEFAULT 0,
                is_internal_note INTEGER DEFAULT 0,
                content TEXT DEFAULT '',
                attachments TEXT DEFAULT '[]',
                created_at REAL
            );
        """)

        # 7. Ticket Transcripts
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_transcripts (
                id TEXT PRIMARY KEY,
                ticket_id TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                html_content TEXT NOT NULL,
                total_messages INTEGER DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                created_at REAL
            );
        """)

        # 8. Ticket Audit Logs
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_audit_logs (
                id TEXT PRIMARY KEY,
                ticket_id TEXT DEFAULT '',
                guild_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_name TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at REAL
            );
        """)

        # 9. Ticket Blacklist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_blacklist (
                id TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT DEFAULT '',
                reason TEXT DEFAULT 'Violation of ticket guidelines',
                added_by_id TEXT DEFAULT '',
                added_by_name TEXT DEFAULT '',
                created_at REAL
            );
        """)

        # 10. Staff & Permissions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_permissions (
                guild_id INTEGER PRIMARY KEY,
                permissions_data TEXT DEFAULT '{}',
                updated_at REAL
            );
        """)

        # Create Indexes for Sub-millisecond Filter & Search Queries
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_guild_status ON tickets(guild_id, status);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_requester ON tickets(guild_id, requester_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(channel_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages(ticket_id, created_at);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_transcripts_ticket ON ticket_transcripts(ticket_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_audit_guild ON ticket_audit_logs(guild_id, created_at);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_panels_guild ON ticket_panels(guild_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_categories_guild ON ticket_categories(guild_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_forms_guild ON ticket_forms(guild_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_blacklist_guild_user ON ticket_blacklist(guild_id, user_id);")

        # Migrations for existing deployments
        try:
            await db.execute("ALTER TABLE tickets ADD COLUMN is_locked INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE tickets ADD COLUMN participants TEXT DEFAULT '[]';")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE ticket_panels ADD COLUMN support_role_ids TEXT DEFAULT '[]';")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE ticket_panels ADD COLUMN config_data TEXT DEFAULT '{}';")
        except Exception:
            pass
        for col_name, col_sql in [
            ("close_confirmation_enabled", "INTEGER DEFAULT 1"),
            ("close_on_member_leave", "INTEGER DEFAULT 0"),
            ("allow_claiming", "INTEGER DEFAULT 1"),
            ("cooldown_seconds", "INTEGER DEFAULT 0"),
            ("working_hours_block_creation", "INTEGER DEFAULT 0"),
            ("templates", "TEXT DEFAULT '{}'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE ticket_settings ADD COLUMN {col_name} {col_sql};")
            except Exception:
                pass

        await db.commit()


# ==============================================================================
# SETTINGS REPOSITORY
# ==============================================================================

async def get_ticket_settings(guild_id: int) -> Dict[str, Any]:
    """Fetches system-wide ticket settings for a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                d = dict(row)
                raw_tmpl = d.get("templates")
                if isinstance(raw_tmpl, str):
                    try:
                        d["templates"] = json.loads(raw_tmpl)
                    except Exception:
                        d["templates"] = {}
                elif not isinstance(raw_tmpl, dict):
                    d["templates"] = {}
                return d

    # Defaults if not configured
    return {
        "guild_id": guild_id,
        "global_ticket_limit": 50,
        "max_tickets_per_user": 1,
        "auto_close_hours": 0,
        "auto_close_warning_hours": 0,
        "auto_close_message": "This ticket has been marked inactive and will close automatically.",
        "transcript_channel_id": "",
        "working_hours_enabled": 0,
        "working_hours_start": "09:00",
        "working_hours_end": "18:00",
        "working_hours_timezone": "UTC",
        "working_hours_message": "Our support team is currently out of office. Your ticket has been logged and we will respond during business hours.",
        "working_hours_block_creation": 0,
        "feedback_enabled": 0,
        "feedback_channel_id": "",
        "default_naming_template": "ticket-{id}",
        "close_confirmation_enabled": 1,
        "close_on_member_leave": 0,
        "allow_claiming": 1,
        "cooldown_seconds": 0,
        "templates": {},
        "created_at": time.time(),
        "updated_at": time.time()
    }


async def save_ticket_settings(guild_id: int, data: Dict[str, Any]) -> bool:
    """Saves or updates system-wide ticket settings for a guild."""
    await init_tickets_db()
    now = time.time()
    raw_tmpl = data.get("templates")
    tmpl_str = json.dumps(raw_tmpl) if isinstance(raw_tmpl, dict) else str(raw_tmpl or "{}")

    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            INSERT INTO ticket_settings (
                guild_id, global_ticket_limit, max_tickets_per_user,
                auto_close_hours, auto_close_warning_hours, auto_close_message,
                transcript_channel_id, working_hours_enabled, working_hours_start,
                working_hours_end, working_hours_timezone, working_hours_message,
                working_hours_block_creation, feedback_enabled, feedback_channel_id,
                default_naming_template, close_confirmation_enabled, close_on_member_leave,
                allow_claiming, cooldown_seconds, templates, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                global_ticket_limit=excluded.global_ticket_limit,
                max_tickets_per_user=excluded.max_tickets_per_user,
                auto_close_hours=excluded.auto_close_hours,
                auto_close_warning_hours=excluded.auto_close_warning_hours,
                auto_close_message=excluded.auto_close_message,
                transcript_channel_id=excluded.transcript_channel_id,
                working_hours_enabled=excluded.working_hours_enabled,
                working_hours_start=excluded.working_hours_start,
                working_hours_end=excluded.working_hours_end,
                working_hours_timezone=excluded.working_hours_timezone,
                working_hours_message=excluded.working_hours_message,
                working_hours_block_creation=excluded.working_hours_block_creation,
                feedback_enabled=excluded.feedback_enabled,
                feedback_channel_id=excluded.feedback_channel_id,
                default_naming_template=excluded.default_naming_template,
                close_confirmation_enabled=excluded.close_confirmation_enabled,
                close_on_member_leave=excluded.close_on_member_leave,
                allow_claiming=excluded.allow_claiming,
                cooldown_seconds=excluded.cooldown_seconds,
                templates=excluded.templates,
                updated_at=excluded.updated_at;
        """, (
            guild_id,
            int(data.get("global_ticket_limit", 50)),
            int(data.get("max_tickets_per_user", 1)),
            int(data.get("auto_close_hours", 0)),
            int(data.get("auto_close_warning_hours", 0)),
            str(data.get("auto_close_message", "")),
            str(data.get("transcript_channel_id", "")),
            1 if data.get("working_hours_enabled") else 0,
            str(data.get("working_hours_start", "09:00")),
            str(data.get("working_hours_end", "18:00")),
            str(data.get("working_hours_timezone", "UTC")),
            str(data.get("working_hours_message", "")),
            1 if data.get("working_hours_block_creation") else 0,
            1 if data.get("feedback_enabled") else 0,
            str(data.get("feedback_channel_id", "")),
            str(data.get("default_naming_template", "ticket-{id}")),
            1 if data.get("close_confirmation_enabled", 1) else 0,
            1 if data.get("close_on_member_leave") else 0,
            1 if data.get("allow_claiming", 1) else 0,
            int(data.get("cooldown_seconds", 0)),
            tmpl_str,
            now,
            now
        ))
        await db.commit()
    return True


async def get_ticket_templates(guild_id: int) -> Dict[str, Any]:
    """Fetches custom lifecycle message templates for a guild."""
    settings = await get_ticket_settings(guild_id)
    tmpl = settings.get("templates")
    return tmpl if isinstance(tmpl, dict) else {}


async def save_ticket_templates(guild_id: int, templates: Dict[str, Any]) -> bool:
    """Saves custom lifecycle message templates for a guild."""
    await init_tickets_db()
    tmpl_str = json.dumps(templates)
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE ticket_settings SET templates = ?, updated_at = ? WHERE guild_id = ?;
        """, (tmpl_str, time.time(), guild_id))
        await db.commit()
    return True


async def get_last_ticket_created_time_for_user(guild_id: int, user_id: str) -> Optional[float]:
    """Gets the timestamp of the most recent ticket opened by a user in a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        async with db.execute(
            "SELECT created_at FROM tickets WHERE guild_id = ? AND requester_id = ? ORDER BY created_at DESC LIMIT 1;",
            (guild_id, str(user_id))
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return float(row[0])
    return None


async def get_ticket_files(ticket_id: str) -> List[Dict[str, Any]]:
    """Extracts all attachments uploaded to a ticket conversation."""
    messages = await get_ticket_messages(ticket_id)
    files = []
    for msg in messages:
        atts = msg.get("attachments") or []
        for att in atts:
            if isinstance(att, dict) and att.get("url"):
                files.append({
                    "url": att["url"],
                    "filename": att.get("filename") or "attachment",
                    "size": att.get("size") or 0,
                    "author_name": msg.get("author_name", "Unknown"),
                    "author_id": msg.get("author_id", "0"),
                    "created_at": msg.get("created_at", 0)
                })
    return files


# ==============================================================================
# TICKET PANELS REPOSITORY
# ==============================================================================

async def get_ticket_panels(guild_id: int) -> List[Dict[str, Any]]:
    """Gets all ticket panels for a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_panels WHERE guild_id = ? ORDER BY created_at DESC", (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                p = dict(r)
                p["embed_fields"] = json.loads(p.get("embed_fields") or "[]")
                p["category_ids"] = json.loads(p.get("category_ids") or "[]")
                p["support_role_ids"] = json.loads(p.get("support_role_ids") or "[]")
                cfg = json.loads(p.get("config_data") or "{}")
                p["config_data"] = cfg
                if isinstance(cfg, dict):
                    for k, v in cfg.items():
                        if k not in p or p[k] is None or p[k] == "":
                            p[k] = v
                p["enabled"] = bool(p.get("enabled", 1))
                result.append(p)
            return result


async def get_ticket_panel_by_id(panel_id: str) -> Optional[Dict[str, Any]]:
    """Gets a specific ticket panel by ID."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_panels WHERE id = ?", (panel_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                p = dict(row)
                p["embed_fields"] = json.loads(p.get("embed_fields") or "[]")
                p["category_ids"] = json.loads(p.get("category_ids") or "[]")
                p["support_role_ids"] = json.loads(p.get("support_role_ids") or "[]")
                cfg = json.loads(p.get("config_data") or "{}")
                p["config_data"] = cfg
                if isinstance(cfg, dict):
                    for k, v in cfg.items():
                        if k not in p or p[k] is None or p[k] == "":
                            p[k] = v
                p["enabled"] = bool(p.get("enabled", 1))
                return p
    return None


async def save_ticket_panel(guild_id: int, panel_data: Dict[str, Any]) -> str:
    """Creates or updates a ticket panel."""
    await init_tickets_db()
    now = time.time()
    panel_id = str(panel_data.get("id") or f"pnl_{uuid.uuid4().hex[:12]}")
    embed_fields_json = json.dumps(panel_data.get("embed_fields") or panel_data.get("embedFields") or [])
    category_ids_json = json.dumps(panel_data.get("category_ids") or panel_data.get("categoryIds") or [])
    support_role_ids_json = json.dumps(panel_data.get("support_role_ids") or panel_data.get("supportRoleIds") or [])

    cfg_data = panel_data.get("config_data")
    if not isinstance(cfg_data, dict):
        cfg_data = {}
    for extra_key in [
        "action_rows", "panel_modal", "ticket_configuration", "ticket_limit",
        "welcome_message", "features", "logs_channel_id", "transcript_enabled",
        "transcript_channel_id", "messages", "author_name", "author_icon_url",
        "author_url", "title_url", "thumbnail_url", "image_url", "footer_text",
        "footer_icon_url", "timestamp_enabled"
    ]:
        if extra_key in panel_data and extra_key not in cfg_data:
            cfg_data[extra_key] = panel_data[extra_key]
    config_data_json = json.dumps(cfg_data)

    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            INSERT INTO ticket_panels (
                id, guild_id, name, description, channel_id, message_id,
                title, message_content, embed_color, embed_description,
                embed_fields, button_label, button_style, button_emoji,
                category_ids, support_role_ids, config_data, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                channel_id=excluded.channel_id,
                message_id=excluded.message_id,
                title=excluded.title,
                message_content=excluded.message_content,
                embed_color=excluded.embed_color,
                embed_description=excluded.embed_description,
                embed_fields=excluded.embed_fields,
                button_label=excluded.button_label,
                button_style=excluded.button_style,
                button_emoji=excluded.button_emoji,
                category_ids=excluded.category_ids,
                support_role_ids=excluded.support_role_ids,
                config_data=excluded.config_data,
                enabled=excluded.enabled,
                updated_at=excluded.updated_at;
        """, (
            panel_id,
            guild_id,
            str(panel_data.get("name", "Support Panel")),
            str(panel_data.get("description", "")),
            str(panel_data.get("channel_id") or panel_data.get("channelId") or ""),
            str(panel_data.get("message_id") or panel_data.get("messageId") or ""),
            str(panel_data.get("title", "Support Desk")),
            str(panel_data.get("message_content") or panel_data.get("messageContent") or ""),
            str(panel_data.get("embed_color") or panel_data.get("embedColor") or "#5865F2"),
            str(panel_data.get("embed_description") or panel_data.get("embedDescription") or ""),
            embed_fields_json,
            str(panel_data.get("button_label") or panel_data.get("buttonLabel") or "Open Ticket"),
            str(panel_data.get("button_style") or panel_data.get("buttonStyle") or "PRIMARY"),
            str(panel_data.get("button_emoji") or panel_data.get("buttonEmoji") or "📩"),
            category_ids_json,
            support_role_ids_json,
            config_data_json,
            1 if panel_data.get("enabled", True) else 0,
            now,
            now
        ))
        await db.commit()
    return panel_id


async def delete_ticket_panel(guild_id: int, panel_id: str) -> bool:
    """Deletes a ticket panel."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("DELETE FROM ticket_panels WHERE id = ? AND guild_id = ?", (panel_id, guild_id))
        await db.commit()
    return True


# ==============================================================================
# TICKET CATEGORIES REPOSITORY
# ==============================================================================

async def get_ticket_categories(guild_id: int) -> List[Dict[str, Any]]:
    """Gets all ticket categories for a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_categories WHERE guild_id = ? ORDER BY created_at ASC", (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                c = dict(r)
                c["support_role_ids"] = json.loads(c.get("support_role_ids") or "[]")
                c["individual_staff_ids"] = json.loads(c.get("individual_staff_ids") or "[]")
                c["enabled"] = bool(c.get("enabled", 1))
                result.append(c)
            return result


async def get_ticket_category_by_id(category_id: str) -> Optional[Dict[str, Any]]:
    """Gets a specific ticket category by ID."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_categories WHERE id = ?", (category_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                c = dict(row)
                c["support_role_ids"] = json.loads(c.get("support_role_ids") or "[]")
                c["individual_staff_ids"] = json.loads(c.get("individual_staff_ids") or "[]")
                c["enabled"] = bool(c.get("enabled", 1))
                return c
    return None


async def save_ticket_category(guild_id: int, category_data: Dict[str, Any]) -> str:
    """Creates or updates a ticket category."""
    await init_tickets_db()
    now = time.time()
    cat_id = str(category_data.get("id") or f"cat_{uuid.uuid4().hex[:12]}")
    support_roles_json = json.dumps(category_data.get("support_role_ids") or category_data.get("supportRoleIds") or [])
    staff_ids_json = json.dumps(category_data.get("individual_staff_ids") or category_data.get("individualStaffIds") or [])

    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            INSERT INTO ticket_categories (
                id, guild_id, name, description, emoji, discord_category_id,
                support_role_ids, individual_staff_ids, opening_message,
                form_id, naming_template, ticket_limit, priority,
                auto_close_hours, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                emoji=excluded.emoji,
                discord_category_id=excluded.discord_category_id,
                support_role_ids=excluded.support_role_ids,
                individual_staff_ids=excluded.individual_staff_ids,
                opening_message=excluded.opening_message,
                form_id=excluded.form_id,
                naming_template=excluded.naming_template,
                ticket_limit=excluded.ticket_limit,
                priority=excluded.priority,
                auto_close_hours=excluded.auto_close_hours,
                enabled=excluded.enabled,
                updated_at=excluded.updated_at;
        """, (
            cat_id,
            guild_id,
            str(category_data.get("name", "General Support")),
            str(category_data.get("description", "")),
            str(category_data.get("emoji", "🎫")),
            str(category_data.get("discord_category_id") or category_data.get("discordCategoryId") or ""),
            support_roles_json,
            staff_ids_json,
            str(category_data.get("opening_message") or category_data.get("openingMessage") or "Hello {user}, a staff member will be with you shortly."),
            str(category_data.get("form_id") or category_data.get("formId") or ""),
            str(category_data.get("naming_template") or category_data.get("namingTemplate") or "ticket-{id}"),
            int(category_data.get("ticket_limit") or category_data.get("ticketLimit") or 1),
            str(category_data.get("priority", "NORMAL")).upper(),
            int(category_data.get("auto_close_hours") or category_data.get("autoCloseHours") or 0),
            1 if category_data.get("enabled", True) else 0,
            now,
            now
        ))
        await db.commit()
    return cat_id


async def delete_ticket_category(guild_id: int, category_id: str) -> bool:
    """Deletes a ticket category."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("DELETE FROM ticket_categories WHERE id = ? AND guild_id = ?", (category_id, guild_id))
        await db.commit()
    return True


# ==============================================================================
# TICKET FORMS REPOSITORY
# ==============================================================================

async def get_ticket_forms(guild_id: int) -> List[Dict[str, Any]]:
    """Gets all intake forms for a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_forms WHERE guild_id = ? ORDER BY created_at DESC", (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                f = dict(r)
                f["questions"] = json.loads(f.get("questions") or "[]")
                result.append(f)
            return result


async def get_ticket_form_by_id(form_id: str) -> Optional[Dict[str, Any]]:
    """Gets a specific form by ID."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_forms WHERE id = ?", (form_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                f = dict(row)
                f["questions"] = json.loads(f.get("questions") or "[]")
                return f
    return None


async def save_ticket_form(guild_id: int, form_data: Dict[str, Any]) -> str:
    """Creates or updates an intake form."""
    await init_tickets_db()
    now = time.time()
    form_id = str(form_data.get("id") or f"frm_{uuid.uuid4().hex[:12]}")
    questions_json = json.dumps(form_data.get("questions") or [])

    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            INSERT INTO ticket_forms (
                id, guild_id, name, description, questions, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                questions=excluded.questions,
                updated_at=excluded.updated_at;
        """, (
            form_id,
            guild_id,
            str(form_data.get("name", "Support Intake Form")),
            str(form_data.get("description", "")),
            questions_json,
            now,
            now
        ))
        await db.commit()
    return form_id


async def delete_ticket_form(guild_id: int, form_id: str) -> bool:
    """Deletes an intake form."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("DELETE FROM ticket_forms WHERE id = ? AND guild_id = ?", (form_id, guild_id))
        await db.commit()
    return True


# ==============================================================================
# TICKETS CRUD & LIFECYCLE REPOSITORY
# ==============================================================================

async def create_ticket_record(
    guild_id: int,
    requester_id: str,
    requester_name: str,
    requester_avatar: str,
    category_id: str = "",
    panel_id: str = "",
    channel_id: str = "",
    subject: str = "",
    priority: str = "NORMAL",
    form_responses: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Creates a new ticket record transactionally."""
    await init_tickets_db()
    now = time.time()
    ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"

    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=20.0) as db:
        db.row_factory = aiosqlite.Row
        # Calculate sequential number for guild
        async with db.execute("SELECT COALESCE(MAX(ticket_number), 0) + 1 FROM tickets WHERE guild_id = ?", (guild_id,)) as cur:
            row = await cur.fetchone()
            ticket_number = int(row[0]) if row else 1

        responses_json = json.dumps(form_responses or [])

        await db.execute("""
            INSERT INTO tickets (
                id, ticket_number, guild_id, panel_id, category_id,
                channel_id, requester_id, requester_name, requester_avatar,
                status, priority, assigned_staff_id, assigned_staff_name,
                subject, form_responses, closed_by_id, closed_by_name,
                closed_reason, closed_at, rating, rating_feedback,
                first_response_at, last_activity_at, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                'OPEN', ?, '', '',
                ?, ?, '', '',
                '', 0, 0, '',
                0, ?, ?, ?
            );
        """, (
            ticket_id, ticket_number, guild_id, panel_id, category_id,
            channel_id, requester_id, requester_name, requester_avatar,
            priority.upper(),
            subject or f"Ticket #{ticket_number:04d}",
            responses_json,
            now, now, now
        ))
        await db.commit()

    return await get_ticket_by_id(ticket_id)


async def get_ticket_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Gets full ticket record by ticket ID."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                t = dict(row)
                t["form_responses"] = json.loads(t.get("form_responses") or "[]")
                try:
                    t["participants"] = json.loads(t.get("participants") or "[]")
                except Exception:
                    t["participants"] = []
                t["is_locked"] = bool(t.get("is_locked", 0))
                return t
    return None


async def get_ticket_by_channel_id(channel_id: str) -> Optional[Dict[str, Any]]:
    """Gets ticket associated with a Discord channel."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE channel_id = ?", (str(channel_id),)) as cursor:
            row = await cursor.fetchone()
            if row:
                t = dict(row)
                t["form_responses"] = json.loads(t.get("form_responses") or "[]")
                try:
                    t["participants"] = json.loads(t.get("participants") or "[]")
                except Exception:
                    t["participants"] = []
                t["is_locked"] = bool(t.get("is_locked", 0))
                return t
    return None


async def get_open_tickets_count_for_user(guild_id: int, user_id: str) -> int:
    """Returns number of currently open tickets for a user in a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND requester_id = ? AND status = 'OPEN'",
            (guild_id, str(user_id))
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def get_open_tickets_for_user(guild_id: int, user_id: str) -> List[Dict[str, Any]]:
    """Returns list of currently open ticket records for a user in a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tickets WHERE guild_id = ? AND requester_id = ? AND status = 'OPEN' ORDER BY created_at DESC",
            (guild_id, str(user_id))
        ) as cur:
            rows = await cur.fetchall()
            tickets = []
            for r in rows:
                t = dict(r)
                try:
                    t["form_responses"] = json.loads(t.get("form_responses") or "[]")
                except Exception:
                    t["form_responses"] = []
                try:
                    t["participants"] = json.loads(t.get("participants") or "[]")
                except Exception:
                    t["participants"] = []
                t["is_locked"] = bool(t.get("is_locked", 0))
                tickets.append(t)
            return tickets


async def get_total_open_tickets_count(guild_id: int) -> int:
    """Returns total open tickets across a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND status = 'OPEN'",
            (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def update_ticket_status(ticket_id: str, status: str, closed_by_id: str = "", closed_by_name: str = "", closed_reason: str = "") -> bool:
    """Updates ticket status (e.g. OPEN, CLOSED)."""
    await init_tickets_db()
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        if status.upper() == "CLOSED":
            await db.execute("""
                UPDATE tickets SET
                    status = 'CLOSED',
                    closed_by_id = ?,
                    closed_by_name = ?,
                    closed_reason = ?,
                    closed_at = ?,
                    updated_at = ?
                WHERE id = ?;
            """, (closed_by_id, closed_by_name, closed_reason, now, now, ticket_id))
        else:
            await db.execute("""
                UPDATE tickets SET
                    status = ?,
                    closed_by_id = '',
                    closed_by_name = '',
                    closed_reason = '',
                    closed_at = 0,
                    updated_at = ?
                WHERE id = ?;
            """, (status.upper(), now, ticket_id))
        await db.commit()
    return True


async def assign_ticket_staff(ticket_id: str, staff_id: str, staff_name: str) -> bool:
    """Claims or assigns a ticket to a staff member."""
    await init_tickets_db()
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE tickets SET
                assigned_staff_id = ?,
                assigned_staff_name = ?,
                updated_at = ?
            WHERE id = ?;
        """, (staff_id, staff_name, now, ticket_id))
        await db.commit()
    return True


async def update_ticket_priority(ticket_id: str, priority: str) -> bool:
    """Updates ticket priority (LOW, NORMAL, HIGH, URGENT)."""
    await init_tickets_db()
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE tickets SET priority = ?, updated_at = ? WHERE id = ?;
        """, (priority.upper(), now, ticket_id))
        await db.commit()
    return True


async def update_ticket_subject(ticket_id: str, subject: str) -> bool:
    """Updates ticket subject / title."""
    await init_tickets_db()
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE tickets SET subject = ?, updated_at = ? WHERE id = ?;
        """, (subject, now, ticket_id))
        await db.commit()
    return True


async def submit_ticket_rating(ticket_id: str, rating: int, feedback: str = "") -> bool:
    """Submits customer satisfaction rating (1-5)."""
    await init_tickets_db()
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE tickets SET rating = ?, rating_feedback = ?, updated_at = ? WHERE id = ?;
        """, (max(1, min(5, rating)), feedback, now, ticket_id))
        await db.commit()
    return True


async def delete_ticket_record(ticket_id: str) -> bool:
    """Permanently deletes ticket and associated messages."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        await db.execute("DELETE FROM ticket_messages WHERE ticket_id = ?", (ticket_id,))
        await db.commit()
    return True


async def update_ticket_lock(ticket_id: str, is_locked: bool) -> bool:
    """Updates ticket locked status."""
    await init_tickets_db()
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE tickets SET is_locked = ?, updated_at = ? WHERE id = ?;
        """, (1 if is_locked else 0, now, ticket_id))
        await db.commit()
    return True


async def update_ticket_category(ticket_id: str, category_id: str) -> bool:
    """Updates ticket category assignment."""
    await init_tickets_db()
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE tickets SET category_id = ?, updated_at = ? WHERE id = ?;
        """, (category_id, now, ticket_id))
        await db.commit()
    return True


async def add_ticket_participant(ticket_id: str, user_id: str, user_name: str) -> bool:
    """Adds a participant to the ticket record."""
    await init_tickets_db()
    ticket = await get_ticket_by_id(ticket_id)
    if not ticket:
        return False
    participants = ticket.get("participants") or []
    if not isinstance(participants, list):
        participants = []
    if not any(isinstance(p, dict) and p.get("user_id") == str(user_id) for p in participants):
        participants.append({
            "user_id": str(user_id),
            "user_name": str(user_name),
            "added_at": time.time()
        })
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE tickets SET participants = ?, updated_at = ? WHERE id = ?;
        """, (json.dumps(participants), now, ticket_id))
        await db.commit()
    return True


async def remove_ticket_participant(ticket_id: str, user_id: str) -> bool:
    """Removes a participant from the ticket record."""
    await init_tickets_db()
    ticket = await get_ticket_by_id(ticket_id)
    if not ticket:
        return False
    participants = ticket.get("participants") or []
    if not isinstance(participants, list):
        participants = []
    updated = [p for p in participants if (isinstance(p, dict) and p.get("user_id") != str(user_id)) or (isinstance(p, str) and p != str(user_id))]
    now = time.time()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            UPDATE tickets SET participants = ?, updated_at = ? WHERE id = ?;
        """, (json.dumps(updated), now, ticket_id))
        await db.commit()
    return True


# ==============================================================================
# TICKET MESSAGES REPOSITORY
# ==============================================================================

async def add_ticket_message(
    ticket_id: str,
    guild_id: int,
    author_id: str,
    author_name: str,
    author_avatar: str,
    content: str,
    message_id: str = "",
    is_staff: bool = False,
    is_dashboard: bool = False,
    is_internal_note: bool = False,
    attachments: List[Dict[str, str]] = None
) -> str:
    """Persists a ticket conversation message or internal staff note."""
    await init_tickets_db()
    now = time.time()
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    attach_json = json.dumps(attachments or [])

    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            INSERT INTO ticket_messages (
                id, ticket_id, guild_id, message_id, author_id,
                author_name, author_avatar, is_staff, is_dashboard,
                is_internal_note, content, attachments, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            msg_id, ticket_id, guild_id, str(message_id), str(author_id),
            author_name, author_avatar, 1 if is_staff else 0,
            1 if is_dashboard else 0, 1 if is_internal_note else 0,
            content, attach_json, now
        ))

        # Update last activity and first response time if staff replied
        if is_staff and not is_internal_note:
            await db.execute("""
                UPDATE tickets SET
                    last_activity_at = ?,
                    first_response_at = CASE WHEN first_response_at = 0 THEN ? ELSE first_response_at END,
                    updated_at = ?
                WHERE id = ?;
            """, (now, now, now, ticket_id))
        else:
            await db.execute("UPDATE tickets SET last_activity_at = ?, updated_at = ? WHERE id = ?;", (now, now, ticket_id))

        await db.commit()

    return msg_id


async def get_ticket_messages(ticket_id: str, include_internal_notes: bool = True) -> List[Dict[str, Any]]:
    """Fetches all messages for a ticket ordered chronologically."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT * FROM ticket_messages WHERE ticket_id = ?"
        params = [ticket_id]
        if not include_internal_notes:
            sql += " AND is_internal_note = 0"
        sql += " ORDER BY created_at ASC;"

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            messages = []
            for r in rows:
                m = dict(r)
                m["attachments"] = json.loads(m.get("attachments") or "[]")
                m["is_staff"] = bool(m.get("is_staff"))
                m["is_dashboard"] = bool(m.get("is_dashboard"))
                m["is_internal_note"] = bool(m.get("is_internal_note"))
                messages.append(m)
            return messages


# ==============================================================================
# AUDIT LOGS REPOSITORY
# ==============================================================================

async def log_ticket_audit_event(
    guild_id: int,
    action: str,
    actor_id: str,
    actor_name: str,
    ticket_id: str = "",
    details: str = ""
):
    """Records an audit event for ticket operations."""
    await init_tickets_db()
    now = time.time()
    evt_id = f"aud_{uuid.uuid4().hex[:12]}"
    try:
        async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
            await db.execute("""
                INSERT INTO ticket_audit_logs (
                    id, ticket_id, guild_id, action, actor_id,
                    actor_name, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (evt_id, ticket_id, guild_id, action, str(actor_id), actor_name, details, now))
            await db.commit()
    except Exception as e:
        print(f"[TICKET AUDIT ERROR] {e}")


async def get_ticket_audit_logs(guild_id: int, ticket_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Gets audit logs for a guild or specific ticket."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        if ticket_id:
            sql = "SELECT * FROM ticket_audit_logs WHERE guild_id = ? AND ticket_id = ? ORDER BY created_at DESC LIMIT ?"
            params = (guild_id, ticket_id, limit)
        else:
            sql = "SELECT * FROM ticket_audit_logs WHERE guild_id = ? ORDER BY created_at DESC LIMIT ?"
            params = (guild_id, limit)

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ==============================================================================
# TRANSCRIPTS REPOSITORY
# ==============================================================================

async def save_ticket_transcript(ticket_id: str, guild_id: int, html_content: str, total_messages: int) -> str:
    """Stores an HTML transcript record."""
    await init_tickets_db()
    now = time.time()
    t_id = f"trn_{uuid.uuid4().hex[:12]}"
    file_size = len(html_content.encode("utf-8"))

    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            INSERT OR REPLACE INTO ticket_transcripts (
                id, ticket_id, guild_id, html_content, total_messages, file_size, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (t_id, ticket_id, guild_id, html_content, total_messages, file_size, now))
        await db.commit()
    return t_id


async def get_ticket_transcript(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Fetches transcript for a ticket."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_transcripts WHERE ticket_id = ?", (ticket_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def get_guild_transcripts(guild_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Gets list of transcripts for a guild (excluding huge html_content in list view)."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT tr.id, tr.ticket_id, tr.guild_id, tr.total_messages, tr.file_size, tr.created_at,
                   tk.ticket_number, tk.subject, tk.requester_name, tk.requester_avatar, tk.closed_by_name, tk.category_id
            FROM ticket_transcripts tr
            LEFT JOIN tickets tk ON tr.ticket_id = tk.id
            WHERE tr.guild_id = ?
            ORDER BY tr.created_at DESC
            LIMIT ?;
        """, (guild_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ==============================================================================
# BLACKLIST REPOSITORY
# ==============================================================================

async def is_user_blacklisted(guild_id: int, user_id: str) -> Tuple[bool, str]:
    """Checks if a user is blacklisted from opening tickets."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        async with db.execute(
            "SELECT reason FROM ticket_blacklist WHERE guild_id = ? AND user_id = ?",
            (guild_id, str(user_id))
        ) as cur:
            row = await cur.fetchone()
            if row:
                return True, row[0]
    return False, ""


async def get_ticket_blacklist(guild_id: int) -> List[Dict[str, Any]]:
    """Gets all blacklisted users for a guild."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ticket_blacklist WHERE guild_id = ? ORDER BY created_at DESC", (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def add_to_ticket_blacklist(
    guild_id: int,
    user_id: str,
    user_name: str,
    reason: str,
    added_by_id: str,
    added_by_name: str
) -> bool:
    """Adds a user to ticket blacklist."""
    await init_tickets_db()
    now = time.time()
    b_id = f"blk_{uuid.uuid4().hex[:12]}"
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            INSERT OR REPLACE INTO ticket_blacklist (
                id, guild_id, user_id, user_name, reason,
                added_by_id, added_by_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (b_id, guild_id, str(user_id), user_name, reason, str(added_by_id), added_by_name, now))
        await db.commit()
    return True


async def remove_from_ticket_blacklist(guild_id: int, user_id: str) -> bool:
    """Removes a user from ticket blacklist."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("DELETE FROM ticket_blacklist WHERE guild_id = ? AND user_id = ?", (guild_id, str(user_id)))
        await db.commit()
    return True


# ==============================================================================
# STAFF PERMISSIONS REPOSITORY
# ==============================================================================

async def get_ticket_permissions(guild_id: int) -> Dict[str, Any]:
    """Gets staff roles and fine-grained permissions matrix."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        async with db.execute("SELECT permissions_data FROM ticket_permissions WHERE guild_id = ?", (guild_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    pass

    return {
        "support_roles": [],
        "admin_roles": [],
        "role_permissions": {}
    }


async def save_ticket_permissions(guild_id: int, permissions_data: Dict[str, Any]) -> bool:
    """Saves staff roles and fine-grained permissions matrix."""
    await init_tickets_db()
    now = time.time()
    data_json = json.dumps(permissions_data)
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=10.0) as db:
        await db.execute("""
            INSERT INTO ticket_permissions (guild_id, permissions_data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                permissions_data=excluded.permissions_data,
                updated_at=excluded.updated_at;
        """, (guild_id, data_json, now))
        await db.commit()
    return True


# ==============================================================================
# ANALYTICS & OVERVIEW REPOSITORY
# ==============================================================================

async def get_ticket_analytics(guild_id: int) -> Dict[str, Any]:
    """Calculates real-time ticket performance and volume metrics from persisted data."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=15.0) as db:
        db.row_factory = aiosqlite.Row

        # 1. Counts
        async with db.execute("""
            SELECT 
                COUNT(*) AS total_tickets,
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) AS open_tickets,
                SUM(CASE WHEN status = 'OPEN' AND (assigned_staff_id IS NULL OR assigned_staff_id = '') THEN 1 ELSE 0 END) AS unclaimed_tickets,
                SUM(CASE WHEN status = 'OPEN' AND (assigned_staff_id IS NOT NULL AND assigned_staff_id != '') THEN 1 ELSE 0 END) AS awaiting_staff,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) AS closed_tickets,
                AVG(CASE WHEN first_response_at > 0 AND created_at > 0 THEN (first_response_at - created_at) ELSE NULL END) AS avg_first_response_sec,
                AVG(CASE WHEN closed_at > 0 AND created_at > 0 THEN (closed_at - created_at) ELSE NULL END) AS avg_resolution_sec,
                AVG(CASE WHEN rating > 0 THEN rating ELSE NULL END) AS avg_rating,
                COUNT(CASE WHEN rating > 0 THEN 1 ELSE NULL END) AS total_ratings
            FROM tickets
            WHERE guild_id = ?;
        """, (guild_id,)) as cur:
            summary = dict(await cur.fetchone() or {})

        # 2. Staff Workload Breakdown
        async with db.execute("""
            SELECT 
                assigned_staff_id,
                assigned_staff_name,
                COUNT(*) as total_assigned,
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) as closed_count,
                AVG(CASE WHEN closed_at > 0 AND created_at > 0 THEN (closed_at - created_at) ELSE NULL END) as avg_res_time
            FROM tickets
            WHERE guild_id = ? AND assigned_staff_id != ''
            GROUP BY assigned_staff_id, assigned_staff_name
            ORDER BY total_assigned DESC
            LIMIT 10;
        """, (guild_id,)) as cur:
            staff_rows = await cur.fetchall()
            staff_workload = [dict(r) for r in staff_rows]

        # 3. Category Distribution
        async with db.execute("""
            SELECT 
                category_id,
                COUNT(*) as count
            FROM tickets
            WHERE guild_id = ?
            GROUP BY category_id;
        """, (guild_id,)) as cur:
            cat_rows = await cur.fetchall()
            category_distribution = {r["category_id"]: r["count"] for r in cat_rows}

        # 4. Recent Activity (Last 10 tickets)
        async with db.execute("""
            SELECT id, ticket_number, requester_name, requester_avatar, status, priority, subject, assigned_staff_name, created_at, closed_at
            FROM tickets
            WHERE guild_id = ?
            ORDER BY created_at DESC
            LIMIT 10;
        """, (guild_id,)) as cur:
            recent_rows = await cur.fetchall()
            recent_tickets = [dict(r) for r in recent_rows]

    # Clean numerical values
    return {
        "total_tickets": summary.get("total_tickets") or 0,
        "open_tickets": summary.get("open_tickets") or 0,
        "unclaimed_tickets": summary.get("unclaimed_tickets") or 0,
        "awaiting_staff": summary.get("awaiting_staff") or 0,
        "awaiting_requester": 0,
        "closed_tickets": summary.get("closed_tickets") or 0,
        "resolved_tickets": summary.get("closed_tickets") or 0,
        "avg_first_response_minutes": round((summary.get("avg_first_response_sec") or 0) / 60.0, 1),
        "avg_resolution_hours": round((summary.get("avg_resolution_sec") or 0) / 3600.0, 1),
        "satisfaction_rating": round(summary.get("avg_rating") or 0.0, 2),
        "total_ratings": summary.get("total_ratings") or 0,
        "staff_workload": staff_workload,
        "category_distribution": category_distribution,
        "recent_tickets": recent_tickets
    }


async def search_and_filter_tickets(
    guild_id: int,
    status: Optional[str] = None,
    category_id: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_staff_id: Optional[str] = None,
    requester_id: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """Filters, searches, and paginates tickets."""
    await init_tickets_db()
    async with aiosqlite.connect(TICKETS_DB_PATH, timeout=15.0) as db:
        db.row_factory = aiosqlite.Row

        where_clauses = ["guild_id = ?"]
        params: List[Any] = [guild_id]

        if status and status.upper() != "ALL":
            if status.upper() == "UNCLAIMED":
                where_clauses.append("status = 'OPEN' AND (assigned_staff_id IS NULL OR assigned_staff_id = '')")
            elif status.upper() == "ASSIGNED":
                where_clauses.append("status = 'OPEN' AND (assigned_staff_id IS NOT NULL AND assigned_staff_id != '')")
            else:
                where_clauses.append("status = ?")
                params.append(status.upper())

        if priority and priority.upper() != "ALL":
            where_clauses.append("priority = ?")
            params.append(priority.upper())

        if category_id and category_id.upper() != "ALL":
            where_clauses.append("category_id = ?")
            params.append(category_id)

        if assigned_staff_id:
            where_clauses.append("assigned_staff_id = ?")
            params.append(assigned_staff_id)

        if requester_id:
            where_clauses.append("requester_id = ?")
            params.append(requester_id)

        if query and query.strip():
            q = f"%{query.strip()}%"
            where_clauses.append("(subject LIKE ? OR requester_name LIKE ? OR CAST(ticket_number AS TEXT) LIKE ?)")
            params.extend([q, q, q])

        where_sql = " AND ".join(where_clauses)

        # Count total
        count_sql = f"SELECT COUNT(*) FROM tickets WHERE {where_sql}"
        async with db.execute(count_sql, params) as cur:
            row = await cur.fetchone()
            total = int(row[0]) if row else 0

        # Fetch page
        fetch_sql = f"""
            SELECT * FROM tickets
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        fetch_params = params + [limit, offset]

        async with db.execute(fetch_sql, fetch_params) as cur:
            rows = await cur.fetchall()
            tickets = []
            for r in rows:
                t = dict(r)
                t["form_responses"] = json.loads(t.get("form_responses") or "[]")
                try:
                    t["participants"] = json.loads(t.get("participants") or "[]")
                except Exception:
                    t["participants"] = []
                t["is_locked"] = bool(t.get("is_locked", 0))
                tickets.append(t)

        return tickets, total
