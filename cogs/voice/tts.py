import pathlib
import random
from typing import TYPE_CHECKING, List, Optional

import discord
from discord.ext import commands

from cogs.audio.types import AudioTrack
from cogs.common import utils
from cogs.common.messaging import bold, code, quoted_text
from cogs.voice.tts_elevenlabs import get_voices as get_elevenlabs_voices
from cogs.voice.tts_piper import get_voices as get_piper_voices
from cogs.voice.tts_types import Voice

if TYPE_CHECKING:
    from bots.voicebot import VoiceBot

MAX_TTS_LENGTH = 500

# The directory where audio files are stored.
AUDIO_DIRECTORY = pathlib.Path("audio/tts")
AUDIO_DIRECTORY.mkdir(parents=True, exist_ok=True)


class TTS(commands.Cog):
    def __init__(self, bot: "VoiceBot"):
        self.bot = bot
        self.voices: List[Voice] = []

    @commands.Cog.listener()
    async def on_ready(self):
        """Load the voices."""
        voices = get_elevenlabs_voices(self.bot.secrets.get("ELEVENLABS_API_KEY"))
        self.bot.log(f"Loaded {len(voices)} voices from ElevenLabs:")
        for voice in voices:
            self.bot.log(f" - [{voice.category}] {voice.name} - {voice.description}")
        self.voices.extend(voices)
        voices = get_piper_voices()
        self.voices.extend(voices)
        self.bot.log(f"Loaded {len(voices)} voices from Piper:")
        for voice in voices:
            self.bot.log(f" - [{voice.category}] {voice.name} - {voice.description}")

    def get_voice(self, message) -> Optional[Voice]:
        """Get the voice for a message from the first word before the colon.
        Args:
            message: The message to get the voice for.
        Returns:
            voice: The voice for the message or None if no voice is found.
        """
        first_word = message.content.split(" ", 1)[0].strip(self.bot.prefix)
        for voice in self.voices:
            if first_word.lower() in voice.name.lower():
                return voice
        return None

    async def fail(self, message: discord.Message, error: str):
        """Send a failure message to the user."""
        await self.bot.messaging.add_reactions(message, ["❌"])
        await self.bot.messaging.send_embed(
            message.channel,
            text=error,
            color=discord.Color.red(),
        )

    async def handle_message_tts(self, message: discord.Message, user):
        """Processes a TTS message. May be triggered by on_message() or on_reaction()

        Args:
            message: The Discord message containing the TTS request
            user: The user who triggered the TTS (may be different from message author)
        """
        try:
            # Remove the existing replay button.
            await self.bot.messaging.remove_reactions(message)

            # Extract and validate the text
            text = message.content[len(self.bot.prefix) :].strip()
            if len(text) > MAX_TTS_LENGTH:
                error = f"Message too long, please keep it under {MAX_TTS_LENGTH} characters."
                return await self.fail(message, error)

            # Get the voice and create TTS instance
            voice = self.get_voice(message)
            if voice and " " in text:
                text = text.split(" ", 1)[1].strip()
            else:
                voice = random.Random(message.id).choice(list(self.voices))

            # Set the audio path.
            mp3_path = AUDIO_DIRECTORY / f"{message.id}.mp3"

            # Build the footer text
            footer_parts = [f"- {voice.name}", f"(by @{message.author.name})"]

            # Add replay info if applicable
            if user != message.author or mp3_path.exists():
                footer_parts.append(f"(🔄 by @{user.name})")

            # Add cost info
            cost_text = "cost: "
            if mp3_path.exists():
                cost_text += "$0 (cached!)"
            else:
                cost_text += f"{voice.calculate_cost(text)}"
            footer_parts.append(cost_text)

            # Combine the footer parts.
            footer = " ".join(footer_parts)

            # Send initial response
            response = await self.bot.messaging.send_embed(
                channel=message.channel,
                text=quoted_text(text),
                color=discord.Color.light_gray(),
                thumbnail=voice.avatar,
                footer=footer,
                footer_icon=message.author.display_avatar.url,
            )

            # Add replay button
            await self.bot.messaging.add_reactions(message, ["🔄"])

            # Get user's voice channel
            assert isinstance(message.guild, discord.Guild)
            voice_channel = self.bot.utils.get_voice_channel(user, message.guild.id)
            if voice_channel is None:
                error = "You must be in a voice channel to play a message."
                return await self.fail(message, error)

            # Generate and save the audio
            try:
                voice.save_audio(text, mp3_path)

                # Update embed to show processing
                await self.bot.messaging.edit_embed(
                    message=response,
                    color=discord.Color.blue(),
                    thumbnail=voice.avatar,
                    footer=footer,
                    footer_icon=message.author.display_avatar.url,
                )

                # Play the audio
                track = AudioTrack(name=mp3_path.stem, path=mp3_path)
                await self.bot.audio.play(voice_channel, track)

                # Update embed to show success
                await self.bot.messaging.edit_embed(
                    message=response, color=discord.Color.green()
                )

            except Exception as e:
                return await self.fail(message, str(e))

        except Exception as e:
            error = f"An unexpected error occurred: {str(e)}"
            return await self.fail(message, error)

    @commands.Cog.listener()
    @utils.ignore_self
    async def on_message(self, message: discord.Message):
        # Help message.
        if message.content.startswith(self.bot.prefix + "help"):
            await self.send_help(message.channel)
            return

        # Play TTS messages that start with the prefix.
        if message.content.startswith(self.bot.prefix):
            await self.handle_message_tts(message, message.author)

    @commands.Cog.listener()
    @utils.ignore_self
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        # Replay TTS messages if the reaction is a 🔄.
        if reaction.emoji == "🔄":
            await self.handle_message_tts(reaction.message, user)

    async def send_help(self, channel):
        """Send the help message to the channel."""
        categories = set(voice.category for voice in self.voices)
        line = "-----------\n"
        text = (
            f"Usage: `{self.bot.prefix}[text]` or `{self.bot.prefix}[voice] [text]`\n\n"
        )
        for category in sorted(categories):
            text += f"{bold(category)} voices:\n"
            for voice in sorted(self.voices, key=lambda v: v.name):
                if voice.category == category:
                    text += f" {code(voice.name)}"
            text += "\n"
            text += line

        text = text[: -len(line)]  # Remove the last line break.
        await self.bot.messaging.send_embed(
            channel, text=text, color=discord.Color.dark_purple()
        )


async def setup(bot: "VoiceBot"):
    await bot.add_cog(TTS(bot))
