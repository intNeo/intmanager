import discord
from discord import app_commands
from discord.ext import commands
from db import Database
from utils.checks import is_admin

class AutoRole(commands.GroupCog, name="role"):
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db

    @is_admin()
    @app_commands.command(name="add", description="Add auto-role")
    async def add(self, interaction: discord.Interaction, role: discord.Role):
        await self.db.add_autorole(interaction.guild.id, role.id)
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Auto-role added", description=role.mention, color=discord.Color.green()), ephemeral=True)

    @is_admin()
    @app_commands.command(name="delete", description="Remove auto-role")
    async def delete(self, interaction: discord.Interaction, role: discord.Role):
        await self.db.remove_autorole(interaction.guild.id, role.id)
        await interaction.response.send_message(embed=discord.Embed(
            title="🗑️ Auto-role removed", description=role.mention, color=discord.Color.red()), ephemeral=True)

    @is_admin()
    @app_commands.command(name="show", description="Show current auto-roles")
    async def show(self, interaction: discord.Interaction):
        role_ids = await self.db.get_autoroles(interaction.guild.id)
        if not role_ids:
            content = "No auto-roles set."
        else:
            roles = [interaction.guild.get_role(rid) for rid in role_ids]
            roles = [r.mention for r in roles if r]
            content = "Given roles: " + ", ".join(roles)

        await interaction.response.send_message(embed=discord.Embed(
            title="📌 Auto-roles", description=content, color=discord.Color.blurple()), ephemeral=True)