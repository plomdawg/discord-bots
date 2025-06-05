import random
from typing import TYPE_CHECKING, Optional

from discord.ext import commands

from cogs.audio.types import AudioTrack
from cogs.dota import utils

if TYPE_CHECKING:
    from bots.dotabot import DotaBot


def get_index_from_query(text):
    """Splits off the last token in the string if it's a number.
    Example: "dota haha 2" -> ("dota haha", 2)
    """
    try:
        tokens = text.split(" ")
        index = int(tokens[-1]) - 1
        text = " ".join(tokens[:-1])
    except:
        index = None
    return text, index


def get_response_url(response):
    """Get the URL for a response."""
    if response.hero:
        return utils.dota_wiki_url(f"{response.hero.localized_name}/Responses")
    return utils.dotabase_url(response.mp3)


class VoiceLines(commands.Cog):
    def __init__(self, bot: "DotaBot"):
        self.bot = bot
        self.play_lock = False

    def log(self, message: str):
        """Log a message to the bot."""
        self.bot.log(f"[VoiceLines] {message}")

    @commands.Cog.listener()
    async def on_message(self, message):
        self.log(f"on_message: {message.content}")
        # Ignore bot messages.
        if message.author.bot:
            return

        # Ignore messages if the author is not in a voice channel.
        if not await self.bot.utils.author_has_voice(message, "play a dota voice line"):
            return

        # Check if the message ends in a number.
        text, index = get_index_from_query(message.content)

        # Check if the message starts with "list" (e.g. "list hero juggernaut")
        list_mode = False
        list_start = 0
        if text.lower().startswith("list "):
            list_mode = True
            text = text.split(" ", 1)[1]
            if text[0].isdigit() and " " in text:
                list_start = int(text.split(" ", 1)[0]) - 1
                text = text.split(" ", 1)[1]

        # Check if the message is an exact match for a response.
        responses, index = self.get_voice_responses(exact_text=text, index=index)
        if responses:
            return await self.respond(message, responses, index, list_mode, list_start)

        # Check if the message starts with "dota" (e.g. "dota haha")
        if text.lower().startswith("dota ") or text.lower().startswith("any "):
            self.log(f"dota: {text}")
            text = text.split(" ", 1)[1]
            responses, index = self.get_voice_responses(text=text, index=index)
            if responses:
                return await self.respond(
                    message, responses, index, list_mode, list_start
                )

        elif text.lower().startswith("hero "):
            self.log(f"hero: {text}")
            hero_name = text.split(" ", 1)[1]
            responses, index = self.get_voice_responses(name=hero_name, index=index)
            if responses:
                return await self.respond(
                    message, responses, index, list_mode, list_start
                )

    def get_voice_responses(self, exact_text=None, text=None, index=None, name=None):
        """Find responses for the given query using dotabase utils."""
        if exact_text:
            responses = utils.find_voice_responses_exact(exact_text)
        elif text:
            if name:
                # Both hero and text
                hero_responses = utils.find_voice_responses_by_hero(name)
                responses = [
                    r for r in hero_responses if text.lower() in r.text.lower()
                ]
            else:
                responses = utils.find_voice_responses_by_text(text)
        elif name:
            responses = utils.find_voice_responses_by_hero(name)
        else:
            responses = []

        # Use a random index if not specified.
        if index is None and responses:
            index = random.randint(0, len(responses) - 1)

        return responses, index

    async def respond(
        self, message, responses, index, list_mode=False, list_start=0, forward=True
    ):
        text_channel = message.channel

        if list_mode:
            max_list_length = 30
            msg = f"Found {len(responses)} responses."

            if list_start >= len(responses):
                msg = f"Start index **{list_start+1}** is greater than the number of responses ({len(responses)})."
                return await self.bot.messaging.send_embed(
                    channel=text_channel, text=msg
                )
            elif list_start < 0:
                msg = f"Start index **{list_start+1}** is less than 1."
                return await self.bot.messaging.send_embed(
                    channel=text_channel, text=msg
                )

            if len(responses) > max_list_length:
                if list_start == 0:
                    msg += f" Showing the first **{max_list_length}**."
                else:
                    msg += f" Showing **{list_start+1}** to **{list_start+max_list_length}**."
                list_end = list_start + max_list_length
                responses = responses[list_start:list_end]
                msg += (
                    "\nUse `list [n] [command]` to list starting at a different index."
                )

            for i, response in enumerate(responses):
                text = response.text
                name = response.hero.localized_name if response.hero else "Unknown"
                voice_line = f"\n{i+1+list_start}. **{text}** ({name})"
                msg += voice_line

            return await self.bot.messaging.send_embed(channel=text_channel, text=msg)

        voice_channel = message.author.voice.channel if message.author.voice else None
        if not voice_channel:
            await self.bot.messaging.send_embed(
                channel=text_channel,
                text="You must be in a voice channel to play a voice line.",
            )
            return
        response = responses[index]
        name = response.hero.localized_name if response.hero else "Unknown"
        url = get_response_url(response)
        text = f"[{response.text} ({name})]({url})"
        footer = f"voice line {index+1} out of {len(responses)}"
        thumbnail = getattr(response, "icon", None) or None

        await self.bot.messaging.send_embed(
            channel=text_channel, text=text, thumbnail=thumbnail, footer=footer
        )
        await self.play_response(voice_channel, utils.dotabase_url(response.mp3))

    async def play_response(self, channel, url):
        # Use the audio cog to play the voice line
        track = AudioTrack(name="voice_line", path=url)
        await self.bot.audio.play(channel, track)


async def setup(bot):
    await bot.add_cog(VoiceLines(bot))
