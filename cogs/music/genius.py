"""
This cog is used to load secrets.
"""

from typing import TYPE_CHECKING

import discord
import lyricsgenius
from discord.ext import commands

from cogs.common.messaging import bold

if TYPE_CHECKING:
    from bots.musicbot import MusicBot


class Genius(commands.Cog):
    def __init__(self, bot: "MusicBot"):
        self.bot = bot
        token = self.bot.secrets.get("GENIUS_API_KEY")
        self.client = lyricsgenius.Genius(token)

    @discord.app_commands.command(name="lyrics", description="Get lyrics from Genius")
    @discord.app_commands.describe(song_name="Song name (default: current song)")
    @discord.app_commands.describe(artist_name="Artist name (default: current artist)")
    async def lyrics(
        self,
        interaction: discord.Interaction,
        song_name: str = "",
        artist_name: str = "",
    ):

        assert isinstance(interaction.channel, discord.TextChannel)
        text = f" > {bold(song_name)}"
        if artist_name:
            text += f" by {bold(artist_name)}"
        response = await self.bot.messaging.send_embed(
            interaction,
            title="Searching for lyrics...",
            text=text,
            color=discord.Color.blue(),
        )
        assert isinstance(response, discord.interactions.InteractionCallbackResponse)
        async with interaction.channel.typing():
            song = self.client.search_song(title=song_name, artist=artist_name)
            if song:
                title = f"{song.artist} - {song.title}"
                text = f"Lyrics from [Genius]({song.url}))\n"
                text += song.lyrics
                thumbnail = song.song_art_image_thumbnail_url
                color = discord.Color.green()
            else:
                title = "Song not found:"
                text = f" > {bold(song_name)}"
                thumbnail = None
                color = discord.Color.red()
            await self.bot.messaging.edit_embed(
                response.resource,
                title=title,
                text=text,
                thumbnail=thumbnail,
                color=color,
            )


async def setup(bot):
    await bot.add_cog(Genius(bot))
