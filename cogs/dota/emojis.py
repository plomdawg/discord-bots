"""Emojis"""

import pathlib
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.dota.utils import upload_icons_to_servers

if TYPE_CHECKING:
    from bots.dotabot import DotaBot

# DotA Heroes servers
SERVERS = [650182236490170369, 650182259248463907, 650180306782912533]
ICON_DIR = pathlib.Path("cogs/dota/icons")
ICON_DIR.mkdir(parents=True, exist_ok=True)


# Checks
def user_is_plomdawg(interaction: discord.Interaction) -> bool:
    """Returns True if the author is plomdawg"""
    return interaction.user.id == 163040232701296641


class Emojis(commands.Cog):
    def __init__(self, bot: "DotaBot"):
        self.bot = bot
        self.emojis = {}

    @commands.Cog.listener()
    async def on_ready(self):
        """Loads all emojis from the 3 servers above"""
        self.load_emojis()

    def get(self, emoji_name) -> str:
        """Get an emoji."""
        emoji_name = emoji_name.replace(" ", "")
        return self.emojis.get(emoji_name, "")

    def load_emojis(self):
        """Loads all emojis from the 3 servers above"""
        for guild_id in SERVERS:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            for emoji in guild.emojis:
                self.emojis[emoji.name] = str(emoji)
        self.bot.log(f"Loaded {len(self.emojis.keys())} emojis.")

    @discord.app_commands.check(user_is_plomdawg)
    @discord.app_commands.command(name="setup", description="Set up the emojis")
    async def setup_emojis(self, interaction: discord.Interaction):
        """Uploads all the hero icons onto 3 different servers (50 max each)"""
        message = await self.bot.messaging.send_embed(
            interaction,
            title="Setting up Emojis",
            text="Starting to upload icons to servers...",
        )

        successful, total = await upload_icons_to_servers(self.bot, ICON_DIR, SERVERS)

        # Reload emojis after upload
        self.load_emojis()

        await self.bot.messaging.edit_embed(
            message,
            title="Emojis Setup Complete",
            text=f"Successfully uploaded {successful}/{total} icons to servers and reloaded emojis.",
            color=discord.Color.green(),
        )


async def setup(bot: "DotaBot"):
    await bot.add_cog(Emojis(bot))
