import asyncio
import enum
import pathlib
import random
import typing
from typing import TYPE_CHECKING, Optional

import discord

from cogs.audio.utils import format_duration

if TYPE_CHECKING:
    from bot import DiscordBot

# The directory where audio files are stored.
AUDIO_DIRECTORY = pathlib.Path("audio")
AUDIO_DIRECTORY.mkdir(parents=True, exist_ok=True)


class AudioTrack:
    def __init__(self, **kwargs) -> None:
        # The unique name/id of the track.
        self.name = kwargs.get("name")
        # The URL of the track (if it's a URL-based track)
        self.source_url = kwargs.get("source_url")
        # The path to the audio file (if it's a local file)
        self.path = kwargs.get("path") or (
            AUDIO_DIRECTORY / f"{self.name}.mp3" if self.name else None
        )
        # Current position in the track.
        self.position = 0
        # Track metadata
        self.title = kwargs.get("title")
        self.data = kwargs.get("data")
        # Bot instance for logging
        self.bot = kwargs.get("bot")
        # Track duration in seconds
        self.duration = kwargs.get("duration", 0)
        # YouTube URL for the track
        self.youtube_url = kwargs.get("youtube_url")
        # Spotify URL for the track
        self.spotify_url = kwargs.get("spotify_url")

    def audio_source(self, volume: float) -> discord.PCMVolumeTransformer:
        """Returns an appropriate audio source for this track."""
        source = self.source_url or str(self.path)
        ffmpeg_options = f"-ss {self.position}"
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(source=source, options=ffmpeg_options),
            volume=volume,
        )


class RepeatMode(enum.Enum):
    OFF = 0
    ALL = 1
    ONE = 2


class AudioQueue:
    """A queue of audio tracks with a pointer to the current track."""

    def __init__(self, bot: "DiscordBot"):
        self.bot = bot
        self.tracks = []  # type: typing.List[AudioTrack]
        self.position = 0  # type: int
        self.queue_message = None
        self.repeat_mode = RepeatMode.OFF

    @property
    def current_track(self) -> typing.Optional[AudioTrack]:
        """Returns the current track."""
        try:
            return self.tracks[self.position]
        except IndexError:
            return None

    @property
    def next_track(self):
        if self.position < len(self.tracks):
            return self.tracks[self.position]
        return None

    def add(self, track: AudioTrack):
        """Adds a track to the queue."""
        self.tracks.append(track)

    def add_next(self, track: AudioTrack):
        """Adds a track to the queue up next."""
        self.tracks.insert(self.position + 1, track)

    def add_list(self, tracks: typing.List[AudioTrack]):
        """Adds a list of tracks to the queue."""
        self.tracks.extend(tracks)

    def add_list_next(self, tracks: typing.List[AudioTrack]):
        """Adds a list of tracks to the queue up next."""
        for track in reversed(tracks):
            self.add_next(track)

    def clear(self) -> typing.List[AudioTrack]:
        """Clears the queue and resets the position. Returns the skipped tracks."""
        cleared_tracks = self.tracks[self.position :]
        self.tracks = []
        self.position = 0
        return cleared_tracks

    def format_queue(self):
        """Returns a track list with the current track highlighted"""
        max_tracks = 10
        track_list = ""

        # Find the start and end of what we should print
        queue_length = len(self.tracks)

        # case 0: no tracks in queue
        if len(self.tracks) == 0:
            return "(empty)"

        # case 1: queue is shorter than max tracks, print the whole thing
        if queue_length <= max_tracks:
            start = 0
            end = queue_length

        # case 2: less than max_tracks away from the current track - print old tracks
        elif self.position - 1 + max_tracks > queue_length:
            start = queue_length - max_tracks
            if start < 0:
                start = 0
            end = queue_length

        # case 3: more than max_tracks away from current track - print current and next few
        else:
            start = max(0, self.position - 1)
            end = self.position + max_tracks

        for i, track in enumerate(self.tracks[start:end]):
            # Nicely format the duration
            duration = format_duration(track.duration)

            # Limit name length
            length = 41 - len(duration)

            # Add a triangle to the current track
            symbol = "⭄" if self.position == start + i else "--"

            # Remove brackets from track title and limit length
            title = track.title[:length].translate(str.maketrans(dict.fromkeys("[]()")))

            track_list += " {} {} [{}]({}) ({})\n".format(
                symbol, start + i, title, track.youtube_url, duration
            )

            if i == max_tracks:
                break

        return track_list

    def increment_position(self):
        """Move the position pointer to the next track, obeying repeat mode."""
        # Do not move if repeat one is set.
        if self.repeat_mode == RepeatMode.ONE:
            return

        # Move to the next track.
        self.position += 1

        # Hit the end of the queue.
        if len(self.tracks) <= self.position:
            if self.repeat_mode == RepeatMode.ALL:
                self.position = 0

    async def send_queue_message(self, channel):
        """Deletes existing queue message and sends a new one.

        Args:
            channel: discord.TextChannel to send the message
        """
        # Delete old message
        if self.queue_message:
            await self.bot.messaging.delete_message(self.queue_message)
        self.queue_message = None

        # Send the new message
        embed = discord.Embed(color=0x22FF33, title="Song Queue ♫")
        embed.description = self.format_queue()
        self.queue_message = await channel.send(embed=embed)

        # Non-empty queue - add shuffle button
        if self.tracks:
            await self.bot.messaging.add_reactions(self.queue_message, ["🔀"])

        return self.queue_message

    async def shuffle(self):
        """Shuffles the tracks beyond the current position"""
        if len(self.tracks) > self.position + 1:
            temp = self.tracks[self.position + 1 :]
            random.shuffle(temp)
            self.tracks[self.position + 1 :] = temp

        await self.update_queue_message()

    async def update_queue_message(self):
        """Updates Queue message if it exists."""
        if self.queue_message is not None and self.queue_message.embeds:
            embed = self.queue_message.embeds[0]
            embed.description = self.format_queue()
            try:
                await self.queue_message.edit(embed=embed)
            except discord.errors.NotFound:
                pass


class AudioPlayerStatus(enum.Enum):
    PLAYING = 1
    PAUSED = 2
    STOPPED = 3
    CONTINUING = 4


class AudioPlayer:
    def __init__(self, bot: "DiscordBot", guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue = AudioQueue(bot)
        self.voice_client = None
        self.volume = 0.30
        self.current_source: Optional[discord.PCMVolumeTransformer] = None
        self.status = AudioPlayerStatus.STOPPED

    async def connect(self, voice_channel):
        """Connects to a voice channel. Returns the voice channel or None if error"""
        # Check if we already have a connected voice client
        if self.voice_client and self.voice_client.is_connected():
            # Move to the user if nobody is in the room with the bot
            if len(self.voice_client.channel.members) == 1:
                await self.voice_client.move_to(voice_channel)
            return self.voice_client

        # Find the voice client for this server
        self.voice_client = discord.utils.get(
            self.bot.voice_clients, guild=voice_channel.guild
        )

        # If we found an existing client but it's not connected, clean it up
        if self.voice_client and not self.voice_client.is_connected():
            try:
                await self.voice_client.disconnect(force=True)
            except:
                pass
            self.voice_client = None

        # Connect if we don't have a connected client
        if self.voice_client is None:
            try:
                self.voice_client = await voice_channel.connect()
                # Wait for connection to be established
                timeout = 10  # 10 second timeout
                while not self.voice_client.is_connected() and timeout > 0:
                    await asyncio.sleep(0.1)
                    timeout -= 0.1

                if not self.voice_client.is_connected():
                    self.bot.error(
                        "Failed to establish voice connection within timeout"
                    )
                    return None

            except discord.errors.ClientException as e:
                self.bot.error(f"ClientException during voice connect: {e}")
                return None
            except asyncio.TimeoutError as e:
                self.bot.error(f"TimeoutError during voice connect: {e}")
                return None

        # Move to the user if nobody is in the room with the bot
        if self.voice_client is not None and self.voice_client.is_connected():
            if len(self.voice_client.channel.members) == 1:
                await self.voice_client.move_to(voice_channel)

        return self.voice_client

    async def play(self, channel: discord.VoiceChannel) -> None:
        """Starts playback in the given voice channel."""
        voice_client = await self.connect(channel)

        if voice_client is None or not voice_client.is_connected():
            self.bot.error("Failed to connect to voice channel")
            self.status = AudioPlayerStatus.STOPPED
            return

        self.voice_client = voice_client

        # If the player is already playing, do nothing.
        if self.status == AudioPlayerStatus.PLAYING:
            return

        # If the player is paused, just resume.
        if self.status == AudioPlayerStatus.PAUSED:
            if self.voice_client.is_connected():
                self.voice_client.resume()
                self.status = AudioPlayerStatus.PLAYING
            return

        # If there is no track, stop the player.
        if self.queue.current_track is None:
            self.status = AudioPlayerStatus.STOPPED
            return

        # Set the status to playing.
        self.status = AudioPlayerStatus.PLAYING

        # Get the audio source for the track.
        audio_source = self.queue.current_track.audio_source(volume=self.volume)
        self.current_source = audio_source

        def next_track(err=None):
            if err:
                self.bot.error(f"During playback: {err}")
            # Set the status to stopped before moving on.
            self.status = AudioPlayerStatus.STOPPED
            self.current_source = None
            # Move on to the next track in the queue.
            self.queue.increment_position()
            # Only continue if we still have tracks and are connected
            if self.queue.current_track is not None:
                self.bot.loop.create_task(self.play(channel))

        # Begin playback.
        try:
            if self.voice_client.is_connected():
                self.voice_client.play(audio_source, after=next_track)
            else:
                self.bot.error("Voice client not connected when trying to play")
                self.status = AudioPlayerStatus.STOPPED
        except Exception as e:
            self.bot.error(f"Starting playback: {e}")
            self.status = AudioPlayerStatus.STOPPED
            self.current_source = None

    def set_volume(self, volume: float) -> float:
        """Set the player volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        if self.current_source:
            self.current_source.volume = self.volume

        return self.volume

    async def stop(self) -> None:
        """Clear the queue and stop playback."""
        self.queue.clear()
        if self.voice_client:
            await self.voice_client.disconnect(force=True)
        self.status = AudioPlayerStatus.STOPPED
