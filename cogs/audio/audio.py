import asyncio
import pathlib
import typing
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.audio.types import AudioPlayer, AudioTrack

if TYPE_CHECKING:
    from bot import DiscordBot

# The directory where audio files are stored.
AUDIO_DIRECTORY = pathlib.Path("audio")
AUDIO_DIRECTORY.mkdir(parents=True, exist_ok=True)


class Audio(commands.Cog):
    """Audio player for the bot."""

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

    @commands.Cog.listener(name="on_voice_state_update")
    async def disconnect_if_alone(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Called when a user changes their voice state

        Args:
            member - The Member whose voice states changed.
            before - The VoiceState prior to the changes.
            after  - The VoiceState after to the changes.

        Leaves and clears the queue if the bot is left alone for 3 minutes
        """
        # Skip if this is the bot itself changing state
        if self.bot.user is not None and member.id == self.bot.user.id:
            return

        # Try to find the voice client for this guild.
        voice_client = None
        for vc in self.bot.voice_clients:
            assert isinstance(vc, discord.VoiceClient)
            if vc.guild == member.guild:
                voice_client = vc
                break

        # Nothing to do if the bot is not in a voice channel.
        if voice_client is None:
            return

        # Ensure we have a proper voice channel with members attribute
        if not isinstance(voice_client.channel, discord.VoiceChannel):
            return

        # If there are any non-bots in the channel, do nothing.
        non_bot_members = [
            user for user in voice_client.channel.members if not user.bot
        ]
        if non_bot_members:
            return

        self.bot.log(
            f"Bot is alone in {voice_client.channel.name}, starting disconnect timer"
        )

        # Save the bot's current channel.
        bot_channel = voice_client.channel

        # If the bot is alone in the channel, start the timer.
        # Loop until somebody comes back, or the timer runs out.
        timeout = 60  # seconds before disconnecting (reduced from 180)
        step = 10  # seconds between checks
        for i in range(0, int(timeout / step)):
            await asyncio.sleep(step)

            # Check if the bot has been disconnected or moved
            if voice_client is None or not voice_client.is_connected():
                self.bot.log(
                    "Voice client disconnected during timer, stopping disconnect sequence"
                )
                return

            # Ensure we still have a proper voice channel
            if not isinstance(voice_client.channel, discord.VoiceChannel):
                self.bot.log(
                    "Voice channel no longer valid, stopping disconnect sequence"
                )
                return

            # Check if the bot has been moved to a different channel.
            if voice_client.channel != bot_channel:
                self.bot.log(
                    "Bot moved to different channel, stopping disconnect sequence"
                )
                return

            # Check if a non-bot has joined the channel.
            non_bot_members = [
                user for user in voice_client.channel.members if not user.bot
            ]
            if non_bot_members:
                self.bot.log(
                    f"Non-bot user joined {voice_client.channel.name}, stopping disconnect sequence"
                )
                return

        # If the bot is still alone, disconnect and clear the queue.
        self.bot.log(f"Timeout reached, disconnecting from {voice_client.channel.name}")
        if voice_client.guild is not None:
            player = self.get_player(voice_client.guild)
            player.queue.clear()
        await voice_client.disconnect()


async def setup(bot):
    await bot.add_cog(Audio(bot))


async def teardown(bot):
    for vc in bot.voice_clients:
        await vc.disconnect(force=True)
