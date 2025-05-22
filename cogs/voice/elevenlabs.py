# voice.py - Voice class for AI Voice Bots
import io
import pathlib
import random
import time
import typing
from typing import TYPE_CHECKING

import discord
import pydub
from discord.ext import commands
from elevenlabs.client import ElevenLabs
from elevenlabs.types.voice import Voice

from cogs.audio.types import AudioTrack
from cogs.common.messaging import bold, code
from cogs.common import utils

if TYPE_CHECKING:
    from bots.voicebot import VoiceBot

MAX_TTS_LENGTH = 500

# The directory where audio files are stored.
AUDIO_DIRECTORY = pathlib.Path("audio/tts")
AUDIO_DIRECTORY.mkdir(parents=True, exist_ok=True)


class ElevenLabsTTS(commands.Cog):
    def __init__(self, bot: "VoiceBot"):
        self.bot = bot
        api_key = self.bot.secrets.get("ELEVENLABS_API_KEY")
        self.client = ElevenLabs(api_key=api_key)

        response = self.client.voices.get_all()
        self.voices = response.voices
        self.bot.log(f"Loaded {len(self.voices)} voices from ElevenLabs.")

    def get_voice(self, message) -> typing.Optional[Voice]:
        """Get the voice for a message from the first word before the colon.
        Args:
            message: The message to get the voice for.
        Returns:
            voice: The voice for the message or None if no voice is found.
        """
        first_word = message.content.split(" ", 1)[0].strip(self.bot.prefix)
        for voice in self.voices:
            if voice.name:
                if first_word.lower() in voice.name.lower():
                    return voice
        return None

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
                await self.bot.messaging.add_reactions(message, ["❌"])
                return await self.bot.messaging.send_embed(
                    message.channel,
                    text=f"{user.mention} Message too long, please keep it under {MAX_TTS_LENGTH} characters.",
                    color=discord.Color.red(),
                )

            # Get the voice and create TTS instance
            voice = self.get_voice(message)
            if voice and voice.name and " " in text:
                text = text.split(" ", 1)[1].strip()
            else:
                voice = random.Random(message.id).choice(list(self.voices))

            tts = TTS(
                elevenlabs=self,
                text=text,
                voice=voice,
                tts_path=AUDIO_DIRECTORY,
                message_id=str(message.id),
            )

            # Build the footer text
            footer_parts = [f"- {tts.voice.name}", f"(by @{message.author.name})"]

            # Add replay info if applicable
            if user != message.author or tts.is_cached:
                footer_parts.append(f"(🔄 by @{user.name})")

            # Add cost info
            cost_text = "cost: $0 (cached!)" if tts.is_cached else f"cost: {tts.cost}"
            footer_parts.append(cost_text)

            footer = " ".join(footer_parts)

            # Send initial response
            response = await self.bot.messaging.send_embed(
                channel=message.channel,
                text=tts.quoted_text,
                color=discord.Color.light_gray(),
                footer=footer,
            )

            # Add replay button
            await self.bot.messaging.add_reactions(message, ["🔄"])

            # Get user's voice channel
            assert isinstance(message.guild, discord.Guild)
            voice_channel = self.bot.utils.get_voice_channel(user, message.guild.id)
            if voice_channel is None:
                return await self.bot.messaging.edit_embed(
                    message=response,
                    color=discord.Color.red(),
                    text="Failed! You must be in a voice channel to play a message.",
                )

            # Generate and save the audio
            try:
                audio_path = tts.save_audio()

                # Update footer with generation time if applicable
                if tts.gen_seconds > 0:
                    footer += f" in {tts.gen_seconds:.2f}s"

                # Update embed to show processing
                await self.bot.messaging.edit_embed(
                    message=response, color=discord.Color.blue(), footer=footer
                )

                # Play the audio
                track = AudioTrack(name=audio_path.stem, path=audio_path)
                await self.bot.audio.play(voice_channel, track)

                # Update embed to show success
                await self.bot.messaging.edit_embed(
                    message=response, color=discord.Color.green()
                )

            except Exception as e:
                await self.bot.messaging.edit_embed(
                    message=response,
                    color=discord.Color.red(),
                    text=f"Failed! {str(e)}",
                )

        except Exception as e:
            if "response" in locals():
                await self.bot.messaging.edit_embed(
                    message=response,
                    color=discord.Color.red(),
                    text=f"An unexpected error occurred: {str(e)}",
                )

    @commands.Cog.listener()
    @utils.ignore_self
    async def on_message(self, message: discord.Message):
        # Help message.
        if message.content.startswith(self.bot.prefix + "help"):
            return await self.send_help(message.channel)

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
        text = f"{bold('Usage')}: `{self.bot.prefix}[text]` or `{self.bot.prefix}[voice] [text]`\n"
        text += "-----------\n"
        text += f"{bold('Built-in voices')}:\n"
        for voice in self.voices:
            if voice.category == "premade":
                text += f" {code(voice.name)}"

        text += "\n-----------\n"
        text += f"{bold('Custom voices')}:\n"
        for voice in self.voices:
            if voice.category != "premade":
                text += f" {code(voice.name)}"

        await self.bot.messaging.send_embed(channel, text=text)
        return


class TTS:
    """Class for generating and managing TTS clips."""

    def __init__(
        self,
        elevenlabs: ElevenLabsTTS,
        text: str,
        voice: Voice,
        tts_path: pathlib.Path,
        message_id: str,
    ):
        """Initialize the TTS object.

        Args:
            elevenlabs: The ElevenLabsTTS instance
            text: The text to convert to speech
            voice: The voice to use for TTS
            tts_path: Path to store TTS files
            message_id: Unique identifier for this TTS request
        """
        self.text = text
        self.elevenlabs = elevenlabs
        self.voice = voice
        self.tts_path = pathlib.Path(tts_path)
        self.mp3_path = self.tts_path / pathlib.Path(f"{message_id}.mp3")
        self._bytes = None
        self.gen_seconds = 0

    def generate(self) -> bytes:
        """Generate the TTS audio bytes.

        Returns:
            bytes: The generated audio data
        """
        if self._bytes is None:
            start = time.time()

            try:
                audio_iterator = self.elevenlabs.client.text_to_speech.convert(
                    text=self.text,
                    voice_id=self.voice.voice_id,
                    output_format="mp3_44100_128",
                )
                self._bytes = b"".join(audio_iterator)
                self.gen_seconds = round(time.time() - start, 2)
            except Exception as e:
                raise

        return self._bytes

    def save_audio(self) -> pathlib.Path:
        """Save the generated audio to a file.

        Returns:
            pathlib.Path: Path to the saved audio file
        """
        if not self.mp3_path.exists():
            self.tts_path.mkdir(parents=True, exist_ok=True)

            try:
                audio_bytes = self.generate()
                raw_audio = pydub.AudioSegment.from_file(io.BytesIO(audio_bytes), "mp3")
                normalized_sound = raw_audio.normalize()
                normalized_sound.export(self.mp3_path, format="wav")
            except Exception as e:
                raise

        return self.mp3_path

    @property
    def cost(self) -> str:
        """Calculate the cost of generating this TTS message.

        Returns:
            str: Formatted cost string
        """
        # Starter tier gives 40,000 characters per month for $5
        cost_per_character = 5 / 40000
        cost = round(len(self.text) * cost_per_character, 8)
        return f"${cost}"

    @property
    def is_cached(self) -> bool:
        """Check if this TTS is already cached.

        Returns:
            bool: True if the audio file exists
        """
        return self.mp3_path.exists()

    @property
    def quoted_text(self) -> str:
        """Get the quoted text.

        Returns:
            str: The quoted text with > prefix on each line
        """
        lines = self.text.split("\n")
        quoted_lines = [f" > {line}" for line in lines]
        return "\n".join(quoted_lines)


async def setup(bot):
    await bot.add_cog(ElevenLabsTTS(bot))
