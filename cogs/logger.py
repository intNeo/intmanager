import discord
from discord.ext import commands
from discord import app_commands
from db import Database
from utils.checks import is_admin
import asyncio

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

    def format_value(self, value):
        if value is None:
            return "None"
        return str(value)

    def format_permission_value(self, value):
        if value is True:
            return "✅ Allow"
        if value is False:
            return "❌ Deny"
        return "➖ Neutral"

    def diff_overwrites(self, before, after):
        changes = []

        before_overwrites = before.overwrites
        after_overwrites = after.overwrites

        targets = set(before_overwrites.keys()) | set(after_overwrites.keys())

        for target in targets:
            before_ow = before_overwrites.get(target)
            after_ow = after_overwrites.get(target)

            if isinstance(target, discord.Role) and target.is_default():
                target_name = "@everyone"
            else:
                target_name = getattr(target, "mention", None) or getattr(target, "name", str(target))

            if before_ow is None:
                changes.append(f"**Permissions added for {target_name}**")
                for perm, value in after_ow:
                    if value is not None:
                        changes.append(
                            f"• `{perm}`: ➖ Neutral → {self.format_permission_value(value)}"
                        )
                continue

            if after_ow is None:
                changes.append(f"**Permissions removed for {target_name}**")
                for perm, value in before_ow:
                    if value is not None:
                        changes.append(
                            f"• `{perm}`: {self.format_permission_value(value)} → ➖ Neutral"
                        )
                continue

            perm_changes = []

            before_perms = dict(before_ow)
            after_perms = dict(after_ow)

            all_perms = set(before_perms.keys()) | set(after_perms.keys())

            for perm in sorted(all_perms):
                old = before_perms.get(perm)
                new = after_perms.get(perm)

                if old != new:
                    perm_changes.append(
                        f"• `{perm}`: {self.format_permission_value(old)} → {self.format_permission_value(new)}"
                    )

            if perm_changes:
                changes.append(f"**Permissions changed for {target_name}:**")
                changes.extend(perm_changes)

        return changes
    
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
                await self.log(
                    guild,
                    f"📝 <@{after.id}> changed global username: "
                    f"**{before.name}** → **{after.name}**"
                )

            if member and before.global_name != after.global_name:
                old_global = before.global_name or before.name
                new_global = after.global_name or after.name

                await self.log(
                    guild,
                    f"🌐 <@{after.id}> changed global display name: "
                    f"**{old_global}** → **{new_global}**"
                )
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick:
            old_nick = before.nick or before.name
            new_nick = after.nick or after.name

            await self.log(
                after.guild,
                f"✏️ <@{after.id}> changed nickname: **{old_nick}** → **{new_nick}**"
            )
    
    """@commands.Cog.listener()
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
                    break"""

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
            if entry.target.id == user.id:
                await self.log(guild, f"⚖️ {entry.user.mention} unbanned {user.mention}")
                break

    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.content != after.content or before.attachments != after.attachments:
            attachments = ""
            if before.attachments:
                links = [f"[📎 Attachment {i+1}]({att.url})" for i, att in enumerate(before.attachments)]
                attachments = "\n".join(links)

            await self.log(before.guild,
                f"✏️ Message from <@{before.author.id}> edited in {before.channel.mention}\n"
                f"**Before:** {before.content or '*[no text]*'}\n"
                f"**After:** {after.content or '*[no text]*'}\n"
                f"{attachments if attachments else ''}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or not message.author or message.author.bot:
            return

        attachments = ""
        if message.attachments:
            links = [f"[📎 Attachment {i+1}]({att.url})" for i, att in enumerate(message.attachments)]
            attachments = "\n".join(links)

        audit_user = None
        async for entry in message.guild.audit_logs(limit=1, action=discord.AuditLogAction.message_delete):
            if (entry.target and entry.target.id == message.author.id and
                    entry.extra and entry.extra.channel.id == message.channel.id):
                audit_user = entry.user
                break

        if audit_user and audit_user.id != message.author.id:
            msg = f"🗑️ {audit_user.mention} deleted a message by {message.author.mention} in {message.channel.mention}\n" \
                f"**Content:** {message.content or '*[no text]*'}"
        else:
            msg = f"🗑️ Message by {message.author.mention} deleted in {message.channel.mention}\n" \
                f"**Content:** {message.content or '*[no text]*'}"

        if attachments:
            msg += f"\n{attachments}"

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
        changes = []

        fields = [
            ("name", "Name"),
            ("topic", "Topic"),
            ("nsfw", "NSFW"),
            ("slowmode_delay", "Slowmode"),
            ("bitrate", "Bitrate"),
            ("user_limit", "User limit"),
            ("position", "Position"),
            ("rtc_region", "Voice region"),
            ("video_quality_mode", "Video quality"),
            ("default_auto_archive_duration", "Auto archive duration"),
            ("default_thread_slowmode_delay", "Thread slowmode"),
            ("default_sort_order", "Sort order"),
            ("default_reaction_emoji", "Default reaction emoji"),
        ]

        for attr, label in fields:
            if hasattr(before, attr) and hasattr(after, attr):
                old = getattr(before, attr)
                new = getattr(after, attr)

                if old != new:
                    changes.append(
                        f"**{label}:** `{self.format_value(old)}` → `{self.format_value(new)}`"
                    )

        if hasattr(before, "category") and before.category != after.category:
            old = before.category.name if before.category else "None"
            new = after.category.name if after.category else "None"
            changes.append(f"**Category:** `{old}` → `{new}`")

        if hasattr(before, "overwrites") and before.overwrites != after.overwrites:
            changes.extend(self.diff_overwrites(before, after))

        if not changes:
            changes.append("Unknown channel settings changed.")

        audit_user = None

        audit_actions = [discord.AuditLogAction.channel_update]

        if hasattr(before, "overwrites") and before.overwrites != after.overwrites:
            audit_actions = [
                discord.AuditLogAction.overwrite_create,
                discord.AuditLogAction.overwrite_update,
                discord.AuditLogAction.overwrite_delete,
                discord.AuditLogAction.channel_update,
            ]

        for action in audit_actions:
            for _ in range(5):
                try:
                    async for entry in before.guild.audit_logs(limit=10, action=action):
                        is_recent = (
                            entry.user
                            and (discord.utils.utcnow() - entry.created_at).total_seconds() < 60
                        )
                        
                        if not is_recent:
                            continue
                        
                        if entry.target and getattr(entry.target, "id", None) == after.id:
                            audit_user = entry.user
                            break

                        extra = getattr(entry, "extra", None)
                        extra_channel = getattr(extra, "channel", None)

                        if extra_channel and getattr(extra_channel, "id", None) == after.id:
                            audit_user = entry.user
                            break

                        if audit_user:
                            break

                except discord.Forbidden:
                    pass

                await asyncio.sleep(1)

                if audit_user:
                    break

        user_text = audit_user.mention if audit_user else "Unknown moderator"

        channel_text = after.mention if hasattr(after, "mention") else f"`{after.name}`"

        await self.log(
            before.guild,
            f"⚙️ {user_text} updated channel: {channel_text}\n"
            + "\n".join(changes)
        )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await self.db.del_autoroles(guild.id)
        await self.db.del_log_channel(guild.id)
        await self.db.clear_guild(guild.id)
