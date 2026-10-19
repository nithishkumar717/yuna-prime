"""
YUNA Billing & Organization Data Management Engine
Handles dual persistence (local SQLite NVMe cache + Cloud MongoDB Atlas) for:
  1. Server Organization & Financial Profiles (`payment_organizations`)
  2. Payment Orders & Tax Invoice Metadata (`payment_payment_orders`)
  3. Dynamic On-Demand Tax Invoice PDF generation directly from stored structured data.

Note: Only structured metadata is stored in MongoDB Atlas (zero PDF bloat in cloud).
PDFs are dynamically generated on-the-fly when requested by the web dashboard or Discord bot.
"""

import os
import io
import time
import sqlite3
import datetime
import pytz
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import aiosqlite

try:
    from pymongo import MongoClient, UpdateOne
except ImportError:
    MongoClient = None
    UpdateOne = None

from core.database.upsert_sync_engine import create_resilient_mongo_client

IST_TZ = pytz.timezone("Asia/Kolkata")
DB_PATH = "db/payment.db"

DEFAULT_UPI_ID = "nithishnithishnk001-2@okaxis"
DEFAULT_PAYEE_NAME = "NITHISH K"

_MONGO_CLIENT_CACHE: Optional[Any] = None
_MONGO_CLIENT_FAIL_TIME: float = 0.0


def _get_current_time_ist() -> Tuple[float, str]:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_ist = now_utc.astimezone(IST_TZ)
    timestamp_ist = now_ist.strftime("%d-%m-%Y %I:%M:%S %p IST")
    return now_utc.timestamp(), timestamp_ist


def get_mongo_db() -> Optional[Any]:
    """Retrieves or initializes a resilient MongoDB database reference for billing."""
    global _MONGO_CLIENT_CACHE, _MONGO_CLIENT_FAIL_TIME

    if MongoClient is None:
        return None

    # Circuit breaker if MongoDB failed recently (< 30s)
    if _MONGO_CLIENT_CACHE is None and (time.time() - _MONGO_CLIENT_FAIL_TIME < 30.0):
        return None

    if _MONGO_CLIENT_CACHE is not None:
        try:
            return _MONGO_CLIENT_CACHE["yuna_db"]
        except Exception:
            _MONGO_CLIENT_CACHE = None

    try:
        from utils.settings_manager import server_settings
        if getattr(server_settings, "mongo_client", None) is not None:
            _MONGO_CLIENT_CACHE = server_settings.mongo_client
            return _MONGO_CLIENT_CACHE["yuna_db"]
    except Exception:
        pass

    uri = os.getenv("MONGODB_URI")
    if not uri:
        return None

    try:
        client = create_resilient_mongo_client(uri, timeout_ms=5000)
        if client:
            _MONGO_CLIENT_CACHE = client
            return client["yuna_db"]
    except Exception as e:
        print(f"[BILLING MONGO WARNING] Failed to connect to MongoDB: {e}")
        _MONGO_CLIENT_FAIL_TIME = time.time()

    return None


async def init_sqlite_billing_tables():
    """Ensures SQLite billing tables exist."""
    os.makedirs(os.path.dirname(DB_PATH) or "db", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                guild_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                upi_id TEXT NOT NULL,
                payee_name TEXT,
                support_contact TEXT,
                terms TEXT,
                manager_role_id TEXT,
                created_at REAL,
                updated_at REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payment_orders (
                order_id TEXT PRIMARY KEY,
                invoice_no TEXT UNIQUE,
                user_id TEXT NOT NULL,
                user_name TEXT,
                guild_id TEXT,
                guild_name TEXT,
                channel_id TEXT,
                message_id TEXT,
                amount REAL NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at REAL,
                paid_at REAL,
                confirmed_by TEXT,
                upi_id TEXT,
                qr_path TEXT,
                invoice_path TEXT
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_pay_user ON payment_orders(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_pay_status ON payment_orders(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_payment_orders_guild_id ON payment_orders(guild_id)")
        await db.commit()


# ==============================================================================
# 1. SERVER ORGANIZATION PROFILE MANAGEMENT
# ==============================================================================

async def save_organization(
    guild_id: str | int,
    name: str,
    upi_id: str,
    payee_name: Optional[str] = None,
    support_contact: Optional[str] = None,
    terms: Optional[str] = None,
    manager_role_id: Optional[str | int] = None
) -> Dict[str, Any]:
    """
    Saves or updates an organization profile in local SQLite and upserts structured data to MongoDB Atlas.
    """
    await init_sqlite_billing_tables()
    g_id = str(guild_id)
    clean_name = str(name).strip()
    clean_upi = str(upi_id).strip()
    clean_payee = str(payee_name or clean_name).strip()
    clean_contact = str(support_contact).strip() if support_contact else None
    clean_terms = str(terms).strip() if terms else None
    clean_role = str(manager_role_id).strip() if manager_role_id else None

    unix_now, ist_time = _get_current_time_ist()

    # 1. Persist to local SQLite
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO organizations (
                guild_id, name, upi_id, payee_name, support_contact, terms, manager_role_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                name = excluded.name,
                upi_id = excluded.upi_id,
                payee_name = excluded.payee_name,
                support_contact = excluded.support_contact,
                terms = excluded.terms,
                manager_role_id = COALESCE(excluded.manager_role_id, organizations.manager_role_id),
                updated_at = excluded.updated_at
        """, (g_id, clean_name, clean_upi, clean_payee, clean_contact, clean_terms, clean_role, unix_now, unix_now))
        await db.commit()

        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM organizations WHERE guild_id = ?", (g_id,)) as cursor:
            row = await cursor.fetchone()
            org_dict = dict(row) if row else {}

    # 2. Upsert structured data to MongoDB Atlas (payment_organizations)
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            mongo_doc = {
                "_id": g_id,
                "guild_id": g_id,
                "name": clean_name,
                "upi_id": clean_upi,
                "payee_name": clean_payee,
                "support_contact": clean_contact,
                "terms": clean_terms,
                "manager_role_id": clean_role,
                "created_at": org_dict.get("created_at", unix_now),
                "updated_at": unix_now,
                "_updated_at_ist": ist_time,
                "_updated_at_unix": unix_now,
            }
            mongo_db["payment_organizations"].update_one(
                {"_id": g_id},
                {"$set": mongo_doc},
                upsert=True
            )
        except Exception as e:
            print(f"[BILLING MONGO SAVE ORG WARNING] {e}")

    return org_dict


async def get_organization(guild_id: str | int) -> Optional[Dict[str, Any]]:
    """Retrieves organization profile from MongoDB Atlas, falling back to local SQLite."""
    g_id = str(guild_id)

    # 1. Try MongoDB Atlas
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            doc = mongo_db["payment_organizations"].find_one({"_id": g_id})
            if doc:
                res = {k: v for k, v in doc.items() if not k.startswith("_") or k == "_id"}
                res["guild_id"] = str(res.get("guild_id") or g_id)
                return res
        except Exception:
            pass

    # 2. Fallback to SQLite
    await init_sqlite_billing_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM organizations WHERE guild_id = ?", (g_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

    return None


async def delete_organization(guild_id: str | int) -> bool:
    """Deletes organization profile from SQLite and MongoDB Atlas."""
    g_id = str(guild_id)
    await init_sqlite_billing_tables()

    # 1. SQLite
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM organizations WHERE guild_id = ?", (g_id,))
        await db.commit()

    # 2. MongoDB
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            mongo_db["payment_organizations"].delete_one({"_id": g_id})
        except Exception:
            pass

    return True


# ==============================================================================
# 2. PAYMENT ORDER & INVOICE DATA MANAGEMENT
# ==============================================================================

async def save_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Saves or updates a payment order in SQLite and MongoDB Atlas.
    Stores purely structured data (zero PDF files or blobs stored in MongoDB).
    """
    await init_sqlite_billing_tables()

    o_id = str(order_data["order_id"]).strip().upper()
    inv_no = str(order_data.get("invoice_no") or f"INV-{o_id}").strip().upper()
    u_id = str(order_data.get("user_id") or "")
    u_name = str(order_data.get("user_name") or f"User {u_id}")
    g_id = str(order_data.get("guild_id") or "")
    g_name = str(order_data.get("guild_name") or "")
    c_id = str(order_data.get("channel_id") or "") if order_data.get("channel_id") else None
    m_id = str(order_data.get("message_id") or "") if order_data.get("message_id") else None
    amt = float(order_data.get("amount") or 0.0)
    rsn = str(order_data.get("reason") or "Payment")
    status = str(order_data.get("status") or "PENDING").upper()
    upi_id = str(order_data.get("upi_id") or DEFAULT_UPI_ID)
    confirmed_by = str(order_data.get("confirmed_by") or "") if order_data.get("confirmed_by") else None

    unix_now, ist_time = _get_current_time_ist()
    created_at = float(order_data.get("created_at") or unix_now)
    paid_at = float(order_data["paid_at"]) if order_data.get("paid_at") else None

    # SQLite
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO payment_orders (
                order_id, invoice_no, user_id, user_name, guild_id, guild_name,
                channel_id, message_id, amount, reason, status, created_at,
                paid_at, confirmed_by, upi_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_id) DO UPDATE SET
                invoice_no = excluded.invoice_no,
                user_name = excluded.user_name,
                guild_name = excluded.guild_name,
                amount = excluded.amount,
                reason = excluded.reason,
                status = excluded.status,
                paid_at = excluded.paid_at,
                confirmed_by = excluded.confirmed_by,
                upi_id = excluded.upi_id
        """, (
            o_id, inv_no, u_id, u_name, g_id, g_name,
            c_id, m_id, amt, rsn, status, created_at,
            paid_at, confirmed_by, upi_id
        ))
        await db.commit()

        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM payment_orders WHERE order_id = ?", (o_id,)) as cursor:
            row = await cursor.fetchone()
            clean_order = dict(row) if row else {}

    # MongoDB Atlas (payment_payment_orders) - pure structured data
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            mongo_doc = {
                "_id": o_id,
                "order_id": o_id,
                "invoice_no": inv_no,
                "user_id": u_id,
                "user_name": u_name,
                "guild_id": g_id,
                "guild_name": g_name,
                "channel_id": c_id,
                "message_id": m_id,
                "amount": amt,
                "reason": rsn,
                "status": status,
                "created_at": created_at,
                "paid_at": paid_at,
                "confirmed_by": confirmed_by,
                "upi_id": upi_id,
                "_updated_at_ist": ist_time,
                "_updated_at_unix": unix_now,
            }
            mongo_db["payment_payment_orders"].update_one(
                {"_id": o_id},
                {"$set": mongo_doc},
                upsert=True
            )
        except Exception as e:
            print(f"[BILLING MONGO SAVE ORDER WARNING] {e}")

    return clean_order


async def update_order_status(
    order_id: str,
    status: str,
    confirmed_by: Optional[str] = None,
    paid_at: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """Updates order status (PAID or CANCELLED) in SQLite and MongoDB Atlas."""
    o_id = str(order_id).strip().upper()
    new_status = str(status).strip().upper()
    unix_now, ist_time = _get_current_time_ist()
    actual_paid_at = paid_at if paid_at is not None else (unix_now if new_status == "PAID" else None)

    # 1. Update SQLite
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""
            UPDATE payment_orders
            SET status = ?, paid_at = ?, confirmed_by = ?
            WHERE order_id = ?
        """, (new_status, actual_paid_at, confirmed_by, o_id))
        await db.commit()

        async with db.execute("SELECT * FROM payment_orders WHERE order_id = ?", (o_id,)) as cursor:
            row = await cursor.fetchone()
            order_dict = dict(row) if row else None

    # 2. Update MongoDB Atlas
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            update_fields: Dict[str, Any] = {
                "status": new_status,
                "paid_at": actual_paid_at,
                "_updated_at_ist": ist_time,
                "_updated_at_unix": unix_now,
            }
            if confirmed_by:
                update_fields["confirmed_by"] = confirmed_by

            mongo_db["payment_payment_orders"].update_one(
                {"_id": o_id},
                {"$set": update_fields}
            )
        except Exception as e:
            print(f"[BILLING MONGO UPDATE ORDER WARNING] {e}")

    return order_dict


async def get_order(order_id: str, guild_id: Optional[str | int] = None) -> Optional[Dict[str, Any]]:
    """Retrieves an order from MongoDB Atlas or SQLite."""
    o_id = str(order_id).strip().upper()
    g_id_str = str(guild_id) if guild_id else None

    # 1. Try MongoDB Atlas
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            query = {"_id": o_id}
            if g_id_str:
                query["guild_id"] = g_id_str
            doc = mongo_db["payment_payment_orders"].find_one(query)
            if doc:
                res = {k: v for k, v in doc.items() if not k.startswith("_") or k == "_id"}
                res["has_invoice"] = (res.get("status") == "PAID")
                return res
        except Exception:
            pass

    # 2. Fallback to SQLite
    await init_sqlite_billing_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT * FROM payment_orders WHERE order_id = ?"
        params: List[Any] = [o_id]
        if g_id_str:
            sql += " AND guild_id = ?"
            params.append(g_id_str)

        async with db.execute(sql, tuple(params)) as cursor:
            row = await cursor.fetchone()
            if row:
                res = dict(row)
                res["has_invoice"] = (res.get("status") == "PAID")
                return res

    return None


async def get_guild_orders(guild_id: str | int) -> List[Dict[str, Any]]:
    """Fetches all orders for a guild, sorted newest first."""
    g_id = str(guild_id)

    # 1. Try MongoDB Atlas
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            docs = list(mongo_db["payment_payment_orders"].find({"guild_id": g_id}).sort("created_at", -1))
            if docs:
                results = []
                for d in docs:
                    item = {k: v for k, v in d.items() if not k.startswith("_") or k == "_id"}
                    item["has_invoice"] = (item.get("status") == "PAID")
                    results.append(item)
                return results
        except Exception:
            pass

    # 2. Fallback to SQLite
    await init_sqlite_billing_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payment_orders WHERE guild_id = ? ORDER BY created_at DESC",
            (g_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["has_invoice"] = (item.get("status") == "PAID")
                results.append(item)
            return results


# ==============================================================================
# 3. DYNAMIC ON-THE-FLY TAX INVOICE PDF GENERATOR
# ==============================================================================

def _load_font(size: int, bold: bool = False):
    """Safely loads Arial / DejaVu or falls back to PIL default font."""
    font_names = (
        ["arialbd.ttf", "DejaVuSans-Bold.ttf", "seguiemb.ttf", "tahomabd.ttf"]
        if bold else
        ["arial.ttf", "DejaVuSans.ttf", "segoeui.ttf", "tahoma.ttf"]
    )
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def build_invoice_pdf_buffer(order_data: Dict[str, Any], org_data: Optional[Dict[str, Any]] = None) -> io.BytesIO:
    """
    Renders an official high-resolution Tax Invoice PDF in-memory (io.BytesIO)
    from stored structured data. Zero static PDF files or blobs needed.
    """
    inv_no = str(order_data.get("invoice_no") or f"INV-{order_data.get('order_id', 'ORDER')}").upper()
    order_id = str(order_data.get("order_id") or "N/A").upper()
    customer_name = str(order_data.get("user_name") or f"User {order_data.get('user_id', '')}")
    customer_id = str(order_data.get("user_id") or "N/A")
    guild_name = str(order_data.get("guild_name") or "Discord Server")
    amount = float(order_data.get("amount") or 0.0)
    reason = str(order_data.get("reason") or "Server Subscription / Goods")
    status = str(order_data.get("status") or "PAID").upper()
    confirmed_by = str(order_data.get("confirmed_by") or "Administrator")
    upi_id = str(order_data.get("upi_id") or (org_data.get("upi_id") if org_data else DEFAULT_UPI_ID))
    payee_name = str(org_data.get("payee_name") if org_data else (order_data.get("payee_name") or DEFAULT_PAYEE_NAME))
    org_name = str(org_data.get("name") if org_data else (order_data.get("guild_name") or "YUNA DEVELOPMENT"))
    terms = org_data.get("terms") if org_data else None
    support_contact = org_data.get("support_contact") if org_data else None

    # Paid timestamp
    paid_at = order_data.get("paid_at") or order_data.get("created_at") or time.time()
    try:
        dt = datetime.datetime.fromtimestamp(paid_at, pytz.timezone("Asia/Kolkata"))
        payment_date_str = dt.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        payment_date_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p IST")

    width, height = 1240, 1754
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    c_primary = (43, 45, 49)
    c_accent = (255, 105, 180)
    c_green = (46, 204, 113)
    c_amber = (245, 158, 11)
    c_red = (239, 68, 68)
    c_gray_bg = (246, 248, 250)
    c_text_dark = (33, 37, 41)
    c_text_muted = (108, 117, 125)
    c_border = (222, 226, 230)

    f_title = _load_font(44, bold=True)
    f_heading = _load_font(28, bold=True)
    f_subheading = _load_font(22, bold=True)
    f_body_bold = _load_font(20, bold=True)
    f_body = _load_font(20, bold=False)
    f_small = _load_font(16, bold=False)
    f_big_amount = _load_font(36, bold=True)

    # 1. Header Banner
    draw.rectangle([(0, 0), (width, 160)], fill=c_primary)
    draw.rectangle([(0, 154), (width, 160)], fill=c_accent)

    display_org_title = (org_name or "YUNA DEVELOPMENT").upper()
    if len(display_org_title) > 30:
        display_org_title = display_org_title[:28] + "..."
    draw.text((60, 45), display_org_title, fill=(255, 255, 255), font=f_title)
    draw.text((60, 100), "Official Payment Receipt & Tax Invoice", fill=(200, 205, 215), font=f_subheading)

    # Status Badge Stamp
    stamp_x, stamp_y = width - 240, 45
    if status == "PAID":
        draw.rounded_rectangle([(stamp_x, stamp_y), (stamp_x + 180, stamp_y + 70)], radius=12, fill=c_green)
        draw.text((stamp_x + 35, stamp_y + 18), "PAID  ✓", fill=(255, 255, 255), font=f_heading)
    elif status == "CANCELLED":
        draw.rounded_rectangle([(stamp_x, stamp_y), (stamp_x + 180, stamp_y + 70)], radius=12, fill=c_red)
        draw.text((stamp_x + 20, stamp_y + 18), "CANCELLED", fill=(255, 255, 255), font=f_heading)
    else:
        draw.rounded_rectangle([(stamp_x, stamp_y), (stamp_x + 180, stamp_y + 70)], radius=12, fill=c_amber)
        draw.text((stamp_x + 28, stamp_y + 18), "PENDING ⏳", fill=(255, 255, 255), font=f_heading)

    # 2. Meta Info Box
    meta_top = 190
    draw.rounded_rectangle([(60, meta_top), (width - 60, meta_top + 130)], radius=10, fill=c_gray_bg, outline=c_border, width=1)

    draw.text((85, meta_top + 20), "Invoice Number:", fill=c_text_muted, font=f_small)
    draw.text((85, meta_top + 45), inv_no, fill=c_text_dark, font=f_body_bold)

    draw.text((380, meta_top + 20), "Order ID:", fill=c_text_muted, font=f_small)
    draw.text((380, meta_top + 45), order_id, fill=c_text_dark, font=f_body_bold)

    draw.text((660, meta_top + 20), "Payment Date:", fill=c_text_muted, font=f_small)
    draw.text((660, meta_top + 45), payment_date_str, fill=c_text_dark, font=f_body_bold)

    draw.text((950, meta_top + 20), "Payment Method:", fill=c_text_muted, font=f_small)
    draw.text((950, meta_top + 45), "UPI (Instant)", fill=c_text_dark, font=f_body_bold)

    draw.text((85, meta_top + 80), f"Verified & Confirmed by: {confirmed_by}", fill=c_text_muted, font=f_small)
    upi_meta_str = f"UPI: {upi_id} ({payee_name})" if payee_name else f"UPI: {upi_id}"
    if len(upi_meta_str) > 45:
        upi_meta_str = upi_meta_str[:42] + "..."
    draw.text((660, meta_top + 80), upi_meta_str, fill=c_text_muted, font=f_small)

    # 3. Bill To Box
    cust_top = 345
    draw.rounded_rectangle([(60, cust_top), (width - 60, cust_top + 110)], radius=10, fill=(255, 255, 255), outline=c_border, width=1)

    draw.text((85, cust_top + 15), "BILLED TO (CUSTOMER)", fill=c_accent, font=f_subheading)
    draw.text((85, cust_top + 48), f"Discord User: {customer_name}", fill=c_text_dark, font=f_body_bold)
    draw.text((85, cust_top + 75), f"User ID: {customer_id}  |  Server: {guild_name}", fill=c_text_muted, font=f_small)

    # 4. Itemized Table
    tbl_top = 480
    tbl_h = 450
    draw.rounded_rectangle([(60, tbl_top), (width - 60, tbl_top + tbl_h)], radius=10, fill=(255, 255, 255), outline=c_border, width=1)

    # Table Header
    draw.rounded_rectangle([(60, tbl_top), (width - 60, tbl_top + 50)], radius=10, fill=c_primary)
    draw.text((85, tbl_top + 12), "DESCRIPTION", fill=(255, 255, 255), font=f_body_bold)
    draw.text((700, tbl_top + 12), "QTY", fill=(255, 255, 255), font=f_body_bold)
    draw.text((850, tbl_top + 12), "UNIT PRICE", fill=(255, 255, 255), font=f_body_bold)
    draw.text((1020, tbl_top + 12), "AMOUNT", fill=(255, 255, 255), font=f_body_bold)

    # Table Row
    row_y = tbl_top + 80
    desc_str = reason or "Digital Goods / Server Membership"
    if len(desc_str) > 55:
        desc_str = desc_str[:52] + "..."
    draw.text((85, row_y), desc_str, fill=c_text_dark, font=f_body_bold)
    draw.text((85, row_y + 30), f"Beneficiary: {org_name} (Order Ref: {order_id})", fill=c_text_muted, font=f_small)

    draw.text((720, row_y), "1", fill=c_text_dark, font=f_body)
    draw.text((850, row_y), f"INR {amount:.2f}", fill=c_text_dark, font=f_body)
    draw.text((1020, row_y), f"INR {amount:.2f}", fill=c_text_dark, font=f_body_bold)

    draw.line([(60, row_y + 80), (width - 60, row_y + 80)], fill=c_border, width=1)

    # Totals
    tot_y = row_y + 110
    draw.text((750, tot_y), "Subtotal:", fill=c_text_muted, font=f_body)
    draw.text((1020, tot_y), f"INR {amount:.2f}", fill=c_text_dark, font=f_body_bold)

    draw.text((750, tot_y + 40), "Tax (GST / VAT):", fill=c_text_muted, font=f_body)
    draw.text((1020, tot_y + 40), "INR 0.00", fill=c_text_dark, font=f_body)

    draw.rectangle([(730, tot_y + 80), (width - 60, tot_y + 150)], fill=c_gray_bg)
    draw.text((750, tot_y + 98), "TOTAL PAID:", fill=c_primary, font=f_heading)
    draw.text((980, tot_y + 93), f"INR {amount:.2f}", fill=c_green, font=f_big_amount)

    # 5. Terms & Conditions Box
    term_top = 970
    draw.rounded_rectangle([(60, term_top), (width - 60, term_top + 160)], radius=10, fill=c_gray_bg, outline=c_border, width=1)
    draw.text((85, term_top + 18), "TERMS & CONDITIONS", fill=c_primary, font=f_subheading)
    if terms:
        t_lines = [line.strip() for line in terms.split("\n") if line.strip()][:3]
        for idx, t_line in enumerate(t_lines):
            draw.text((85, term_top + 48 + (idx * 24)), f"• {t_line[:85]}", fill=c_text_dark, font=f_small)
        draw.text((85, term_top + 125), f"• Thank you for supporting {org_name}!", fill=c_accent, font=f_body_bold)
    else:
        draw.text((85, term_top + 50), "• This is an electronically generated official tax invoice and proof of payment.", fill=c_text_dark, font=f_small)
        draw.text((85, term_top + 75), "• Services & subscriptions are activated immediately upon payment confirmation.", fill=c_text_dark, font=f_small)
        contact_display = support_contact if support_contact else "our official server"
        draw.text((85, term_top + 100), f"• For any billing queries, contact: {contact_display[:60]}", fill=c_text_muted, font=f_small)
        draw.text((85, term_top + 125), f"• Thank you for supporting {org_name}!", fill=c_accent, font=f_body_bold)

    # 6. Footer
    draw.line([(60, height - 90), (width - 60, height - 90)], fill=c_border, width=1)
    footer_text = f"Powered by Yuna Development™ • Merchant: {org_name}"
    if support_contact:
        footer_text += f" ({support_contact})"
    draw.text((60, height - 65), footer_text[:80], fill=c_text_muted, font=f_small)
    draw.text((width - 320, height - 65), "Official Receipt & Invoice", fill=c_text_muted, font=f_small)

    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    buf.seek(0)
    return buf


# ==============================================================================
# 4. INITIAL BACKFILL / SYNC FROM SQLITE TO MONGODB
# ==============================================================================

def backfill_sqlite_to_mongo():
    """Syncs existing SQLite billing & organization data to MongoDB Atlas if not already synced."""
    if not os.path.exists(DB_PATH):
        return

    mongo_db = get_mongo_db()
    if mongo_db is None:
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        # 1. Backfill organizations
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations")
            org_rows = cursor.fetchall()
            cursor.close()

            if org_rows:
                ops = []
                for row in org_rows:
                    d = dict(row)
                    g_id = str(d["guild_id"])
                    doc = {
                        "_id": g_id,
                        "guild_id": g_id,
                        "name": d.get("name"),
                        "upi_id": d.get("upi_id"),
                        "payee_name": d.get("payee_name"),
                        "support_contact": d.get("support_contact"),
                        "terms": d.get("terms"),
                        "manager_role_id": str(d.get("manager_role_id")) if d.get("manager_role_id") else None,
                        "created_at": d.get("created_at"),
                        "updated_at": d.get("updated_at"),
                    }
                    ops.append(UpdateOne({"_id": g_id}, {"$set": doc}, upsert=True))
                if ops:
                    mongo_db["payment_organizations"].bulk_write(ops, ordered=False)
                    print(f"[BILLING BACKFILL] Mirrored {len(ops)} organization records to MongoDB Atlas.")
        except Exception as e:
            print(f"[BILLING BACKFILL ORGS WARNING] {e}")

        # 2. Backfill payment_orders (pure structured data, no PDF binary)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payment_orders")
            order_rows = cursor.fetchall()
            cursor.close()

            if order_rows:
                ops = []
                for row in order_rows:
                    d = dict(row)
                    o_id = str(d["order_id"])
                    doc = {
                        "_id": o_id,
                        "order_id": o_id,
                        "invoice_no": d.get("invoice_no"),
                        "user_id": str(d.get("user_id") or ""),
                        "user_name": d.get("user_name"),
                        "guild_id": str(d.get("guild_id") or ""),
                        "guild_name": d.get("guild_name"),
                        "channel_id": d.get("channel_id"),
                        "message_id": d.get("message_id"),
                        "amount": float(d.get("amount") or 0.0),
                        "reason": d.get("reason"),
                        "status": str(d.get("status") or "PENDING").upper(),
                        "created_at": d.get("created_at"),
                        "paid_at": d.get("paid_at"),
                        "confirmed_by": d.get("confirmed_by"),
                        "upi_id": d.get("upi_id"),
                    }
                    ops.append(UpdateOne({"_id": o_id}, {"$set": doc}, upsert=True))
                if ops:
                    mongo_db["payment_payment_orders"].bulk_write(ops, ordered=False)
                    print(f"[BILLING BACKFILL] Mirrored {len(ops)} payment orders to MongoDB Atlas.")
        except Exception as e:
            print(f"[BILLING BACKFILL ORDERS WARNING] {e}")

        conn.close()
    except Exception as e:
        print(f"[BILLING BACKFILL ERROR] {e}")


_BACKFILL_DONE = False

def ensure_backfill():
    """Starts a safe background worker to backfill any unsynced SQLite records to MongoDB Atlas."""
    global _BACKFILL_DONE
    if not _BACKFILL_DONE:
        _BACKFILL_DONE = True
        import threading
        t = threading.Thread(target=backfill_sqlite_to_mongo, daemon=True, name="BillingMongoBackfill")
        t.start()

# Automatically trigger safe backfill on first load
ensure_backfill()
