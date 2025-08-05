"""Music cog for music-related commands."""

import typing
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.audio.types import AudioPlayer, AudioQueue, RepeatMode
from cogs.audio.utils import format_duration, volume_bar
from cogs.music.music_source import MusicSource

if TYPE_CHECKING:
    from bot import DiscordBot


class MusicQueue(AudioQueue):
    """A queue for music."""

    def __init__(self, bot: "DiscordBot"):
        super().__init__(bot)


class MusicPlayer(AudioPlayer):
    """A music player with features like now playing messages and volume controls."""

    def __init__(self, bot: "DiscordBot", guild: discord.Guild):
        super().__init__(bot, guild)
        self.queue = MusicQueue(bot)  # Use MusicQueue instead of AudioQueue
        # Now playing and volume messages
        self.np_message = None
        self.volume_message = None

    async def send_now_playing(
        self, text_channel: discord.TextChannel
    ) -> Optional[discord.Message]:
        """Sends a Now Playing message, if possible also deletes the last one"""
        # Delete the last message if it exists
        if self.np_message:
            await self.bot.messaging.delete_message(self.np_message)
        self.np_message = None

        # Queue is empty, delete previous now_playing messages
        if self.queue.current_track is None:
            await self.bot.messaging.send_embed(
                text_channel, text="Nothing is playing right now."
            )
            return None

        track = self.queue.current_track

        # Add user's name and track duration to footer (if user info is available)
        footer_parts = []
        if hasattr(track, "user") and track.user:
            duration = format_duration(track.duration - track.position)
            footer_parts.append(f"@{track.user.display_name} ({duration})")

        # Add "Up next" to footer if something is in the queue
        if len(self.queue.tracks) > self.queue.position + 1:
            next_track = self.queue.tracks[self.queue.position + 1]
            footer_parts.append(
                f"Up next: {next_track.title or next_track.name or 'Unknown'}"
            )

        footer = " ".join(footer_parts) if footer_parts else None
        footer_icon = None
        if hasattr(track, "user") and track.user:
            footer_icon = (
                track.user.display_avatar.with_size(64).with_static_format("png").url
            )

        # Create a link using the track name.
        link = (
            f"[{track.title}]({track.youtube_url})"
            if track.youtube_url
            else track.title
        )

        # Send the new message
        self.np_message = await self.bot.messaging.send_embed(
            channel=text_channel,
            color=0xFF69B4,
            title="Now Playing ♫",
            text=link,
            thumbnail=track.thumbnail,
            footer=footer,
            footer_icon=footer_icon,
        )

        # Add emoji controls
        if self.np_message:
            await self.bot.messaging.add_reactions(
                self.np_message,
                [
                    "⏮️",  # previous
                    "▶️",  # resume
                    "⏸",  # pause
                    "⏭️",  # skip
                    "🛑",  # stop
                ],
            )

        return self.np_message

    async def update_now_playing_status(self, title: str) -> None:
        """Updates the now playing message title (e.g., 'Now Playing' vs 'Now Paused')"""
        if self.np_message and self.np_message.embeds:
            try:
                await self.bot.messaging.edit_embed(
                    message=self.np_message, title=title
                )
            except discord.errors.NotFound:
                pass

    async def send_volume(
        self, interaction: discord.Interaction
    ) -> Optional[discord.Message]:
        """Sends a volume message, if possible also deletes the last one"""
        if self.volume_message:
            await self.bot.messaging.delete_message(self.volume_message)
        self.volume_message = None

        # Send the new message
        self.volume_message = await self.bot.messaging.send_embed(
            interaction,
            color=0x22FF33,
            title=f"Current volume: {self.volume * 100}%",
            text=volume_bar(self.volume),
        )

        # Add emoji controls
        if self.volume_message:
            await self.bot.messaging.add_reactions(
                self.volume_message,
                [
                    "⏬",  # volume down 5
                    "⬇",  # volume down 1
                    "⬆",  # volume up 1
                    "⏫",  # volume up 5
                    "✳",  # volume set 20
                ],
            )

        return self.volume_message

    async def update_volume_message(self, user: discord.Member) -> None:
        """Updates the last sent volume message"""
        if self.volume_message is None:
            return

        try:
            await self.bot.messaging.edit_embed(
                message=self.volume_message,
                title=f"Current volume: {self.volume * 100}%",
                text=volume_bar(self.volume),
                footer=f"Changed by {user.display_name}",
                footer_icon=user.display_avatar.with_size(64)
                .with_static_format("png")
                .url,
            )
        except discord.errors.NotFound:
            pass

    # Override methods to work with now playing messages
    async def pause(self) -> None:
        """Pause playback."""
        await super().pause()
        await self.update_now_playing_status("Now Paused ♫")

    async def resume(self) -> None:
        """Resume playback."""
        await super().resume()
        await self.update_now_playing_status("Now Playing ♫")

    async def stop(self) -> None:
        """Clear the queue and stop playback."""
        await super().stop()

        # Clean up music-specific messages
        if self.np_message:
            await self.bot.messaging.delete_message(self.np_message)
            self.np_message = None
        if self.volume_message:
            await self.bot.messaging.delete_message(self.volume_message)
            self.volume_message = None


class Music(commands.Cog):
    """A cog for music-related commands."""

    def __init__(self, bot: "DiscordBot"):
        self.bot = bot
        self.music_source = MusicSource(
            youtube_api_key=self.bot.secrets.get("YOUTUBE_API_KEY"),
            spotify_client_id=self.bot.secrets.get("SPOTIFY_CLIENT_ID"),
            spotify_client_secret=self.bot.secrets.get("SPOTIFY_CLIENT_SECRET"),
        )
        # Music-specific player management
        self.music_players = {}  # type: typing.Dict[discord.Guild, MusicPlayer]

    def get_music_player(self, guild: discord.Guild) -> MusicPlayer:
        """Get or create a MusicPlayer for the guild."""
        if guild not in self.music_players:
            self.music_players[guild] = MusicPlayer(self.bot, guild)
        return self.music_players[guild]

    async def _update_queued_message(
        self,
        message: discord.Message,
        tracks: list[typing.Any],
        query: str,
        playlist: Optional[dict[str, typing.Any]] = None,
    ) -> None:
        """Helper function to send a queued message."""
        self.bot.log(f"Updating queued message for {tracks}")
        # Generate the response based on number of tracks and playlist info
        if len(tracks) == 1:
            track = tracks[0]
            # Create a link using the track name and url if available
            link = (
                f"[{track.title}]({track.youtube_url})"
                if hasattr(track, "youtube_url") and track.youtube_url
                else track.title
            )
            response = f"Queued {link}"
        elif playlist is not None:
            response = f"Queued **{len(tracks)}** tracks from [{playlist['name']}]({playlist['external_urls']['spotify']})"
        else:
            response = f"Queued **{len(tracks)}** tracks"

        # Add the query command
        response += f"\n```/play {query}```"

        # Send the embed
        await self.bot.messaging.edit_embed(
            message,
            text=response,
            color=discord.Color.green(),
        )

    async def _ensure_guild_command(self, interaction: discord.Interaction) -> bool:
        """Check if the command is being used in a server. Send error and return False if not."""
        if not interaction.guild:
            await self.bot.messaging.send_error(
                interaction,
                text="This command can only be used in a server.",
            )
            return False
        return True

    @app_commands.command(
        name="shuffle",
        description="Shuffles the queue.",
    )
    async def shuffle(self, interaction: discord.Interaction):
        """Shuffle the queue."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)
        await player.queue.shuffle()
        await self.bot.messaging.send_embed(
            interaction,
            title="Shuffled",
            text="The queue has been shuffled.",
            color=discord.Color.blue(),
        )

    @app_commands.command(
        name="repeat",
        description="Sets the repeat mode of the player.",
    )
    async def repeat(
        self,
        interaction: discord.Interaction,
        mode: RepeatMode,
    ):
        """Set the repeat mode of the player."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)
        player.queue.repeat_mode = mode
        await self.bot.messaging.send_embed(
            interaction,
            title="Repeat Mode",
            text=f"Repeat mode set to {mode.name.lower()}.",
            color=discord.Color.blue(),
        )

    @app_commands.command(
        name="volume",
        description="Sets the volume of the player.",
    )
    async def volume(self, interaction: discord.Interaction, volume: int):
        """Set the volume of the player."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)
        player.set_volume(volume / 100)

        # Send volume message
        if isinstance(interaction.channel, discord.TextChannel) and isinstance(
            interaction.user, discord.Member
        ):
            await player.send_volume(interaction)

    @app_commands.command(
        name="nowplaying",
        description="Displays the currently playing track.",
    )
    async def nowplaying(self, interaction: discord.Interaction):
        """Display the currently playing track."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)

        # Send now playing message
        if isinstance(interaction.channel, discord.TextChannel):
            await player.send_now_playing(interaction.channel)

    @app_commands.command(
        name="queue",
        description="Displays the current queue.",
    )
    async def queue(self, interaction: discord.Interaction):
        """Display the current queue."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)
        # Use the built-in format_queue method for better formatting
        queue_text = player.queue.format_queue()
        await self.bot.messaging.send_embed(
            interaction,
            title="Song Queue ♫",
            text=queue_text,
            color=discord.Color.blue(),
        )

    @app_commands.command(
        name="stop",
        description="Stops playback and clears the queue.",
    )
    async def stop(self, interaction: discord.Interaction):
        """Stop playback and clear the queue."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)
        await player.stop()
        await self.bot.messaging.send_embed(
            interaction,
            title="Stopped",
            text="Playback has been stopped and the queue has been cleared.",
            color=discord.Color.red(),
        )

    @app_commands.command(
        name="skip",
        description="Skips the currently playing track.",
    )
    async def skip(self, interaction: discord.Interaction, count: int = 1):
        """Skip the currently playing track."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)
        skipped_tracks = await player.skip(count)
        if skipped_tracks:
            await self.bot.messaging.send_embed(
                interaction,
                title="Skipped",
                text=f"Skipped {len(skipped_tracks)} track(s).",
                color=discord.Color.green(),
            )
        else:
            await self.bot.messaging.send_embed(
                interaction,
                title="Error",
                text="There are no more tracks to skip.",
                color=discord.Color.red(),
            )

    @app_commands.command(
        name="resume",
        description="Resumes the currently paused track.",
    )
    async def resume(self, interaction: discord.Interaction):
        """Resume the currently paused track."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)
        await player.resume()
        await self.bot.messaging.send_embed(
            interaction,
            title="Resumed",
            text="Playback has been resumed.",
            color=discord.Color.green(),
        )

    @app_commands.command(
        name="pause",
        description="Pauses the currently playing track.",
    )
    async def pause(self, interaction: discord.Interaction):
        """Pause the currently playing track."""
        if not await self._ensure_guild_command(interaction):
            return
        assert interaction.guild is not None  # Type guard

        player = self.get_music_player(interaction.guild)
        await player.pause()
        await self.bot.messaging.send_embed(
            interaction,
            title="Paused",
            text="Playback has been paused.",
            color=discord.Color.orange(),
        )

    @app_commands.command(
        name="play",
        description="Play a song from YouTube or Spotify.",
    )
    async def play(
        self,
        interaction: discord.Interaction,
        query: str,
        voice_channel: Optional[discord.VoiceChannel] = None,
    ):
        """Play a song from a URL or search query."""
        if not interaction.user:
            return

        # Respond immediately to avoid timeouts
        reply = await self.bot.messaging.send_embed(
            interaction,
            text=f"Searching for track 🔍\n```/play {query}```",
            color=discord.Color.blue(),
            footer=f"Requested by @{interaction.user.display_name}",
            footer_icon=interaction.user.display_avatar.with_size(64)
            .with_static_format("png")
            .url,
        )

        # Basic validation
        if not interaction.guild:
            await self.bot.messaging.send_error(
                interaction,
                text="This command can only be used in a server.",
            )
            return

        # Log with safe channel name
        channel_name = getattr(
            interaction.channel, "name", "DM" if interaction.channel else "Unknown"
        )
        self.bot.log(f"Playing {query} in {channel_name}")

        if not isinstance(interaction.user, discord.Member):
            self.bot.log(f"User {interaction.user} is not a member")
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            self.bot.log(f"Channel {interaction.channel} is not a text channel")
            return

        # Check if user has voice access and get their voice channel if not specified
        if not await self.bot.utils.user_has_voice(
            interaction.user, interaction.channel, "play music"
        ):
            self.bot.log(f"User {interaction.user} does not have a voice channel")
            return

        # Get the user's voice channel if not specified
        if voice_channel is None:
            if interaction.user.voice and interaction.user.voice.channel:
                if isinstance(interaction.user.voice.channel, discord.VoiceChannel):
                    voice_channel = interaction.user.voice.channel
                else:
                    await self.bot.messaging.send_error(
                        interaction.channel,
                        text="You must be in a voice channel (not stage channel).",
                    )
                    return
            else:
                await self.bot.messaging.send_error(
                    interaction.channel,
                    text="You must be in a voice channel or specify one.",
                )
                return

        self.bot.log(f"Voice channel: {voice_channel}")

        self.bot.log(f"Getting track for {query}")
        track = await self.music_source.get_track(query)

        self.bot.log(f"Playing {track}")

        if track is None:
            await self.bot.messaging.send_error(
                interaction.channel,
                text=f"Could not find a track for `{query}`.",
            )
            return

        player = self.get_music_player(interaction.guild)
        # Set the user who requested the track
        track.user = interaction.user
        player.queue.add(track)

        # Send queued message
        await self._update_queued_message(
            message=reply,
            tracks=[track],
            query=query,
        )

        # Play the track
        self.bot.log(f"Playing {track} in {voice_channel}")
        await player.play(voice_channel)

        # Send now playing message
        await player.send_now_playing(interaction.channel)


async def setup(bot):
    """Adds the cog to the bot."""
    await bot.add_cog(Music(bot))
