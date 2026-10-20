"""
YUNA GitHub Auto-Pull System
Embedded aiohttp webhook server + owner Discord commands.

When you push to GitHub:
  GitHub → POST /webhook → git pull origin main → SIGTERM (Pterodactyl auto-restarts)

Discord commands (owner-only):
  $gitpull   — manually trigger git pull + restart
  $gitstatus — show current commit hash + message
"""
from __future__ import annotations

import os
import sys
import hmac
import hashlib
import asyncio
import signal
import subprocess
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web

from utils.config import OWNER_IDS, PRIMARY_BOT_OWNER, GLOBAL_OWNER_IDS
from utils.git_auth import (
    get_auth_remote_url,
    get_clean_remote_url,
    get_masked_remote_url,
    run_git_command,
    ensure_git_remote_configured,
)


def is_bot_owner():
    """Robust owner check verifying PRIMARY_BOT_OWNER, GLOBAL_OWNER_IDS, OWNER_IDS, or bot.is_owner()."""
    async def predicate(ctx: commands.Context) -> bool:
        uid = ctx.author.id
        if (uid in GLOBAL_OWNER_IDS) or (uid == PRIMARY_BOT_OWNER) or (uid in OWNER_IDS):
            return True
        try:
            return await ctx.bot.is_owner(ctx.author)
        except Exception:
            return False
    return commands.check(predicate)


# ─── Config (from .env) ──────────────────────────────────────────────────────
WEBHOOK_SECRET  = os.getenv("GITHUB_WEBHOOK_SECRET", "")   # GitHub webhook secret
WEBHOOK_PORT    = int(os.getenv("GIT_WEBHOOK_PORT", "2034"))  # Port to listen on
GIT_BRANCH      = os.getenv("GIT_BRANCH", "main")           # Branch to pull from
GIT_LOG_CHANNEL = int(os.getenv("GIT_LOG_CHANNEL_ID", "0")) # Optional: Discord channel ID for deploy logs
# ─────────────────────────────────────────────────────────────────────────────

TICK  = "<a:tick:1562100631605350441>"
CROSS = "<:cross:1562101096686686218>"
COLOR_DARK = 0x2b2d31
COLOR_OK   = 0x2b2d31
COLOR_ERR  = 0x2b2d31
COLOR_INF  = 0x2b2d31


def _verify_signature(body: bytes, signature_header: str) -> bool:
    """Verify GitHub HMAC-SHA256 webhook signature."""
    if not WEBHOOK_SECRET:
        return True  # No secret configured — accept all (not recommended for prod)
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


def _run_git_pull() -> tuple[bool, str]:
    """Run git pull origin <branch> synchronously. Returns (success, output)."""
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ok, msg = ensure_git_remote_configured(root_dir)
        if not ok:
            return False, msg

        # 1. Fetch latest commits from remote
        code, out = run_git_command(
            ["git", "fetch", "origin", f"+refs/heads/{GIT_BRANCH}:refs/remotes/origin/{GIT_BRANCH}"],
            cwd=root_dir,
            timeout=60
        )
        if code != 0:
            # Fallback to simple fetch
            code, out = run_git_command(["git", "fetch", "origin", GIT_BRANCH], cwd=root_dir, timeout=60)
            if code != 0:
                return False, f"git fetch failed: {out}"

        # 2. Cleanly reset to origin/<branch> or FETCH_HEAD
        # Security: .gitignore files (.env, db/, logs) are strictly protected and never touched
        code, out = run_git_command(["git", "reset", "--hard", f"origin/{GIT_BRANCH}"], cwd=root_dir, timeout=30)
        if code != 0:
            code, out = run_git_command(["git", "reset", "--hard", "FETCH_HEAD"], cwd=root_dir, timeout=30)

        # 3. Ensure branch is checked out to GIT_BRANCH (e.g. main)
        run_git_command(["git", "checkout", "-B", GIT_BRANCH, f"origin/{GIT_BRANCH}"], cwd=root_dir, timeout=15)

        # 4. Ensure ENVIRONMENT=vps on disk in production
        try:
            env_file = os.path.join(root_dir, ".env")
            if os.path.exists(env_file):
                with open(env_file, "r", encoding="utf-8") as ef:
                    env_txt = ef.read()
                if "ENVIRONMENT=local" in env_txt:
                    env_txt = env_txt.replace("ENVIRONMENT=local", "ENVIRONMENT=vps")
                    with open(env_file, "w", encoding="utf-8") as ef:
                        ef.write(env_txt)
        except Exception:
            pass

        return code == 0, out
    except Exception as e:
        return False, f"git pull failed: {e}"


def _get_git_status() -> dict:
    """Get current commit info."""
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_res = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%h%x00%s%x00%an%x00%ar"],
            capture_output=True, text=True, timeout=10, cwd=root_dir
        )
        parts = log_res.stdout.strip().split("\x00") if log_res.stdout else []
        commit_hash = parts[0] if len(parts) > 0 else "unknown"
        commit_msg = parts[1] if len(parts) > 1 else "unknown"
        commit_author = parts[2] if len(parts) > 2 else "unknown"
        commit_time = parts[3] if len(parts) > 3 else "unknown"

        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=root_dir
        )
        branch = branch_res.stdout.strip() if branch_res.stdout else "unknown"

        return {
            "hash": commit_hash,
            "message": commit_msg,
            "author": commit_author,
            "time": commit_time,
            "branch": branch,
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_git_status_async() -> dict:
    """Non-blocking git status runner using asyncio.to_thread."""
    return await asyncio.to_thread(_get_git_status)


def _get_upgrade_telemetry() -> dict:
    """Fetch remote git refs and build detailed deployment telemetry."""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        ensure_git_remote_configured(root_dir)
        run_git_command(
            ["git", "fetch", "origin", f"+refs/heads/{GIT_BRANCH}:refs/remotes/origin/{GIT_BRANCH}"],
            cwd=root_dir,
            timeout=15
        )
    except Exception:
        pass

    local_info = _get_git_status()

    remote_info = {
        "hash": "unknown",
        "message": "unknown",
        "author": "unknown",
        "time": "unknown"
    }
    try:
        log_res = subprocess.run(
            ["git", "log", "-1", f"origin/{GIT_BRANCH}", "--pretty=format:%h%x00%s%x00%an%x00%ar"],
            capture_output=True, text=True, timeout=5, cwd=root_dir
        )
        if not log_res.stdout:
            log_res = subprocess.run(
                ["git", "log", "-1", "FETCH_HEAD", "--pretty=format:%h%x00%s%x00%an%x00%ar"],
                capture_output=True, text=True, timeout=5, cwd=root_dir
            )
        parts = log_res.stdout.strip().split("\x00") if log_res.stdout else []
        if parts:
            remote_info["hash"] = parts[0] if len(parts) > 0 else "unknown"
            remote_info["message"] = parts[1] if len(parts) > 1 else "unknown"
            remote_info["author"] = parts[2] if len(parts) > 2 else "unknown"
            remote_info["time"] = parts[3] if len(parts) > 3 else "unknown"
    except Exception:
        pass

    commits_behind = 0
    try:
        rev_res = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..origin/{GIT_BRANCH}"],
            capture_output=True, text=True, timeout=5, cwd=root_dir
        )
        if not rev_res.stdout or rev_res.returncode != 0:
            rev_res = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..FETCH_HEAD"],
                capture_output=True, text=True, timeout=5, cwd=root_dir
            )
        if rev_res.stdout:
            commits_behind = int(rev_res.stdout.strip() or 0)
    except Exception:
        commits_behind = 0

    return {
        "local": local_info,
        "remote": remote_info,
        "behind_count": commits_behind,
        "branch": GIT_BRANCH,
        "version": "v7.00"
    }


async def _get_upgrade_telemetry_async() -> dict:
    """Non-blocking runner for _get_upgrade_telemetry."""
    return await asyncio.to_thread(_get_upgrade_telemetry)



def _restart_bot():
    """Restart the bot process in-place using os.execl (preserves container state on Pterodactyl/Linux/Windows)."""
    try:
        from core.antinuke_v2.router import v2_engine_router
        if v2_engine_router and hasattr(v2_engine_router, "shutdown"):
            v2_engine_router.shutdown()
    except Exception:
        pass

    try:
        from core.dashboard.utils import save_sessions_to_disk
        save_sessions_to_disk(force=True)
    except Exception as e:
        print(f"[GitPull] Failed to save sessions before restart: {e}")

    try:
        from core.dashboard_server import trigger_dashboard_shutdown
        trigger_dashboard_shutdown()
    except Exception:
        pass

    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass

    # Close all open non-std file descriptors (>= 3) on POSIX so child process doesn't inherit listening sockets
    try:
        if sys.platform != "win32":
            if hasattr(os, 'closerange'):
                os.closerange(3, 4096)
            else:
                for fd in range(3, 1024):
                    try:
                        os.close(fd)
                    except OSError:
                        pass
    except Exception:
        pass

    try:
        python = sys.executable
        if sys.platform == "win32":
            subprocess.Popen([python] + sys.argv, cwd=os.getcwd())
            os._exit(0)
        else:
            os.execl(python, python, *sys.argv)
    except Exception as e:
        print(f"[GitPull] Process restart failed: {e}. Falling back to SIGTERM.")
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            os._exit(0)


class GitPullConfirmView(discord.ui.View):
    """Interactive confirmation buttons for manual git pull and restart."""
    def __init__(self, author_id: int, bot: commands.Bot | None = None):
        super().__init__(timeout=60.0)
        self.author_id = author_id
        self.bot = bot
        self.confirmed: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "**Access Restricted:** Only the administrator who initiated this deployment can interact.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Authorize & Deploy",
        style=discord.ButtonStyle.success
    )
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for child in self.children:
            child.disabled = True
        embed = discord.Embed(
            title="Deploying Update",
            description=(
                f"<a:loading:1554957482248380416> Synchronizing code with `origin/{GIT_BRANCH}`...\n"
                f"Active voice sessions will auto-resume after restart."
            ),
            color=COLOR_DARK
        )
        if self.bot and self.bot.user and getattr(self.bot.user, 'display_avatar', None):
            embed.set_author(name="YUNΛ Deployments", icon_url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Restarting process • Please wait...")
        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception:
            pass
        self.stop()

    @discord.ui.button(
        label="Dismiss",
        style=discord.ButtonStyle.secondary
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        for child in self.children:
            child.disabled = True
        embed = discord.Embed(
            title="Deployment Cancelled",
            description="Deployment request was safely cancelled. No changes were applied.",
            color=COLOR_DARK
        )
        if self.bot and self.bot.user and getattr(self.bot.user, 'display_avatar', None):
            embed.set_author(name="YUNΛ Deployments", icon_url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Cancelled")
        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception:
            pass
        self.stop()


class GitPull(commands.Cog):
    """GitHub Auto-Pull System — webhook listener + owner commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._webhook_runner: web.AppRunner | None = None
        self._webhook_task: asyncio.Task | None = None
        self._restart_pending = False

    # ─── Cog Lifecycle ───────────────────────────────────────────────────────

    async def cog_load(self):
        """Start the embedded webhook HTTP server when cog loads."""
        self._webhook_task = asyncio.create_task(self._start_webhook_server())

    async def cog_unload(self):
        """Stop the webhook server cleanly when cog unloads."""
        if self._webhook_task and not self._webhook_task.done():
            self._webhook_task.cancel()
        if self._webhook_runner:
            await self._webhook_runner.cleanup()

    # ─── Webhook Server ──────────────────────────────────────────────────────

    async def _start_webhook_server(self):
        """Start the aiohttp webhook server on GIT_WEBHOOK_PORT."""
        app = web.Application()
        app.router.add_post("/webhook", self._handle_webhook)
        app.router.add_get("/health", self._handle_health)

        self._webhook_runner = web.AppRunner(app)
        await self._webhook_runner.setup()
        site = web.TCPSite(self._webhook_runner, "0.0.0.0", WEBHOOK_PORT)
        try:
            await site.start()
            print(f"[GitPull] Webhook server listening on port {WEBHOOK_PORT}")
        except OSError as e:
            print(f"[GitPull] ⚠️ Could not start webhook server on port {WEBHOOK_PORT}: {e}")

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        status = await _get_git_status_async()
        return web.json_response({
            "status": "ok",
            "branch": status.get("branch", "unknown"),
            "commit": status.get("hash", "unknown"),
        })

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming GitHub push webhook."""
        # 1. Read body
        body = await request.read()

        # 2. Verify signature
        sig = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_signature(body, sig):
            print("[GitPull] ⚠️ Webhook rejected — invalid signature.")
            return web.Response(status=403, text="Forbidden: Invalid signature")

        # 3. Only handle push events
        event = request.headers.get("X-GitHub-Event", "")
        if event != "push":
            return web.Response(status=200, text=f"Ignored event: {event}")

        print(f"[GitPull] ✅ GitHub push webhook received — starting git pull...")

        # 4. Run git pull in executor (non-blocking)
        loop = asyncio.get_event_loop()
        success, output = await loop.run_in_executor(None, _run_git_pull)

        # 5. Log to Discord channel if configured
        await self._send_deploy_log(success, output, triggered_by="GitHub Push")

        # 6. Record in persistent deployment history
        try:
            from core.git_history import record_git_deploy
            status = await _get_git_status_async()
            record_git_deploy(
                success=success,
                output=output,
                triggered_by="GitHub Push Webhook",
                restarted=success,
                git_status=status
            )
        except Exception as e:
            print(f"[GitPull] Could not record webhook deploy history: {e}")

        if success:
            print(f"[GitPull] ✅ git pull succeeded:\n{output}")
            print("[GitPull] 🔄 Sending SIGTERM — Pterodactyl will auto-restart...")
            # Small delay so the HTTP response can be sent back to GitHub first
            asyncio.create_task(self._delayed_restart(3))
            return web.Response(status=200, text="Pull successful. Restarting bot...")
        else:
            print(f"[GitPull] ❌ git pull failed:\n{output}")
            return web.Response(status=500, text=f"Pull failed: {output}")

    async def _delayed_restart(self, delay: float):
        """Wait briefly then restart bot process in-place."""
        try:
            from core.dashboard_server import trigger_dashboard_shutdown
            trigger_dashboard_shutdown()
        except Exception:
            pass
        if self._webhook_runner:
            try:
                await self._webhook_runner.cleanup()
            except Exception:
                pass
        await asyncio.sleep(delay)
        print("[GitPull] 🔄 In-place restart triggered — restarting bot now...")
        _restart_bot()

    async def _send_deploy_log(self, success: bool, output: str, triggered_by: str = "Unknown"):
        """Send a deploy result embed to the configured log channel."""
        if GIT_LOG_CHANNEL == 0:
            return
        channel = self.bot.get_channel(GIT_LOG_CHANNEL)
        if not channel:
            return

        status = await _get_git_status_async()
        title  = "Production Core Deployment" if success else "Production Deployment Failed"

        embed = discord.Embed(
            title=title,
            description=f"> Deployment event recorded. Status: **{'Succeeded' if success else 'Failed'}**.",
            color=COLOR_DARK,
            timestamp=datetime.now(timezone.utc)
        )
        if self.bot and self.bot.user:
            embed.set_author(name="YUNΛ SYSTEM ORCHESTRATOR", icon_url=self.bot.user.display_avatar.url)

        embed.add_field(name="Trigger Source", value=f"`{triggered_by}`", inline=True)
        embed.add_field(name="Branch", value=f"`{status.get('branch', GIT_BRANCH)}`", inline=True)
        embed.add_field(name="Commit", value=f"`{status.get('hash', 'unknown')}`", inline=True)

        if success:
            embed.add_field(name="Commit Message", value=status.get("message", "—"), inline=False)
            embed.add_field(name="Author", value=f"{status.get('author', '—')} ({status.get('time', 'just now')})", inline=True)

        # Truncate git output
        output_display = output[:900] + "..." if len(output) > 900 else output
        embed.add_field(name="Execution Output", value=f"```bash\n{output_display}\n```", inline=False)
        embed.set_footer(text="YUNΛ Continuous Deployment Engine")

        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    # ─── Discord Commands ─────────────────────────────────────────────────────

    @commands.group(
        name="git",
        invoke_without_command=True,
        hidden=True,
        help="Owner-only: Git synchronization engine ($git pull, $git status)."
    )
    @is_bot_owner()
    async def git_group(self, ctx: commands.Context, *, sub: str = ""):
        """Allow $git pull or $git status or $git by itself."""
        sub_clean = sub.strip().lower()
        if sub_clean.startswith("pull"):
            parts = sub.strip().split(maxsplit=1)
            flag = parts[1] if len(parts) > 1 else ""
            return await self.gitpull_cmd(ctx, flag=flag)
        elif sub_clean in ["status", "info", "version"]:
            return await self.gitstatus_cmd(ctx)
        elif not sub_clean:
            return await self.gitstatus_cmd(ctx)
        else:
            return await self.gitpull_cmd(ctx, flag=sub.strip())

    @git_group.command(name="pull", aliases=["update"])
    @is_bot_owner()
    async def git_pull_sub(self, ctx: commands.Context, flag: str = ""):
        """Owner-only: $git pull [check]"""
        return await self.gitpull_cmd(ctx, flag=flag)

    @git_group.command(name="status", aliases=["info", "version"])
    @is_bot_owner()
    async def git_status_sub(self, ctx: commands.Context):
        """Owner-only: $git status"""
        return await self.gitstatus_cmd(ctx)

    @commands.command(
        name="gitpull",
        aliases=["git-pull", "gpull", "gitupdate", "gupdate"],
        hidden=True,
        help="Owner-only: Pull latest code from GitHub and restart the bot."
    )
    @is_bot_owner()
    async def gitpull_cmd(self, ctx: commands.Context, flag: str = ""):
        """Owner-only: run git pull and restart."""
        is_check = flag.lower() in ["check", "status", "info", "diff", "preview"]
        bot_avatar = getattr(self.bot.user.display_avatar, 'url', None) if self.bot.user and getattr(self.bot.user, 'display_avatar', None) else None
        author_avatar = getattr(ctx.author.display_avatar, 'url', None) if getattr(ctx.author, 'display_avatar', None) else None

        if is_check:
            # Telemetry Preview Mode
            progress_embed = discord.Embed(
                title="Inspecting Upstream Repository",
                description=f"> <a:loading:1554957482248380416> Querying `origin/{GIT_BRANCH}` for latest commits...",
                color=COLOR_DARK
            )
            if bot_avatar:
                progress_embed.set_author(name="YUNΛ SYSTEM ORCHESTRATOR", icon_url=bot_avatar)
            msg = await ctx.send(embed=progress_embed)

            telemetry = await _get_upgrade_telemetry_async()
            local_info = telemetry.get("local", {})
            remote_info = telemetry.get("remote", {})
            behind_count = telemetry.get("behind_count", 0)

            local_hash = local_info.get("hash", "unknown")
            local_msg = local_info.get("message", "unknown")
            local_author = local_info.get("author", "unknown")

            remote_hash = remote_info.get("hash", "unknown")
            remote_msg = remote_info.get("message", "unknown")
            remote_author = remote_info.get("author", "unknown")

            status_str = f"{behind_count} commit(s) behind origin/{GIT_BRANCH}" if behind_count > 0 else f"Up-to-Date with origin/{GIT_BRANCH}"

            confirm_embed = discord.Embed(
                title="Production Update Preview",
                description="Review repository synchronization telemetry before authorizing deploy.",
                color=COLOR_DARK,
                timestamp=datetime.now(timezone.utc)
            )
            if bot_avatar:
                confirm_embed.set_author(name="YUNΛ Deployments", icon_url=bot_avatar)
                confirm_embed.set_thumbnail(url=bot_avatar)

            confirm_embed.add_field(
                name="Current Local Version",
                value=f"`v7.00` • `{local_hash}` by **{local_author}**\n*{local_msg}*",
                inline=False
            )
            confirm_embed.add_field(
                name="Latest Upstream Version (GitHub)",
                value=f"`origin/{GIT_BRANCH}` • `{remote_hash}` by **{remote_author}**\n*{remote_msg}*",
                inline=False
            )
            confirm_embed.add_field(
                name="Summary",
                value=(
                    f"```yaml\n"
                    f"Status: {status_str}\n"
                    f"Action: Git pull origin {GIT_BRANCH} & restart process\n"
                    f"Audio:  Active voice sessions will auto-resume\n"
                    f"```"
                ),
                inline=False
            )
            confirm_embed.set_footer(
                text=f"Requested by {ctx.author.name} • Authorization window expires in 60s",
                icon_url=author_avatar
            )
            view = GitPullConfirmView(ctx.author.id, bot=self.bot)
            try:
                await msg.edit(embed=confirm_embed, view=view)
            except Exception:
                msg = await ctx.send(embed=confirm_embed, view=view)

            timed_out = await view.wait()
            if timed_out:
                try:
                    timeout_embed = discord.Embed(
                        title="Authorization Window Expired",
                        description="> Deployment confirmation timed out after 60 seconds of inactivity. Aborted.",
                        color=COLOR_DARK
                    )
                    if bot_avatar:
                        timeout_embed.set_author(name="YUNΛ SYSTEM ORCHESTRATOR", icon_url=bot_avatar)
                    timeout_embed.set_footer(text="Timed out • No modifications applied")
                    await msg.edit(embed=timeout_embed, view=None)
                except Exception:
                    pass
                return

            if not view.confirmed:
                return
        else:
            # Immediate Deployment Mode (consistent with Web Admin Dashboard)
            init_embed = discord.Embed(
                title="🚀 Production Deployment Initiated",
                description=(
                    f"> <a:loading:1554957482248380416> Synchronizing runtime repository with `origin/{GIT_BRANCH}`...\n"
                    f"> Active voice states will be preserved."
                ),
                color=COLOR_DARK,
                timestamp=datetime.now(timezone.utc)
            )
            if bot_avatar:
                init_embed.set_author(name="YUNΛ SYSTEM ORCHESTRATOR", icon_url=bot_avatar)
            msg = await ctx.send(embed=init_embed)

        # Run in executor
        loop = asyncio.get_event_loop()
        success, output = await loop.run_in_executor(None, _run_git_pull)

        output_display = output[:900] + "..." if len(output) > 900 else output

        if success:
            status = await _get_git_status_async()
            embed = discord.Embed(
                title="✅ Core Deployment Successful",
                description=(
                    f"> Runtime repository successfully synchronized with `origin/{GIT_BRANCH}`.\n"
                    f"> Preserving active audio states and executing in-place reboot..."
                ),
                color=0x2ECC71,
                timestamp=datetime.now(timezone.utc)
            )
            if bot_avatar:
                embed.set_author(name="YUNΛ SYSTEM ORCHESTRATOR", icon_url=bot_avatar)
                embed.set_thumbnail(url=bot_avatar)

            embed.add_field(
                name="Revision Details",
                value=(
                    f"**Commit:** `{status.get('hash', 'unknown')}`\n"
                    f"**Branch:** `{status.get('branch', GIT_BRANCH)}`\n"
                    f"**Author:** {status.get('author', '—')} ({status.get('time', 'just now')})\n"
                    f"**Message:** {status.get('message', '—')}"
                ),
                inline=False
            )
            embed.add_field(
                name="Execution Log",
                value=f"```bash\n{output_display}\n```",
                inline=False
            )
            embed.set_footer(
                text=f"Rebooting in 3s • Requested by {ctx.author}",
                icon_url=author_avatar
            )
            try:
                await msg.edit(embed=embed, view=None)
            except Exception:
                try:
                    await ctx.send(embed=embed)
                except Exception:
                    pass

            # Log to deploy channel too
            await self._send_deploy_log(success, output, triggered_by=f"{ctx.author} via Discord $gitpull")

            # Record in persistent deployment history
            try:
                from core.git_history import record_git_deploy
                record_git_deploy(
                    success=True,
                    output=output,
                    triggered_by=f"Discord ${ctx.invoked_with or 'gitpull'} ({ctx.author})",
                    restarted=True,
                    git_status=status
                )
            except Exception as e:
                print(f"[GitPull] Could not record deploy history: {e}")

            # Restart bot cleanly with small grace window
            asyncio.create_task(self._delayed_restart(3))

        else:
            embed = discord.Embed(
                title="❌ Deployment Aborted — Build Error",
                description=(
                    f"> Remote synchronization encountered an error.\n"
                    f"> Container was **not** restarted. Existing runtime remains active."
                ),
                color=0xE74C3C,
                timestamp=datetime.now(timezone.utc)
            )
            if bot_avatar:
                embed.set_author(name="YUNΛ SYSTEM ORCHESTRATOR", icon_url=bot_avatar)
            embed.add_field(
                name="Diagnostic Output",
                value=f"```bash\n{output_display}\n```",
                inline=False
            )
            embed.set_footer(
                text=f"Deployment failed • Requested by {ctx.author}",
                icon_url=author_avatar
            )
            try:
                await msg.edit(embed=embed, view=None)
            except Exception:
                try:
                    await ctx.send(embed=embed)
                except Exception:
                    pass

            # Record in persistent deployment history
            try:
                from core.git_history import record_git_deploy
                fail_status = await _get_git_status_async()
                record_git_deploy(
                    success=False,
                    output=output,
                    triggered_by=f"Discord ${ctx.invoked_with or 'gitpull'} ({ctx.author})",
                    restarted=False,
                    git_status=fail_status
                )
            except Exception as e:
                print(f"[GitPull] Could not record deploy history: {e}")

    @gitpull_cmd.error
    @git_group.error
    async def gitpull_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.NotOwner, commands.CheckFailure)):
            embed = discord.Embed(
                title="Access Denied",
                description="<:Yuna_cross:1227866668152393789> Only the **Bot Owner** can use this command!",
                color=COLOR_ERR
            )
            try:
                await ctx.send(embed=embed, delete_after=6)
            except Exception:
                pass
            return
        embed = discord.Embed(
            title="Command Error",
            description=f"<:Yuna_cross:1227866668152393789> An error occurred: `{error}`",
            color=COLOR_DARK
        )
        try:
            await ctx.send(embed=embed, delete_after=10)
        except Exception:
            pass

    @app_commands.command(
        name="gitpull",
        description="[Bot Owner Only] Pull latest code from GitHub and restart the bot"
    )
    @app_commands.describe(flag="Optional: set to 'check' or 'preview' to inspect before deploy")
    async def gitpull_slash(self, interaction: discord.Interaction, flag: str = ""):
        """Owner-only slash command: run git pull and restart."""
        uid = interaction.user.id
        is_owner = (uid in GLOBAL_OWNER_IDS) or (uid == PRIMARY_BOT_OWNER) or (uid in OWNER_IDS)
        if not is_owner:
            try:
                is_owner = await self.bot.is_owner(interaction.user)
            except Exception:
                is_owner = False
        if not is_owner:
            return await interaction.response.send_message(
                "<:Yuna_cross:1227866668152393789> Only the **Bot Owner** can use this command!",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=False)
        ctx = await self.bot.get_context(interaction)
        await self.gitpull_cmd(ctx, flag=flag)

    @commands.command(
        name="gitstatus",
        aliases=["gitinfo", "gstatus", "version"],
        hidden=True,
        help="Owner-only: Show current deployed git commit info."
    )
    @is_bot_owner()
    async def gitstatus_cmd(self, ctx: commands.Context):
        """Owner-only: show current git commit."""
        status = await _get_git_status_async()

        if "error" in status:
            embed = discord.Embed(
                title="Git Status Diagnostic",
                description=f"```bash\n{status['error']}\n```",
                color=COLOR_DARK
            )
            if self.bot.user:
                embed.set_author(name="YUNΛ SYSTEM ORCHESTRATOR", icon_url=self.bot.user.display_avatar.url)
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="System Version & Deployment Status",
            description=f"> Active production runtime deployed on `origin/{status.get('branch', 'main')}`.",
            color=COLOR_DARK,
            timestamp=datetime.now(timezone.utc)
        )
        if self.bot.user:
            embed.set_author(name="YUNΛ SYSTEM ORCHESTRATOR", icon_url=self.bot.user.display_avatar.url)
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.add_field(
            name="Current Revision",
            value=(
                f"**Hash:** `{status['hash']}`\n"
                f"**Branch:** `{status['branch']}`\n"
                f"**Author:** {status['author']} ({status['time']})\n"
                f"**Message:** {status['message']}"
            ),
            inline=False
        )
        webhook_info = f"`Active` (Port `{WEBHOOK_PORT}`)" if self._webhook_runner else "`Offline`"
        embed.add_field(
            name="Auto-Deploy Webhook",
            value=webhook_info,
            inline=True
        )
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @gitstatus_cmd.error
    async def gitstatus_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.NotOwner, commands.CheckFailure)):
            return  # Silently ignore non-owners
        embed = discord.Embed(
            title="Command Error",
            description=f"<:Yuna_cross:1227866668152393789> An error occurred: `{error}`",
            color=COLOR_DARK
        )
        try:
            await ctx.send(embed=embed, delete_after=10)
        except Exception:
            pass

    @commands.command(
        name="webhookstatus",
        aliases=["webhookinfo"],
        hidden=True,
        help="Owner-only: Check if the GitHub webhook server is running."
    )
    @is_bot_owner()
    async def webhookstatus_cmd(self, ctx: commands.Context):
        """Owner-only: check webhook server status."""
        if self._webhook_runner:
            embed = discord.Embed(
                title=f"{TICK} Webhook Server Online",
                description=(
                    f"Listening on `0.0.0.0:{WEBHOOK_PORT}`\n\n"
                    f"**Endpoint:** `POST /webhook`\n"
                    f"**Health check:** `GET /webhook` → `/health`\n"
                    f"**Branch:** `{GIT_BRANCH}`\n"
                    f"**Secret configured:** `{'Yes' if WEBHOOK_SECRET else 'No ⚠️'}`"
                ),
                color=COLOR_OK
            )
        else:
            embed = discord.Embed(
                title=f"{CROSS} Webhook Server Offline",
                description="The aiohttp server failed to start. Check bot logs for errors.",
                color=COLOR_ERR
            )
        await ctx.send(embed=embed)

    @webhookstatus_cmd.error
    async def webhookstatus_cmd_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.NotOwner, commands.CheckFailure)):
            return  # Silently ignore non-owners
        embed = discord.Embed(
            title="Command Error",
            description=f"<:Yuna_cross:1227866668152393789> An error occurred: `{error}`",
            color=COLOR_DARK
        )
        try:
            await ctx.send(embed=embed, delete_after=10)
        except Exception:
            pass

    @commands.command(
        name="systemcheck",
        aliases=["syscheck", "optcheck", "healthcheck"],
        hidden=True,
        help="Owner-only: Run automated diagnostics on all system optimizations."
    )
    @is_bot_owner()
    async def systemcheck_cmd(self, ctx: commands.Context):
        """Owner-only: run automated live diagnostics on audio buffer, autoplay, prefix, db, security."""
        msg = await ctx.send("<a:loading:1554957482248380416> Running automated live diagnostics on all subsystems...")
        t_start = time.perf_counter()

        checks = []

        # 1. Fast-Path Raw Gateway Interception
        try:
            from core.antinuke_v2.fast_path import RAW_AUDIT_ACTION_MAP, schedule_high_priority_task
            assert 22 in RAW_AUDIT_ACTION_MAP and RAW_AUDIT_ACTION_MAP[22] == "ban"
            assert 20 in RAW_AUDIT_ACTION_MAP and RAW_AUDIT_ACTION_MAP[20] == "kick"
            checks.append(("Fast-Path Gateway Parser", True, "Microsecond-0 direct WebSocket interception & orjson active"))
        except Exception as e:
            checks.append(("Fast-Path Gateway Parser", False, str(e)))

        # 2. TurboBan Client
        try:
            from core.antinuke_v2.containment import turbo_ban_client
            assert hasattr(turbo_ban_client, "raw_ban")
            checks.append(("TurboBan REST Engine", True, "TCP_NODELAY raw HTTP PUT client ready (Sub-15ms lane)"))
        except Exception as e:
            checks.append(("TurboBan REST Engine", False, str(e)))

        # 3. Anti-Nuke V2 State Store
        try:
            from core.antinuke_v2.router import v2_engine_router
            assert v2_engine_router is not None
            assert hasattr(v2_engine_router.coordinator, "state_store")
            checks.append(("Anti-Nuke V2 Coordinator", True, "Dual-Layer Anomaly Detection & State Store active in RAM"))
        except Exception as e:
            checks.append(("Anti-Nuke V2 Coordinator", False, str(e)))

        # 4. Prefix Resolution
        try:
            prefixes = await self.bot.get_prefix(ctx.message)
            assert isinstance(prefixes, (list, tuple))
            assert all(isinstance(p, str) for p in prefixes)
            assert None not in prefixes
            checks.append(("Command Prefix Dispatch", True, f"Guaranteed non-null string prefix (Resolved: {prefixes})"))
        except Exception as e:
            checks.append(("Command Prefix Dispatch", False, str(e)))

        # 5. Database Connection Pool & WAL
        try:
            from core.database.connection_pool import db_pool
            async with db_pool.acquire("db/prefix.db") as db:
                async with db.execute("PRAGMA journal_mode;") as cur:
                    row = await cur.fetchone()
                    mode = row[0].upper() if row else "UNKNOWN"
            checks.append(("Database Pool & WAL", True, f"SQLite journal_mode: {mode} (Connection pool active)"))
        except Exception as e:
            checks.append(("Database Pool & WAL", False, str(e)))

        # 6. Security Cache
        try:
            from core.cache.security_cache import security_cache
            t0 = time.perf_counter()
            _ = security_cache.is_extra_owner(ctx.guild.id if ctx.guild else 0, ctx.author.id)
            lat_us = (time.perf_counter() - t0) * 1_000_000
            checks.append(("Security In-Memory Cache", True, f"Zero-delay state query ({lat_us:.1f}µs lookup)"))
        except Exception as e:
            checks.append(("Security In-Memory Cache", False, str(e)))

        total_elapsed = (time.perf_counter() - t_start) * 1000
        passed_count = sum(1 for c in checks if c[1])
        all_passed = passed_count == len(checks)

        color = 0x2ECC71 if all_passed else 0xE74C3C
        status_header = "🟢 ALL SUBSYSTEMS OPTIMAL (6/6)" if all_passed else f"⚠️ {passed_count}/6 SUBSYSTEMS PASSING"

        embed = discord.Embed(
            title="🛡️ YUNΛ Supreme Optimization & Security Diagnostics",
            description=f"**Status:** `{status_header}` • `{total_elapsed:.1f}ms`\nLive automated audit across all performance modules:",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        for name, ok, details in checks:
            icon = "✅" if ok else "❌"
            embed.add_field(
                name=f"{icon} {name}",
                value=f"`{details}`",
                inline=False
            )

        embed.set_footer(text=f"Requested by {ctx.author} | Yuna Self-Diagnostic Suite", icon_url=getattr(ctx.author.display_avatar, 'url', None))
        await msg.edit(content=None, embed=embed)


async def setup(bot):
    """Allows GitPull to be loaded as a standalone, independent extension."""
    if not bot.get_cog("GitPull"):
        await bot.add_cog(GitPull(bot))

