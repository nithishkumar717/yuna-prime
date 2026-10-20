import discord
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check, is_server_owner_or_extra_owner

class AuditTools(commands.Cog):
    """Advanced Server & Role Audit Tools."""

    def __init__(self, bot):
        self.bot = bot
        self.color = 0x2B2D31

    @commands.hybrid_command(name="massrole", help="Mass add or remove a role from all humans or bots.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def massrole(self, ctx: commands.Context, action: str, target: str, role: discord.Role):
        action = action.lower()
        target = target.lower()

        if action not in ["add", "remove"]:
            return await ctx.reply("❌ Action must be `add` or `remove`.")
        if target not in ["humans", "bots", "all"]:
            return await ctx.reply("❌ Target must be `humans`, `bots`, or `all`.")

        targets = []
        for member in ctx.guild.members:
            if target == "humans" and member.bot:
                continue
            if target == "bots" and not member.bot:
                continue
            if action == "add" and role not in member.roles:
                targets.append(member)
            elif action == "remove" and role in member.roles:
                targets.append(member)

        total_targets = len(targets)
        if total_targets == 0:
            return await ctx.reply("ℹ️ No members require role modification for this target selection.")

        # Safety Gate: Confirm operations if >= 500 members
        if total_targets >= 500:
            confirm_embed = discord.Embed(
                title="⚠️ Large Bulk Operation Safety Gate",
                description=f"Massrole **{action}** will update **{total_targets} members**. Are you sure you want to proceed?",
                color=0xFFA500
            )
            confirm_embed.set_footer(text="Confirmation timeout: 30 seconds")
            
            view = discord.ui.View(timeout=30)
            confirmed = False

            async def confirm_callback(interaction: discord.Interaction):
                nonlocal confirmed
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("❌ Only the command author can confirm.", ephemeral=True)
                confirmed = True
                await interaction.response.edit_message(content="✅ **Confirmed.** Starting bulk queue...", embed=None, view=None)

            async def cancel_callback(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("❌ Only the command author can cancel.", ephemeral=True)
                await interaction.response.edit_message(content="🛑 **Operation Cancelled.**", embed=None, view=None)

            confirm_btn = discord.ui.Button(label="Proceed", style=discord.ButtonStyle.danger)
            cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
            confirm_btn.callback = confirm_callback
            cancel_btn.callback = cancel_callback
            view.add_item(confirm_btn)
            view.add_item(cancel_btn)

            msg = await ctx.reply(embed=confirm_embed, view=view)
            await view.wait()
            if not confirmed:
                return
        else:
            msg = await ctx.reply(f"<a:loading:1554957482248380416> Processing massrole **{action}** for `{total_targets}` member(s)... Please wait.")

        from core.discord.request_manager import request_manager, Priority

        coro_funcs = []
        for mem in targets:
            if action == "add":
                coro_funcs.append(lambda m=mem: m.add_roles(role, reason=f"Massrole executed by {ctx.author}"))
            else:
                coro_funcs.append(lambda m=mem: m.remove_roles(role, reason=f"Massrole executed by {ctx.author}"))

        async def _progress_cb(current: int, total: int):
            try:
                await msg.edit(content=f"<a:loading:1554957482248380416> Processing massrole **{action}**: `{current}/{total}` updated...")
            except Exception:
                pass

        await request_manager.enqueue_bulk(
            priority=Priority.P2_NORMAL,
            base_task_id=f"massrole_{ctx.guild.id}",
            coro_funcs=coro_funcs,
            guild_id=ctx.guild.id,
            progress_callback=_progress_cb,
            delay_between_tasks=0.05
        )

        await msg.edit(content=f"✅ Massrole **{action}** completed! Updated role for `{total_targets}` members.")

async def setup(bot):
    await bot.add_cog(AuditTools(bot))
