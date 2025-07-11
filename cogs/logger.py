import discord
from discord.ext import commands
from discord import app_commands
from db import Database
from utils.checks import is_admin

class Logger(commands.GroupCog, name="log"):
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db

    async def log(self, guild, message):
        channel_id = await self.db.get_log_channel(guild.id)
        if not channel_id:
            return
        
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        # проверка прав на отправку сообщений
        perms = channel.permissions_for(guild.me)
        if not perms.send_messages:
            return
        
        embed = discord.Embed(description=message, color=discord.Color.orange())

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @is_admin()
    @app_commands.command(name="add", description="Set log channel")
    async def add(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.db.set_log_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Log channel set", description=channel.mention, color=discord.Color.green()), ephemeral=True)

    @is_admin()
    @app_commands.command(name="delete", description="Remove log channel")
    async def delete(self, interaction: discord.Interaction):
        await self.db.del_log_channel(interaction.guild.id)
        await interaction.response.send_message(embed=discord.Embed(
            title="🗑️ Log channel removed", color=discord.Color.red()), ephemeral=True)

    @is_admin()
    @app_commands.command(name="show", description="Show current log channel")
    async def show(self, interaction: discord.Interaction):
        log_id = await self.db.get_log_channel(interaction.guild.id)
        channel = interaction.guild.get_channel(log_id) if log_id else None
        await interaction.response.send_message(embed=discord.Embed(
            title="📌 Current log channel", description=channel.mention if channel else "Not set.", color=discord.Color.blurple()), ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f"DEBUG: {member} joined, checking autorole...")
        await self.log(member.guild, f"✅ Member <@{member.id}> joined the server.")

        role_ids = await self.db.get_autoroles(member.guild.id)
        roles = [member.guild.get_role(rid) for rid in role_ids]
        roles = [r for r in roles if r and r < member.guild.me.top_role]

        if roles:
            await member.add_roles(*roles, reason="Joined the server")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    return await self.log(member.guild,
                        f"👢 <@{entry.user.id}> kicked <@{entry.target.id}>")
                
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == member.id:
                    await self.log(member.guild, f"⛔ {entry.user.mention} banned {member.mention}")
                    return
        except discord.Forbidden:
            pass
        except discord.NotFound:
            pass

        # Если не найдено — обычный выход
        await self.log(member.guild, f"❌ Member {member.mention} left the server.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            mention = member.mention
            
            # Попытка найти, кто переместил
            moved_by = None
            
            if before.channel and after.channel:
                async for entry in member.guild.audit_logs(limit=3, action=discord.AuditLogAction.member_move):
                    # Защита от пустых target/user и устаревших записей
                    if (entry.target and entry.target.id == member.id and
                            entry.user and
                            (discord.utils.utcnow() - entry.created_at).total_seconds() < 10):
                        moved_by = entry.user
                        break

                if moved_by and moved_by.id != member.id:
                    msg = f"🔁 {moved_by.mention} moved {mention} from {before.channel.mention} to {after.channel.mention}"
                else:
                    msg = f"🔁 {mention} switched from {before.channel.mention} to {after.channel.mention}"

            elif after.channel:
                msg = f"🎙️ {mention} joined voice channel: {after.channel.mention}"
            else:
                msg = f"🔇 {mention} left voice channel: {before.channel.mention}"

            await self.log(member.guild, msg)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        for guild in self.bot.guilds:
            member = guild.get_member(after.id)
            if member and before.name != after.name:
                await self.log(guild, f"📝 <@{after.id}> changed username from **{before.name}** to **{after.name}**")
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick:
            old_nick = before.nick or before.name
            new_nick = after.nick or after.name
            await self.log(after.guild, f"✏️ <@{after.id}> changed nickname: **{old_nick}** → **{new_nick}**")

        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                    if entry.target.id == after.id:
                        await self.log(after.guild, f"⏳ {entry.user.mention} timed out {after.mention} until {after.timed_out_until.strftime('%Y-%m-%d %H:%M:%S')}")
                        break
        
        if before.timed_out_until and not after.timed_out_until:
            async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                if entry.target.id == after.id:
                    await self.log(after.guild, f"🔓 {entry.user.mention} removed timeout from {after.mention}")
                    break

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
            if entry.target.id == user.id:
                await self.log(guild, f"⚖️ {entry.user.mention} unbanned {user.mention}")
                break

    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.content != after.content:
            await self.log(before.guild,
                f"✏️ Message from <@{before.author.id}> edited in {before.channel.mention}\n"
                f"**Before:** {before.content}\n**After:** {after.content}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or not message.author or message.author.bot:
            return

        audit_user = None
        
        async for entry in message.guild.audit_logs(limit=1, action=discord.AuditLogAction.message_delete):
            if (entry.target and entry.target.id == message.author.id and
                    entry.extra and entry.extra.channel.id == message.channel.id):
                audit_user = entry.user
                break

        # Если сам удалил — не выдаём как чужое удаление
        if audit_user and audit_user.id != message.author.id:
            msg = f"🗑️ {audit_user.mention} deleted a message by {message.author.mention} в {message.channel.mention}\n**Content:** {message.content}"
        else:
            msg = f"🗑️ Message by {message.author.mention} deleted in {message.channel.mention}\n**Content:** {message.content}"

        await self.log(message.guild, msg)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            await self.log(channel.guild, f"🆕 {entry.user.mention} created channel: {channel.mention}")
            break

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            await self.log(channel.guild, f"❌ {entry.user.mention} deleted channel: `{channel.name}`")
            break

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        async for entry in before.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
            await self.log(before.guild, f"⚙️ {entry.user.mention} updated channel: `{before.name}`")
            break

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await self.db.del_autoroles(guild.id)
        await self.db.del_log_channel(guild.id)
        await self.db.clear_guild(guild.id)
