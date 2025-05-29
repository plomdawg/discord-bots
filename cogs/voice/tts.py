import pathlib
import random
import time
from typing import TYPE_CHECKING, List, Optional

import discord
from discord.ext import commands

from cogs.audio.types import AudioTrack
from cogs.common import utils
from cogs.common.messaging import bold, code, quoted_text
from cogs.voice.tts_elevenlabs import get_elevenlabs_voices
from cogs.voice.tts_fish import get_fish_voices
from cogs.voice.tts_piper import get_piper_voices
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

    def log(self, message: str):
        """Log a message to the bot."""
        self.bot.log(f"[TTS] {message}")

    @discord.app_commands.command(
        name="reload-voices", description="Reload the TTS voices"
    )
    async def reload_voices(self, interaction: discord.Interaction):
        """Reload the TTS voices."""
        start = time.time()
        self.load_voices()
        end = time.time()
        await interaction.response.send_message(
            f"Voices reloaded in {end - start:.2f} seconds ✔️"
        )

    def load_voices_from_source(self, get_voices_func, source_name: str):
        """Load voices from a source and log them.

        Args:
            get_voices_func: Function that returns a list of voices
            source_name: Name of the voice source for logging
        """
        self.log(f"Loading voices from {source_name}...")
        voices = get_voices_func()
        self.log(f"Loaded {len(voices)} voices from {source_name}:")
        for voice in voices:
            self.log(f" - [{voice.category}] {voice.name} - {voice.description}")
        self.voices.extend(voices)
        return voices

    @commands.Cog.listener()
    async def on_ready(self):
        """Load the voices."""
        self.load_voices()

    def load_voices(self):
        self.voices.clear()
        # Load ElevenLabs voices
        # self.load_voices_from_source(
        #    lambda: get_elevenlabs_voices(self.bot.secrets.get("ELEVENLABS_API_KEY")),
        #    "ElevenLabs",
        # )

        # Load Piper voices
        self.load_voices_from_source(get_piper_voices, "Piper")

        # Load Fish voices
        self.load_voices_from_source(get_fish_voices, "Fish TTS")

    def get_voice_and_text(self, message) -> "tuple[Voice, str]":
        """Get the voice for a message and return the cleaned text with voice name removed.
        Args:
            message: The message to get the voice for.
        Returns:
            tuple: (voice, cleaned_text) where voice is the Voice object (random if no match),
                   and cleaned_text is the text with the voice name stripped out
        """
        # Remove prefix and split into words
        content_without_prefix = message.content[len(self.bot.prefix) :].strip()
        words = content_without_prefix.split()

        if not words:
            # No text at all, return random voice and empty text
            voice = random.Random(message.id).choice(list(self.voices))
            return voice, ""

        # Try matching with increasing number of words (up to the full voice name length)
        best_match = None
        best_words_matched = 0

        for voice in self.voices:
            voice_words = voice.name.lower().split()

            # Try matching from 1 word up to the length of the voice name or available words
            max_words_to_try = min(len(voice_words), len(words))

            for num_words in range(1, max_words_to_try + 1):
                user_phrase = " ".join(words[:num_words]).lower()

                # Check if this phrase matches any part of the voice name
                if any(
                    user_phrase in " ".join(voice_words[i : i + num_words])
                    for i in range(len(voice_words) - num_words + 1)
                ):
                    # Prefer longer matches
                    if num_words > best_words_matched:
                        best_match = voice
                        best_words_matched = num_words

        # If we found a match with at least 3 characters, use it and strip the matched words
        if best_match and len("".join(words[:best_words_matched])) >= 3:
            if len(words) > best_words_matched:
                cleaned_text = " ".join(words[best_words_matched:]).strip()
            else:
                cleaned_text = ""  # All words were part of the voice name
            return best_match, cleaned_text

        # No match found, return random voice and original text
        voice = random.Random(message.id).choice(list(self.voices))
        return voice, content_without_prefix

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
        if not await self.bot.utils.author_has_voice(message, "use TTS"):
            return

        # Remove the existing replay button.
        await self.bot.messaging.remove_reactions(message)

        # Extract and validate the text
        text = message.content[len(self.bot.prefix) :].strip()
        if len(text) > MAX_TTS_LENGTH:
            error = (
                f"Message too long, please keep it under {MAX_TTS_LENGTH} characters."
            )
            return await self.fail(message, error)

        try:
            # Get the voice and cleaned text
            voice, text = self.get_voice_and_text(message)

            # Set the audio path.
            mp3_path = AUDIO_DIRECTORY / f"{message.id}.mp3"

            # Build the footer text
            # 🗨️ plomdawg 🔁 plomdawg 💰 $0 ⌚ 7.75 seconds
            footer_parts = [f"🗨️ {message.author.name}"]

            # Add replay info if applicable
            if user != message.author or mp3_path.exists():
                footer_parts.append(f"🔁 {user.name}")

            # Add cost info
            cost_text = "💰 "
            if mp3_path.exists():
                cost_text += "$0"
            else:
                cost_text += f"{voice.calculate_cost(text)}"
            footer_parts.append(cost_text)

            # Combine the footer parts.
            footer = " ".join(footer_parts)

            # Use a loading gif for the footer icon
            footer_icon = "https://media.tenor.com/-n8JvVIqBXkAAAAM/dddd.gif"

            # Send initial response
            response = await self.bot.messaging.send_embed(
                channel=message.channel,
                title=f"{voice.name} 🗣️",
                text=quoted_text(text),
                color=discord.Color.light_gray(),
                thumbnail=voice.avatar,
                footer=footer,
                footer_icon=footer_icon,
            )

            # Add replay button
            await self.bot.messaging.add_reactions(message, ["🔄"])

            # Generate and save the audio
            start_time = time.time()
            try:
                if not mp3_path.exists():
                    self.log(f"[{voice.name}] Generating TTS audio: {mp3_path}")
                    voice.save_audio(text, mp3_path)
            except Exception as e:
                return await self.fail(message, str(e))

            duration = time.time() - start_time
            self.log(f"Generated in {duration:.2f} seconds")
            footer += f" ⌚ {duration:.2f} seconds"
            try:
                # Update embed to show processing
                await self.bot.messaging.edit_embed(
                    message=response,
                    color=discord.Color.blue(),
                    footer=footer,
                )

                # Play the audio
                track = AudioTrack(name=mp3_path.stem, path=mp3_path)
                await self.bot.audio.play(user.voice.channel, track)

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
