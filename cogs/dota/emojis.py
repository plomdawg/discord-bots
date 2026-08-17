"""Emojis"""

import pathlib
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from cogs.dota.utils import (
    download_hero_icons,
    emoji_name,
    get_heroes,
    upload_icons_to_servers,
)

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

    def get(self, name) -> str:
        """Get an emoji.

        Uses the same normalization as the uploader -- this used to strip only
        spaces, so heroes with punctuation (Anti-Mage, Nature's Prophet) could
        never match their uploaded emoji.
        """
        return self.emojis.get(emoji_name(name), "")

    def missing_heroes(self) -> list:
        """Heroes that currently have no emoji loaded from the 3 servers."""
        return [h for h in get_heroes() if not self.emojis.get(emoji_name(h.localized_name))]

    def load_emojis(self):
        """Loads all emojis from the 3 servers above"""
        for guild_id in SERVERS:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            for emoji in guild.emojis:
                self.emojis[emoji.name] = str(emoji)
        self.bot.log(f"Loaded {len(self.emojis.keys())} emojis.")

    @app_commands.check(user_is_plomdawg)
    @app_commands.command(name="setup", description="Set up the emojis")
    async def setup_emojis(self, interaction: discord.Interaction):
        """Uploads all the hero icons onto 3 different servers (50 max each)"""
        message = await self.bot.messaging.send_embed(
            interaction,
            title="Setting up Emojis",
            text="Checking which heroes are missing emoji...",
        )

        # Refresh from the servers first so "missing" reflects reality.
        self.load_emojis()
        missing = self.missing_heroes()

        if not missing:
            await self.bot.messaging.edit_embed(
                message,
                title="Emojis Setup Complete",
                text=f"All {len(get_heroes())} heroes already have an emoji. Nothing to do.",
                color=discord.Color.green(),
            )
            return

        # Fetch icons for only the missing heroes. Uploading the whole directory
        # would spend the free-slot budget on icons that already exist.
        await self.bot.messaging.edit_embed(
            message,
            title="Setting up Emojis",
            text=f"Downloading {len(missing)} hero icons from dotabase...",
        )
        icons = download_hero_icons(ICON_DIR, missing)

        await self.bot.messaging.edit_embed(
            message,
            title="Setting up Emojis",
            text=f"Uploading {len(icons)} icons to {len(SERVERS)} servers...",
        )
        successful, total = await upload_icons_to_servers(
            self.bot, ICON_DIR, SERVERS, icons=icons
        )

        # Reload emojis after upload
        self.load_emojis()
        still_missing = self.missing_heroes()

        text = (
            f"Uploaded **{successful}/{total}** icons and reloaded emojis.\n"
            f"Heroes with an emoji: **{len(get_heroes()) - len(still_missing)}/{len(get_heroes())}**"
        )
        if still_missing:
            names = ", ".join(h.localized_name for h in still_missing[:15])
            slots = 50 * len(SERVERS) - len(self.emojis)
            text += (
                f"\n\nStill missing ({len(still_missing)}): {names}"
                f"\nFree emoji slots left: **{slots}** "
                f"(50 per server x {len(SERVERS)})."
            )
            if slots <= 0:
                text += "\n⚠️ Servers are full — add another server to `SERVERS`."

        await self.bot.messaging.edit_embed(
            message,
            title="Emojis Setup Complete",
            text=text,
            color=discord.Color.green(),
        )


async def setup(bot: "DotaBot"):
    await bot.add_cog(Emojis(bot))
