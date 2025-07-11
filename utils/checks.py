from discord import Interaction
from discord.app_commands import check, CheckFailure

def is_admin():
    async def predicate(interaction: Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            raise CheckFailure("Требуются права администратора.")
        return True
    return check(predicate)
