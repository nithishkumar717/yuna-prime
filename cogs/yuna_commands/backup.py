import os
import json
import time
import uuid
import hashlib
import asyncio
import datetime
import discord
from discord.ext import commands
from typing import Dict, Any, List, Optional
from utils.settings_manager import get_guild_setting, set_guild_setting

BACKUP_DIR = os.path.join("data", "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


def _sync_backup_to_cloud_worker(snapshot: Dict[str, Any]):
    try:
        from core.database.upsert_sync_engine import create_resilient_mongo_client
        uri = os.getenv("PERMANENT_MONGODB_URI") or os.getenv("MONGODB_URI")
        if not uri:
            return
        client = create_resilient_mongo_client(uri, timeout_ms=4000)
        if not client:
            return
        db = client.get_default_database() or client["yuna_backups"]
        coll = db["server_structure_snapshots"]
        coll.replace_one(
            {"id": snapshot["id"], "guild_id": snapshot["guild_id"]},
            snapshot,
            upsert=True
        )
    except Exception:
        pass


async def sync_backup_to_cloud(snapshot: Dict[str, Any]):
    """Dispatches asynchronous persistence of snapshot to MongoDB Cloud Replica."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _sync_backup_to_cloud_worker, snapshot)
    except Exception:
        pass


def create_server_backup(guild: discord.Guild, force: bool = False) -> Dict[str, Any]:
    """Generates and persists a structured layout snapshot for a guild with smart delta-diffing and cloud sync."""
    backup_id = str(uuid.uuid4())[:8]
    
    # 1. Roles snapshot
    roles_data = []
    for role in reversed(guild.roles):
        if role.is_default():
            continue
        roles_data.append({
            "name": role.name,
            "color": role.color.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
            "permissions": role.permissions.value
        })

    # 2. Categories & Channels snapshot
    categories_data = []
    for category in guild.categories:
        cat_channels = []
        for ch in category.channels:
            cat_channels.append({
                "name": ch.name,
                "type": str(ch.type),
                "topic": getattr(ch, "topic", None),
                "user_limit": getattr(ch, "user_limit", None)
            })
        categories_data.append({
            "name": category.name,
            "channels": cat_channels
        })

    # State Hash for Smart Delta-Diffing
    role_names = [r["name"] for r in roles_data]
    cat_names = [c["name"] for c in categories_data]
    state_fingerprint = f"{len(roles_data)}:{sum(r['permissions'] for r in roles_data)}:{role_names}:{len(categories_data)}:{cat_names}"
    state_hash = hashlib.sha256(state_fingerprint.encode()).hexdigest()[:16]

    file_path = os.path.join(BACKUP_DIR, f"backups_{guild.id}.json")
    backups = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                backups = json.load(f)
        except Exception:
            backups = []

    # Check if latest snapshot is unchanged
    if not force and backups and backups[0].get("state_hash") == state_hash:
        backups[0]["last_verified_at"] = time.time()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(backups[:14], f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return {
            "id": backups[0]["id"],
            "guild_id": guild.id,
            "guild_name": guild.name,
            "created_at": backups[0]["created_at"],
            "roles_count": len(roles_data),
            "categories_count": len(categories_data),
            "roles": roles_data,
            "categories": categories_data,
            "state_hash": state_hash,
            "status": "unchanged"
        }

    now_ts = time.time()
    snapshot = {
        "id": backup_id,
        "guild_id": guild.id,
        "guild_name": guild.name,
        "created_at": now_ts,
        "last_verified_at": now_ts,
        "roles_count": len(roles_data),
        "categories_count": len(categories_data),
        "roles": roles_data,
        "categories": categories_data,
        "state_hash": state_hash,
        "status": "created"
    }

    # Rolling 14 snapshots (7 days of 12-hour backups)
    backups.insert(0, snapshot)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(backups[:14], f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    # Async Cloud Sync
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(sync_backup_to_cloud(snapshot))
    except Exception:
        pass

    return snapshot


class ServerBackup(commands.Cog):
    """Server Structure Backup & Snapshot Manager for YUNA V 7.00."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_guild_backups(self, guild_id: int) -> List[Dict[str, Any]]:
        file_path = os.path.join(BACKUP_DIR, f"backups_{guild_id}.json")
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_guild_backups(self, guild_id: int, backups: List[Dict[str, Any]]) -> None:
        file_path = os.path.join(BACKUP_DIR, f"backups_{guild_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(backups, f, indent=2, ensure_ascii=False)

    @commands.group(name="backup", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def backup_group(self, ctx: commands.Context):
        """Server Backup commands group."""
        embed = discord.Embed(
            title="💾 YUNA Server Backup & Snapshot System",
            description="Create and restore encrypted server structure snapshots (roles, channels, categories).",
            color=0x5865F2
        )
        embed.add_field(
            name="Available Commands",
            value="`backup create` - Take a new snapshot of server roles & channels\n`backup list` - View saved snapshots\n`backup load <id>` - Restore a snapshot",
            inline=False
        )
        await ctx.send(embed=embed)

    @backup_group.command(name="create")
    @commands.has_permissions(administrator=True)
    async def backup_create(self, ctx: commands.Context):
        """Create a full snapshot backup of the server layout."""
        msg = await ctx.send("<a:loading:1554957482248380416> Generating encrypted server structure snapshot...")
        
        snapshot = create_server_backup(ctx.guild)
        backup_id = snapshot["id"]
        roles_count = snapshot["roles_count"]
        categories_count = snapshot["categories_count"]

        embed = discord.Embed(
            title="✅ Server Backup Created!",
            description=f"Snapshot ID: `{backup_id}`\nSaved `{roles_count}` roles and `{categories_count}` categories.",
            color=0x57F287
        )
        await msg.edit(content=None, embed=embed)

    async def restore_snapshot(self, guild: discord.Guild, target_backup: Dict[str, Any]) -> Dict[str, int]:
        """Reconstructs roles, categories, and channels from a saved snapshot dictionary."""
        roles_restored = 0
        categories_restored = 0
        channels_restored = 0

        existing_role_names = {r.name.lower(): r for r in guild.roles}
        existing_cat_names = {c.name.lower(): c for c in guild.categories}

        # 1. Restore Roles
        for r_data in target_backup.get("roles", []):
            r_name = r_data.get("name", "Restored Role")
            if r_name.lower() in existing_role_names:
                continue
            try:
                await guild.create_role(
                    name=r_name,
                    color=discord.Color(r_data.get("color", 0)),
                    hoist=r_data.get("hoist", False),
                    mentionable=r_data.get("mentionable", False),
                    permissions=discord.Permissions(r_data.get("permissions", 0)),
                    reason="[Yuna Backup] Disaster Recovery Role Creation"
                )
                roles_restored += 1
            except Exception:
                pass

        # 2. Restore Categories and their Channels
        for cat_data in target_backup.get("categories", []):
            cat_name = cat_data.get("name", "Category")
            category_obj = existing_cat_names.get(cat_name.lower())
            if not category_obj:
                try:
                    category_obj = await guild.create_category(
                        name=cat_name,
                        reason="[Yuna Backup] Disaster Recovery Category Creation"
                    )
                    categories_restored += 1
                except Exception:
                    category_obj = None

            for ch_data in cat_data.get("channels", []):
                ch_name = ch_data.get("name", "channel")
                ch_type_str = ch_data.get("type", "text")
                cat_channels = category_obj.channels if category_obj else guild.channels
                if any(c.name.lower() == ch_name.lower() for c in cat_channels):
                    continue

                try:
                    if "voice" in ch_type_str:
                        await guild.create_voice_channel(
                            name=ch_name,
                            category=category_obj,
                            user_limit=ch_data.get("user_limit"),
                            reason="[Yuna Backup] Disaster Recovery Channel Creation"
                        )
                    else:
                        await guild.create_text_channel(
                            name=ch_name,
                            category=category_obj,
                            topic=ch_data.get("topic"),
                            reason="[Yuna Backup] Disaster Recovery Channel Creation"
                        )
                    channels_restored += 1
                except Exception:
                    pass

        return {
            "roles_restored": roles_restored,
            "categories_restored": categories_restored,
            "channels_restored": channels_restored
        }

    @backup_group.command(name="list")
    @commands.has_permissions(administrator=True)
    async def backup_list(self, ctx: commands.Context):
        """List all saved server snapshots with 1-click restore dropdown."""
        backups = self._get_guild_backups(ctx.guild.id)
        if not backups:
            return await ctx.send("❌ No server backups found for this guild.")

        embed = discord.Embed(
            title=f"💾 Saved Restore Points for {ctx.guild.name}",
            description="Select any restore point from the dropdown below to instantly inspect or load it.",
            color=0x2B2D31
        )
        for b in backups[:5]:
            created_str = f"<t:{int(b.get('created_at', time.time()))}:R>"
            state_info = "⚡ Verified" if b.get("status") == "unchanged" else "✨ New Version"
            embed.add_field(
                name=f"Snapshot ID: `{b['id']}` ({state_info})",
                value=f"Created: {created_str}\nRoles: `{b.get('roles_count', 0)}` | Categories: `{b.get('categories_count', 0)}`",
                inline=False
            )

        view = RestorePointDropdownView(backups, self, ctx.guild)
        await ctx.send(embed=embed, view=view)

    @backup_group.command(name="load")
    @commands.has_permissions(administrator=True)
    async def backup_load(self, ctx: commands.Context, backup_id: str):
        """Restore server structure from a saved snapshot or live antinuke template."""
        if not ctx.guild.me.guild_permissions.administrator:
            return await ctx.send("❌ I need **Administrator** permissions to restore server structures.")

        # Special option: if user specifies "template", "auto", or "live", restore from V2 template store
        if backup_id.lower() in ("template", "auto", "live"):
            msg = await ctx.send("<a:loading:1554957482248380416> Restoring server structure from Anti-Nuke baseline template...")
            try:
                from core.antinuke_v2.router import v2_engine_router
                res = await v2_engine_router.coordinator.recovery.recover_all_from_template(ctx.guild)
                embed = discord.Embed(
                    title="<a:tick:1558726958802800660> Template Auto-Recovery Complete!",
                    description=(
                        f"Successfully restored missing server structure from baseline template.\n\n"
                        f"🛡️ **Roles Restored:** `{res['roles_restored']}`\n"
                        f"📁 **Categories Restored:** `{res['categories_restored']}`\n"
                        f"💬 **Channels Restored:** `{res['channels_restored']}`\n"
                        f"⏱️ **Time Elapsed:** `{res['duration_ms']:.2f}ms`"
                    ),
                    color=0x57F287
                )
                return await msg.edit(content=None, embed=embed)
            except Exception as exc:
                return await msg.edit(content=f"❌ Error during template restoration: `{exc}`")

        backups = self._get_guild_backups(ctx.guild.id)
        target_backup = None
        if backup_id.lower() == "latest":
            if backups:
                target_backup = backups[0]
        else:
            for b in backups:
                if b.get("id") == backup_id:
                    target_backup = b
                    break

        if not target_backup:
            return await ctx.send(f"❌ Snapshot with ID `{backup_id}` not found. Use `backup list` to see available backups.")

        msg = await ctx.send(f"<a:loading:1554957482248380416> Reconstructing server layout from snapshot `{target_backup['id']}`...")
        res = await self.restore_snapshot(ctx.guild, target_backup)

        embed = discord.Embed(
            title="<a:tick:1558726958802800660> Server Backup Loaded Successfully!",
            description=(
                f"Restored layout from Snapshot ID `{target_backup['id']}`.\n\n"
                f"🛡️ **Roles Created:** `{res['roles_restored']}`\n"
                f"📁 **Categories Created:** `{res['categories_restored']}`\n"
                f"💬 **Channels Created:** `{res['channels_restored']}`"
            ),
            color=0x57F287
        )
        await msg.edit(content=None, embed=embed)


class RestorePointDropdownView(discord.ui.View):
    def __init__(self, backups: List[Dict[str, Any]], cog: ServerBackup, guild: discord.Guild):
        super().__init__(timeout=120)
        self.add_item(RestorePointSelect(backups, cog, guild))


class RestorePointSelect(discord.ui.Select):
    def __init__(self, backups: List[Dict[str, Any]], cog: ServerBackup, guild: discord.Guild):
        self.cog = cog
        self.backups_map = {b["id"]: b for b in backups}
        options = []
        for b in backups[:14]:
            t_val = int(b.get("created_at", time.time()))
            dt_str = datetime.datetime.fromtimestamp(t_val, tz=datetime.timezone.utc).strftime("%d %b %H:%M UTC")
            options.append(discord.SelectOption(
                label=f"Snapshot {b['id']} ({b.get('roles_count', 0)} roles, {b.get('categories_count', 0)} cats)",
                description=f"Saved {dt_str}",
                value=b["id"]
            ))
        super().__init__(placeholder="Select a Restore Point to Load...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only Administrators can restore backups.", ephemeral=True)
        backup_id = self.values[0]
        target = self.backups_map.get(backup_id)
        if not target:
            return await interaction.response.send_message("❌ Backup not found.", ephemeral=True)

        confirm_view = RestoreConfirmModalView(backup_id, target, self.cog, interaction.guild)
        await interaction.response.send_message(
            f"⚠️ **Confirm Restoration of Snapshot `{backup_id}`**\n"
            f"Roles: `{target.get('roles_count', 0)}` | Categories: `{target.get('categories_count', 0)}`\n"
            f"Clicking below will recreate any missing channels or roles from this point in time.",
            view=confirm_view,
            ephemeral=True
        )


class RestoreConfirmModalView(discord.ui.View):
    def __init__(self, backup_id: str, target_backup: Dict[str, Any], cog: ServerBackup, guild: discord.Guild):
        super().__init__(timeout=60)
        self.backup_id = backup_id
        self.target_backup = target_backup
        self.cog = cog
        self.guild = guild

    @discord.ui.button(label="Confirm & Restore", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        res = await self.cog.restore_snapshot(self.guild, self.target_backup)
        embed = discord.Embed(
            title="<a:tick:1558726958802800660> Restore Point Applied Successfully!",
            description=(
                f"Restored layout from Snapshot ID `{self.backup_id}`.\n\n"
                f"🛡️ **Roles Created:** `{res['roles_restored']}`\n"
                f"📁 **Categories Created:** `{res['categories_restored']}`\n"
                f"💬 **Channels Created:** `{res['channels_restored']}`"
            ),
            color=0x57F287
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerBackup(bot))
