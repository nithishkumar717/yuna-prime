import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import time
import pytz
from typing import Optional, Union, Tuple, List, Dict

from utils.Tools import send_antinuke_log, send_antinuke_dm_report
from core.cache.security_cache import security_cache
from core.cache.audit_ratelimit import guarded_audit_fetch
from core.database.connection_pool import db_pool
from core.metrics.security_metrics import security_metrics
from security.authorization.dangerous_permissions import is_dangerous_role
from core.antinuke_v2.router import v2_engine_router, EngineMode


class AntiBotAdd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 10-minute rolling window rate tracker: {(guild_id, user_id): [timestamps]}
        self._rolling_window: dict[tuple[int, int], list[float]] = {}
        self._rolling_window_seconds: float = 600.0  # 10 Minutes
        self.bot_protection_loop.start()

    def cog_unload(self):
        self.bot_protection_loop.cancel()

    @tasks.loop(minutes=5)
    async def bot_protection_loop(self):
        """
        Periodic Bot Security Audit Loop (Every 5 Minutes).
        Audits member list against trusted bot database and purges unauthorized bots.
        """
        try:
            for guild in self.bot.guilds:
                if not guild or not guild.me or not (guild.me.guild_permissions.kick_members or guild.me.guild_permissions.ban_members):
                    continue

                # 1. Check: Is Bot Protection EXPLICITLY enabled for this guild?
                cfg = await self.get_bot_protection_config(guild.id)
                if not cfg["enabled"] or not cfg.get("auto_sweep", True):
                    continue

                # 2. Chunk members if not loaded yet
                if len(guild.members) < 2:
                    try:
                        await guild.chunk()
                    except Exception:
                        pass

                other_bots = [m for m in guild.members if m.bot and m.id != self.bot.user.id]
                if not other_bots:
                    continue

                # 3. Perform periodic audit sweep
                await self.purge_unwhitelisted_bots(guild, cfg=cfg)
                # Rate-limit safety: 500ms pause between guilds
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[PERIODIC BOT AUDIT LOOP ERROR] {e}")

    @bot_protection_loop.before_loop
    async def before_bot_protection_loop(self):
        await self.bot.wait_until_ready()

    def record_bot_add_event(self, guild_id: int, user_id: int) -> int:
        """
        Records a bot addition event in the 10-minute rolling window.
        Returns the number of bot additions by this user within the rolling window.
        """
        now = time.time()
        cutoff = now - self._rolling_window_seconds
        key = (guild_id, user_id)
        history = self._rolling_window.get(key, [])
        # Evict events outside rolling window
        history = [t for t in history if t > cutoff]
        history.append(now)
        self._rolling_window[key] = history
        return len(history)

    async def is_bot_protection_active(self, guild_id: int) -> bool:
        if guild_id not in security_cache._loaded_guilds:
            await security_cache.warm_guild(guild_id)

        # 1. Zero-Latency Security Cache lookup
        if guild_id in security_cache._loaded_guilds:
            return security_cache.is_bot_protection_active(guild_id)

        # 2. SQLite direct read fallback
        try:
            row = await db_pool.fetch_one(
                'db/anti.db',
                "SELECT status FROM bot_protection WHERE guild_id = ?",
                (guild_id,)
            )
            if row is not None:
                return bool(str(row[0]).lower() in ("1", "true", "on"))
        except Exception:
            pass

        # 3. Settings Manager fallback
        from utils.settings_manager import get_guild_setting
        cfg = get_guild_setting(guild_id, "botprotection", None) or get_guild_setting(guild_id, "bot_protection", False)
        if isinstance(cfg, dict):
            return bool(cfg.get("enabled", False))
        return bool(cfg in (1, "1", True, "true", "on"))

    async def get_bot_protection_config(self, guild_id: int) -> dict:
        """
        Retrieves full Bot Protection policy:
        - enabled: bool
        - bot_punishment: 'ban' or 'kick' (Instant Kick / Ban)
        - inviter_punishment: 'ban', 'kick', or 'demote' (Ban, Kick, or Demote)
        - second_offense_ban: bool
        - auto_sweep: bool
        """
        config = {
            "enabled": False,
            "bot_punishment": "ban",
            "inviter_punishment": "ban",
            "second_offense_ban": True,
            "auto_sweep": True
        }

        # 1. Zero-Latency cache status
        if guild_id in security_cache._loaded_guilds:
            config["enabled"] = security_cache.is_bot_protection_active(guild_id)

        # 2. SQLite lookup
        try:
            row = await db_pool.fetch_one(
                'db/anti.db',
                "SELECT status, action, second_offense_ban, auto_sweep FROM bot_protection WHERE guild_id = ?",
                (guild_id,)
            )
            if row is not None:
                config["enabled"] = bool(str(row[0]).lower() in ("1", "true", "on"))
                action_str = str(row[1] or "BAN_BOT_AND_INVITER").upper()

                # Bot Punishment: Instant Kick / Ban
                if action_str.startswith("KICK_BOT") or action_str == "KICK":
                    config["bot_punishment"] = "kick"
                else:
                    config["bot_punishment"] = "ban"

                # Inviter Punishment: Ban, Kick, or Demote
                if "DEMOTE" in action_str:
                    config["inviter_punishment"] = "demote"
                elif "KICK_INVITER" in action_str or action_str == "KICK_BOT_AND_INVITER":
                    config["inviter_punishment"] = "kick"
                elif action_str in ("KICK_BOT", "BAN_BOT"):
                    config["inviter_punishment"] = "none"
                else:
                    config["inviter_punishment"] = "ban"

                if row[2] is not None:
                    config["second_offense_ban"] = bool(str(row[2]).lower() in ("1", "true", "on"))
                if row[3] is not None:
                    config["auto_sweep"] = bool(str(row[3]).lower() in ("1", "true", "on"))
                return config
        except Exception:
            pass

        # 3. Settings manager fallback
        from utils.settings_manager import get_guild_setting
        cfg = get_guild_setting(guild_id, "botprotection", None) or get_guild_setting(guild_id, "bot_protection", {})
        if isinstance(cfg, dict):
            config["enabled"] = bool(cfg.get("enabled", config["enabled"]))
            action_str = str(cfg.get("action", cfg.get("actionOnUnauthorized", "BAN_BOT_AND_INVITER"))).upper()
            if action_str.startswith("KICK_BOT") or action_str == "KICK":
                config["bot_punishment"] = "kick"
            else:
                config["bot_punishment"] = "ban"

            if "DEMOTE" in action_str:
                config["inviter_punishment"] = "demote"
            elif "KICK_INVITER" in action_str or action_str == "KICK_BOT_AND_INVITER":
                config["inviter_punishment"] = "kick"
            elif action_str in ("KICK_BOT", "BAN_BOT"):
                config["inviter_punishment"] = "none"
            else:
                config["inviter_punishment"] = "ban"

            config["second_offense_ban"] = bool(cfg.get("secondOffenseInstantBan", True))
            config["auto_sweep"] = bool(cfg.get("autoSweepEnabled", True))
        elif cfg in (1, "1", True, "true", "on"):
            config["enabled"] = True

        return config

    async def get_bot_kick_count(self, guild_id: int, bot_id: int) -> int:
        try:
            row = await db_pool.fetch_one(
                'db/anti.db',
                "SELECT kick_count FROM bot_kick_history WHERE guild_id = ? AND bot_id = ?",
                (guild_id, bot_id)
            )
            return row[0] if row else 0
        except Exception:
            return 0

    async def increment_bot_kick_count(self, guild_id: int, bot_id: int):
        try:
            await db_pool.execute(
                'db/anti.db',
                '''
                INSERT INTO bot_kick_history (guild_id, bot_id, kick_count)
                VALUES (?, ?, 1)
                ON CONFLICT(guild_id, bot_id) DO UPDATE SET kick_count = kick_count + 1
                ''',
                (guild_id, bot_id)
            )
        except Exception:
            pass

    async def is_bot_whitelisted(self, guild_id: int, bot_id: int) -> bool:
        from utils.config import SIBLING_BOT_IDS
        if bot_id == self.bot.user.id or bot_id in SIBLING_BOT_IDS:
            return True
        if guild_id not in security_cache._loaded_guilds:
            await security_cache.warm_guild(guild_id)
        return security_cache.is_bot_whitelisted(guild_id, bot_id)


    async def check_executor_permissions(self, guild, executor):
        if not guild or not executor:
            return True

        if security_cache.is_immune(guild, executor):
            return True

        try:
            if await security_cache.check_executor_permission(guild, executor, "botadd"):
                return True
        except Exception:
            pass

        # Check Administrator permission on resolved Member
        member = executor if hasattr(executor, 'guild_permissions') else guild.get_member(executor.id)
        if member and hasattr(member, 'guild_permissions') and member.guild_permissions.administrator:
            return True

        return False

    async def fetch_audit_logs(self, guild, action, target_id=None, max_retries=2):
        return await guarded_audit_fetch(guild, action, target_id, max_retries)

    async def demote_offender(self, guild: discord.Guild, member: discord.Member, reason: str) -> bool:
        """
        Demotes an unauthorized staff member by stripping all dangerous administrative roles.
        Protects the server without banning the member.
        """
        if not guild or not member or not hasattr(member, 'roles'):
            return False

        if not guild.me.guild_permissions.manage_roles:
            return False

        roles_to_strip = [
            r for r in member.roles
            if is_dangerous_role(r) and r < guild.me.top_role and not r.is_default()
        ]
        if not roles_to_strip:
            return True

        try:
            await member.remove_roles(*roles_to_strip, reason=f"[Anti-Nuke] {reason}")
            return True
        except Exception as e:
            print(f"[DEMOTE OFFENDER ERROR] {e}")
            return False

    async def punish_inviter(
        self,
        guild: discord.Guild,
        executor: Union[discord.Member, discord.User],
        bot_name: str,
        punishment: str = "ban"
    ) -> tuple[bool, str]:
        """
        Executes configured inviter punishment: Ban, Kick, or Demote.
        """
        if not executor or security_cache.is_immune(guild, executor):
            return False, "Inviter Immune"

        resolved_member = executor if isinstance(executor, discord.Member) else guild.get_member(executor.id)
        p_lower = str(punishment).lower().strip()

        if p_lower == "demote":
            if resolved_member:
                success = await self.demote_offender(
                    guild, resolved_member, f"Demoted for inviting unauthorized bot ({bot_name})"
                )
                if success:
                    return True, "Demoted Inviter (Stripped Dangerous Roles)"
            # Fallback to kick if demotion could not be applied
            success = await self.instant_kick(
                guild, executor, f"Invited unauthorized rogue bot ({bot_name})"
            )
            return success, "Kicked Inviter (Demote Fallback)"

        elif p_lower == "kick":
            if resolved_member:
                await self.demote_offender(guild, resolved_member, "Stripping roles before kick")
            success = await self.instant_kick(
                guild, executor, f"Invited unauthorized rogue bot ({bot_name})"
            )
            return success, "Kicked Inviter"

        elif p_lower == "none":
            return False, "No Action on Inviter"

        else:  # Default: Ban
            success = await self.instant_ban(
                guild, executor, f"Invited Non-Whitelisted Rogue Bot ({bot_name})"
            )
            return success, "Banned Inviter"

    @commands.Cog.listener()
    async def on_member_join(self, member):
        from utils.config import SIBLING_BOT_IDS
        if not member.bot or member.id == self.bot.user.id or member.id in SIBLING_BOT_IDS:
            return


        guild = member.guild
        if not guild:
            return

        # High-Vigilance Probation: Enroll joining bot into new_bots surveillance
        try:
            j_ts = member.joined_at.timestamp() if getattr(member, "joined_at", None) else time.time()
            v2_engine_router.coordinator.state_store.record_new_bot(guild.id, member.id, j_ts)
        except Exception:
            pass

        if not guild.me or not (guild.me.guild_permissions.kick_members or guild.me.guild_permissions.ban_members):
            return

        # Stage 8: V2 Engine Router (legacy | shadow | v2)
        if v2_engine_router.get_engine_mode(guild.id) == EngineMode.V2:
            state = v2_engine_router.coordinator.state_store.get_guild_config(guild.id)
            if state.antinuke_enabled and state.is_action_enabled("botadd"):
                await v2_engine_router.handle_v2_bot_add(member)
                return

        trace = security_metrics.create_trace(
            event_type="bot_add",
            guild_id=guild.id,
            processing_path="entity_listener"
        )
        trace.record_stage("started")

        # Check if Bot Protection or Anti Bot Add action is active for this server
        cfg = await self.get_bot_protection_config(guild.id)
        is_action_on = security_cache.is_action_enabled(guild.id, "antiBotAdd")
        trace.record_stage("policy_checked")

        if v2_engine_router.get_engine_mode(guild.id) != EngineMode.LEGACY and (cfg["enabled"] or is_action_on):
            await v2_engine_router.handle_v2_bot_add(member)
            return

        if not cfg["enabled"] and not is_action_on:
            logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.bot_add, member.id)
            executor = logs.user if logs else None
            exec_name = getattr(executor, 'name', 'Staff / Integration')
            asyncio.create_task(send_antinuke_dm_report(
                guild=guild,
                event_type="BOT ADDED",
                executor=executor or member,
                target=member,
                is_authorized=True,
                punishment="None",
                reason="Bot Added to Server",
                explanation=f"A new bot ({member.name}) was integrated into the server by {exec_name}."
            ))
            trace.finish(result="skipped_disabled")
            return

        # 1. Check if the joining bot is in whitelisted_bots
        is_wl_bot = await self.is_bot_whitelisted(guild.id, member.id)
        if is_wl_bot:
            logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.bot_add, member.id)
            executor = logs.user if logs else None
            exec_name = getattr(executor, 'name', 'Whitelisted')
            asyncio.create_task(send_antinuke_dm_report(
                guild=guild,
                event_type="BOT ADDED (WHITELISTED)",
                executor=executor or member,
                target=member,
                is_authorized=True,
                punishment="None",
                reason="Whitelisted Bot Added",
                explanation=f"Whitelisted bot ({member.name}) was integrated into the server."
            ))
            trace.finish(result="whitelisted_bot")
            return  # Whitelisted Bot is safely allowed to join!

        # 2. Lookup inviter FIRST to respect Whitelisted Roles, Whitelisted Members, and Server Owners
        trace.record_stage("audit_attribution_started")
        logs = await self.fetch_audit_logs(guild, discord.AuditLogAction.bot_add, member.id)
        trace.record_stage("audit_attribution_completed")
        executor = logs.user if logs else None

        if executor:
            is_allowed = await self.check_executor_permissions(guild, executor)
            if is_allowed:
                # Inviter holds a Whitelisted Role, is a Whitelisted Member, or is Server Owner!
                # Authoritative dispatch via send_antinuke_log (handles audit log & DM report)
                asyncio.create_task(send_antinuke_log(
                    guild,
                    "Anti Bot Add • Authorized Bot Addition",
                    executor,
                    "Allowed Bot Addition (Whitelisted Staff)",
                    target=member,
                    details=f"Bot: {member.name} ({member.id}) | Invited by Whitelisted User/Role: {executor.mention}"
                ))
                trace.finish(result="authorized_executor")
                return

        # 3. Inviter is UNAUTHORIZED or Rogue!
        trace.record_stage("threat_decision_completed")
        executor_id = executor.id if executor else member.id
        rolling_count = self.record_bot_add_event(guild.id, executor_id)

        # 4. Priority #1: Punish Inviter (The Offender) FIRST before taking bot action
        trace.record_stage("containment_dispatched")
        inviter_punished = False
        inviter_action_label = ""
        punish_mode = "ban" if rolling_count > 1 else cfg["inviter_punishment"]
        if executor and not security_cache.is_immune(guild, executor):
            inviter_punished, inviter_action_label = await self.punish_inviter(
                guild, executor, member.name, punishment=punish_mode
            )

        # 5. Determine Bot Punishment: Instant Kick / Ban
        prev_kicks = await self.get_bot_kick_count(guild.id, member.id)
        bot_action_taken = False
        action_title = ""

        # Instant Kick / Ban logic:
        # If bot_punishment is 'ban' OR repeat offense (second_offense_ban and prev_kicks >= 1) OR fast rolling window rate > 1:
        should_ban_bot = (cfg["bot_punishment"] == "ban") or (cfg["second_offense_ban"] and prev_kicks >= 1) or (rolling_count > 1)

        if should_ban_bot:
            bot_action_taken = await self.instant_ban(
                guild, member, f"Unauthorized Rogue Bot ({member.name}) - Instant Ban"
            )
            action_title = "Instant Banned Rogue Bot"
        else:
            bot_action_taken = await self.instant_kick(
                guild, member, f"Unauthorized Rogue Bot ({member.name}) - Instant Kick"
            )
            await self.increment_bot_kick_count(guild.id, member.id)
            action_title = "Instant Kicked Rogue Bot"

        trace.record_stage("containment_completed")

        # 6. Compose action summary message
        if bot_action_taken and inviter_punished:
            action_msg = f"{inviter_action_label} & {action_title}"
        elif inviter_punished:
            action_msg = f"{inviter_action_label} & Failed Bot Action"
        elif bot_action_taken:
            action_msg = action_title
        else:
            action_msg = "Action Failed (Permission / Hierarchy Issue)"

        # 7. Authoritatively send security log (send_antinuke_log internally dispatches DM report)
        exec_display = executor if executor else member
        rolling_msg = f" | Rolling Window Adds: #{rolling_count} in 10m" if rolling_count > 1 else ""
        asyncio.create_task(send_antinuke_log(
            guild,
            "Anti Bot Add • Rogue Bot Defense",
            exec_display,
            action_msg,
            target=member,
            details=f"Rogue Bot: {member.name} ({member.id}) | Offense Count: #{prev_kicks + 1}{rolling_msg} | Inviter: {executor.mention if executor else 'Unknown'}"
        ))
        await self.log_bot_incident(
            guild.id, member.id, member.name,
            executor.id if executor else 0,
            executor.name if executor else 'Unknown',
            action_msg
        )
        trace.finish(result="containment_dispatched" if (bot_action_taken or inviter_punished) else "containment_failed")

    async def purge_unwhitelisted_bots(self, guild, cfg: Optional[dict] = None) -> int:
        if not guild or not guild.me or not (guild.me.guild_permissions.kick_members or guild.me.guild_permissions.ban_members):
            return 0

        if cfg is None:
            cfg = await self.get_bot_protection_config(guild.id)

        from utils.config import SIBLING_BOT_IDS
        other_bots = [m for m in guild.members if m.bot and m.id != self.bot.user.id and m.id not in SIBLING_BOT_IDS]
        if not other_bots:
            return 0


        # Fix #15: Use in-memory security_cache instead of a DB query (zero I/O)
        whitelisted_bot_ids = security_cache.get_whitelisted_bots(guild.id)
        if not whitelisted_bot_ids:
            # Cache might be empty on first boot — fall back to DB and warm the cache
            try:
                rows = await db_pool.fetch_all(
                    'db/anti.db',
                    "SELECT bot_id FROM whitelisted_bots WHERE guild_id = ?",
                    (guild.id,)
                )
                whitelisted_bot_ids = {r[0] for r in rows if r[0]}
            except Exception:
                pass

        bots_to_purge = [b for b in other_bots if b.id not in whitelisted_bot_ids]
        if not bots_to_purge:
            return 0

        # Fix #8: Batch-fetch ALL kick counts for this guild in ONE query (eliminates N+1)
        kick_counts: dict[int, int] = {}
        try:
            bot_ids_in = ",".join(str(int(b.id)) for b in bots_to_purge)
            rows = await db_pool.fetch_all(
                'db/anti.db',
                f"SELECT bot_id, kick_count FROM bot_kick_history WHERE guild_id = ? AND bot_id IN ({bot_ids_in})",
                (guild.id,)
            )
            for row in rows:
                kick_counts[row[0]] = row[1]
        except Exception:
            pass

        kicked_count = 0
        banned_count = 0
        for bot_member in bots_to_purge:
            prev_kicks = kick_counts.get(bot_member.id, 0)
            should_ban = (cfg["bot_punishment"] == "ban") or (cfg["second_offense_ban"] and prev_kicks >= 1)
            if should_ban:
                # Instant Ban
                banned = await self.instant_ban(
                    guild, bot_member, f"Periodic Bot Audit - Instant Ban Unwhitelisted Bot ({bot_member.name})"
                )
                if banned:
                    banned_count += 1
                    await self.log_bot_incident(guild.id, bot_member.id, bot_member.name, 0, "Periodic Audit", "Instant Ban Bot")
            else:
                # Instant Kick
                kicked = await self.instant_kick(
                    guild, bot_member, f"Periodic Bot Audit - Instant Kick Unwhitelisted Bot ({bot_member.name})"
                )
                if kicked:
                    kicked_count += 1
                    await self.increment_bot_kick_count(guild.id, bot_member.id)
                    await self.log_bot_incident(guild.id, bot_member.id, bot_member.name, 0, "Periodic Audit", "Instant Kick Bot")
            # Rate-limit safety pause
            await asyncio.sleep(1.0)

        total_actions = kicked_count + banned_count
        if total_actions > 0:
            asyncio.create_task(send_antinuke_log(
                guild,
                "Bot Protection • Periodic Bot Audit",
                self.bot.user,
                f"Audit Purged {total_actions} Unwhitelisted Bot(s) ({kicked_count} Kicked, {banned_count} Banned)",
                details=f"Periodic audit checked {len(bots_to_purge)} non-whitelisted bot(s): {kicked_count} kicked (Instant Kick), {banned_count} banned (Instant Ban)."
            ))
        return total_actions

    @commands.command(name="bpaudit", aliases=["botaudit", "auditbots"])
    @commands.has_permissions(administrator=True)
    async def bpaudit_command(self, ctx: commands.Context):
        """
        Manually triggers a Periodic Bot Security Audit for this server.
        """
        cfg = await self.get_bot_protection_config(ctx.guild.id)
        msg = await ctx.send("<a:tick:1558726958802800660> **Initiating Periodic Bot Security Audit...** Scanning server bots against whitelist...")
        purged = await self.purge_unwhitelisted_bots(ctx.guild, cfg=cfg)
        if purged > 0:
            await msg.edit(content=f"<a:tick:1558726958802800660> **Bot Security Audit Complete:** Purged `{purged}` unauthorized bot(s).")
        else:
            await msg.edit(content="<a:tick:1558726958802800660> **Bot Security Audit Complete:** All bots in the server are authorized and whitelisted.")

    async def log_bot_incident(self, guild_id: int, bot_id: int, bot_name: str, inviter_id: int, inviter_name: str, action_taken: str):
        from datetime import datetime
        try:
            await db_pool.execute(
                'db/anti.db',
                '''
                INSERT INTO bot_incidents (guild_id, bot_id, bot_name, inviter_id, inviter_name, action_taken, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (guild_id, bot_id, bot_name, inviter_id, inviter_name, action_taken, datetime.now().strftime("%b %d, %H:%M"))
            )
        except Exception as e:
            print(f"[BOT INCIDENT LOG ERROR] {e}")

    async def instant_kick(self, guild, target, reason):
        for attempt in range(4):
            try:
                await guild.kick(target, reason=f"[Anti-Nuke] {reason}")
                return True
            except discord.Forbidden:
                return False
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(e.response.headers.get('Retry-After', 1.0)) if (hasattr(e, 'response') and e.response and 'Retry-After' in e.response.headers) else 1.0
                    await asyncio.sleep(retry_after + 0.2)
                else:
                    return False
            except Exception:
                return False
        return False

    async def instant_ban(self, guild, target, reason):
        from core.services.neutralizer import security_neutralizer
        return await security_neutralizer.neutralize_offender(guild, target, reason)
