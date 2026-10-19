"""
YUNA Ticket Transcript Generator.
Produces high-fidelity, secure, self-contained HTML transcripts styled after Discord dark mode.
All user inputs and messages are strictly escaped against XSS attacks.
"""

from __future__ import annotations
import html
import time
from typing import Dict, Any, List


def generate_ticket_html_transcript(
    guild_name: str,
    guild_icon: str,
    ticket: Dict[str, Any],
    messages: List[Dict[str, Any]],
    category_name: str = "General Support"
) -> str:
    """Renders a complete, standalone, responsive HTML transcript for a ticket."""
    ticket_num = ticket.get("ticket_number", 1)
    subject = html.escape(ticket.get("subject") or f"Ticket #{ticket_num:04d}")
    safe_guild_name = html.escape(guild_name or "Discord Server")
    safe_guild_icon = html.escape(guild_icon or "https://cdn.discordapp.com/embed/avatars/0.png")
    requester_name = html.escape(ticket.get("requester_name") or "User")
    requester_id = html.escape(str(ticket.get("requester_id") or ""))
    requester_avatar = html.escape(ticket.get("requester_avatar") or "https://cdn.discordapp.com/embed/avatars/0.png")
    assigned_staff = html.escape(ticket.get("assigned_staff_name") or "Unassigned")
    status = html.escape(ticket.get("status", "CLOSED"))
    priority = html.escape(ticket.get("priority", "NORMAL"))
    created_ts = ticket.get("created_at") or time.time()
    created_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(created_ts))
    closed_ts = ticket.get("closed_at") or time.time()
    closed_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(closed_ts)) if closed_ts else "Active"
    closed_by = html.escape(ticket.get("closed_by_name") or "System")
    closed_reason = html.escape(ticket.get("closed_reason") or "No reason provided")
    safe_cat_name = html.escape(category_name or "General")

    # Priority color mapping
    priority_colors = {
        "LOW": "#57F287",
        "NORMAL": "#5865F2",
        "HIGH": "#FEE75C",
        "URGENT": "#ED4245"
    }
    p_color = priority_colors.get(priority.upper(), "#5865F2")

    # Form Responses section
    form_responses = ticket.get("form_responses") or []
    form_html = ""
    if form_responses and isinstance(form_responses, list):
        form_items = ""
        for item in form_responses:
            q = html.escape(str(item.get("question") or item.get("label") or "Question"))
            a = html.escape(str(item.get("answer") or item.get("value") or "No answer"))
            form_items += f"""
                <div class="form-item">
                    <span class="form-q">{q}</span>
                    <span class="form-a">{a}</span>
                </div>
            """
        form_html = f"""
            <div class="transcript-section form-section">
                <div class="section-title">📋 Intake Form Responses</div>
                <div class="form-grid">{form_items}</div>
            </div>
        """

    # Messages rendering
    rendered_messages = ""
    for msg in messages:
        author_name = html.escape(msg.get("author_name") or "Unknown")
        author_avatar = html.escape(msg.get("author_avatar") or "https://cdn.discordapp.com/embed/avatars/0.png")
        is_staff = bool(msg.get("is_staff"))
        is_dash = bool(msg.get("is_dashboard"))
        is_note = bool(msg.get("is_internal_note"))
        raw_content = msg.get("content") or ""
        escaped_content = html.escape(raw_content).replace("\n", "<br>")
        msg_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(msg.get("created_at") or time.time()))

        badge = ""
        row_extra_class = ""
        if is_note:
            badge = '<span class="badge badge-note">INTERNAL NOTE</span>'
            row_extra_class = " message-note"
        elif is_dash:
            badge = '<span class="badge badge-staff">DASHBOARD</span>'
        elif is_staff:
            badge = '<span class="badge badge-staff">STAFF</span>'

        # Attachments
        attach_html = ""
        attachments = msg.get("attachments") or []
        if attachments and isinstance(attachments, list):
            for att in attachments:
                url = html.escape(str(att.get("url") or ""))
                filename = html.escape(str(att.get("filename") or "Attachment"))
                is_img = any(url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"])
                if is_img:
                    attach_html += f'<div class="msg-img"><a href="{url}" target="_blank"><img src="{url}" alt="{filename}" loading="lazy"/></a></div>'
                else:
                    attach_html += f'<div class="msg-file"><a href="{url}" target="_blank">📎 {filename}</a></div>'

        rendered_messages += f"""
            <div class="message-row{row_extra_class}">
                <img class="avatar" src="{author_avatar}" alt="{author_name}" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'" />
                <div class="msg-body">
                    <div class="msg-header">
                        <span class="author-name">{author_name}</span>
                        {badge}
                        <span class="timestamp">{msg_time}</span>
                    </div>
                    <div class="msg-text">{escaped_content}</div>
                    {attach_html}
                </div>
            </div>
        """

    if not rendered_messages:
        rendered_messages = '<div class="no-messages">No messages recorded in this ticket.</div>'

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcript #{ticket_num:04d} - {subject}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: #1e1f22;
            color: #dbdee1;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            padding: 24px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background-color: #2b2d31;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #383a40;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }}
        .header {{
            background: linear-gradient(135deg, #232428 0%, #1e1f22 100%);
            padding: 24px;
            border-bottom: 1px solid #383a40;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .guild-info {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .guild-icon {{
            width: 52px;
            height: 52px;
            border-radius: 14px;
            object-fit: cover;
            border: 2px solid #5865F2;
        }}
        .guild-title {{
            font-size: 18px;
            font-weight: 700;
            color: #f2f3f5;
        }}
        .guild-subtitle {{
            font-size: 12px;
            color: #949ba4;
        }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            background: rgba(88, 101, 242, 0.15);
            color: #5865F2;
            border: 1px solid rgba(88, 101, 242, 0.3);
        }}
        .status-CLOSED {{
            background: rgba(237, 66, 69, 0.15);
            color: #ed4245;
            border-color: rgba(237, 66, 69, 0.3);
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            padding: 20px 24px;
            background-color: #232428;
            border-bottom: 1px solid #383a40;
        }}
        .meta-card {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .meta-label {{
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 700;
            color: #949ba4;
            letter-spacing: 0.5px;
        }}
        .meta-val {{
            font-size: 13px;
            color: #f2f3f5;
            font-weight: 500;
        }}
        .form-section {{
            padding: 20px 24px;
            background-color: #2b2d31;
            border-bottom: 1px solid #383a40;
        }}
        .section-title {{
            font-size: 13px;
            font-weight: 700;
            color: #f2f3f5;
            margin-bottom: 12px;
        }}
        .form-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 12px;
        }}
        .form-item {{
            background-color: #232428;
            padding: 10px 14px;
            border-radius: 8px;
            border: 1px solid #383a40;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .form-q {{
            font-size: 11px;
            font-weight: 700;
            color: #b5bac1;
        }}
        .form-a {{
            font-size: 13px;
            color: #f2f3f5;
        }}
        .messages-container {{
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .message-row {{
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 6px 8px;
            border-radius: 8px;
            transition: background 0.15s;
        }}
        .message-row:hover {{
            background-color: #2e3035;
        }}
        .message-note {{
            background-color: rgba(254, 231, 92, 0.06);
            border-left: 3px solid #fee75c;
        }}
        .avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
            flex-shrink: 0;
        }}
        .msg-body {{
            flex: 1;
            min-width: 0;
        }}
        .msg-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }}
        .author-name {{
            font-weight: 600;
            color: #f2f3f5;
            font-size: 14px;
        }}
        .badge {{
            font-size: 9px;
            font-weight: 800;
            padding: 1px 5px;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        .badge-staff {{
            background: #5865F2;
            color: white;
        }}
        .badge-note {{
            background: #fee75c;
            color: #111;
        }}
        .timestamp {{
            font-size: 11px;
            color: #949ba4;
        }}
        .msg-text {{
            word-break: break-word;
            white-space: pre-wrap;
            color: #dbdee1;
        }}
        .msg-img img {{
            max-width: 100%;
            max-height: 350px;
            border-radius: 8px;
            margin-top: 8px;
            border: 1px solid #383a40;
        }}
        .msg-file {{
            margin-top: 6px;
        }}
        .msg-file a {{
            color: #00a8fc;
            text-decoration: none;
            font-size: 13px;
        }}
        .msg-file a:hover {{
            text-decoration: underline;
        }}
        .no-messages {{
            text-align: center;
            padding: 40px 0;
            color: #949ba4;
            font-style: italic;
        }}
        .footer {{
            padding: 16px 24px;
            background-color: #232428;
            border-top: 1px solid #383a40;
            text-align: center;
            font-size: 12px;
            color: #949ba4;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="guild-info">
                <img class="guild-icon" src="{safe_guild_icon}" alt="{safe_guild_name}" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'" />
                <div>
                    <h1 class="guild-title">{safe_guild_name}</h1>
                    <div class="guild-subtitle">Support System Transcript • #{ticket_num:04d}</div>
                </div>
            </div>
            <div class="status-badge status-{status}">{status}</div>
        </header>

        <section class="meta-grid">
            <div class="meta-card">
                <span class="meta-label">Ticket ID</span>
                <span class="meta-val">#{ticket_num:04d}</span>
            </div>
            <div class="meta-card">
                <span class="meta-label">Category</span>
                <span class="meta-val">{safe_cat_name}</span>
            </div>
            <div class="meta-card">
                <span class="meta-label">Priority</span>
                <span class="meta-val" style="color: {p_color}; font-weight: 700;">{priority}</span>
            </div>
            <div class="meta-card">
                <span class="meta-label">Requester</span>
                <span class="meta-val">{requester_name} ({requester_id})</span>
            </div>
            <div class="meta-card">
                <span class="meta-label">Claimed By</span>
                <span class="meta-val">{assigned_staff}</span>
            </div>
            <div class="meta-card">
                <span class="meta-label">Created</span>
                <span class="meta-val">{created_str}</span>
            </div>
            <div class="meta-card">
                <span class="meta-label">Closed</span>
                <span class="meta-val">{closed_str}</span>
            </div>
            <div class="meta-card">
                <span class="meta-label">Closed By</span>
                <span class="meta-val">{closed_by}</span>
            </div>
        </section>

        {form_html}

        <main class="messages-container">
            <div class="section-title">💬 Message History ({len(messages)} messages)</div>
            {rendered_messages}
        </main>

        <footer class="footer">
            🌸 Generated by YUNA Tickets Engine • Exported at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}
        </footer>
    </div>
</body>
</html>"""
    return html_doc
