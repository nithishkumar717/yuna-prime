import discord
import aiosqlite
import asyncio
from datetime import timedelta
import re
from typing import Optional
from utils.Tools import parse_duration_string
from core.logging.log_aggregator import log_aggregator


async def get_threshold(guild_id: int, event_name: str, default_val: int = 5) -> int:
    """Fetches custom threshold/limit integer for AutoMod event from database."""
    try:
        async with aiosqlite.connect("db/automod.db") as db:
            async with db.execute("SELECT threshold FROM automod_thresholds WHERE guild_id = ? AND event = ?", (guild_id, event_name)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] is not None:
                    return int(row[0])
    except Exception:
        pass
    return default_val


async def get_custom_warn_message(guild_id: int, event_name: str) -> Optional[str]:
    """Fetches custom warning message template for AutoMod event from database."""
    try:
        async with aiosqlite.connect("db/automod.db") as db:
            async with db.execute("SELECT message FROM automod_warn_messages WHERE guild_id = ? AND event = ?", (guild_id, event_name)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] and str(row[0]).strip():
                    return str(row[0]).strip()
    except Exception:
        pass
    return None


async def get_punishment(guild_id: int, event_name: str) -> Optional[str]:
    """Fetches punishment action for AutoMod event from database."""
    try:
        async with aiosqlite.connect("db/automod.db") as db:
            async with db.execute("SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = ?", (guild_id, event_name)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return str(row[0]).strip()
    except Exception:
        pass
    return None


async def log_automod_action(guild: discord.Guild, user: discord.Member, channel: discord.TextChannel, event_name: str, action_taken: str, reason: str, bot: discord.Client):
    """Logs AutoMod enforcement action to database incident logs and logging channel."""
    # 1. Log incident to SQLite automod_incidents table for live dashboard
    try:
        async with aiosqlite.connect("db/automod.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    user_name TEXT,
                    rule_triggered TEXT,
                    action_taken TEXT,
                    channel_name TEXT,
                    timestamp TEXT
                )
            """)
            await db.execute("""
                INSERT INTO automod_incidents (guild_id, user_id, user_name, rule_triggered, action_taken, channel_name, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                guild.id,
                user.id,
                str(user),
                event_name,
                action_taken,
                f"#{channel.name}" if hasattr(channel, "name") else str(channel.id),
                discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            ))
            await db.commit()
    except Exception as ex:
        print(f"[AUTOMOD INCIDENT LOG ERROR] {ex}")

    # 2. Send log embed to designated automod_logging channel
    try:
        from core.database.connection_pool import db_pool
        lrow = await db_pool.fetch_one("db/automod.db", "SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
        if lrow and lrow[0]:
            log_ch = guild.get_channel(lrow[0])
            if log_ch:
                embed = discord.Embed(title=f"AutoMod Log: {event_name}", color=0xff0000)
                embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)
                embed.add_field(name="Action Taken", value=action_taken, inline=False)
                embed.add_field(name="Channel", value=channel.mention if hasattr(channel, "mention") else str(channel), inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"User ID: {user.id}")
                if getattr(user, "avatar", None):
                    embed.set_thumbnail(url=user.avatar.url)
                embed.timestamp = discord.utils.utcnow()
                from core.services.log_dispatcher import log_dispatcher
                log_dispatcher.enqueue_log(log_ch, embed)
    except Exception as ex:
        print(f"[AUTOMOD LOG CHANNEL ERROR] {ex}")

    # 3. Log to internal aggregator
    try:
        log_aggregator.log_event(
            guild_id=guild.id,
            action_type=f"AutoMod ({event_name}) - {action_taken}",
            executor=user,
            details=f"Channel: #{getattr(channel, 'name', channel.id)} | Reason: {reason}"
        )
    except Exception:
        pass


async def execute_automod_action(
    bot: discord.Client,
    guild: discord.Guild,
    user: discord.Member,
    channel: discord.TextChannel,
    message: Optional[discord.Message],
    event_name: str,
    reason: str = "AutoMod Rule Triggered"
):
    # Whitelist & Immunity Check
    from utils.config import GLOBAL_OWNER_IDS, PRIMARY_BOT_OWNER, SIBLING_BOT_IDS
    if not guild or not user or user.id in {guild.owner_id, bot.user.id} or user.id in SIBLING_BOT_IDS or user.id == PRIMARY_BOT_OWNER or user.id in GLOBAL_OWNER_IDS:
        return


    from core.cache.security_cache import security_cache
    try:
        if security_cache.is_whitelisted(guild.id, user.id) or security_cache.is_extra_owner(guild.id, user.id):
            return
        wl_roles = security_cache._whitelisted_roles.get(guild.id, set())
        if wl_roles and hasattr(user, "roles"):
            if any(r.id in wl_roles for r in user.roles):
                return
    except Exception:
        pass

    # 1. Delete offending message immediately if present
    if message:
        try:
            await message.delete()
        except Exception:
            pass

    punishment = await get_punishment(guild.id, event_name)
    if not punishment or str(punishment).strip().lower() in ("disabled", "none", "off", "0", ""):
        return

    pun_norm = str(punishment).strip().upper()
    action_taken = "Message Deleted"

    try:
        if "BAN" in pun_norm:
            try:
                await user.ban(reason=f"[AutoMod] {reason}", delete_message_days=1)
                action_taken = "Banned"
            except Exception as e:
                action_taken = f"Ban Failed ({e})"

        elif "KICK" in pun_norm:
            try:
                await user.kick(reason=f"[AutoMod] {reason}")
                action_taken = "Kicked"
            except Exception as e:
                action_taken = f"Kick Failed ({e})"

        elif "QUARANTINE" in pun_norm:
            try:
                roles_to_remove = [
                    r for r in user.roles 
                    if r.name != "@everyone" and (
                        r.permissions.administrator or 
                        r.permissions.manage_guild or 
                        r.permissions.ban_members or 
                        r.permissions.kick_members
                    )
                ]
                if roles_to_remove:
                    await user.remove_roles(*roles_to_remove, reason=f"[AutoMod Quarantine] {reason}")
                timeout_until = discord.utils.utcnow() + timedelta(hours=24)
                await user.edit(timed_out_until=timeout_until, reason=f"[AutoMod Quarantine] {reason}")
                action_taken = "Quarantined & Stripped Administrative Roles"
            except Exception as e:
                action_taken = f"Quarantine Applied ({e})"

        elif "MUTE" in pun_norm or "TIMEOUT" in pun_norm:
            raw_str = str(punishment)
            from utils.Tools import parse_duration_string
            parsed = parse_duration_string(raw_str)
            if parsed:
                td, t_lbl = parsed
            else:
                dur_match = re.search(r'(\d+)\s*(m|min|mins|minutes|h|hr|hrs|hours|d|day|days|w|week|weeks)?', raw_str, re.IGNORECASE)
                if "28D" in pun_norm:
                    td, t_lbl = timedelta(days=28), "28 days"
                elif "1W" in pun_norm or "1 WEEK" in pun_norm or "7D" in pun_norm:
                    td, t_lbl = timedelta(days=7), "7 days (1 week)"
                elif "24H" in pun_norm or "1 DAY" in pun_norm:
                    td, t_lbl = timedelta(hours=24), "24 hours"
                elif dur_match:
                    val = int(dur_match.group(1))
                    unit = (dur_match.group(2) or "m").lower()
                    if "w" in unit:
                        td, t_lbl = timedelta(weeks=val), f"{val} week{'s' if val > 1 else ''}"
                    elif "d" in unit:
                        td, t_lbl = timedelta(days=val), f"{val} days"
                    elif "h" in unit:
                        td, t_lbl = timedelta(hours=val), f"{val} hours"
                    else:
                        td, t_lbl = timedelta(minutes=val), f"{val} minutes"
                else:
                    td, t_lbl = timedelta(minutes=7), "7 minutes"

            if td.total_seconds() > 2419200:
                td = timedelta(days=28)
                t_lbl = "28 days"

            try:
                timeout_until = discord.utils.utcnow() + td
                await user.edit(timed_out_until=timeout_until, reason=f"[AutoMod] {reason}")
                action_taken = f"Muted for {t_lbl}"
            except Exception as e:
                action_taken = f"Mute Failed ({e})"

        elif "WARN" in pun_norm:
            action_taken = "Warned"

        else:
            action_taken = "Message Deleted"
    except Exception as ex:
        print(f"[AUTOMOD PUNISHMENT EXECUTION ERROR] {ex}")

    # 2. Check for Custom Warning Message
    custom_msg = await get_custom_warn_message(guild.id, event_name)
    if custom_msg:
        formatted = custom_msg \
            .replace("{user}", user.mention) \
            .replace("{user.name}", user.name) \
            .replace("{username}", user.name) \
            .replace("{server}", guild.name) \
            .replace("{guild}", guild.name) \
            .replace("{rule}", event_name) \
            .replace("{event}", event_name) \
            .replace("{action}", action_taken)
        try:
            warn_sent = await channel.send(formatted)
            await warn_sent.delete(delay=10)
        except Exception:
            pass
    else:
        # Default embed notification
        try:
            simple_embed = discord.Embed(title=f"AutoMod: {event_name}", color=0xff0000)
            simple_embed.description = f"<a:tick:1558726958802800660> | {user.mention} has been **{action_taken}** for **{reason}.**"
            simple_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1294125691587006525.png")
            if bot.user and bot.user.avatar:
                simple_embed.set_footer(text="YUNA Security Engine • AutoMod Protection", icon_url=bot.user.avatar.url)
            warn_sent = await channel.send(embed=simple_embed)
            await warn_sent.delete(delay=10)
        except Exception:
            pass

    # 3. Log incident to database and logging channel
    await log_automod_action(guild, user, channel, event_name, action_taken, reason, bot)
