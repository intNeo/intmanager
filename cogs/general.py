import discord
from discord.ext import commands
from discord import app_commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show the list of available commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📘 Help",
            description="List of available commands:",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🛠️ Auto-role management (`/role`):",
            value=(
                "`/role add <role>` — Add an auto-role\n"
                "`/role delete <role>` — Remove an auto-role\n"
                "`/role show` — Show current auto-roles"
            ),
            inline=False
        )

        embed.add_field(
            name="📋 Log channel management (`/log`):",
            value=(
                "`/log add <channel>` — Set log channel\n"
                "`/log delete` — Remove log channel\n"
                "`/log show` — Show current log channel"
            ),
            inline=False
        )

        embed.add_field(
            name="🎵 Music commands (`/music`):",
            value=(
                "`/music add <channel>` — Set music text channel\n"
                "`/music delete` — Remove music text channel\n"
                "`/music show` — Show current music text channel\n"
                "`/music play <url/query>` — Play music from YouTube or search query\n"
                "`/music pause` — Pause current track\n"
                "`/music resume` — Resume paused track\n"
                "`/music skip` — Skip current track\n"
                "`/music stop` — Stop playback and clear queue\n"
                "`/music queue` — Show current queue\n"
                "`/music nowplaying` — Show currently playing track\n"
                "`/music repeat` — Toggle current track repeat\n"
                "`/music replay` — Restart current track\n"
            ),
            inline=False
        )

        embed.add_field(
            name="ℹ️ Info:",
            value="`/help` — Show this help menu",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
