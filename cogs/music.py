import asyncio
import discord
import yt_dlp

from discord import app_commands
from discord.ext import commands


YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class MusicTrack:
    def __init__(self, title, url, webpage_url, requester):
        self.title = title
        self.url = url
        self.webpage_url = webpage_url
        self.requester = requester


class Music(commands.GroupCog, name="music"):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current = {}
        self.repeat = {}
        self.replay_requested = set()
        self.db = bot.db

    async def get_music_text_channel(self, guild: discord.Guild, fallback_channel):
        channel_id = await self.db.get_music_channel(guild.id)

        if not channel_id:
            return fallback_channel

        channel = guild.get_channel(channel_id)

        if not channel:
            return fallback_channel

        return channel
    
    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = asyncio.Queue()
        return self.queues[guild_id]

    async def search_track(self, query, requester):
        loop = asyncio.get_running_loop()

        def extract():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                return ydl.extract_info(query, download=False)

        data = await loop.run_in_executor(None, extract)

        if "entries" in data:
            data = data["entries"][0]

        return MusicTrack(
            title=data.get("title", "Unknown title"),
            url=data["url"],
            webpage_url=data.get("webpage_url", query),
            requester=requester,
        )

    async def ensure_voice(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(
                "❌ You must be in a voice channel.",
                ephemeral=True,
            )
            return None

        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client

        try:
            if voice_client and voice_client.is_connected():
                if voice_client.channel != voice_channel:
                    await voice_client.move_to(voice_channel)
            else:
                if voice_client:
                    await voice_client.disconnect(force=True)

                await voice_channel.connect(
                    timeout=45,
                    reconnect=True,
                    self_deaf=True,
                )

        except TimeoutError:
            await interaction.followup.send(
                "❌ Voice connection timed out. Try again or change the voice region.",
                ephemeral=True,
            )
            return None

        except Exception as exc:
            await interaction.followup.send(
                f"❌ Failed to connect to voice: `{exc}`",
                ephemeral=True,
            )
            return None

        return interaction.guild.voice_client
    
    async def play_next(self, interaction_or_guild, text_channel):
        guild = (
            interaction_or_guild.guild
            if hasattr(interaction_or_guild, "guild")
            else interaction_or_guild
        )

        queue = self.get_queue(guild.id)
        voice = guild.voice_client
        track = None

        if guild.id in self.replay_requested:
            self.replay_requested.remove(guild.id)
            track = self.current.get(guild.id)

        elif self.repeat.get(guild.id) and self.current.get(guild.id):
            track = self.current[guild.id]

        else:
            if queue.empty():
                self.current.pop(guild.id, None)
                return

            track = await queue.get()
            self.current[guild.id] = track

        if not track:
            return

        if not voice or not voice.is_connected():
            return

        source = discord.FFmpegPCMAudio(
            track.url,
            before_options=FFMPEG_OPTIONS["before_options"],
            options=FFMPEG_OPTIONS["options"],
        )

        def after_play(error):
            if error:
                print(f"Music playback error: {error}")

            future = asyncio.run_coroutine_threadsafe(
                self.play_next(guild, text_channel),
                self.bot.loop,
            )

            try:
                future.result()
            except Exception as exc:
                print(f"Music next track error: {exc}")

        voice.play(source, after=after_play)

        embed = discord.Embed(
            title="🎶 Now playing",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.green(),
        )
        embed.add_field(name="Requested by", value=track.requester.mention, inline=True)

        music_channel = await self.get_music_text_channel(guild, text_channel)
        await music_channel.send(embed=embed)

    @app_commands.command(name="add", description="Set music text channel")
    @app_commands.describe(channel="Text channel for music messages")
    @app_commands.checks.has_permissions(administrator=True)
    async def add(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.db.set_music_channel(interaction.guild.id, channel.id)

        await interaction.response.send_message(
            f"✅ Music channel set to {channel.mention}",
            ephemeral=True,
        )


    @app_commands.command(name="delete", description="Remove music text channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction):
        await self.db.delete_music_channel(interaction.guild.id)

        await interaction.response.send_message(
            "🗑️ Music channel removed.",
            ephemeral=True,
        )


    @app_commands.command(name="show", description="Show current music text channel")
    async def show(self, interaction: discord.Interaction):
        channel_id = await self.db.get_music_channel(interaction.guild.id)

        if not channel_id:
            await interaction.response.send_message(
                "📭 Music channel is not set.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(channel_id)

        await interaction.response.send_message(
            f"🎵 Current music channel: {channel.mention if channel else '`Deleted channel`'}",
            ephemeral=True,
        )
    
    @app_commands.command(name="play", description="Play music from YouTube URL or search query")
    @app_commands.describe(query="YouTube URL or search query")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        voice_client = await self.ensure_voice(interaction)
        if not voice_client:
            return

        try:
            track = await self.search_track(query, interaction.user)
        except Exception as exc:
            await interaction.followup.send(
                f"❌ Failed to load track: `{exc}`",
                ephemeral=True,
            )
            return

        queue = self.get_queue(interaction.guild.id)
        await queue.put(track)

        await interaction.followup.send(
            f"✅ Added to queue: **{track.title}**",
            ephemeral=True
        )

        voice_client = interaction.guild.voice_client

        if voice_client and not voice_client.is_playing() and not voice_client.is_paused():
            await self.play_next(interaction, interaction.channel)

    @app_commands.command(name="pause", description="Pause current track")
    async def pause(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client

        if not voice or not voice.is_playing():
            await interaction.response.send_message(
                "❌ Nothing is playing.",
                ephemeral=True,
            )
            return

        voice.pause()
        await interaction.response.send_message(
                "⏸️ Playback paused.",
                ephemeral=True
            )

    @app_commands.command(name="resume", description="Resume current track")
    async def resume(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client

        if not voice or not voice.is_paused():
            await interaction.response.send_message(
                "❌ Playback is not paused.",
                ephemeral=True,
            )
            return

        voice.resume()
        await interaction.response.send_message(
                "▶️ Playback resumed.",
                ephemeral=True
            )

    @app_commands.command(name="skip", description="Skip current track")
    async def skip(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client

        if not voice or not voice.is_playing():
            await interaction.response.send_message(
                "❌ Nothing is playing.",
                ephemeral=True,
            )
            return

        voice.stop()
        await interaction.response.send_message(
                "⏭️ Track skipped.",
                ephemeral=True
            )

    @app_commands.command(name="stop", description="Stop playback and clear queue")
    async def stop(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client

        queue = self.get_queue(interaction.guild.id)

        while not queue.empty():
            try:
                queue.get_nowait()
                queue.task_done()
            except asyncio.QueueEmpty:
                break

        self.current.pop(interaction.guild.id, None)

        if voice:
            voice.stop()
            await voice.disconnect()

        await interaction.response.send_message(
                "⏹️ Playback stopped and queue cleared.",
                ephemeral=True
            )

    @app_commands.command(name="queue", description="Show current music queue")
    async def queue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)

        if queue.empty():
            await interaction.response.send_message(
                "📭 Queue is empty.",
                ephemeral=True,
            )
            return

        tracks = list(queue._queue)

        description = "\n".join(
            f"`{index + 1}.` [{track.title}]({track.webpage_url}) — {track.requester.mention}"
            for index, track in enumerate(tracks[:10])
        )

        if len(tracks) > 10:
            description += f"\n\nAnd **{len(tracks) - 10}** more..."

        embed = discord.Embed(
            title="🎵 Music queue",
            description=description,
            color=discord.Color.blurple(),
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @app_commands.command(name="nowplaying", description="Show current track")
    async def nowplaying(self, interaction: discord.Interaction):
        track = self.current.get(interaction.guild.id)

        if not track:
            await interaction.response.send_message(
                "❌ Nothing is playing.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🎶 Now playing",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.green(),
        )
        embed.add_field(name="Requested by", value=track.requester.mention, inline=True)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @app_commands.command(name="repeat", description="Toggle repeat for current track")
    async def repeat(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id

        if not self.current.get(guild_id):
            await interaction.response.send_message(
                "❌ Nothing is playing.",
                ephemeral=True,
            )
            return

        self.repeat[guild_id] = not self.repeat.get(guild_id, False)
        status = "enabled" if self.repeat[guild_id] else "disabled"

        await interaction.response.send_message(
            f"🔁 Repeat is now **{status}**.",
            ephemeral=True,
        )


    @app_commands.command(name="replay", description="Restart current track")
    async def replay(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client
        guild_id = interaction.guild.id

        if not voice or not self.current.get(guild_id):
            await interaction.response.send_message(
                "❌ Nothing is playing.",
                ephemeral=True,
            )
            return

        self.replay_requested.add(guild_id)
        voice.stop()

        await interaction.response.send_message(
            f"🔄 Restarting: **{self.current[guild_id].title}**",
            ephemeral=True,
        )

async def setup(bot):
    await bot.add_cog(Music(bot))