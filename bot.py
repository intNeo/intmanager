import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db import Database
from cogs.autorole import AutoRole
from cogs.logger import Logger
from cogs.loggerserver import LoggerServer
from cogs.general import General

load_dotenv(os.getenv("ENV_FILE", "config/.env"))
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True

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
        self.tree.on_error = self.on_app_command_error
        await self.tree.sync()
    
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        from discord.app_commands import CheckFailure
        if isinstance(error, CheckFailure):
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
bot.run(TOKEN)