import discord
from discord.ext import commands, tasks
from db import Database


class LoggerServer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
        self.active_timeouts = {}
        self._ready_scanned = False

    async def cog_load(self):
        self.timeout_watcher.start()

    async def cog_unload(self):
        self.timeout_watcher.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_scanned:
            return

        self._ready_scanned = True
        now = discord.utils.utcnow()

        for guild in self.bot.guilds:
            for member in guild.members:
                if member.timed_out_until and member.timed_out_until > now:
                    self.active_timeouts[(guild.id, member.id)] = member.timed_out_until

    @tasks.loop(seconds=30)
    async def timeout_watcher(self):
        now = discord.utils.utcnow()

        for (guild_id, member_id), until in list(self.active_timeouts.items()):
            if now < until:
                continue

            guild = self.bot.get_guild(guild_id)
            if not guild:
                self.active_timeouts.pop((guild_id, member_id), None)
                continue

            try:
                member = await guild.fetch_member(member_id)
            except discord.NotFound:
                self.active_timeouts.pop((guild_id, member_id), None)
                continue
            except (discord.Forbidden, discord.NotFound):
                continue

            if not member.timed_out_until or member.timed_out_until <= now:
                await self.log(
                    guild,
                    f"⌛ Timeout expired for {member.mention}"
                )
                self.active_timeouts.pop((guild_id, member_id), None)
            else:
                self.active_timeouts[(guild_id, member_id)] = member.timed_out_until
    
    async def log(self, guild, message):
        channel_id = await self.db.get_log_channel(guild.id)
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        perms = channel.permissions_for(guild.me)
        if not perms.send_messages:
            return

        embed = discord.Embed(description=message, color=discord.Color.orange())

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.NotFound):
            pass

    def diff_role_permissions(self, before_perms, after_perms):
        changes = []

        before_dict = dict(before_perms)
        after_dict = dict(after_perms)

        for perm in sorted(set(before_dict.keys()) | set(after_dict.keys())):
            old = before_dict.get(perm)
            new = after_dict.get(perm)

            if old != new:
                changes.append(f"• `{perm}`: `{old}` → `{new}`")

        return changes

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        audit_user = None

        try:
            async for entry in role.guild.audit_logs(
                limit=5,
                action=discord.AuditLogAction.role_create
            ):
                if entry.target and entry.target.id == role.id:
                    audit_user = entry.user
                    break
        except (discord.Forbidden, discord.NotFound):
            return

        user_text = audit_user.mention if audit_user else "Someone"

        await self.log(
            role.guild,
            f"🆕 {user_text} created role: {role.mention}\n"
            f"**Name:** `{role.name}`\n"
            f"**Color:** `{role.color}`\n"
            f"**Hoist:** `{role.hoist}`\n"
            f"**Mentionable:** `{role.mentionable}`"
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        audit_user = None

        try:
            async for entry in role.guild.audit_logs(
                limit=5,
                action=discord.AuditLogAction.role_delete
            ):
                if entry.target and entry.target.id == role.id:
                    audit_user = entry.user
                    break
        except (discord.Forbidden, discord.NotFound):
            return

        user_text = audit_user.mention if audit_user else "Someone"

        await self.log(
            role.guild,
            f"❌ {user_text} deleted role: `{role.name}`"
        )

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []

        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")

        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` → `{after.color}`")

        if before.hoist != after.hoist:
            changes.append(f"**Displayed separately:** `{before.hoist}` → `{after.hoist}`")

        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`")

        if before.position != after.position:
            changes.append(f"**Position:** `{before.position}` → `{after.position}`")

        if before.permissions != after.permissions:
            perm_changes = self.diff_role_permissions(
                before.permissions,
                after.permissions
            )

            if perm_changes:
                changes.append("**Permissions changed:**")
                changes.extend(perm_changes)

        if not changes:
            changes.append("Unknown role settings changed.")

        audit_user = None

        try:
            async for entry in before.guild.audit_logs(
                limit=5,
                action=discord.AuditLogAction.role_update
            ):
                if entry.target and entry.target.id == after.id:
                    audit_user = entry.user
                    break
        except (discord.Forbidden, discord.NotFound):
            return

        user_text = audit_user.mention if audit_user else "Someone"

        await self.log(
            after.guild,
            f"⚙️ {user_text} updated role: {after.mention}\n"
            + "\n".join(changes)
        )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Роли
        if before.roles != after.roles:
            before_roles = set(before.roles)
            after_roles = set(after.roles)

            added_roles = after_roles - before_roles
            removed_roles = before_roles - after_roles

            audit_user = None

            try:
                async for entry in after.guild.audit_logs(
                    limit=5,
                    action=discord.AuditLogAction.member_role_update
                ):
                    if entry.target and entry.target.id == after.id:
                        audit_user = entry.user
                        break
            except (discord.Forbidden, discord.NotFound):
                return

            user_text = audit_user.mention if audit_user else "Someone"

            for role in added_roles:
                if role.name != "@everyone":
                    await self.log(
                        after.guild,
                        f"➕ {user_text} gave role {role.mention} to {after.mention}"
                    )

            for role in removed_roles:
                if role.name != "@everyone":
                    await self.log(
                        after.guild,
                        f"➖ {user_text} removed role `{role.name}` from {after.mention}"
                    )

        # Выдача timeout
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                self.active_timeouts[(after.guild.id, after.id)] = after.timed_out_until
                audit_user = None

                try:
                    async for entry in after.guild.audit_logs(
                        limit=5,
                        action=discord.AuditLogAction.member_update
                    ):
                        if entry.target and entry.target.id == after.id:
                            audit_user = entry.user
                            break
                except (discord.Forbidden, discord.NotFound):
                    pass

                user_text = audit_user.mention if audit_user else "Someone"

                await self.log(
                    after.guild,
                    f"⏳ {user_text} timed out {after.mention} until "
                    f"{after.timed_out_until.strftime('%Y-%m-%d %H:%M:%S')}"
                )

        # Снятие timeout / истечение timeout
        if before.timed_out_until and not after.timed_out_until:
            self.active_timeouts.pop((after.guild.id, after.id), None)
            audit_user = None

            try:
                async for entry in after.guild.audit_logs(
                    limit=5,
                    action=discord.AuditLogAction.member_update
                ):
                    if (
                        entry.target
                        and entry.target.id == after.id
                        and entry.user
                        and (discord.utils.utcnow() - entry.created_at).total_seconds() < 15
                    ):
                        audit_user = entry.user
                        break
            except (discord.Forbidden, discord.NotFound):
                pass

            if audit_user:
                await self.log(
                    after.guild,
                    f"🔓 {audit_user.mention} removed timeout from {after.mention}"
                )
            else:
                await self.log(
                    after.guild,
                    f"⌛ Timeout expired for {after.mention}"
                )

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        changes = []

        if before.name != after.name:
            changes.append(f"**Server name:** `{before.name}` → `{after.name}`")

        if before.description != after.description:
            changes.append(f"**Description:** `{before.description}` → `{after.description}`")

        if before.verification_level != after.verification_level:
            changes.append(
                f"**Verification level:** `{before.verification_level}` → `{after.verification_level}`"
            )

        if before.default_notifications != after.default_notifications:
            changes.append(
                f"**Default notifications:** `{before.default_notifications}` → `{after.default_notifications}`"
            )

        if before.explicit_content_filter != after.explicit_content_filter:
            changes.append(
                f"**Content filter:** `{before.explicit_content_filter}` → `{after.explicit_content_filter}`"
            )

        if before.afk_channel != after.afk_channel:
            old = before.afk_channel.mention if before.afk_channel else "None"
            new = after.afk_channel.mention if after.afk_channel else "None"
            changes.append(f"**AFK channel:** {old} → {new}")

        if before.afk_timeout != after.afk_timeout:
            changes.append(f"**AFK timeout:** `{before.afk_timeout}` → `{after.afk_timeout}`")

        if not changes:
            changes.append("Unknown server settings changed.")

        audit_user = None

        try:
            async for entry in after.audit_logs(
                limit=5,
                action=discord.AuditLogAction.guild_update
            ):
                audit_user = entry.user
                break
        except (discord.Forbidden, discord.NotFound):
            return

        user_text = audit_user.mention if audit_user else "Someone"

        await self.log(
            after,
            f"⚙️ {user_text} updated server settings\n"
            + "\n".join(changes)
        )