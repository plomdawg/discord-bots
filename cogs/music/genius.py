"""
This cog is used to load secrets.
"""

from typing import TYPE_CHECKING

import discord
import lyricsgenius
from discord.ext import commands
from lyricsgenius.types.song import Song

from cogs.common.messaging import bold

if TYPE_CHECKING:
    from bots.musicbot import MusicBot


class Genius(commands.Cog):
    def __init__(self, bot: "MusicBot"):
        self.bot = bot
        token = self.bot.secrets.get("GENIUS_API_KEY")
        self.client = lyricsgenius.Genius(token)

    def get_song(self, song_name: str, artist_name: str) -> Song | None:
        song = self.client.search_song(title=song_name, artist=artist_name)
        # Remove the non-lyrics part of the lyrics.
        if song and "Read More " in song.lyrics:
            song.lyrics = song.lyrics.split("Read More ")[1]
        return song

    @discord.app_commands.command(name="lyrics", description="Get lyrics from Genius")
    @discord.app_commands.describe(song="Song name (default: current song)")
    @discord.app_commands.describe(artist="Artist name (default: current artist)")
    async def lyrics(
        self,
        interaction: discord.Interaction,
        song: str = "",
        artist: str = "",
    ):

        assert isinstance(interaction.channel, discord.TextChannel)
        # Format the song and artist names.
        text = f" > {bold(song)}"
        if artist:
            text += f" by {bold(artist)}"
        # Send the message to the channel.
        message = await self.bot.messaging.send_embed(
            interaction,
            title="Searching for lyrics...",
            text=text,
            color=discord.Color.blue(),
        )
        async with interaction.channel.typing():
            # Get the song from Genius.
            genius_song = self.get_song(song, artist)
            # Respond with the lyrics or a message if the song is not found.
            if genius_song:
                await self.bot.messaging.edit_embed(
                    message,
                    title=f"{genius_song.artist} - {genius_song.title}",
                    text=f"Lyrics from [Genius]({genius_song.url}))\n{genius_song.lyrics}",
                    thumbnail=genius_song.song_art_image_thumbnail_url,
                    color=discord.Color.green(),
                )
            else:
                await self.bot.messaging.edit_embed(
                    message,
                    title="Song not found:",
                    text=f" > {bold(song)}",
                    color=discord.Color.red(),
                )


async def setup(bot: "MusicBot"):
    await bot.add_cog(Genius(bot))
