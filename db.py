import aiosqlite

class Database:
    def __init__(self, path="data/data.db"):
        self.path = path

    async def setup(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS autoroles (
                guild_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )""")
            await db.execute("""CREATE TABLE IF NOT EXISTS logchannels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER
            )""")
            await db.commit()

    async def add_autorole(self, guild_id: int, role_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO autoroles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
            await db.commit()

    async def remove_autorole(self, guild_id: int, role_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM autoroles WHERE guild_id = ? AND role_id = ?", (guild_id, role_id))
            await db.commit()

    async def del_autoroles(self, guild_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM autoroles WHERE guild_id = ?", (guild_id,))
            await db.commit()

    async def get_autoroles(self, guild_id: int) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT role_id FROM autoroles WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows] if rows else []

    async def set_log_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("REPLACE INTO logchannels (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
            await db.commit()

    async def del_log_channel(self, guild_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM logchannels WHERE guild_id = ?", (guild_id,))
            await db.commit()

    async def get_log_channel(self, guild_id: int):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT channel_id FROM logchannels WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def clear_guild(self, guild_id: int):
        await self.del_autoroles(guild_id)
        await self.del_log_channel(guild_id)
