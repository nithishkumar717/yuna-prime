from discord.ext import commands
from core import BotBase, Cog
import discord
import logging
import asyncio
from discord.ui import View, Button
from utils.support_utils import SUPPORT_GUILD_ID, get_or_generate_support_invite, get_support_url

logging.basicConfig(
    level=logging.INFO,
    format="\x1b[38;5;197m[\x1b[0m%(asctime)s\x1b[38;5;197m]\x1b[0m -> \x1b[38;5;197m%(message)s\x1b[0m",
    datefmt="%I:%M:%S %p IST",
)

class DMInviteButton(Button):
    def __init__(self, guild: discord.Guild, invite_url: str | None, bot: BotBase):
        super().__init__(
            label="Send Invite to DM",
            style=discord.ButtonStyle.secondary,
            emoji="📩",
            custom_id=f"dm_inv_btn_{guild.id}"
        )
        self.guild = guild
        self.invite_url = invite_url
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        url = self.invite_url
        if not url:
            try:
                invites = await self.guild.invites()
                for inv in invites:
                    if inv.max_age == 0 and inv.max_uses == 0:
                        url = str(inv.url)
                        break
                if not url and invites:
                    url = str(invites[0].url)
            except Exception:
                pass

        if not url:
            try:
                for tc in self.guild.text_channels:
                    if tc.permissions_for(self.guild.me).create_instant_invite:
                        inv = await tc.create_invite(max_age=0, max_uses=0, reason="Owner DM Invite Request")
                        url = str(inv.url)
                        break
            except Exception:
                pass

        if not url:
            await interaction.response.send_message(
                "❌ Unable to generate an invite link for this server (insufficient permissions).",
                ephemeral=True
            )
            return

        try:
            from utils.guild_logs_db import update_guild_invite_url
            update_guild_invite_url(str(self.guild.id), url)
        except Exception:
            pass

        try:
            embed = discord.Embed(
                title=f"🔗 Server Invite Link: {self.guild.name}",
                description=f"Invite link for **{self.guild.name}**:\n\n👉 **{url}**",
                color=0x7C3AED,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Guild ID", value=f"`{self.guild.id}`", inline=True)
            embed.add_field(name="Member Count", value=f"`{len(self.guild.members)}`", inline=True)
            if self.guild.icon:
                embed.set_thumbnail(url=self.guild.icon.url)
            embed.set_footer(text="Yuna Admin Assistant", icon_url=self.bot.user.display_avatar.url if self.bot.user else None)

            await interaction.user.send(embed=embed)
            await interaction.response.send_message(
                f"✅ **Invite link sent to your DM!**\nLink: {url}",
                ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                f"⚠️ Could not send DM (DMs might be closed). Here is your link:\n**{url}**",
                ephemeral=True
            )


class GuildJoinLogView(View):
    def __init__(self, guild: discord.Guild, invite_url: str | None, bot: BotBase):
        super().__init__(timeout=None)
        if invite_url:
            self.add_item(Button(label="Server Invite", style=discord.ButtonStyle.link, url=invite_url, emoji="🔗"))
        self.add_item(DMInviteButton(guild, invite_url, bot))


class Guild(Cog):
    def __init__(self, client: BotBase):
        self.client = client

    @commands.Cog.listener(name="on_guild_join")
    async def on_guild_add(self, guild):
        try:
            if guild.id == SUPPORT_GUILD_ID:
                asyncio.create_task(get_or_generate_support_invite(self.client, force_refresh=True))

            inv_url = None
            try:
                invites = await guild.invites()
                rope = [inv for inv in invites if inv.max_age == 0 and inv.max_uses == 0]
                if not rope and invites:
                    rope = invites
                if rope:
                    inv_url = str(rope[0].url)
            except Exception:
                rope = []

            if not inv_url:
                try:
                    for tc in guild.text_channels:
                        if tc.permissions_for(guild.me).create_instant_invite:
                            inv = await tc.create_invite(max_age=0, max_uses=0, reason="Guild Join Logging")
                            inv_url = str(inv.url)
                            break
                except Exception as ie:
                    logging.warning(f"Could not auto-create invite for {guild.name}: {ie}")

            # Persist join event to Admin Guild Logs database
            try:
                from utils.guild_logs_db import record_guild_event
                record_guild_event("JOIN", guild, invite_url=inv_url, bot=self.client)
            except Exception as ex:
                logging.warning(f"Could not persist guild join event: {ex}")

            # Preserve & ensure Anti-Nuke remains ENABLED when bot joins/rejoins a guild
            try:
                import aiosqlite
                from utils.settings_manager import set_guild_setting
                from core.cache.security_cache import security_cache

                async with aiosqlite.connect('db/anti.db', timeout=5) as db:
                    async with db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)) as cursor:
                        row = await cursor.fetchone()
                    if row is not None:
                        # Guild previously had Anti-Nuke configured: ensure it is active
                        await db.execute("UPDATE antinuke SET status = 1 WHERE guild_id = ?", (guild.id,))
                        await db.commit()
                        set_guild_setting(guild.id, "antinuke", True)
                        security_cache.set_antinuke_status(guild.id, True)
                        try:
                            from core.antinuke_v2.router import v2_engine_router
                            v2_engine_router.coordinator.state_store.set_antinuke_status(guild.id, True)
                        except Exception:
                            pass
                        logging.info(f"[ANTINUKE] Ensured antinuke remains ENABLED for joined/rejoined guild {guild.name} ({guild.id})")
            except Exception as an_err:
                logging.warning(f"Could not update antinuke status on guild join: {an_err}")

            try:
                ch = 1271825681092706415  
                me = self.client.get_channel(ch)
                if me is not None:
                    channels = len(set(self.client.get_all_channels()))
                    embed = discord.Embed(title=f"{guild.name}'s Information", color=0x000000)
                    
                    embed.set_author(name="Guild Joined")
                    embed.set_footer(text=f"Added in {guild.name}")

                    embed.add_field(
                        name="**__About__**",
                        value=f"**Name : ** {guild.name}\n**ID :** {guild.id}\n**Owner <:Yuna_owner:1228227536207740989> :** {guild.owner} (<@{guild.owner_id}>)\n**Created At : **{guild.created_at.month}/{guild.created_at.day}/{guild.created_at.year}\n**Members :** {len(guild.members)}",
                        inline=False
                    )
                    embed.add_field(
                        name="**__Description__**",
                        value=f"""{guild.description}""",
                        inline=False
                    )
                    embed.add_field(
                        name="**__Members__**",
                        value=f"""<:Yuna_users:1226064812157571163> Members : {len(guild.members)}\n<:Yuna_friend:1228229690376982549> Humans : {len(list(filter(lambda m: not m.bot, guild.members)))}\n<:Yuna_bot:1227873668466741320> Bots : {len(list(filter(lambda m: m.bot, guild.members)))}
                        """,
                        inline=False
                    )
                    embed.add_field(
                        name="**__Channels__**",
                        value=f"""
Categories : {len(guild.categories)}
Text Channels : {len(guild.text_channels)}
Voice Channels : {len(guild.voice_channels)}
Threads : {len(guild.threads)}
                        """,
                        inline=False
                    )  
                    embed.add_field(name="__Bot Stats:__", 
                    value=f"Servers: `{len(self.client.guilds)}`\nUsers: `{len(self.client.users)}`\nChannels: `{channels}`", inline=False)  

                    if guild.icon is not None:
                        embed.set_thumbnail(url=guild.icon.url)

                    embed.timestamp = discord.utils.utcnow()
                    
                    log_view = GuildJoinLogView(guild, inv_url, self.client)
                    msg_content = f"🔗 **Invite Link:** {inv_url}" if inv_url else "⚠️ No pre-existing invite found"
                    await me.send(msg_content, embed=embed, view=log_view)
            except Exception as dev_ch_err:
                logging.debug("Developer join log dispatch skipped: %s", dev_ch_err)

            if not guild.chunked:
                await guild.chunk()

            import os
            support_url = get_support_url(self.client)
            invite_url = f"https://discord.com/oauth2/authorize?client_id={self.client.user.id}&permissions=8&scope=bot%20applications.commands"
            bot_name = self.client.user.name if self.client.user else "YUNA"
            prefix = "$"
            try:
                from utils import getConfig
                cfg = await getConfig(guild.id)
                if isinstance(cfg, dict):
                    prefix = cfg.get("prefix", "$")
                elif isinstance(cfg, str) and cfg:
                    prefix = cfg
            except Exception:
                prefix = "$"

            # Fetch adder for personalized greeting matching reference design
            adder = None
            try:
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                    if entry.target and entry.target.id == self.client.user.id:
                        adder = entry.user
                        break
                    elif adder is None:
                        adder = entry.user
            except Exception:
                pass

            if adder is None:
                adder = guild.owner
                if not adder and getattr(guild, "owner_id", None):
                    try:
                        adder = await self.client.fetch_user(guild.owner_id)
                    except Exception:
                        pass
            from utils.welcome_cv2 import build_welcome_greeting_payload

            content, cv2_view, fallback_embed, fallback_view = build_welcome_greeting_payload(
                guild=guild,
                adder=adder,
                bot=self.client,
                prefix=prefix,
                support_url=support_url,
                invite_url=invite_url,
            )

            channel = guild.system_channel
            if not channel or not channel.permissions_for(guild.me).send_messages:
                channel = discord.utils.get(guild.text_channels, name="general")
            if not channel or not channel.permissions_for(guild.me).send_messages:
                channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages]
                channel = channels[0] if channels else None

            if channel:
                try:
                    await channel.send(content=content, view=cv2_view)
                except Exception as cv2_err:
                    logging.debug("CV2 Channel welcome failed, falling back to embed: %s", cv2_err)
                    try:
                        await channel.send(content=content, embed=fallback_embed, view=fallback_view)
                    except Exception as send_err:
                        logging.warning(f"Failed to send welcome message in {guild.name}: {send_err}")


        except Exception as e:
            logging.error(f"Error in on_guild_join: {e}")

    @commands.Cog.listener(name="on_guild_remove")
    async def on_guild_remove(self, guild):
        try:
            # Persist leave event to Admin Guild Logs database
            try:
                from utils.guild_logs_db import record_guild_event
                record_guild_event("LEAVE", guild, invite_url=None, bot=self.client)
            except Exception as ex:
                logging.warning(f"Could not persist guild leave event: {ex}")
            ch = 1271825683672203294  
            idk = self.client.get_channel(ch)
            if idk is None:
                logging.error(f"Channel with ID {ch} not found.")
                return

            channels = len(set(self.client.get_all_channels()))
            embed = discord.Embed(title=f"{guild.name}'s Information", color=0x000000)
        
            embed.set_author(name="Guild Removed")
            embed.set_footer(text=f"{guild.name}")

            embed.add_field(
                name="**__About__**",
                value=f"**Name : ** {guild.name}\n**ID :** {guild.id}\n**Owner <:Yuna_owner:1228227536207740989> :** {guild.owner} (<@{guild.owner_id}>)\n**Created At : **{guild.created_at.month}/{guild.created_at.day}/{guild.created_at.year}\n**Members :** {len(guild.members)}",
                inline=False
            )
            embed.add_field(
                name="**__Description__**",
                value=f"""{guild.description}""",
                inline=False
            )
            
                
            embed.add_field(
                name="**__Members__**",
                value=f"""
Members : {len(guild.members)}
Humans : {len(list(filter(lambda m: not m.bot, guild.members)))}
Bots : {len(list(filter(lambda m: m.bot, guild.members)))}
                """,
                inline=False
            )
            embed.add_field(
                name="**__Channels__**",
                value=f"""
Categories : {len(guild.categories)}
Text Channels : {len(guild.text_channels)}
Voice Channels : {len(guild.voice_channels)}
Threads : {len(guild.threads)}
                """,
                inline=False
            )   
            embed.add_field(name="__Bot Stats:__", 
            value=f"Servers: `{len(self.client.guilds)}`\nUsers: `{len(self.client.users)}`\nChannels: `{channels}`", inline=False)

            if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)

            embed.timestamp = discord.utils.utcnow()
            await idk.send(embed=embed)
        except Exception as e:
            logging.error(f"Error in on_guild_remove: {e}")

#client.add_cog(Guild(client))


