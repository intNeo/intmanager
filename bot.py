import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db import Database
from cogs.autorole import AutoRole
from cogs.logger import Logger
from cogs.loggerserver import LoggerServer
from cogs.general import General
from cogs.music import Music

load_dotenv(os.getenv("ENV_FILE", "config/.env"))
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.guilds = True

class AutoRoleBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database()

    async def setup_hook(self):
        await self.db.setup()
        await self.add_cog(AutoRole(self))
        await self.add_cog(Logger(self))
        await self.add_cog(LoggerServer(self))
        await self.add_cog(General(self))
        await self.add_cog(Music(self))
        
        self.tree.on_error = self.on_app_command_error

        # Глобальная синхронизация команд
        try:
            global_synced = await self.tree.sync()
            print(f"🌍 Synced global commands: {len(global_synced)}")
        except Exception as e:
            print(f"❌ Failed to sync global commands: {e}")
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        from discord.app_commands import CheckFailure
        if isinstance(error, CheckFailure):
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ You do not have administrator permissions for this command.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ You do not have administrator permissions for this command.",
                    ephemeral=True
                )
        else:
            raise error  # для других ошибок

bot = AutoRoleBot()
@bot.event
async def on_ready():
    print(f"✅ Bot is started: {bot.user}")
    print('Creator intNeo for intNeo Production server.')
    activity = discord.Activity(type=discord.ActivityType.listening, name="/help")
    await bot.change_presence(status=discord.Status.online, activity=activity)
@bot.event
async def on_guild_join(guild):
    print(f"✅ Bot joined new guild: {guild.name} ({guild.id})")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set. Check config/.env or ENV_FILE path."
    )
bot.run(TOKEN)