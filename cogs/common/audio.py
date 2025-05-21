import asyncio
import enum
import pathlib
import random
import re
import typing
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import DiscordBot

# The directory where audio files are stored.
AUDIO_DIRECTORY = pathlib.Path("audio")
AUDIO_DIRECTORY.mkdir(parents=True, exist_ok=True)


def format_duration(duration) -> str:
    """Converts a duration into a string like '4h20m'"""
    if duration is None:
        return "?"
    if duration < 60:  # Under a minute
        return "{}s".format(int(duration))
    if duration < 3600:  # Under an hour
        return "{}m{}s".format(int(duration / 60), int(duration % 60))
    # Over an hour
    return "{}h{}m{}s".format(
        int(duration / 3600), int(duration % 3600 / 60), int(duration % 60)
    )


def format_title(title) -> str:
    """Removes "official audio/video" etc from video titles"""
    keywords = [
        " \\(official audio\\)",
        " \\(official video\\)",
        " \\(official music audio\\)",
        " \\(official music video\\)",
        " \\[official audio\\]",
        " \\[official video\\]",
        " \\[official music audio\\]",
        " \\[official music video\\]",
    ]
    title_format = re.compile("|".join(keywords), re.IGNORECASE)
    _title = title.replace("&amp;", "&")
    _title = _title.replace("&quot;", '"')
    return title_format.sub("", _title).strip()


def volume_bar(volume):
    """Returns an ASCII volume bar for the given volume.
    volume_bar(25): █████░░░░░░░░░░░░░░░
    """
    length = 20
    filled = int(volume * length / 100)
    unfilled = length - filled
    return "█" * filled + "░" * unfilled


class AudioTrack:
    def __init__(self, name=None, url=None, path=None, bot=None) -> None:
        # The unique name/id of the track.
        self.name = name
        # The URL of the track (if it's a URL-based track)
        self.url = url
        # The path to the audio file (if it's a local file)
        self.path = path or (AUDIO_DIRECTORY / f"{self.name}.mp3" if name else None)
        # Current position in the track.
        self.position = 0
        # Track metadata
        self.title = None
        self.data = None
        # Bot instance for logging
        self.bot = bot

    @property
    def is_url(self) -> bool:
        """Returns True if this track is URL-based."""
        return bool(self.url)

    @property
    def is_local(self) -> bool:
        """Returns True if this track is a local file."""
        return bool(self.path and self.path.exists())

    def get_audio_source(self, volume=0.5):
        """Returns an appropriate audio source for this track."""
        if self.is_url:
            raise RuntimeError("URL tracks must be downloaded first")

        if not self.is_local:
            raise RuntimeError("Local track file does not exist")

        # Set up FFMPEG options.
        # -ss skips ahead to the current position in the track.
        # -af loudnorm normalizes the audio.
        # -ac 2 forces stereo output
        # -ar 48000 sets sample rate to 48kHz
        ffmpeg_options = (
            f"-ss {self.position} -af loudnorm=I=-16.0:TP=-1.0 -ac 2 -ar 48000"
        )

        # Create the audio source.
        try:
            audio_source = discord.FFmpegPCMAudio(
                source=str(self.path), options=ffmpeg_options
            )
            return discord.PCMVolumeTransformer(audio_source, volume=volume)
        except Exception as e:
            raise


class AudioQueue:
    def __init__(self, bot):
        self.bot = bot
        self.tracks = []  # type: typing.List[AudioTrack]
        self.position = 0  # type: int
        self.queue_message = None

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

class AudioPlayerStatus(enum.Enum):
    PLAYING = 1
    PAUSED = 2
    STOPPED = 3
    CONTINUING = 4


class AudioPlayerRepeat(enum.Enum):
    OFF = 0
    ALL = 1
    ONE = 2


class AudioPlayer:
    def __init__(self, bot: "DiscordBot", guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue = AudioQueue(bot)
        self.voice_client = None
        self.volume = 0.30
        self.current_source: Optional[discord.PCMVolumeTransformer] = None
        self.status = AudioPlayerStatus.STOPPED
        self.repeat = AudioPlayerRepeat.OFF

    async def increment_position(self):
        """Used by play when going to the next track."""
        # Do not increment position if repeat one is set
        if self.repeat == AudioPlayerRepeat.ONE:
            return

        self.queue.position += 1
        # Hit the end of the queue
        if len(self.queue.tracks) <= self.queue.position:
            # Repeat
            if self.repeat == AudioPlayerRepeat.ALL:
                self.queue.position = 0

    async def connect(self, voice_channel):
        """Connects to a voice channel. Returns the voice channel or None if error"""
        # Find the voice client for this server
        if self.voice_client is None:
            self.voice_client = discord.utils.get(
                self.bot.voice_clients, guild=voice_channel.guild
            )

        if self.voice_client is None:
            try:
                self.voice_client = await voice_channel.connect()
                while not self.voice_client.is_connected():
                    await asyncio.sleep(1)
            except discord.errors.ClientException:
                pass
            except asyncio.TimeoutError:
                pass

        # Move to the user if nobody is in the room with the bot
        if self.voice_client is not None:
            if len(self.voice_client.channel.members) == 1:
                await self.voice_client.move_to(voice_channel)

        return self.voice_client

    async def play(self, channel: discord.VoiceChannel) -> None:
        """Starts playback in the given voice channel."""
        await self.connect(channel)

        if self.voice_client is None:
            raise RuntimeError("Voice client not found")

        # If the player is already playing, do nothing.
        if self.status == AudioPlayerStatus.PLAYING:
            return

        # If the player is paused, just resume.
        if self.status == AudioPlayerStatus.PAUSED:
            self.voice_client.resume()
            return

        # If there is no track, stop the player.
        if self.queue.current_track is None:
            self.status = AudioPlayerStatus.STOPPED
            return

        # Set the status to playing.
        self.status = AudioPlayerStatus.PLAYING

        # Make sure the track is downloaded if it's a URL.
        if self.queue.current_track.is_url:
            player = await self.queue.current_track.download()
            if player:
                audio_source = player
            else:
                self.status = AudioPlayerStatus.STOPPED
                return
        else:
            # Get the audio source for local files
            try:
                audio_source = self.queue.current_track.get_audio_source(
                    volume=self.volume
                )
            except RuntimeError as e:
                self.bot.error(f"Creating audio source: {e}")
                self.status = AudioPlayerStatus.STOPPED
                return

        def next_track(err=None):
            if err:
                self.bot.error(f"During playback: {err}")
            # Set the status to stopped before moving on.
            self.status = AudioPlayerStatus.STOPPED
            # Move on to the next track in the queue.
            self.bot.loop.create_task(self.increment_position())
            self.bot.loop.create_task(self.play(channel))

        # Begin playback.
        try:
            self.voice_client.play(audio_source, after=next_track)
        except Exception as e:
            self.bot.error(f"Starting playback: {e}")
            self.status = AudioPlayerStatus.STOPPED

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


class Audio(commands.Cog):
    def __init__(self, bot: "DiscordBot"):
        # Store the bot instance so we can access it inside the cog.
        self.bot = bot
        self.players = {}  # type: typing.Dict[discord.Guild, AudioPlayer]

    def get_player(self, guild: discord.Guild) -> AudioPlayer:
        """Get the player for a guild."""
        if guild not in self.players:
            self.players[guild] = AudioPlayer(self.bot, guild)
        return self.players[guild]

    async def play(self, voice_channel: discord.VoiceChannel, track: AudioTrack):
        """Add a track to the queue, then play/resume the queue.

        Args:
            voice_channel: The voice channel to play the track in.
            track: The track to play.
        """
        self.bot.log(f"Playing track {track.name} in {voice_channel.name}")
        player = self.get_player(voice_channel.guild)
        # Set the bot instance on the track for logging
        track.bot = self.bot
        player.queue.add(track)
        await player.play(voice_channel)

async def setup(bot):
    await bot.add_cog(Audio(bot))
